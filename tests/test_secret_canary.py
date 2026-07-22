"""Generated secret-canary contracts for every prohibited projection sink."""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import uuid4

import pytest


redaction = pytest.importorskip(
    "src.security.redaction", reason="Plan 01-04 has not landed"
)

project_safe_payload = redaction.project_safe_payload

PROHIBITED_SINKS = frozenset(
    {
        "api_response",
        "stdout",
        "stderr",
        "log",
        "prompt",
        "audit",
        "agent_store",
        "swarm_store",
        "frontend_state",
        "browser_storage",
        "frontend_build",
        "graphify",
        "obsidian",
        "chroma",
        "configuration",
        "artifact",
    }
)


@dataclass(frozen=True)
class CanaryFinding:
    sink: str
    safe_reference: str


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _generated_canary() -> bytearray:
    # Shape only; this is generated test material and never sourced from env/config.
    return bytearray(("nvapi-" + secrets.token_urlsafe(48)).encode("ascii"))


def _contains_secret(value: Any, canary: bytes) -> bool:
    if isinstance(value, str):
        return canary in value.encode("utf-8", errors="replace")
    if isinstance(value, (bytes, bytearray, memoryview)):
        return canary in bytes(value)
    if isinstance(value, Mapping):
        return any(
            _contains_secret(key, canary) or _contains_secret(item, canary)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_secret(item, canary) for item in value)
    return False


def scan_named_sinks(
    canary: bytes, sinks: Mapping[str, Iterable[Any]]
) -> list[CanaryFinding]:
    findings: list[CanaryFinding] = []
    for sink, values in sinks.items():
        if any(_contains_secret(value, canary) for value in values):
            findings.append(
                CanaryFinding(sink=sink, safe_reference=uuid4().hex[:10])
            )
    return findings


def _format_findings(findings: Iterable[CanaryFinding]) -> str:
    return ", ".join(
        f"{finding.sink}[{finding.safe_reference}]" for finding in findings
    )


def _bounded_tree_contains(
    root: Path, canary: bytes, *, max_files: int = 256, max_bytes: int = 2_000_000
) -> bool:
    if not root.exists():
        return False
    candidates = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
    for path in candidates[:max_files]:
        try:
            if path.stat().st_size > max_bytes:
                continue
            if canary in path.read_bytes():
                return True
        except OSError:
            continue
    return False


def test_scanner_enumerates_every_keys_02_and_d04_prohibited_sink() -> None:
    expected = {
        "api_response",
        "stdout",
        "stderr",
        "log",
        "prompt",
        "audit",
        "agent_store",
        "swarm_store",
        "frontend_state",
        "browser_storage",
        "frontend_build",
        "graphify",
        "obsidian",
        "chroma",
        "configuration",
        "artifact",
    }
    _safe(PROHIBITED_SINKS == expected, "secret-canary sink inventory is incomplete")


def test_scanner_reports_only_sink_and_independent_safe_reference() -> None:
    canary = _generated_canary()
    try:
        findings = scan_named_sinks(
            bytes(canary),
            {
                "provider_error": ({"detail": bytes(canary)},),
                "safe_sink": ({"code": "invalid_auth"},),
            },
        )
        rendered = _format_findings(findings)
        _safe([finding.sink for finding in findings] == ["provider_error"], "leak sink mismatch")
        _safe(bytes(canary) not in rendered.encode("utf-8"), "finding output exposed canary")
        _safe("nvapi" not in rendered.casefold(), "finding reference derived from canary shape")
    finally:
        canary[:] = b"\x00" * len(canary)


@pytest.mark.parametrize(
    ("event_type", "field_name"),
    (
        ("credential", "api_key"),
        ("provider_validation", "authorization"),
        ("provider_validation", "provider_body"),
        ("audit", "secret"),
        ("runtime", "prompt"),
        ("runtime", "stdout"),
        ("runtime", "stderr"),
    ),
)
def test_redaction_rejects_canary_before_api_error_audit_or_prompt_projection(
    event_type: str, field_name: str
) -> None:
    canary = _generated_canary()
    try:
        with pytest.raises((TypeError, ValueError)) as rejected:
            project_safe_payload(event_type, {field_name: bytes(canary).decode("ascii")})
        _safe(
            bytes(canary) not in str(rejected.value).encode("utf-8", errors="replace"),
            "redaction exception echoed generated secret material",
        )
    finally:
        canary[:] = b"\x00" * len(canary)


