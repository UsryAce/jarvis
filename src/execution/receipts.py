"""Immutable, content-free execution receipts and their public projection."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+/-]{0,127}$")
_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_EFFECT_STATES = frozenset(
    {
        "reserved",
        "dispatching",
        "applied",
        "not_applied",
        "needs_reconciliation",
        "reconciled_applied",
        "reconciled_not_applied",
        "reconciliation_failed",
    }
)
_SAFE_EVIDENCE_FIELDS = frozenset(
    {
        "active_processes",
        "after_sha256",
        "applied",
        "applied_truth",
        "artifact_id",
        "artifact_ids",
        "before_sha256",
        "bounded_bytes",
        "canonical_remote_id",
        "cleanup_truth",
        "code",
        "combined_bytes",
        "count",
        "deadline_ms",
        "descendants_verified",
        "duration_ms",
        "exit_code",
        "job_accounting_queried",
        "media_type",
        "observed_bytes",
        "promoted",
        "reason_code",
        "reconciliation_truth",
        "remote_reference",
        "residue",
        "retryable",
        "sha256",
        "signal",
        "size_bytes",
        "state",
        "status",
        "stderr_bytes",
        "stdout_bytes",
    }
)


class ReceiptProjectionError(ValueError):
    """Safe, stable receipt validation failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class CleanupTruth(str, Enum):
    NOT_REQUIRED = "not_required"
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    UNCONFIRMED = "unconfirmed"


class AppliedTruth(str, Enum):
    APPLIED = "applied"
    NOT_APPLIED = "not_applied"
    UNKNOWN = "unknown"


