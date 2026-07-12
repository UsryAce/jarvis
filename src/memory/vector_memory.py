"""Vector Memory System for Jarvis using ChromaDB."""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

from src.config import config
from src.clients.nvidia_client import NVIDIAClient

logger = logging.getLogger(__name__)


class VectorMemory:
    """Vector-based memory system using ChromaDB and NVIDIA embeddings."""

    def __init__(self):
        self.client: Optional[chromadb.Client] = None
        self.collection = None
        self.embedding_model = config.get("memory.embedding_model", "nvidia/nv-embedqa-e5-v5")
        self.nvidia_client: Optional[NVIDIAClient] = None
        self._initialized = False

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

            # Get or create collection
            collection_name = config.get("memory.collection", "jarvis_memory")
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )

            # Initialize NVIDIA client for embeddings
            self.nvidia_client = NVIDIAClient()

            self._initialized = True
            logger.info(f"Memory initialized at {memory_path}")

        except Exception as e:
            logger.error(f"Failed to initialize memory: {e}")
            raise

    @property
    def is_connected(self) -> bool:
        return self._initialized and self.collection is not None

    async def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Get embeddings for texts using NVIDIA API with fallback."""
        if not self.nvidia_client:
            raise RuntimeError("NVIDIA client not initialized")

        try:
            async with NVIDIAClient() as client:
                result = await client.embeddings(texts, model=self.embedding_model)
                return [item["embedding"] for item in result["data"]]
        except Exception as e:
            logger.warning(f"NVIDIA embeddings failed: {e}. Using fallback.")
            # Fallback: use simple hash-based embeddings
            return self._fallback_embeddings(texts)

    def _fallback_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Simple fallback embeddings using hash-based approach."""
        import hashlib
        embeddings = []
        for text in texts:
            # Create a deterministic pseudo-embedding from text hash
            hash_obj = hashlib.sha256(text.encode())
            hash_bytes = hash_obj.digest()
            # Convert to 1024-dim vector (matching NVIDIA embedding dim)
            vec = []
            for i in range(32):  # 32 bytes * 32 = 1024
                byte_val = hash_bytes[i % 32]
                # Expand each byte to 32 float values
                for bit in range(8):
                    vec.append(float((byte_val >> bit) & 1))
            # Pad or truncate to 1024
            vec = vec[:1024] if len(vec) > 1024 else vec + [0.0] * (1024 - len(vec))
            embeddings.append(vec)
        return embeddings

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
        embeddings = await self._get_embeddings([content])
        embedding = embeddings[0]

        # Prepare metadata
        meta = {
            "timestamp": datetime.now().isoformat(),
            "type": "memory",
            **(metadata or {}),
        }

        # Add to ChromaDB
        self.collection.add(
            ids=[memory_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[meta],
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

        threshold = threshold or config.get("memory.similarity_threshold", 0.7)

        # Get query embedding
        embeddings = await self._get_embeddings([query])
        query_embedding = embeddings[0]

        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=filter_metadata,
        )

        memories = []
        if results["ids"] and results["ids"][0]:
            for i, mem_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                similarity = 1 - distance  # Cosine similarity

                if similarity >= threshold:
                    memories.append({
                        "id": mem_id,
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "similarity": similarity,
                    })

        return memories

    async def get_conversation_history(self, limit: int = 50) -> List[Dict]:
        """Get recent conversation history."""
        if not self._initialized:
            await self.initialize()

        results = self.collection.get(
            where={"type": "conversation"},
            limit=limit,
            include=["documents", "metadatas"],
        )

        conversations = []
        if results["ids"]:
            # Sort by timestamp
            items = list(zip(results["ids"], results["documents"], results["metadatas"]))
            items.sort(key=lambda x: x[2].get("timestamp", ""), reverse=True)

            for mem_id, doc, meta in items[:limit]:
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
        self.collection.delete(where={"type": "conversation"})

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
            self.collection.delete(ids=[memory_id])
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            return False

    async def update(self, memory_id: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """Update a memory entry."""
        if not self._initialized:
            await self.initialize()

        try:
            embeddings = await self._get_embeddings([content])
            meta = {
                "timestamp": datetime.now().isoformat(),
                "type": "memory",
                **(metadata or {}),
            }

            self.collection.update(
                ids=[memory_id],
                embeddings=[embeddings[0]],
                documents=[content],
                metadatas=[meta],
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update memory {memory_id}: {e}")
            return False

    async def get_stats(self) -> Dict:
        """Get memory statistics."""
        if not self._initialized:
            await self.initialize()

        count = self.collection.count()
        return {
            "total_memories": count,
            "embedding_model": self.embedding_model,
            "collection": self.collection.name if self.collection else None,
        }

    async def close(self):
        """Close connections."""
        if self.client:
            # ChromaDB persistent client doesn't need explicit close
            pass
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