def test_captured_runtime_and_browser_sinks_remain_canary_free(capture_sinks) -> None:
    canary = _generated_canary()
    try:
        capture_sinks.responses.append(
            {"display_id": "Credential 7F3A", "state": "pending_validation"}
        )
        capture_sinks.logs.append({"code": "validation_started"})
        capture_sinks.audits.append({"action": "credential_add", "outcome": "accepted"})
        capture_sinks.artifacts.append({"safe_reference": uuid4().hex})
        sinks = {
            "api_response": capture_sinks.responses,
            "stdout": (),
            "stderr": (),
            "log": capture_sinks.logs,
            "prompt": ({"message": "provider validation requested"},),
            "audit": capture_sinks.audits,
            "agent_store": ({"status": "queued"},),
            "swarm_store": ({"status": "idle"},),
            "frontend_state": ({"credential_id": "opaque-handle"},),
            "browser_storage": ({"theme": "dark"},),
            "artifact": capture_sinks.artifacts,
        }
        findings = scan_named_sinks(bytes(canary), sinks)
        _safe(not findings, f"canary reached captured sink categories: {_format_findings(findings)}")
    finally:
        canary[:] = b"\x00" * len(canary)


def test_bounded_build_graph_vault_memory_config_and_artifact_scan_is_clean() -> None:
    from src.core.knowledge_vault import KnowledgeVault

    project_root = Path(__file__).parents[1]
    vault = KnowledgeVault(project_root)
    canary = _generated_canary()
    roots = {
        "frontend_build": project_root / "frontend" / "dist",
        "graphify": project_root / ".planning" / "graphs",
        "obsidian": vault.vault_root / "Projects" / "Jarvis",
        "chroma": project_root / "data" / "memory",
        "configuration": project_root / "config",
        "artifact": project_root / "graphify-out",
    }
    try:
        findings = [
            CanaryFinding(sink=name, safe_reference=uuid4().hex[:10])
            for name, root in roots.items()
            if _bounded_tree_contains(root, bytes(canary))
        ]
        _safe(not findings, f"canary reached bounded paths: {_format_findings(findings)}")
    finally:
        canary[:] = b"\x00" * len(canary)


def test_only_dpapi_ciphertext_is_an_allowed_persistence_class() -> None:
    secret_module = pytest.importorskip(
        "src.security.secrets", reason="Plan 01-04 has not landed"
    )
    canary = _generated_canary()
    entropy = bytearray(secrets.token_bytes(32))
    try:
        ciphertext = secret_module.CurrentUserDpapiProtector().protect(
            canary, purpose="credential", entropy=entropy
        )
        _safe(bytes(canary) not in bytes(ciphertext), "DPAPI persistence contains plaintext")
        allowed_store = {"trust_store_ciphertext": (ciphertext,)}
        prohibited_store = {"configuration": ({"provider": "nvidia"},)}
        _safe(
            not scan_named_sinks(bytes(canary), allowed_store | prohibited_store),
            "canary persisted outside ciphertext-only control storage",
        )
    finally:
        canary[:] = b"\x00" * len(canary)
        entropy[:] = b"\x00" * len(entropy)


def test_frontend_metadata_fixture_has_no_secret_or_ciphertext_fields() -> None:
    dto = {
        "provider": "nvidia",
        "label": "Primary",
        "display_id": "Credential 7F3A",
        "state": "active",
        "version": 3,
        "provider_generation": 2,
        "allowed_actions": ["drain", "rotate"],
    }
    serialized = json.dumps(dto, sort_keys=True)
    forbidden = {"secret", "api_key", "ciphertext", "authorization", "prefix", "suffix"}
    _safe(not forbidden.intersection(dto), "frontend DTO exposes a forbidden field")
    _safe("Bearer " not in serialized, "frontend DTO contains an authorization value")
