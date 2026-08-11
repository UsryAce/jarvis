import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock
from unittest.mock import patch

import chromadb

from src.memory.vector_memory import EmbeddingSpace, VectorMemory


class VectorMemoryCircuitTests(unittest.IsolatedAsyncioTestCase):
    async def test_embedding_failure_opens_circuit_and_uses_local_fallback(self):
        memory = VectorMemory()
        error = RuntimeError("bad embedding request")
        error.status = 400
        memory.nvidia_client = type("Client", (), {"embeddings": AsyncMock(side_effect=error)})()

        first = await memory._get_embeddings(["hello"])
        second = await memory._get_embeddings(["hello"])

        self.assertEqual(first, second)
        self.assertEqual(len(first[0]), 1024)
        self.assertEqual(memory.nvidia_client.embeddings.await_count, 1)
        self.assertGreater(memory._embedding_disabled_until, 0)

    async def test_nvidia_and_fallback_embeddings_use_separate_collections(self):
        with TemporaryDirectory() as temp_dir:
            embedding = [0.0] * 1024
            embedding[0] = 1.0
            error = RuntimeError("provider unavailable")
            error.status = 503
            client = type(
                "Client",
                (),
                {"embeddings": AsyncMock(side_effect=[{"data": [{"embedding": embedding}]}, error])},
            )()
            memory = VectorMemory(nvidia_client=client)
            memory_path = Path(temp_dir) / "memory"
            chroma_client = chromadb.EphemeralClient()

            with patch("src.memory.vector_memory.chromadb.PersistentClient", return_value=chroma_client), patch(
                    "src.memory.vector_memory.config.get",
                    side_effect=lambda key, default=None: {
                        "memory.path": str(memory_path),
                        "memory.collection": "test_memory",
                    }.get(key, default),
                ):
                # Constructor reads collection settings, so make the test base explicit.
                memory._collection_base = "test_memory"
                await memory.initialize()
                nvidia_id = await memory.add("NVIDIA memory")
                fallback_id = await memory.add("fallback memory")

            collections = {
                collection.metadata["embedding_provider"]: collection
                for collection in memory.client.list_collections()
                if (collection.metadata or {}).get("jarvis_collection_base") == "test_memory"
            }
            self.assertEqual(set(collections), {"nvidia", "local"})
            self.assertNotEqual(collections["nvidia"].name, collections["local"].name)
            self.assertEqual(collections["nvidia"].count(), 1)
            self.assertEqual(collections["local"].count(), 2)
            self.assertEqual(
                collections["nvidia"].metadata["embedding_version"],
                "nvidia-api-v2-query-passage",
            )
            self.assertEqual(collections["nvidia"].metadata["embedding_dimensions"], 1024)
            self.assertEqual(
                collections["local"].metadata["embedding_model"],
                "normalized-token-shingle-hashing",
            )

            nvidia_record = collections["nvidia"].get(ids=[nvidia_id], include=["metadatas"])
            fallback_record = collections["local"].get(ids=[fallback_id], include=["metadatas"])
            self.assertEqual(nvidia_record["metadatas"][0]["embedding_provider"], "nvidia")
            self.assertEqual(fallback_record["metadatas"][0]["embedding_provider"], "local")
            self.assertNotEqual(
                nvidia_record["metadatas"][0]["embedding_space_id"],
                fallback_record["metadatas"][0]["embedding_space_id"],
            )

    async def test_search_queries_only_the_compatible_embedding_space(self):
        with TemporaryDirectory() as temp_dir:
            embedding = [0.0] * 1024
            embedding[0] = 1.0
            error = RuntimeError("provider unavailable")
            error.status = 503
            client = type(
                "Client",
                (),
                {"embeddings": AsyncMock(side_effect=[{"data": [{"embedding": embedding}]}, error])},
            )()
            memory = VectorMemory(nvidia_client=client)
            memory._collection_base = "search_memory"
            chroma_client = chromadb.EphemeralClient()

            with patch("src.memory.vector_memory.chromadb.PersistentClient", return_value=chroma_client), patch(
                    "src.memory.vector_memory.config.get",
                    side_effect=lambda key, default=None: {
                        "memory.path": str(Path(temp_dir) / "memory"),
                    }.get(key, default),
                ):
                await memory.initialize()
                await memory.add("NVIDIA-only content")
                await memory.add("fallback-only content")
                results = await memory.search("fallback-only content", threshold=0.99)

            self.assertEqual([item["content"] for item in results], ["fallback-only content"])
            self.assertEqual(results[0]["metadata"]["embedding_provider"], "local")
            self.assertEqual(results[0]["source"]["provider"], "local")

    async def test_legacy_untagged_collection_is_quarantined(self):
        with TemporaryDirectory() as temp_dir:
            memory_path = Path(temp_dir) / "memory"
            client = chromadb.EphemeralClient()
            legacy = client.get_or_create_collection(
                name="legacy_memory",
                metadata={"hnsw:space": "cosine"},
            )
            legacy.add(
                ids=["legacy"],
                embeddings=[[0.0] * 1024],
                documents=["unknown embedding provenance"],
                metadatas=[{"type": "memory"}],
            )

            memory = VectorMemory()
            memory._collection_base = "legacy_memory"
            with patch("src.memory.vector_memory.chromadb.PersistentClient", return_value=client), patch(
                    "src.memory.vector_memory.config.get",
                    side_effect=lambda key, default=None: {
                        "memory.path": str(memory_path),
                    }.get(key, default),
                ):
                await memory.initialize()
                await memory.add("new local memory")
                stats = await memory.get_stats()

            self.assertTrue(stats["legacy_collection_quarantined"])
            self.assertEqual(stats["legacy_documents_migrated"], 1)
            self.assertEqual(stats["total_memories"], 2)
            self.assertEqual(legacy.count(), 1)
            self.assertNotEqual(memory.collection.name, legacy.name)
            recalled = await memory.search("unknown embedding provenance", threshold=0.99)
            self.assertEqual(recalled[0]["id"], "legacy")
            self.assertEqual(
                recalled[0]["metadata"]["migrated_from_collection"],
                "legacy_memory",
            )

    async def test_provenance_scoped_collection_is_reused_after_restart(self):
        client = chromadb.EphemeralClient()
        first = VectorMemory()
        first._collection_base = "restart_memory"
        second = VectorMemory()
        second._collection_base = "restart_memory"

        with patch("src.memory.vector_memory.chromadb.PersistentClient", return_value=client):
            await first.initialize()
            memory_id = await first.add("survives restart")
            first_collection_name = first.collection.name
            await first.close()

            await second.initialize()
            stats = await second.get_stats()
            record = second.collection.get(ids=[memory_id], include=["metadatas"])

        self.assertEqual(second.collection.name, first_collection_name)
        self.assertEqual(stats["total_memories"], 1)
        self.assertEqual(record["metadatas"][0]["embedding_provider"], "local")

    async def test_nvidia_uses_passage_for_documents_and_query_for_search(self):
        calls = []

        async def embed(texts, *, model, input_type):
            calls.append((tuple(texts), model, input_type))
            return {"data": [{"embedding": [1.0] + [0.0] * 7} for _ in texts]}

        client = type("Client", (), {"embeddings": AsyncMock(side_effect=embed)})()
        memory = VectorMemory(nvidia_client=client)
        memory._collection_base = "roles_memory"
        chroma_client = chromadb.EphemeralClient()
        with patch("src.memory.vector_memory.chromadb.PersistentClient", return_value=chroma_client):
            await memory.initialize()
            await memory.add("document content")
            await memory.search("document query", threshold=-1.0)

        self.assertEqual(calls[0][2], "passage")
        self.assertIn("query", [call[2] for call in calls])
        nvidia_spaces = [
            collection.metadata
            for collection in chroma_client.list_collections()
            if (collection.metadata or {}).get("embedding_provider") == "nvidia"
            and collection.count()
        ]
        self.assertEqual(
            nvidia_spaces[0]["embedding_version"],
            "nvidia-api-v2-query-passage",
        )

    def test_local_fallback_is_normalized_and_lexically_meaningful(self):
        memory = VectorMemory()
        related, paraphrase, unrelated = memory._fallback_embeddings([
            "build futuristic dashboard",
            "build advanced dashboard",
            "calendar weather tomorrow",
        ])

        def cosine(left, right):
            return sum(a * b for a, b in zip(left, right))

        self.assertAlmostEqual(sum(value * value for value in related), 1.0, places=6)
        self.assertGreater(cosine(related, paraphrase), cosine(related, unrelated))
        self.assertGreater(cosine(related, paraphrase), 0.2)
        self.assertEqual(memory._fallback_space().version, "2")

    async def test_provider_outage_shadow_recall_and_bounded_recovery_promotion(self):
        state = {"offline": False}

        async def embed(texts, *, model, input_type):
            if state["offline"]:
                error = RuntimeError("provider unavailable")
                error.status = 503
                raise error
            vectors = []
            for text in texts:
                vector = [0.0] * 16
                vector[sum(text.encode("utf-8")) % len(vector)] = 1.0
                vectors.append({"embedding": vector})
            return {"data": vectors}

        provider = type("Client", (), {"embeddings": AsyncMock(side_effect=embed)})()
        memory = VectorMemory(nvidia_client=provider)
        memory._collection_base = "recovery_memory"
        memory.promotion_batch_size = 10
        chroma_client = chromadb.EphemeralClient()
        with patch("src.memory.vector_memory.chromadb.PersistentClient", return_value=chroma_client):
            await memory.initialize()
            provider_id = await memory.add("provider durable memory")

            state["offline"] = True
            memory._embedding_disabled_until = 0
            outage_results = await memory.search("provider durable memory", threshold=0.99)
            self.assertEqual(outage_results[0]["id"], provider_id)
            outage_id = await memory.add("outage-created memory")

            state["offline"] = False
            memory._embedding_disabled_until = 0
            recovered_results = await memory.search("outage-created memory", threshold=0.99)

        self.assertEqual(recovered_results[0]["id"], outage_id)
        local_records = []
        nvidia_records = []
        for collection in chroma_client.list_collections():
            provider_name = (collection.metadata or {}).get("embedding_provider")
            ids = collection.get(include=["metadatas"])["ids"]
            if provider_name == "local":
                local_records.extend(ids)
            elif provider_name == "nvidia":
                nvidia_records.extend(ids)
        self.assertIn(outage_id, local_records)
        self.assertIn(outage_id, nvidia_records)

    async def test_initialize_accepts_chroma_name_string_collection_listing(self):
        underlying = chromadb.EphemeralClient()
        seed = VectorMemory()
        seed._collection_base = "string_api_memory"
        space = seed._fallback_space(seed.fallback_dimensions)
        collection = underlying.get_or_create_collection(
            name=seed._collection_name(space),
            metadata=space.metadata(seed._collection_base),
        )
        collection.add(
            ids=["existing"],
            embeddings=seed._fallback_embeddings(["existing memory"]),
            documents=["existing memory"],
            metadatas=[{"type": "memory", **space.record_metadata()}],
        )

        class StringListingClient:
            def list_collections(self):
                return [item.name for item in underlying.list_collections()]

            def __getattr__(self, name):
                return getattr(underlying, name)

        memory = VectorMemory()
        memory._collection_base = "string_api_memory"
        with patch(
            "src.memory.vector_memory.chromadb.PersistentClient",
            return_value=StringListingClient(),
        ):
            await memory.initialize()
            recalled = await memory.search("existing memory", threshold=0.99)

        self.assertEqual(recalled[0]["id"], "existing")

    async def test_search_never_reuses_query_vector_across_nvidia_versions(self):
        async def embed(texts, *, model, input_type):
            return {"data": [{"embedding": [1.0] + [0.0] * 7} for _ in texts]}

        provider = type("Client", (), {"embeddings": AsyncMock(side_effect=embed)})()
        memory = VectorMemory(nvidia_client=provider)
        memory._collection_base = "version_memory"
        client = chromadb.EphemeralClient()
        with patch("src.memory.vector_memory.chromadb.PersistentClient", return_value=client):
            await memory.initialize()
            old_space = EmbeddingSpace(
                provider="nvidia",
                model=memory.embedding_model,
                version="nvidia-api-v1",
                dimensions=8,
            )
            old_collection = memory._ensure_collection(old_space)
            old_collection.add(
                ids=["old"],
                embeddings=[[1.0] + [0.0] * 7],
                documents=["old version memory"],
                metadatas=[{"type": "memory", **old_space.record_metadata()}],
            )

            class QueryTrap:
                name = old_collection.name
                metadata = old_collection.metadata

                def count(self):
                    return old_collection.count()

                def get(self, **kwargs):
                    return old_collection.get(**kwargs)

                def query(self, **_kwargs):
                    raise AssertionError("incompatible NVIDIA collection was queried")

            memory._collections_by_space[old_space.identifier] = QueryTrap()
            recalled = await memory.search("old version memory", threshold=0.99)

        self.assertEqual(recalled[0]["id"], "old")
        self.assertNotEqual(recalled[0]["source"]["version"], "nvidia-api-v1")

    async def test_promotion_skips_existing_first_page_and_stats_dedupe_replicas(self):
        embedded_texts = []

        async def embed(texts, *, model, input_type):
            embedded_texts.append(list(texts))
            return {"data": [{"embedding": [1.0] + [0.0] * 1023} for _ in texts]}

        provider = type("Client", (), {"embeddings": AsyncMock(side_effect=embed)})()
        memory = VectorMemory(nvidia_client=provider)
        memory._collection_base = "promotion_memory"
        client = chromadb.EphemeralClient()
        with patch("src.memory.vector_memory.chromadb.PersistentClient", return_value=client):
            await memory.initialize()
            local_space = memory._fallback_space(memory.fallback_dimensions)
            nvidia_space = memory._nvidia_space(memory.embedding_dimensions)
            local = memory._ensure_collection(local_space)
            target = memory._ensure_collection(nvidia_space)
            ids = ["a", "b", "c", "d"]
            documents = ["memory a", "memory b", "memory c", "memory d"]
            local.upsert(
                ids=ids,
                embeddings=memory._fallback_embeddings(documents),
                documents=documents,
                metadatas=[{"type": "memory", **local_space.record_metadata()} for _ in ids],
            )
            target.upsert(
                ids=ids[:2],
                embeddings=[[1.0] + [0.0] * 1023 for _ in ids[:2]],
                documents=documents[:2],
                metadatas=[{"type": "memory", **nvidia_space.record_metadata()} for _ in ids[:2]],
            )

            promoted = await memory._promote_documents_to_nvidia(
                limit=2, target_space=nvidia_space,
            )
            stats = await memory.get_stats()

        self.assertEqual(promoted, 2)
        self.assertEqual(embedded_texts, [["memory c", "memory d"]])
        self.assertEqual(set(target.get(include=["metadatas"])["ids"]), set(ids))
        self.assertEqual(stats["total_memories"], 4)
        self.assertEqual(stats["vector_entries"], 8)

    async def test_local_shadow_progresses_past_already_shadowed_records(self):
        memory = VectorMemory()
        memory._collection_base = "shadow_memory"
        client = chromadb.EphemeralClient()
        with patch("src.memory.vector_memory.chromadb.PersistentClient", return_value=client):
            await memory.initialize()
            local_space = memory._fallback_space(memory.fallback_dimensions)
            nvidia_space = memory._nvidia_space(memory.embedding_dimensions)
            local = memory._ensure_collection(local_space)
            provider_collection = memory._ensure_collection(nvidia_space)
            ids = ["a", "b", "c"]
            documents = ["memory a", "memory b", "memory c"]
            provider_collection.upsert(
                ids=ids,
                embeddings=[[1.0] + [0.0] * 1023 for _ in ids],
                documents=documents,
                metadatas=[{"type": "memory", **nvidia_space.record_metadata()} for _ in ids],
            )
            await memory._upsert_local_shadow(
                [("a", "memory a", {"type": "memory"})], source="seed"
            )

            first = await memory._shadow_known_documents_locally(limit=1)
            second = await memory._shadow_known_documents_locally(limit=1)

        self.assertEqual((first, second), (1, 1))
        self.assertEqual(set(local.get(include=["metadatas"])["ids"]), set(ids))


if __name__ == "__main__":
    unittest.main()
