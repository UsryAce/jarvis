import json
import tempfile
import time
import unittest
from pathlib import Path

from src.skills.nvidia_catalog import NvidiaSkillsCatalog


def _payload(*skills):
    return json.dumps({"skills": list(skills)}).encode()


def _skill(name, description, product="Test Product", category="ai_and_machine_learning", subdomain="vision-ai", tags="generate,deploy"):
    return {
        "path": f"skills/{name}",
        "name": name,
        "description": description,
        "metadata": {
            "product.primary": product,
            "classification.category.primary": category,
            "catalog.subdomain": subdomain,
            "audience": "developer,ai_engineer",
            "discovery.activity_tags": tags,
        },
    }


class NvidiaSkillsCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_remote_catalog_is_sanitized_cached_and_searchable(self):
        calls = []
        payload = _payload(
            _skill("video-pipeline", "Build an object detection video pipeline", "DeepStream SDK"),
            _skill("weather-forecast", "Run a global weather forecast", "Earth2Studio", subdomain="simulation-modeling", tags="inference,validate"),
            {"path": "../../unsafe", "name": "unsafe", "description": "must be rejected"},
        )

        def fetch(url, timeout):
            calls.append((url, timeout))
            return payload

        cache = self.root / "catalog.json"
        catalog = NvidiaSkillsCatalog(cache, fetcher=fetch)
        self.assertEqual([item.name for item in catalog.load()], ["video-pipeline", "weather-forecast"])
        self.assertEqual(catalog.source, "remote")
        self.assertTrue(cache.exists())
        self.assertEqual(catalog.search("DeepStream object detection")[0].name, "video-pipeline")
        self.assertEqual(catalog.recommend("forecast the weather")[0].name, "weather-forecast")
        self.assertEqual(catalog.categories(), {"ai_and_machine_learning": 2})
        self.assertEqual(len(calls), 1)

    def test_fresh_cache_avoids_network(self):
        cache = self.root / "catalog.json"
        cache.write_text(json.dumps({
            "updated_at": time.time(),
            "skills": [_skill("cached-skill", "Cached description")],
        }), encoding="utf-8")

        def fail_fetch(url, timeout):
            raise AssertionError("network should not be called")

        catalog = NvidiaSkillsCatalog(cache, fetcher=fail_fetch)
        self.assertEqual(catalog.load()[0].name, "cached-skill")
        self.assertEqual(catalog.source, "cache")

    def test_stale_cache_is_used_when_refresh_fails(self):
        cache = self.root / "catalog.json"
        cache.write_text(json.dumps({
            "updated_at": 1,
            "skills": [_skill("stale-skill", "Still useful offline")],
        }), encoding="utf-8")

        def offline(url, timeout):
            raise OSError("offline")

        catalog = NvidiaSkillsCatalog(cache, ttl_seconds=0, fetcher=offline)
        self.assertEqual(catalog.load()[0].name, "stale-skill")
        self.assertEqual(catalog.source, "stale_cache")

    def test_bundled_fallback_is_metadata_only(self):
        catalog = NvidiaSkillsCatalog(self.root / "missing.json", fetcher=lambda *_: b"not json")
        skills = catalog.load()
        self.assertGreaterEqual(len(skills), 10)
        self.assertEqual(catalog.source, "fallback")
        self.assertFalse(catalog.status()["executes_remote_code"])
        self.assertTrue(all(item.path.startswith("skills/") for item in skills))


if __name__ == "__main__":
    unittest.main()