class ReconciliationTruth(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPLIED = "applied"
    NOT_APPLIED = "not_applied"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    artifact_id: str
    kind: str
    sha256: str
    size_bytes: int
    media_type: str
    sensitivity: str
    canonical_remote_id: str | None = None

    def __post_init__(self) -> None:
        _require_safe_id(self.artifact_id)
        _require_safe_id(self.kind)
        _require_digest(self.sha256)
        if not isinstance(self.size_bytes, int) or isinstance(self.size_bytes, bool) or self.size_bytes < 0:
            raise ReceiptProjectionError("invalid_artifact_size")
        _require_safe_id(self.media_type)
        _require_safe_id(self.sensitivity)
        if self.canonical_remote_id is not None:
            _require_safe_id(self.canonical_remote_id)


@dataclass(frozen=True, slots=True)
class ActionReceipt:
    receipt_id: str
    reservation_id: str
    request_id: str
    tool_id: str
    idempotency_key: str
    action_digest: str
    policy_outcome: str
    state: str
    applied_truth: AppliedTruth
    cleanup_truth: CleanupTruth
    reconciliation_truth: ReconciliationTruth
    reason_code: str
    started_at: str
    completed_at: str | None
    revision: int
    safe_evidence: tuple[tuple[str, Any], ...] = ()
    artifact_references: tuple[ArtifactReference, ...] = ()

    def __post_init__(self) -> None:
        for value in (
            self.receipt_id,
            self.reservation_id,
            self.request_id,
            self.tool_id,
            self.idempotency_key,
            self.reason_code,
        ):
            _require_safe_id(value)
        _require_digest(self.action_digest)
        if self.policy_outcome not in {"allow", "ask", "deny"}:
            raise ReceiptProjectionError("invalid_policy_outcome")
        if self.state not in _EFFECT_STATES:
            raise ReceiptProjectionError("invalid_effect_state")
        if type(self.applied_truth) is not AppliedTruth:
            raise ReceiptProjectionError("invalid_applied_truth")
        if type(self.cleanup_truth) is not CleanupTruth:
            raise ReceiptProjectionError("invalid_cleanup_truth")
        if type(self.reconciliation_truth) is not ReconciliationTruth:
            raise ReceiptProjectionError("invalid_reconciliation_truth")
        _require_timestamp(self.started_at)
        if self.completed_at is not None:
            _require_timestamp(self.completed_at)
        if not isinstance(self.revision, int) or isinstance(self.revision, bool) or self.revision < 1:
            raise ReceiptProjectionError("invalid_receipt_revision")
        if type(self.safe_evidence) is not tuple:
            raise ReceiptProjectionError("invalid_safe_evidence")
        evidence_keys: set[str] = set()
        for item in self.safe_evidence:
            if type(item) is not tuple or len(item) != 2:
                raise ReceiptProjectionError("invalid_safe_evidence")
            key, value = item
            if key in evidence_keys or key not in _SAFE_EVIDENCE_FIELDS:
                raise ReceiptProjectionError("unsafe_effect_evidence")
            evidence_keys.add(key)
            _validate_safe_value(value, depth=0)
        if type(self.artifact_references) is not tuple or any(
            type(item) is not ArtifactReference for item in self.artifact_references
        ):
            raise ReceiptProjectionError("invalid_artifact_references")

    @property
    def applied(self) -> bool | None:
        if self.applied_truth is AppliedTruth.APPLIED:
            return True
        if self.applied_truth is AppliedTruth.NOT_APPLIED:
            return False
        return None


def project_safe_receipt(receipt: ActionReceipt) -> dict[str, Any]:
    """Return the exact content-free durable/API projection for one receipt."""

    if type(receipt) is not ActionReceipt:
        raise ReceiptProjectionError("invalid_receipt")
    return {
        "receipt_id": receipt.receipt_id,
        "request_id": receipt.request_id,
        "tool_id": receipt.tool_id,
        "action_digest": receipt.action_digest,
        "effect_idempotency_key": receipt.idempotency_key,
        "policy_outcome": receipt.policy_outcome,
        "effect_state": receipt.state,
        "applied": receipt.applied,
        "reason_code": receipt.reason_code,
    }


def receipt_from_authority_row(
    row: Mapping[str, Any],
    *,
    artifact_rows: Iterable[Mapping[str, Any]] = (),
) -> ActionReceipt:
    """Hydrate only the allowlisted columns from authoritative store rows."""

    try:
        raw_evidence = json.loads(str(row["safe_evidence_json"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise ReceiptProjectionError("invalid_safe_evidence") from None
    if type(raw_evidence) is not dict or any(key not in _SAFE_EVIDENCE_FIELDS for key in raw_evidence):
        raise ReceiptProjectionError("unsafe_effect_evidence")
    evidence = tuple(sorted(raw_evidence.items()))
    artifacts = tuple(
        ArtifactReference(
            artifact_id=str(artifact["artifact_id"]),
            kind=str(artifact["kind"]),
            sha256=str(artifact["sha256"]),
            size_bytes=int(artifact["size_bytes"]),
            media_type=str(artifact["media_type"]),
            sensitivity=str(artifact["sensitivity"]),
            canonical_remote_id=(
                None
                if artifact["canonical_remote_id"] is None
                else str(artifact["canonical_remote_id"])
            ),
        )
        for artifact in artifact_rows
    )
    try:
        return ActionReceipt(
            receipt_id=str(row["receipt_id"]),
            reservation_id=str(row["reservation_id"]),
            request_id=str(row["request_id"]),
            tool_id=str(row["tool_id"]),
            idempotency_key=str(row["idempotency_key"]),
            action_digest=str(row["action_digest"]),
            policy_outcome=str(row["policy_outcome"]),
            state=str(row["state"]),
            applied_truth=AppliedTruth(str(row["applied_truth"])),
            cleanup_truth=CleanupTruth(str(row["cleanup_truth"])),
            reconciliation_truth=ReconciliationTruth(str(row["reconciliation_truth"])),
            reason_code=str(row["reason_code"]),
            started_at=str(row["started_at"]),
            completed_at=None if row["completed_at"] is None else str(row["completed_at"]),
            revision=int(row["revision"]),
            safe_evidence=evidence,
            artifact_references=artifacts,
        )
    except (KeyError, TypeError, ValueError):
        raise ReceiptProjectionError("invalid_authority_receipt") from None


def _require_safe_id(value: Any) -> str:
    if not isinstance(value, str) or _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ReceiptProjectionError("invalid_safe_identifier")
    return value


def _require_digest(value: Any) -> str:
    if not isinstance(value, str) or _HEX_DIGEST.fullmatch(value.casefold()) is None:
        raise ReceiptProjectionError("invalid_digest")
    return value.casefold()


def _require_timestamp(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 40
        or not value.endswith("Z")
        or "T" not in value
        or any(character in value for character in "\r\n\x00")
    ):
        raise ReceiptProjectionError("invalid_timestamp")
    return value


def _validate_safe_value(value: Any, *, depth: int) -> None:
    if depth > 5:
        raise ReceiptProjectionError("invalid_safe_evidence")
    if value is None or type(value) in {bool, int}:
        return
    if type(value) is str:
        _require_safe_id(value)
        return
    if type(value) in {tuple, list} and len(value) <= 64:
        for item in value:
            _validate_safe_value(item, depth=depth + 1)
        return
    if type(value) is dict and len(value) <= 64:
        for key, item in value.items():
            safe_key = _require_safe_id(key)
            if safe_key.casefold() in {
                "argument", "arguments", "environment", "browser_content",
                "command_output", "secret", "secrets", "exception",
                "exception_text", "stdout", "stderr", "raw_bytes", "output",
            }:
                raise ReceiptProjectionError("unsafe_effect_evidence")
            _validate_safe_value(item, depth=depth + 1)
        return
    raise ReceiptProjectionError("invalid_safe_evidence")


__all__ = [
    "ActionReceipt",
    "AppliedTruth",
    "ArtifactReference",
    "CleanupTruth",
    "ReceiptProjectionError",
    "ReconciliationTruth",
    "project_safe_receipt",
    "receipt_from_authority_row",
]
