"""Allowlist-first payload projection for every durable or rendered sink."""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypeAlias


JsonPrimitive: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]

_MAX_STRING_LENGTH = 512
_MAX_COLLECTION_ITEMS = 64
_MAX_DEPTH = 6
_FIELD_BREAKS = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|[^A-Za-z0-9]+")
_FORBIDDEN_FIELD_PARTS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "token",
        "secret",
        "password",
        "passwd",
        "cookie",
        "csrf",
        "ciphertext",
        "private_key",
        "request_body",
        "response_body",
        "provider_body",
        "headers",
        "stdout",
        "stderr",
        "prompt",
        "prefix",
        "suffix",
        "fingerprint",
        "hash",
        "digest",
    }
)

_SCHEMAS = MappingProxyType(
    {
        "auth": (
            "action",
            "outcome",
            "reason_code",
            "scope",
            "scopes",
            "session_state",
            "expires_at",
            "operator_id",
            "correlation_id",
            "audit_id",
        ),
        "control": (
            "reason_code",
            "scope_type",
            "scope_id",
            "previous_state",
            "state",
            "status",
            "revision",
            "accepted",
            "applied",
            "residue",
            "correlation_id",
            "audit_id",
        ),
        "audit": (
            "action",
            "outcome",
            "reason_code",
            "event_id",
            "sequence",
            "integrity_state",
            "safe_id",
            "correlation_id",
            "audit_id",
        ),
        "credential": (
            "provider",
            "label",
            "display_id",
            "credential_id",
            "state",
            "status",
            "version",
            "provider_generation",
            "allowed_actions",
            "reason_code",
            "correlation_id",
            "audit_id",
        ),
        "migration": (
            "safe_id",
            "version",
            "name",
            "status",
            "check",
            "checks",
            "backup_id",
            "applied",
            "reason_code",
            "correlation_id",
            "audit_id",
        ),
        "provider_validation": (
            "provider",
            "display_id",
            "credential_id",
            "state",
            "status",
            "code",
            "correlation_id",
            "audit_id",
            "retryable",
            "applied",
        ),
        "runtime": (
            "status",
            "state",
            "code",
            "action",
            "outcome",
            "reason_code",
            "run_id",
            "task_id",
            "revision",
            "residue",
            "correlation_id",
            "audit_id",
            "retryable",
            "applied",
        ),
    }
)


def sanitize_text(value: str, *, max_length: int = _MAX_STRING_LENGTH) -> str:
    """Remove line/control injection and bound a display-safe string."""

    if not isinstance(value, str) or not isinstance(max_length, int) or max_length < 0:
        raise TypeError("invalid_text")
    sanitized = "".join(
        " " if character in "\r\n" or unicodedata.category(character) == "Cc" else character
        for character in value
    )
    return sanitized[:max_length]


def _normalized_field_name(field_name: str) -> str:
    if not isinstance(field_name, str):
        raise TypeError("invalid_field")
    return "_".join(part.casefold() for part in _FIELD_BREAKS.split(field_name) if part)


def _is_forbidden_field(field_name: str) -> bool:
    normalized = _normalized_field_name(field_name)
    if normalized in _FORBIDDEN_FIELD_PARTS:
        return True
    segments = normalized.split("_")
    if any(segment in _FORBIDDEN_FIELD_PARTS for segment in segments):
        return True
    return any(
        marker in normalized
        for marker in (
            "authorization",
            "apikey",
            "api_key",
            "access_token",
            "refresh_token",
            "private_key",
            "provider_body",
            "request_body",
            "response_body",
            "ciphertext",
        )
    )


@dataclass(frozen=True, slots=True)
class SafeError:
    """Immutable error envelope containing only stable safe metadata."""

    code: str
    correlation_id: str
    audit_id: str | None = None
    retryable: bool = False
    applied: bool | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.retryable, bool):
            raise TypeError("invalid_safe_error")
        if self.applied is not None and not isinstance(self.applied, bool):
            raise TypeError("invalid_safe_error")
        object.__setattr__(self, "code", _safe_identifier(self.code))
        object.__setattr__(self, "correlation_id", _safe_identifier(self.correlation_id))
        if self.audit_id is not None:
            object.__setattr__(self, "audit_id", _safe_identifier(self.audit_id))

    def to_payload(self) -> dict[str, JsonValue]:
        payload: dict[str, Any] = {
            "code": self.code,
            "correlation_id": self.correlation_id,
            "retryable": self.retryable,
            "applied": self.applied,
        }
        if self.audit_id is not None:
            payload["audit_id"] = self.audit_id
        return project_safe_payload("runtime", payload)


