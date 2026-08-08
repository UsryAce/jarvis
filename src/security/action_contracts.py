"""Exact action records and module-owned canonicalization.

Proposal data stops at :class:`StrictActionEnvelope`.  Trusted identity and
authority fields are supplied separately by the resolver and copied into the
frozen :class:`ResolvedAction` record.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


ACTION_SCHEMA_VERSION = "resolved-action.v1"
ACTION_ENVELOPE_SCHEMA_VERSION = "action-envelope.v1"
CANONICAL_DOMAIN = b"jarvis.resolved-action.v1\x00"
MAX_DEPTH = 8
MAX_WIDTH = 32
MAX_STRING_BYTES = 4096
MAX_TOTAL_BYTES = 16384
MIN_INTEGER = -(2**63)
MAX_INTEGER = 2**63 - 1
_MAX_IDENTIFIER_BYTES = 256
_EFFECTS = frozenset(
    {"read", "local_write", "process", "network_read", "external_write"}
)


class ActionContractError(ValueError):
    """A stable, non-secret action-boundary rejection."""

    __slots__ = ("code", "reference")

    def __init__(self, code: str, *, reference: str = "action") -> None:
        self.code = code
        self.reference = reference
        super().__init__(code)


def _safe_text(value: Any, *, code: str, allow_empty: bool = False) -> str:
    if type(value) is not str:
        raise ActionContractError(code)
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise ActionContractError(code) from None
    if (not allow_empty and not value) or len(encoded) > _MAX_IDENTIFIER_BYTES:
        raise ActionContractError(code)
    normalized = unicodedata.normalize("NFC", value)
    if normalized != value or any(ord(character) < 0x20 for character in value):
        raise ActionContractError(code)
    return value


def _normalize_value(value: Any, *, depth: int, budget: list[int]) -> Any:
    if depth > MAX_DEPTH:
        raise ActionContractError("schema_argument_depth_exceeded")
    value_type = type(value)
    if value is None:
        budget[0] += 4
        normalized: Any = None
    elif value_type is bool:
        # No registered v1 argument schema consumes a boolean.  Rejecting it
        # here also prevents Python's bool-is-int relationship from widening
        # integer fields implicitly.
        raise ActionContractError("schema_boolean_not_declared")
    elif value_type is int:
        if value < MIN_INTEGER or value > MAX_INTEGER:
            raise ActionContractError("schema_integer_out_of_range")
        budget[0] += len(str(value))
        normalized = value
    elif value_type is float:
        if not math.isfinite(value):
            raise ActionContractError("schema_non_finite_number")
        raise ActionContractError("schema_float_not_supported")
    elif value_type is str:
        try:
            encoded = value.encode("utf-8", errors="strict")
        except UnicodeError:
            raise ActionContractError("schema_string_encoding_invalid") from None
        if len(encoded) > MAX_STRING_BYTES:
            raise ActionContractError("schema_string_bytes_exceeded")
        normalized = unicodedata.normalize("NFC", value)
        if normalized != value:
            raise ActionContractError("schema_string_not_normalized")
        budget[0] += len(encoded)
    elif value_type is tuple:
        if len(value) > MAX_WIDTH:
            raise ActionContractError("schema_argument_width_exceeded")
        normalized = tuple(
            _normalize_value(item, depth=depth + 1, budget=budget) for item in value
        )
    elif value_type is dict:
        if len(value) > MAX_WIDTH:
            raise ActionContractError("schema_argument_width_exceeded")
        pairs: list[tuple[str, Any]] = []
        for key, item in value.items():
            normalized_key = _safe_text(key, code="schema_argument_key_invalid")
            budget[0] += len(normalized_key.encode("utf-8"))
            pairs.append(
                (
                    normalized_key,
                    _normalize_value(item, depth=depth + 1, budget=budget),
                )
            )
        pairs.sort(key=lambda pair: pair[0])
        if len({key for key, _item in pairs}) != len(pairs):
            raise ActionContractError("schema_argument_key_duplicate")
        normalized = _CanonicalMap(tuple(pairs))
    else:
        raise ActionContractError("schema_argument_type_invalid")
    if budget[0] > MAX_TOTAL_BYTES:
        raise ActionContractError("schema_argument_total_bytes_exceeded")
    return normalized


class _CanonicalMap(tuple):
    """Module-owned marker distinguishing a map from a sequence internally."""

    __slots__ = ()


@dataclass(frozen=True, slots=True)
class CanonicalArguments:
    """Immutable arguments in the closed canonical value grammar."""

    items: tuple[tuple[str, Any], ...]

    def __post_init__(self) -> None:
        if type(self) is not CanonicalArguments or type(self.items) is not tuple:
            raise ActionContractError("schema_arguments_exact_type_required")
        if len(self.items) > MAX_WIDTH:
            raise ActionContractError("schema_argument_width_exceeded")
        budget = [0]
        normalized: list[tuple[str, Any]] = []
        seen: set[str] = set()
        for pair in self.items:
            if type(pair) is not tuple or len(pair) != 2:
                raise ActionContractError("schema_argument_pair_invalid")
            key = _safe_text(pair[0], code="schema_argument_key_invalid")
            if key in seen:
                raise ActionContractError("schema_argument_key_duplicate")
            seen.add(key)
            budget[0] += len(key.encode("utf-8"))
            normalized.append(
                (key, _normalize_value(pair[1], depth=1, budget=budget))
            )
        normalized.sort(key=lambda pair: pair[0])
        if budget[0] > MAX_TOTAL_BYTES:
            raise ActionContractError("schema_argument_total_bytes_exceeded")
        object.__setattr__(self, "items", tuple(normalized))

    @classmethod
    def from_dict(cls, value: object) -> "CanonicalArguments":
        if type(value) is not dict:
            raise ActionContractError("schema_arguments_mapping_required")
        return cls(tuple((key, item) for key, item in value.items()))

    def get(self, name: str, default: Any = None) -> Any:
        if type(name) is not str:
            return default
        for key, value in self.items:
            if key == name:
                return value
        return default


class StrictActionEnvelope(BaseModel):
    """Strict untrusted proposal DTO; it intentionally has no identity fields."""

    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
        hide_input_in_errors=True,
        validate_by_alias=False,
        validate_by_name=True,
    )

    schema_version: str = ACTION_ENVELOPE_SCHEMA_VERSION
    tool_id: str
    tool_schema_version: str
    arguments: dict[str, Any]

    @model_validator(mode="before")
    @classmethod
    def _require_exact_mapping(cls, value: Any) -> Any:
        if type(value) is not dict:
            raise ValueError("schema_envelope_mapping_required")
        return value

    @field_validator("schema_version", "tool_id", "tool_schema_version", mode="before")
    @classmethod
    def _validate_text(cls, value: Any) -> str:
        return _safe_text(value, code="schema_envelope_text_invalid")

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        if value != ACTION_ENVELOPE_SCHEMA_VERSION:
            raise ValueError("schema_envelope_version_unknown")
        return value

    @field_validator("arguments", mode="before")
    @classmethod
    def _validate_arguments(cls, value: Any) -> dict[str, Any]:
        canonical = CanonicalArguments.from_dict(value)
        return {key: _public_value(item) for key, item in canonical.items}

    def canonical_arguments(self) -> CanonicalArguments:
        return CanonicalArguments.from_dict(self.arguments)


@dataclass(frozen=True, slots=True)
class ResolvedAction:
    """Authority-neutral, exact action consumed by policy and approval code."""

    schema_version: str
    tool_id: str
    tool_schema_version: str
    actor_id: str
    session_digest: str
    request_id: str
    run_id: str
    project_id: str
    workspace_id: str
    worktree_id: str
    policy_digest: str
    manifest_digest: str
    declared_effect: str
    arguments: CanonicalArguments
    precondition_digest: str

    def __post_init__(self) -> None:
        if type(self) is not ResolvedAction:
            raise ActionContractError("schema_action_exact_type_required")
        if self.schema_version != ACTION_SCHEMA_VERSION:
            raise ActionContractError("schema_action_version_unknown")
        for name in (
            "tool_id",
            "tool_schema_version",
            "actor_id",
            "session_digest",
            "request_id",
            "run_id",
            "project_id",
            "workspace_id",
            "worktree_id",
            "policy_digest",
            "manifest_digest",
        ):
            _safe_text(getattr(self, name), code=f"schema_{name}_invalid")
        if self.declared_effect not in _EFFECTS or type(self.declared_effect) is not str:
            raise ActionContractError("schema_effect_unknown")
        if type(self.arguments) is not CanonicalArguments:
            raise ActionContractError("schema_arguments_exact_type_required")
        _safe_text(
            self.precondition_digest,
            code="precondition_digest_missing",
            allow_empty=False,
        )


def _public_value(value: Any) -> Any:
    value_type = type(value)
    if value is None or value_type in {int, str}:
        return value
    if value_type is tuple:
        return tuple(_public_value(item) for item in value)
    if value_type is _CanonicalMap:
        return {key: _public_value(item) for key, item in value}
    raise ActionContractError("schema_canonical_value_invalid")


def _json_value(value: Any) -> Any:
    value_type = type(value)
    if value is None or value_type in {int, str}:
        return value
    if value_type is tuple:
        return [_json_value(item) for item in value]
    if value_type is _CanonicalMap:
        return {key: _json_value(item) for key, item in value}
    raise ActionContractError("schema_canonical_value_invalid")


def canonical_action_bytes(action: ResolvedAction) -> bytes:
    """Return compact, sorted, domain-separated UTF-8 JSON for one action."""

    if type(action) is not ResolvedAction:
        raise ActionContractError("schema_action_exact_type_required")
    payload = {
        "actor_id": action.actor_id,
        "arguments": {key: _json_value(value) for key, value in action.arguments.items},
        "declared_effect": action.declared_effect,
        "manifest_digest": action.manifest_digest,
        "policy_digest": action.policy_digest,
        "precondition_digest": action.precondition_digest,
        "project_id": action.project_id,
        "request_id": action.request_id,
        "run_id": action.run_id,
        "schema_version": action.schema_version,
        "session_digest": action.session_digest,
        "tool_id": action.tool_id,
        "tool_schema_version": action.tool_schema_version,
        "workspace_id": action.workspace_id,
        "worktree_id": action.worktree_id,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8", errors="strict")
    if len(encoded) > MAX_TOTAL_BYTES + 8192:
        raise ActionContractError("schema_action_total_bytes_exceeded")
    return CANONICAL_DOMAIN + encoded


def resolved_action_digest(action: ResolvedAction) -> str:
    return hashlib.sha256(canonical_action_bytes(action)).hexdigest()


__all__ = [
    "ACTION_ENVELOPE_SCHEMA_VERSION",
    "ACTION_SCHEMA_VERSION",
    "ActionContractError",
    "CanonicalArguments",
    "ResolvedAction",
    "StrictActionEnvelope",
    "canonical_action_bytes",
    "resolved_action_digest",
]
