"""Vector Memory System for Jarvis using ChromaDB."""
import hashlib
import json
import logging
import re
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

from src.config import config
from src.clients.nvidia_client import NVIDIAClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbeddingSpace:
    """Identity of a vector space whose embeddings are mutually comparable."""

    provider: str
    model: str
    version: str
    dimensions: int

    @property
    def identifier(self) -> str:
        return json.dumps(
            {
                "dimensions": self.dimensions,
                "model": self.model,
                "provider": self.provider,
                "version": self.version,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def metadata(self, collection_base: str) -> Dict[str, Any]:
        return {
            "hnsw:space": "cosine",
            "jarvis_collection_base": collection_base,
            "embedding_schema": "1",
            "embedding_space_id": self.identifier,
            "embedding_provider": self.provider,
            "embedding_model": self.model,
            "embedding_version": self.version,
            "embedding_dimensions": self.dimensions,
        }

    def record_metadata(self) -> Dict[str, Any]:
        return {
            "embedding_schema": "1",
            "embedding_space_id": self.identifier,
            "embedding_provider": self.provider,
            "embedding_model": self.model,
            "embedding_version": self.version,
            "embedding_dimensions": self.dimensions,
        }


@dataclass(frozen=True)
class EmbeddedBatch:
    vectors: List[List[float]]
    space: EmbeddingSpace


class VectorMemory:
    """Vector-based memory system using ChromaDB and NVIDIA embeddings."""

    def __init__(self, *, nvidia_client: Optional[NVIDIAClient] = None):
        self.client: Optional[chromadb.Client] = None
        self.collection = None
        self.embedding_model = config.get("memory.embedding_model", "nvidia/nv-embedqa-e5-v5")
        self.embedding_version = config.get(
            "memory.embedding_version", "nvidia-api-v2-query-passage"
        )
        self.embedding_dimensions = int(config.get("memory.embedding_dimensions", 1024))
        self.fallback_dimensions = int(config.get("memory.fallback_embedding_dimensions", 1024))
        self.promotion_batch_size = max(
            1, int(config.get("memory.promotion_batch_size", 25))
        )
        self.nvidia_client = nvidia_client
        self._initialized = False
        self._embedding_disabled_until = 0.0
        self._embedding_failures = 0
        self._collection_base = config.get("memory.collection", "jarvis_memory")
        self._collections_by_space: Dict[str, Any] = {}
        self._legacy_collections: List[Any] = []
        self._legacy_collection_quarantined = False
        self._legacy_documents_migrated = 0

    def _nvidia_space(self, dimensions: int) -> EmbeddingSpace:
        return EmbeddingSpace(
            provider="nvidia",
            model=self.embedding_model,
            version=self.embedding_version,
            dimensions=dimensions,
        )

    @staticmethod
    def _fallback_space(dimensions: int = 1024) -> EmbeddingSpace:
        return EmbeddingSpace(
            provider="local",
            model="normalized-token-shingle-hashing",
            version="2",
            dimensions=dimensions,
        )

    @staticmethod
    def _legacy_fallback_space(dimensions: int = 1024) -> EmbeddingSpace:
        return EmbeddingSpace(
            provider="local",
            model="sha256-bit-pseudo-embedding",
            version="1",
            dimensions=dimensions,
        )

    def _collection_name(self, space: EmbeddingSpace) -> str:
        """Return a stable Chroma-safe collection name for an embedding space."""
        safe_base = re.sub(r"[^A-Za-z0-9._-]+", "-", self._collection_base).strip("._-")
        safe_base = safe_base or "jarvis-memory"
        if len(safe_base) < 3:
            safe_base = f"jarvis-{safe_base}"
        collection_identity = f"{self._collection_base}\0{space.identifier}"
        suffix = f"-emb-{hashlib.sha256(collection_identity.encode('utf-8')).hexdigest()[:16]}"
        safe_base = safe_base[: 63 - len(suffix)].rstrip("._-")
        return f"{safe_base}{suffix}"

    @staticmethod
    def _space_from_metadata(metadata: Dict[str, Any]) -> Optional[EmbeddingSpace]:
        try:
            if str(metadata.get("embedding_schema")) != "1":
                return None
            return EmbeddingSpace(
                provider=str(metadata["embedding_provider"]),
                model=str(metadata["embedding_model"]),
                version=str(metadata["embedding_version"]),
                dimensions=int(metadata["embedding_dimensions"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _load_existing_collections(self) -> None:
        """Load only provenance-tagged collections; quarantine the legacy base."""
        if self.client is None:
            return
        for listed in self.client.list_collections():
            collection = (
                self.client.get_collection(name=listed)
                if isinstance(listed, str)
                else listed
            )
            if collection.name == self._collection_base:
                self._legacy_collection_quarantined = True
                self._legacy_collections.append(collection)
                continue
            metadata = collection.metadata or {}
            if metadata.get("jarvis_collection_base") != self._collection_base:
                continue
            space = self._space_from_metadata(metadata)
            if space is None or metadata.get("embedding_space_id") != space.identifier:
                logger.warning(
                    "Ignoring vector collection %s with incomplete embedding provenance",
                    collection.name,
                )
                continue
            self._collections_by_space[space.identifier] = collection

    def _ensure_collection(self, space: EmbeddingSpace):
        if self.client is None:
            raise RuntimeError("Vector memory is not initialized")
        cached = self._collections_by_space.get(space.identifier)
        if cached is not None:
            self.collection = cached
            return cached

        expected_metadata = space.metadata(self._collection_base)
        collection = self.client.get_or_create_collection(
            name=self._collection_name(space),
            metadata=expected_metadata,
        )
        actual_metadata = collection.metadata or {}
        for key, expected in expected_metadata.items():
            if actual_metadata.get(key) != expected:
                raise RuntimeError(
                    f"Embedding collection provenance mismatch for {collection.name}: {key}"
                )
        self._collections_by_space[space.identifier] = collection
        self.collection = collection
        return collection

    def _all_collections(self) -> List[Any]:
        return list(self._collections_by_space.values())

    def _all_storage_collections(self) -> List[Any]:
        collections = self._all_collections() + self._legacy_collections
        return list({collection.name: collection for collection in collections}.values())

    async def initialize(self):
        """Initialize ChromaDB and create collection."""
        if self._initialized:
            return

        try:
            # Get memory path
            memory_path = config.get("memory.path", "./data/memory")
            Path(memory_path).mkdir(parents=True, exist_ok=True)

            # Initialize ChromaDB
            self.client = chromadb.PersistentClient(
                path=memory_path,
                settings=Settings(anonymized_telemetry=False),
            )

            # Existing untagged collections may already contain a mixture of
            # incompatible vectors. They are deliberately left untouched and
            # excluded; new data is routed to a provenance-scoped collection.
            self._load_existing_collections()
            # The local lexical space is an always-available shadow index. The
            # configured NVIDIA collection is also opened eagerly when enabled;
            # the actual response dimension is still authoritative on first use.
            self._ensure_collection(self._fallback_space(self.fallback_dimensions))
            if self.nvidia_client:
                self._ensure_collection(self._nvidia_space(self.embedding_dimensions))

            self._initialized = True
            await self._migrate_legacy_documents()
            await self._shadow_known_documents_locally(limit=self.promotion_batch_size)
            if self._legacy_collection_quarantined:
                logger.warning(
                    "Legacy vector collection %s quarantined because its embedding provenance is unknown",
                    self._collection_base,
                )
            logger.info("Memory initialized at %s", memory_path)

        except Exception as e:
            logger.error("Failed to initialize memory with safe code %s", type(e).__name__)
            raise

    @property
    def is_connected(self) -> bool:
        return self._initialized and self.collection is not None

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Compatibility wrapper returning vectors without their provenance."""
        return (await self._get_embeddings_with_space(texts)).vectors

    async def _get_embeddings_with_space(
        self, texts: List[str], *, input_type: str = "query"
    ) -> EmbeddedBatch:
        """Get embeddings together with the identity of their vector space."""
        if not texts:
            raise ValueError("at least one text is required for embedding")
        if not self.nvidia_client:
            vectors = self._fallback_embeddings(texts, self.fallback_dimensions)
            return EmbeddedBatch(vectors=vectors, space=self._fallback_space(len(vectors[0])))

        if time.monotonic() < self._embedding_disabled_until:
            vectors = self._fallback_embeddings(texts, self.fallback_dimensions)
            return EmbeddedBatch(vectors=vectors, space=self._fallback_space(len(vectors[0])))

        try:
            result = await self.nvidia_client.embeddings(
                texts,
                model=self.embedding_model,
                input_type=input_type,
            )
            self._embedding_failures = 0
            self._embedding_disabled_until = 0.0
            vectors = [item["embedding"] for item in result["data"]]
            if len(vectors) != len(texts) or not vectors or not vectors[0]:
                raise ValueError("NVIDIA embedding response has an invalid shape")
            dimensions = len(vectors[0])
            if any(len(vector) != dimensions for vector in vectors):
                raise ValueError("NVIDIA embedding response has inconsistent dimensions")
            return EmbeddedBatch(vectors=vectors, space=self._nvidia_space(dimensions))
        except Exception as e:
            self._embedding_failures += 1
            status = int(getattr(e, "status", 0) or 0)
            cooldown = 600 if status == 400 else min(300, 30 * (2 ** min(self._embedding_failures - 1, 3)))
            self._embedding_disabled_until = time.monotonic() + cooldown
            logger.warning(
                "NVIDIA embeddings unavailable; using local fallback for %ss (status=%s)",
                cooldown,
                status,
            )
            # Fallback: use the versioned normalized lexical hashing space.
            vectors = self._fallback_embeddings(texts, self.fallback_dimensions)
            return EmbeddedBatch(vectors=vectors, space=self._fallback_space(len(vectors[0])))

    def _fallback_embeddings(
        self, texts: List[str], dimensions: Optional[int] = None
    ) -> List[List[float]]:
        """Create normalized lexical hashing vectors without external models."""
        size = int(dimensions or self.fallback_dimensions)
        if size < 8:
            raise ValueError("fallback embedding dimensions must be at least 8")
        embeddings: List[List[float]] = []
        for text in texts:
            normalized = unicodedata.normalize("NFKC", text).casefold()
            tokens = re.findall(r"[^\W_]+", normalized, flags=re.UNICODE)
            if not tokens:
                tokens = [normalized.strip() or "<empty>"]
            features = [f"u:{token}" for token in tokens]
            features.extend(
                f"b:{tokens[index]}\0{tokens[index + 1]}"
                for index in range(len(tokens) - 1)
            )
            for token in tokens:
                if len(token) >= 3:
                    features.extend(
                        f"c:{token[index:index + 3]}"
                        for index in range(len(token) - 2)
                    )
            vector = [0.0] * size
            for feature in features:
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=16).digest()
                index = int.from_bytes(digest[:8], "big") % size
                sign = 1.0 if digest[8] & 1 else -1.0
                vector[index] += sign
            norm = sum(value * value for value in vector) ** 0.5
            if norm == 0.0:
                index = int.from_bytes(
                    hashlib.blake2b(normalized.encode("utf-8"), digest_size=8).digest(),
                    "big",
                ) % size
                vector[index] = 1.0
                norm = 1.0
            embeddings.append([value / norm for value in vector])
        return embeddings

    @staticmethod
    def _legacy_fallback_embeddings(texts: List[str]) -> List[List[float]]:
        """Reproduce version-1 local vectors so existing fallback data is queryable."""
        embeddings = []
        for text in texts:
            hash_bytes = hashlib.sha256(text.encode()).digest()
            vector = [
                float((hash_bytes[index // 8] >> (index % 8)) & 1)
                for index in range(256)
            ]
            embeddings.append(vector + [0.0] * (1024 - len(vector)))
        return embeddings

    @staticmethod
    def _collection_documents(collection: Any, limit: Optional[int] = None) -> List[tuple[str, str, Dict]]:
        kwargs: Dict[str, Any] = {"include": ["documents", "metadatas"]}
        if limit is not None:
            kwargs["limit"] = max(1, int(limit))
        results = collection.get(**kwargs)
        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []
        records = []
        for index, memory_id in enumerate(results.get("ids") or []):
            document = documents[index] if index < len(documents) else None
            metadata = metadatas[index] if index < len(metadatas) else None
            if isinstance(document, str) and document:
                records.append((str(memory_id), document, dict(metadata or {})))
        return records

    async def _upsert_local_shadow(
        self,
        records: List[tuple[str, str, Dict]],
        *,
        source: str,
    ) -> int:
        if not records:
            return 0
        local_space = self._fallback_space(self.fallback_dimensions)
        collection = self._ensure_collection(local_space)
        documents = [record[1] for record in records]
        vectors = self._fallback_embeddings(documents, local_space.dimensions)
        metadatas = [
            {
                **record[2],
                "shadow_source": source,
                **local_space.record_metadata(),
            }
            for record in records
        ]
        collection.upsert(
            ids=[record[0] for record in records],
            embeddings=vectors,
            documents=documents,
            metadatas=metadatas,
        )
        return len(records)

    async def _migrate_legacy_documents(self) -> None:
        """Re-index readable legacy documents without touching unknown vectors."""
        for legacy in self._legacy_collections:
            records = self._collection_documents(legacy)
            if not records:
                continue
            for start in range(0, len(records), 64):
                batch = records[start:start + 64]
                documents = [record[1] for record in batch]
                embedded = await self._get_embeddings_with_space(
                    documents, input_type="passage"
                )
                target = self._ensure_collection(embedded.space)
                metadatas = [
                    {
                        **record[2],
                        "migrated_from_collection": legacy.name,
                        **embedded.space.record_metadata(),
                    }
                    for record in batch
                ]
                target.upsert(
                    ids=[record[0] for record in batch],
                    embeddings=embedded.vectors,
                    documents=documents,
                    metadatas=metadatas,
                )
                self._legacy_documents_migrated += len(batch)
                if embedded.space.provider == "nvidia":
                    await self._upsert_local_shadow(
                        [
                            (record[0], record[1], metadatas[index])
                            for index, record in enumerate(batch)
                        ],
                        source=f"legacy:{legacy.name}",
                    )

    async def _shadow_known_documents_locally(self, *, limit: int) -> int:
        """Boundedly mirror provider records into the always-queryable local index."""
        limit = max(0, int(limit))
        if limit <= 0:
            return 0
        local_collection = self._ensure_collection(
            self._fallback_space(self.fallback_dimensions)
        )
        existing = set(
            local_collection.get(include=["metadatas"]).get("ids") or []
        )
        candidates: Dict[str, tuple[str, str, Dict]] = {}
        for collection in list(self._collections_by_space.values()):
            if len(candidates) >= limit:
                break
            space = self._space_from_metadata(collection.metadata or {})
            if space is None or space.provider != "nvidia":
                continue
            for record in self._collection_documents(collection):
                if record[0] in existing:
                    continue
                candidates.setdefault(record[0], record)
                if len(candidates) >= limit:
                    break
        return await self._upsert_local_shadow(
            list(candidates.values()), source="nvidia-shadow"
        )

    async def _promote_documents_to_nvidia(
        self, *, limit: int, target_space: EmbeddingSpace
    ) -> int:
        """Boundedly copy fallback/legacy documents to the current NVIDIA space."""
        if not self.nvidia_client or limit <= 0 or target_space.provider != "nvidia":
            return 0
        target = self._ensure_collection(target_space)
        existing = set(target.get(include=["metadatas"]).get("ids") or [])
        candidates: Dict[str, tuple[str, str, Dict]] = {}
        for collection in self._all_collections():
            space = self._space_from_metadata(collection.metadata or {})
            if space is None or space.provider != "local":
                continue
            for record in self._collection_documents(collection):
                if record[0] in existing:
                    continue
                candidates.setdefault(record[0], record)
                if len(candidates) >= limit:
                    break
            if len(candidates) >= limit:
                break
        if len(candidates) < limit:
            for legacy in self._legacy_collections:
                for record in self._collection_documents(legacy):
                    if record[0] in existing:
                        continue
                    candidates.setdefault(record[0], record)
                    if len(candidates) >= limit:
                        break
                if len(candidates) >= limit:
                    break
        if not candidates:
            return 0
        records = list(candidates.values())
        embedded = await self._get_embeddings_with_space(
            [record[1] for record in records], input_type="passage"
        )
        if embedded.space != target_space:
            return 0
        target.upsert(
            ids=[record[0] for record in records],
            embeddings=embedded.vectors,
            documents=[record[1] for record in records],
            metadatas=[
                {
                    **record[2],
                    "promoted_from": record[2].get("embedding_space_id", "legacy"),
                    **embedded.space.record_metadata(),
                }
                for record in records
            ],
        )
        return len(records)

    async def add(
        self,
        content: str,
        metadata: Optional[Dict] = None,
        memory_id: Optional[str] = None,
    ) -> str:
        """Add a memory entry."""
        if not self._initialized:
            await self.initialize()

        memory_id = memory_id or str(uuid.uuid4())

        # Get embedding
        embedded = await self._get_embeddings_with_space([content], input_type="passage")
        collection = self._ensure_collection(embedded.space)
        embedding = embedded.vectors[0]

        # Prepare metadata
        meta = {
            "timestamp": datetime.now().isoformat(),
            "type": "memory",
            **(metadata or {}),
            **embedded.space.record_metadata(),
        }

        # Add to ChromaDB
        collection.add(
            ids=[memory_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[meta],
        )
        if embedded.space.provider == "nvidia":
            await self._upsert_local_shadow(
                [(memory_id, content, meta)], source="nvidia-shadow"
            )

        return memory_id

    async def add_conversation(
        self,
        user_msg: str,
        assistant_msg: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Add a conversation pair to memory."""
        conversation = f"User: {user_msg}\nAssistant: {assistant_msg}"
        return await self.add(
            content=conversation,
            metadata={
                "type": "conversation",
                "user_msg": user_msg,
                "assistant_msg": assistant_msg,
                **(metadata or {}),
            },
        )

    async def search(
        self,
        query: str,
        limit: int = 5,
        threshold: Optional[float] = None,
        filter_metadata: Optional[Dict] = None,
    ) -> List[Dict]:
        """Search memories by similarity."""
        if not self._initialized:
            await self.initialize()

        if threshold is None:
            threshold = config.get("memory.similarity_threshold", 0.7)

        query_vectors: Dict[str, List[float]] = {}
        await self._shadow_known_documents_locally(limit=self.promotion_batch_size)
        local_space = self._fallback_space(self.fallback_dimensions)
        query_vectors[local_space.identifier] = self._fallback_embeddings(
            [query], local_space.dimensions
        )[0]
        embedded = await self._get_embeddings_with_space([query], input_type="query")
        query_vectors[embedded.space.identifier] = embedded.vectors[0]
        if embedded.space.provider == "nvidia":
            await self._promote_documents_to_nvidia(
                limit=self.promotion_batch_size,
                target_space=embedded.space,
            )

        memories_by_id: Dict[str, Dict] = {}
        for collection in self._all_collections():
            if collection.count() <= 0:
                continue
            space = self._space_from_metadata(collection.metadata or {})
            if space is None:
                continue
            vector = query_vectors.get(space.identifier)
            if vector is None and space.provider == "local":
                if space == self._legacy_fallback_space(space.dimensions) and space.dimensions == 1024:
                    vector = self._legacy_fallback_embeddings([query])[0]
                elif space.model == local_space.model and space.version == local_space.version:
                    vector = self._fallback_embeddings([query], space.dimensions)[0]
            if vector is None:
                continue
            results = collection.query(
                query_embeddings=[vector],
                n_results=min(max(1, limit), collection.count()),
                where=filter_metadata,
            )
            if not results.get("ids") or not results["ids"][0]:
                continue
            for index, memory_id in enumerate(results["ids"][0]):
                similarity = 1 - results["distances"][0][index]
                if similarity < threshold:
                    continue
                candidate = {
                    "id": memory_id,
                    "content": results["documents"][0][index],
                    "metadata": results["metadatas"][0][index],
                    "similarity": similarity,
                    "source": {
                        "collection": collection.name,
                        "provider": space.provider,
                        "model": space.model,
                        "version": space.version,
                    },
                }
                previous = memories_by_id.get(memory_id)
                if previous is None or candidate["similarity"] > previous["similarity"]:
                    memories_by_id[memory_id] = candidate
        return sorted(
            memories_by_id.values(),
            key=lambda item: item["similarity"],
            reverse=True,
        )[: max(0, limit)]

    async def get_conversation_history(self, limit: int = 50) -> List[Dict]:
        """Get recent conversation history."""
        if not self._initialized:
            await self.initialize()

        conversations = []
        items_by_id: Dict[str, tuple[str, str, Dict]] = {}
        for collection in self._all_collections():
            results = collection.get(
                where={"type": "conversation"},
                limit=limit,
                include=["documents", "metadatas"],
            )
            if results["ids"]:
                for item in zip(results["ids"], results["documents"], results["metadatas"]):
                    previous = items_by_id.get(item[0])
                    if previous is None or item[2].get("timestamp", "") > previous[2].get("timestamp", ""):
                        items_by_id[item[0]] = item
        items = sorted(
            items_by_id.values(),
            key=lambda item: item[2].get("timestamp", ""),
            reverse=True,
        )

        for mem_id, _doc, meta in items[:limit]:
            conversations.append({
                "id": mem_id,
                "user_msg": meta.get("user_msg", ""),
                "assistant_msg": meta.get("assistant_msg", ""),
                "timestamp": meta.get("timestamp", ""),
            })

        return conversations

    async def save_conversation_history(self, history: List[Dict]):
        """Save full conversation history."""
        if not self._initialized:
            await self.initialize()

        # Clear old conversation entries
        for collection in self._all_storage_collections():
            collection.delete(where={"type": "conversation"})

        # Add new ones
        for i, msg in enumerate(history):
            if msg["role"] == "user":
                # Find matching assistant message
                if i + 1 < len(history) and history[i + 1]["role"] == "assistant":
                    await self.add_conversation(
                        user_msg=msg["content"],
                        assistant_msg=history[i + 1]["content"],
                    )

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        if not self._initialized:
            await self.initialize()

        try:
            for collection in self._all_storage_collections():
                collection.delete(ids=[memory_id])
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            return False

    async def update(self, memory_id: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """Update a memory entry."""
        if not self._initialized:
            await self.initialize()

        try:
            embedded = await self._get_embeddings_with_space(
                [content], input_type="passage"
            )
            meta = {
                "timestamp": datetime.now().isoformat(),
                "type": "memory",
                **(metadata or {}),
                **embedded.space.record_metadata(),
            }
            target_collection = self._ensure_collection(embedded.space)
            target_collection.upsert(
                ids=[memory_id],
                embeddings=[embedded.vectors[0]],
                documents=[content],
                metadatas=[meta],
            )
            preserved_names = {target_collection.name}
            if embedded.space.provider == "nvidia":
                local_collection = self._ensure_collection(
                    self._fallback_space(self.fallback_dimensions)
                )
                await self._upsert_local_shadow(
                    [(memory_id, content, meta)], source="nvidia-shadow"
                )
                preserved_names.add(local_collection.name)
            for collection in self._all_storage_collections():
                if collection.name not in preserved_names:
                    collection.delete(ids=[memory_id])
            return True
        except Exception as e:
            logger.error(f"Failed to update memory {memory_id}: {e}")
            return False

    async def get_stats(self) -> Dict:
        """Get memory statistics."""
        if not self._initialized:
            await self.initialize()

        spaces = []
        vector_entries = 0
        memory_ids = set()
        for collection in self._all_collections():
            collection_count = collection.count()
            vector_entries += collection_count
            memory_ids.update(
                collection.get(include=["metadatas"]).get("ids") or []
            )
            metadata = collection.metadata or {}
            spaces.append({
                "collection": collection.name,
                "provider": metadata.get("embedding_provider"),
                "model": metadata.get("embedding_model"),
                "version": metadata.get("embedding_version"),
                "dimensions": metadata.get("embedding_dimensions"),
                "memories": collection_count,
            })
        return {
            "total_memories": len(memory_ids),
            "vector_entries": vector_entries,
            "embedding_model": self.embedding_model,
            "collection": self.collection.name if self.collection else None,
            "embedding_spaces": spaces,
            "legacy_collection_quarantined": self._legacy_collection_quarantined,
            "legacy_documents_migrated": self._legacy_documents_migrated,
        }

    async def close(self):
        """Close connections."""
        if self.nvidia_client:
            await self.nvidia_client.__aexit__(None, None, None)
            self.nvidia_client = None
        if self.client:
            # ChromaDB persistent client doesn't need explicit close
            pass
        self.collection = None
        self.client = None
        self._collections_by_space.clear()
        self._legacy_collections.clear()
        self._initialized = False


# SQLite fallback for simple key-value memory
import sqlite3
from contextlib import contextmanager


class SQLiteMemory:
    """Simple SQLite-based memory for key-value storage."""

    def __init__(self, db_path: str = "./data/memory/jarvis.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    key TEXT UNIQUE,
                    value TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_msg TEXT,
                    assistant_msg TEXT,
                    metadata TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def set(self, key: str, value: str, metadata: Optional[Dict] = None) -> str:
        """Set a key-value memory."""
        import uuid
        memory_id = str(uuid.uuid4())
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO memories (id, key, value, metadata) VALUES (?, ?, ?, ?)",
                (memory_id, key, value, json.dumps(metadata or {})),
            )
        return memory_id

    def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT value FROM memories WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    def delete(self, key: str) -> bool:
        """Delete memory by key."""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE key = ?", (key,))
            return cursor.rowcount > 0

    def add_conversation(self, user_msg: str, assistant_msg: str, metadata: Optional[Dict] = None):
        """Add conversation to history."""
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO conversations (user_msg, assistant_msg, metadata) VALUES (?, ?, ?)",
                (user_msg, assistant_msg, json.dumps(metadata or {})),
            )

    def get_conversation_history(self, limit: int = 50) -> List[Dict]:
        """Get conversation history."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT user_msg, assistant_msg, metadata, timestamp FROM conversations ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [
                {
                    "user_msg": row["user_msg"],
                    "assistant_msg": row["assistant_msg"],
                    "metadata": json.loads(row["metadata"]),
                    "timestamp": row["timestamp"],
                }
                for row in rows
            ]