def _safe_identifier(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise TypeError("invalid_safe_identifier")
    sanitized = sanitize_text(value, max_length=128)
    if sanitized != value:
        raise ValueError("invalid_safe_identifier")
    return sanitized


class Redactor:
    """Project canonical JSON-compatible values through named field schemas."""

    def __init__(
        self,
        *,
        max_string_length: int = _MAX_STRING_LENGTH,
        max_collection_items: int = _MAX_COLLECTION_ITEMS,
        max_depth: int = _MAX_DEPTH,
    ) -> None:
        if min(max_string_length, max_collection_items, max_depth) < 1:
            raise ValueError("invalid_redaction_bounds")
        self.max_string_length = max_string_length
        self.max_collection_items = max_collection_items
        self.max_depth = max_depth

    def project(self, event_type: str, value: Mapping[str, Any]) -> dict[str, JsonValue]:
        normalized_event = self._event_name(event_type)
        if not isinstance(value, Mapping):
            raise TypeError("invalid_payload")
        self._reject_forbidden_fields(value, depth=0)
        allowed_fields = _SCHEMAS[normalized_event]
        allowed_set = frozenset(allowed_fields)
        if any(not isinstance(key, str) or key not in allowed_set for key in value):
            raise ValueError("field_not_allowed")
        projected: dict[str, JsonValue] = {}
        for field_name in allowed_fields:
            if field_name in value:
                projected[field_name] = self._canonicalize(value[field_name], depth=0)
        return projected

    @staticmethod
    def _event_name(event_type: str) -> str:
        if not isinstance(event_type, str):
            raise TypeError("invalid_event_type")
        normalized = event_type.casefold().replace("-", "_")
        if normalized not in _SCHEMAS:
            raise ValueError("unsupported_event_type")
        return normalized

    def _reject_forbidden_fields(self, value: Any, *, depth: int) -> None:
        if depth > self.max_depth:
            raise ValueError("payload_too_deep")
        if isinstance(value, Mapping):
            if len(value) > self.max_collection_items:
                raise ValueError("payload_too_large")
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError("invalid_field")
                if _is_forbidden_field(key):
                    raise ValueError("unsafe_field")
                self._reject_forbidden_fields(item, depth=depth + 1)
        elif isinstance(value, Sequence) and not isinstance(
            value, (str, bytes, bytearray, memoryview)
        ):
            if len(value) > self.max_collection_items:
                raise ValueError("payload_too_large")
            for item in value:
                self._reject_forbidden_fields(item, depth=depth + 1)
        elif isinstance(value, (bytes, bytearray, memoryview, BaseException)):
            raise TypeError("unsafe_value")

    def _canonicalize(self, value: Any, *, depth: int) -> JsonValue:
        if depth > self.max_depth:
            raise ValueError("payload_too_deep")
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("non_finite_number")
            return value
        if isinstance(value, str):
            return sanitize_text(value, max_length=self.max_string_length)
        if isinstance(value, Mapping):
            if len(value) > self.max_collection_items:
                raise ValueError("payload_too_large")
            result: dict[str, JsonValue] = {}
            for key in sorted(value):
                if not isinstance(key, str):
                    raise TypeError("invalid_field")
                if _is_forbidden_field(key):
                    raise ValueError("unsafe_field")
                safe_key = sanitize_text(key, max_length=128)
                if not safe_key or safe_key != key:
                    raise ValueError("invalid_field")
                result[safe_key] = self._canonicalize(value[key], depth=depth + 1)
            return result
        if isinstance(value, Sequence) and not isinstance(
            value, (bytes, bytearray, memoryview)
        ):
            if len(value) > self.max_collection_items:
                raise ValueError("payload_too_large")
            return [self._canonicalize(item, depth=depth + 1) for item in value]
        raise TypeError("unsupported_value")


def project_safe_payload(event_type: str, value: Mapping[str, Any]) -> dict[str, JsonValue]:
    """Apply the mandatory default Jarvis sink projection."""

    return Redactor().project(event_type, value)


__all__ = ["Redactor", "SafeError", "project_safe_payload", "sanitize_text"]
