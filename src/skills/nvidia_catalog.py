"""Safe discovery service for NVIDIA's official Agent Skills catalog.

NVIDIA Agent Skills are portable instruction sets, not NVIDIA NIM runtime
models.  This module deliberately reads catalog *metadata only*.  It never
downloads or executes SKILL.md instructions, scripts, or package installers.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

NVIDIA_SKILLS_REPOSITORY = "https://github.com/NVIDIA/skills"
NVIDIA_SKILLS_CATALOG_URL = (
    "https://raw.githubusercontent.com/NVIDIA/skills/main/"
    ".github/scripts/marketplace/metadata.json"
)
_ALLOWED_HOSTS = {"raw.githubusercontent.com"}
_MAX_CATALOG_BYTES = 4 * 1024 * 1024
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#._-]*")


@dataclass(frozen=True)
class NvidiaSkill:
    """Sanitized catalog metadata for one NVIDIA-verified Agent Skill."""

    name: str
    description: str
    path: str
    product: str = "NVIDIA"
    category: str = "other"
    subdomain: str = "general"
    audience: tuple[str, ...] = ()
    activity_tags: tuple[str, ...] = ()
    repository_url: str = NVIDIA_SKILLS_REPOSITORY

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["audience"] = list(self.audience)
        result["activity_tags"] = list(self.activity_tags)
        return result


# A deliberately small metadata-only fallback.  A successful refresh replaces
# this with the complete official catalog (currently 100+ entries).
_FALLBACK_SKILLS = (
    NvidiaSkill("accelerated-computing-cudf", "GPU DataFrames, pandas acceleration, ETL, joins and multi-GPU data workloads.", "skills/accelerated-computing-cudf", "cuDF", "accelerated_computing", "data-science", ("developer", "data_scientist"), ("transform", "integrate", "validate")),
    NvidiaSkill("cuopt-numerical-optimization-api", "Solve LP, MILP and QP optimization problems with NVIDIA cuOpt.", "skills/cuopt-numerical-optimization-api", "cuOpt", "ai_and_machine_learning", "decision-optimization", ("developer", "data_scientist"), ("optimize", "integrate", "benchmark")),
    NvidiaSkill("cuopt-routing-api-python", "Solve vehicle routing, TSP and pickup-delivery problems with the cuOpt Python API.", "skills/cuopt-routing-api-python", "cuOpt", "accelerated_computing", "decision-optimization", ("developer",), ("optimize", "configure", "validate")),
    NvidiaSkill("deepstream-generate-pipeline", "Build DeepStream video and image inference, detection, tracking and streaming pipelines.", "skills/deepstream-generate-pipeline", "DeepStream SDK", "ai_and_machine_learning", "vision-ai", ("ai_engineer", "developer"), ("generate", "inference", "deploy")),
    NvidiaSkill("deepstream-profile-pipeline", "Profile, benchmark and tune DeepStream pipelines with Nsight Systems.", "skills/deepstream-profile-pipeline", "DeepStream SDK", "ai_and_machine_learning", "vision-ai", ("developer",), ("profile", "benchmark", "optimize")),
    NvidiaSkill("earth2studio-deterministic-forecast", "Build deterministic weather and climate forecast inference with Earth2Studio.", "skills/earth2studio-deterministic-forecast", "Earth2Studio", "ai_and_machine_learning", "simulation-modeling", ("data_scientist",), ("inference", "configure", "validate")),
    NvidiaSkill("earth2studio-data-fetch", "Fetch weather and climate data through Earth2Studio data sources.", "skills/earth2studio-data-fetch", "Earth2Studio", "ai_and_machine_learning", "simulation-modeling", ("data_scientist",), ("extract", "transform", "validate")),
    NvidiaSkill("data-designer", "Create datasets, generate synthetic data and build data-generation pipelines.", "skills/data-designer", "NeMo", "ai_and_machine_learning", "training-ai", ("ai_engineer", "data_engineer"), ("generate", "synthesize", "validate")),
    NvidiaSkill("dynamo-recipe-runner", "Select, validate and deploy NVIDIA Dynamo Kubernetes inference recipes.", "skills/dynamo-recipe-runner", "Dynamo", "ai_and_machine_learning", "inference-ai", ("devops_engineer", "platform_engineer"), ("deploy", "orchestrate", "scale")),
    NvidiaSkill("dynamo-troubleshoot", "Diagnose failed or unhealthy NVIDIA Dynamo deployments.", "skills/dynamo-troubleshoot", "Dynamo", "ai_and_machine_learning", "inference-ai", ("devops_engineer",), ("troubleshoot", "debug", "recover")),
    NvidiaSkill("holoscan-setup", "Inspect a host and recommend a compatible NVIDIA Holoscan installation method.", "skills/holoscan-setup", "Holoscan", "physical_ai", "infrastructure", ("developer", "platform_engineer"), ("assess", "select", "configure")),
    NvidiaSkill("cudaq-guide", "Install, test and use CUDA-Q for GPU simulation, QPU hardware and quantum applications.", "skills/cudaq-guide", "CUDA-Q", "accelerated_computing", "quantum-computing", ("developer", "quantum_researcher"), ("get_started", "configure", "validate")),
)


def _default_cache_path() -> Path:
    override = os.getenv("JARVIS_CACHE_DIR")
    root = Path(override).expanduser() if override else Path.home() / ".jarvis" / "cache"
    return root / "nvidia-skills-catalog.json"


class NvidiaSkillsCatalog:
    """Cached, read-only discovery facade for official NVIDIA Agent Skills."""

    def __init__(
        self,
        cache_path: Optional[Path | str] = None,
        *,
        ttl_seconds: int = 24 * 60 * 60,
        timeout_seconds: float = 8.0,
        fetcher: Optional[Callable[[str, float], bytes]] = None,
    ) -> None:
        self.cache_path = Path(cache_path) if cache_path else _default_cache_path()
        self.ttl_seconds = max(0, ttl_seconds)
        self.timeout_seconds = max(0.1, timeout_seconds)
        self._fetcher = fetcher or self._fetch_url
        self._skills: Optional[tuple[NvidiaSkill, ...]] = None
        self.source = "not_loaded"
        self.last_updated: Optional[float] = None

    @staticmethod
    def _fetch_url(url: str, timeout: float) -> bytes:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
            raise ValueError("Refusing untrusted NVIDIA catalog URL")
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "Jarvis-NvidiaSkillsCatalog/1.0"})
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - host allowlisted above
            content_type = response.headers.get("Content-Type", "")
            if "json" not in content_type and "text/plain" not in content_type:
                raise ValueError(f"Unexpected catalog content type: {content_type}")
            data = response.read(_MAX_CATALOG_BYTES + 1)
        if len(data) > _MAX_CATALOG_BYTES:
            raise ValueError("NVIDIA catalog exceeds safe size limit")
        return data

    @staticmethod
    def _parse(payload: bytes | str | Mapping[str, Any]) -> tuple[NvidiaSkill, ...]:
        if isinstance(payload, bytes):
            raw = json.loads(payload.decode("utf-8"))
        elif isinstance(payload, str):
            raw = json.loads(payload)
        else:
            raw = payload
        entries = raw.get("skills") if isinstance(raw, Mapping) else None
        if not isinstance(entries, list):
            raise ValueError("Catalog must contain a skills list")

        parsed: list[NvidiaSkill] = []
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            name = str(entry.get("name", "")).strip()
            path = str(entry.get("path", "")).strip()
            description = str(entry.get("description", "")).strip()
            metadata = entry.get("metadata") if isinstance(entry.get("metadata"), Mapping) else {}
            if not name or name in seen or not path.startswith("skills/") or not description:
                continue
            if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}", name):
                continue
            parsed.append(NvidiaSkill(
                name=name,
                description=" ".join(description.split()),
                path=path,
                product=str(metadata.get("product.primary", "NVIDIA")).strip() or "NVIDIA",
                category=str(metadata.get("classification.category.primary", "other")).strip() or "other",
                subdomain=str(metadata.get("catalog.subdomain", "general")).strip() or "general",
                audience=_split_metadata(metadata.get("audience")),
                activity_tags=_split_metadata(metadata.get("discovery.activity_tags")),
            ))
            seen.add(name)
        if not parsed:
            raise ValueError("Catalog did not contain any valid skills")
        return tuple(sorted(parsed, key=lambda item: item.name.casefold()))

    def load(self, *, force_refresh: bool = False) -> list[NvidiaSkill]:
        """Load catalog, preferring memory/fresh disk then remote/stale/fallback."""
        if self._skills is not None and not force_refresh:
            return list(self._skills)

        cached = self._read_cache()
        if cached and not force_refresh and cached[1] + self.ttl_seconds >= time.time():
            self._set(cached[0], "cache", cached[1])
            return list(self._skills or ())

        try:
            skills = self._parse(self._fetcher(NVIDIA_SKILLS_CATALOG_URL, self.timeout_seconds))
            updated = time.time()
            self._write_cache(skills, updated)
            self._set(skills, "remote", updated)
        except Exception as exc:
            logger.warning("NVIDIA Skills catalog refresh failed: %s", exc)
            if cached:
                self._set(cached[0], "stale_cache", cached[1])
            else:
                self._set(_FALLBACK_SKILLS, "fallback", None)
        return list(self._skills or ())

    def refresh(self) -> list[NvidiaSkill]:
        return self.load(force_refresh=True)

    def list_skills(self, *, category: Optional[str] = None, product: Optional[str] = None) -> list[NvidiaSkill]:
        skills = self.load()
        if category:
            skills = [item for item in skills if item.category.casefold() == category.casefold()]
        if product:
            skills = [item for item in skills if item.product.casefold() == product.casefold()]
        return skills

    def categories(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.load():
            counts[item.category] = counts.get(item.category, 0) + 1
        return dict(sorted(counts.items()))

    def search(self, query: str, *, limit: int = 20) -> list[NvidiaSkill]:
        if not query.strip():
            return self.load()[: max(0, limit)]
        ranked = self._rank(query)
        return [item for score, item in ranked if score > 0][: max(0, limit)]

    def recommend(self, task: str, *, limit: int = 5) -> list[NvidiaSkill]:
        """Recommend metadata matches; activation remains an explicit caller choice."""
        return self.search(task, limit=limit)

    def status(self) -> dict[str, Any]:
        skills = self.load()
        return {
            "count": len(skills),
            "source": self.source,
            "last_updated": self.last_updated,
            "categories": self.categories(),
            "catalog_url": NVIDIA_SKILLS_CATALOG_URL,
            "repository_url": NVIDIA_SKILLS_REPOSITORY,
            "executes_remote_code": False,
        }

    def _rank(self, query: str) -> list[tuple[int, NvidiaSkill]]:
        terms = set(_tokens(query))
        ranked: list[tuple[int, NvidiaSkill]] = []
        for item in self.load():
            name = set(_tokens(item.name))
            product = set(_tokens(item.product))
            tags = set(_tokens(" ".join(item.activity_tags + (item.category, item.subdomain))))
            description = set(_tokens(item.description))
            audience = set(_tokens(" ".join(item.audience)))
            score = 8 * len(terms & name) + 6 * len(terms & product) + 5 * len(terms & tags)
            score += 3 * len(terms & description) + len(terms & audience)
            if query.casefold() in item.name.casefold() or query.casefold() in item.description.casefold():
                score += 10
            ranked.append((score, item))
        return sorted(ranked, key=lambda pair: (-pair[0], pair[1].name.casefold()))

    def _read_cache(self) -> Optional[tuple[tuple[NvidiaSkill, ...], float]]:
        try:
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
            updated = float(raw["updated_at"])
            skills = self._parse({"skills": raw["skills"]})
            return skills, updated
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    def _write_cache(self, skills: Iterable[NvidiaSkill], updated: float) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
            entries = []
            for item in skills:
                entries.append({
                    "name": item.name,
                    "description": item.description,
                    "path": item.path,
                    "metadata": {
                        "product.primary": item.product,
                        "classification.category.primary": item.category,
                        "catalog.subdomain": item.subdomain,
                        "audience": ",".join(item.audience),
                        "discovery.activity_tags": ",".join(item.activity_tags),
                    },
                })
            temp.write_text(json.dumps({"updated_at": updated, "skills": entries}, indent=2), encoding="utf-8")
            temp.replace(self.cache_path)
        except OSError as exc:
            logger.warning("Could not persist NVIDIA Skills catalog cache: %s", exc)

    def _set(self, skills: Iterable[NvidiaSkill], source: str, updated: Optional[float]) -> None:
        self._skills = tuple(skills)
        self.source = source
        self.last_updated = updated


def _split_metadata(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        return ()
    return tuple(str(item).strip() for item in values if str(item).strip())


def _tokens(value: str) -> list[str]:
    return _TOKEN_RE.findall(value.casefold().replace("_", " ").replace("-", " "))


__all__ = [
    "NVIDIA_SKILLS_CATALOG_URL",
    "NVIDIA_SKILLS_REPOSITORY",
    "NvidiaSkill",
    "NvidiaSkillsCatalog",
]
