"""Pure, deterministic, total policy decisions over sealed actions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any

from src.security.action_contracts import ACTION_SCHEMA_VERSION, CanonicalArguments, ResolvedAction


POLICY_SCHEMA_VERSION = "policy-snapshot.v1"
_ALLOWED_EFFECTS = frozenset(
    {"read", "local_write", "process", "network_read", "external_write"}
)
_DENIED_TOOL_IDS = frozenset(
    {"shell.raw", "github.mutate", "project.autonomous_write"}
)
_PATH_NAMES = frozenset(
    {"path", "cwd", "source", "destination", "target_path", "output_path"}
)


class PolicyOutcome(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


def _safe_ascii(value: Any, *, code: str, maximum: int = 256) -> str:
    if type(value) is not str or not value or len(value) > maximum:
        raise ValueError(code)
    try:
        value.encode("ascii", errors="strict")
    except UnicodeError:
        raise ValueError(code) from None
    if any(ord(character) < 0x20 for character in value):
        raise ValueError(code)
    return value


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Safe policy output containing no raw argument or exception text."""

    outcome: PolicyOutcome
    reason_code: str
    capability_id: str = "none"
    boundary_id: str = "none"
    effect: str = "none"
    limits_summary: tuple[tuple[str, int], ...] = ()
    argument_summary: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self) is not PolicyDecision:
            raise ValueError("schema_policy_decision_exact_type_required")
        if type(self.outcome) is not PolicyOutcome:
            raise ValueError("schema_policy_outcome_invalid")
        _safe_ascii(self.reason_code, code="schema_policy_reason_invalid", maximum=96)
        _safe_ascii(self.capability_id, code="schema_policy_capability_invalid")
        _safe_ascii(self.boundary_id, code="schema_policy_boundary_invalid")
        _safe_ascii(self.effect, code="schema_policy_effect_invalid")
        if type(self.limits_summary) is not tuple or len(self.limits_summary) > 16:
            raise ValueError("schema_policy_limits_invalid")
        for item in self.limits_summary:
            if (
                type(item) is not tuple
                or len(item) != 2
                or type(item[0]) is not str
                or type(item[1]) is not int
                or isinstance(item[1], bool)
                or item[1] < 0
            ):
                raise ValueError("schema_policy_limits_invalid")
            _safe_ascii(item[0], code="schema_policy_limits_invalid", maximum=64)
        if type(self.argument_summary) is not tuple or len(self.argument_summary) > 32:
            raise ValueError("schema_policy_argument_summary_invalid")
        for name in self.argument_summary:
            _safe_ascii(name, code="schema_policy_argument_summary_invalid", maximum=64)

    @classmethod
    def deny(cls, reason_code: str) -> "PolicyDecision":
        return cls(PolicyOutcome.DENY, reason_code)


@dataclass(frozen=True, slots=True)
class PolicySnapshot:
    """Immutable, callback-free policy rule data."""

    schema_version: str
    policy_id: str
    version: str
    digest: str
    manifest_digest: str
    rules: tuple[tuple[str, str, str, str, str], ...]

    def __post_init__(self) -> None:
        if type(self) is not PolicySnapshot:
            raise ValueError("schema_policy_snapshot_exact_type_required")
        if self.schema_version != POLICY_SCHEMA_VERSION:
            raise ValueError("schema_policy_snapshot_version_unknown")
        for value, code in (
            (self.policy_id, "schema_policy_id_invalid"),
            (self.version, "schema_policy_version_invalid"),
            (self.digest, "schema_policy_digest_invalid"),
            (self.manifest_digest, "schema_manifest_digest_invalid"),
        ):
            _safe_ascii(value, code=code)
        if type(self.rules) is not tuple or len(self.rules) > 128:
            raise ValueError("schema_policy_rules_invalid")
        normalized: list[tuple[str, str, str, str, str]] = []
        keys: set[tuple[str, str, str]] = set()
        for rule in self.rules:
            if type(rule) is not tuple or len(rule) != 5:
                raise ValueError("schema_policy_rule_invalid")
            tool_id, tool_version, effect, outcome, reason_code = rule
            _safe_ascii(tool_id, code="schema_policy_tool_invalid")
            _safe_ascii(tool_version, code="schema_policy_tool_version_invalid")
            if type(effect) is not str or effect not in _ALLOWED_EFFECTS:
                raise ValueError("schema_policy_effect_invalid")
            if type(outcome) is not str or outcome not in {
                item.value for item in PolicyOutcome
            }:
                raise ValueError("schema_policy_outcome_invalid")
            _safe_ascii(reason_code, code="schema_policy_reason_invalid", maximum=96)
            key = (tool_id, tool_version, effect)
            if key in keys:
                raise ValueError("schema_policy_rule_duplicate")
            keys.add(key)
            normalized.append(rule)
        normalized.sort(key=lambda rule: (rule[0], rule[1], rule[2]))
        object.__setattr__(self, "rules", tuple(normalized))


def _is_relative_path(value: Any) -> bool:
    if type(value) is not str or not value:
        return False
    if "\x00" in value or "\\" in value or ":" in value:
        return False
    if value.startswith("/") or value.endswith("/"):
        return False
    segments = value.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        return False
    return all(not segment.endswith((".", " ")) for segment in segments)


def _path_rejection(arguments: CanonicalArguments) -> str | None:
    for name, value in arguments.items:
        if name in _PATH_NAMES or name.endswith("_path"):
            if not _is_relative_path(value):
                return "path_relative_required"
    return None


def _safe_boundary(action: ResolvedAction) -> str:
    if action.worktree_id:
        return "worktree"
    if action.workspace_id:
        return "workspace"
    if action.project_id:
        return "project"
    return "none"


class PolicyKernel:
    """Compiled data-only decision table; evaluation performs no I/O."""

    __slots__ = ("_effects_by_tool", "_rules", "_snapshot")

    def __init__(self, snapshot: PolicySnapshot) -> None:
        if type(snapshot) is not PolicySnapshot:
            raise ValueError("schema_policy_snapshot_exact_type_required")
        rules = {
            (tool_id, version, effect): (PolicyOutcome(outcome), reason_code)
            for tool_id, version, effect, outcome, reason_code in snapshot.rules
        }
        effects_by_tool: dict[str, tuple[tuple[str, str], ...]] = {}
        for tool_id, version, effect, _outcome, _reason_code in snapshot.rules:
            current = effects_by_tool.get(tool_id, ())
            effects_by_tool[tool_id] = current + ((version, effect),)
        object.__setattr__(self, "_snapshot", snapshot)
        object.__setattr__(self, "_rules", MappingProxyType(rules))
        object.__setattr__(self, "_effects_by_tool", MappingProxyType(effects_by_tool))

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("policy_kernel_frozen")

    @property
    def snapshot(self) -> PolicySnapshot:
        return self._snapshot

    def evaluate(self, action: ResolvedAction) -> PolicyDecision:
        if type(action) is not ResolvedAction:
            return PolicyDecision.deny("schema_action_exact_type_required")
        snapshot = self.snapshot
        if action.schema_version != ACTION_SCHEMA_VERSION:
            return PolicyDecision.deny("schema_action_version_unknown")
        if action.tool_id in _DENIED_TOOL_IDS:
            return PolicyDecision.deny("scope_capability_deferred")
        if action.policy_digest != snapshot.digest:
            return PolicyDecision.deny("schema_policy_snapshot_stale")
        if action.manifest_digest != snapshot.manifest_digest:
            return PolicyDecision.deny("schema_manifest_snapshot_stale")
        if not action.precondition_digest:
            return PolicyDecision.deny("precondition_digest_missing")
        if not all(
            (
                action.actor_id,
                action.session_digest,
                action.request_id,
                action.run_id,
                action.project_id,
                action.workspace_id,
            )
        ):
            return PolicyDecision.deny("identity_resolved_context_missing")
        path_reason = _path_rejection(action.arguments)
        if path_reason is not None:
            return PolicyDecision.deny(path_reason)
        variants = self._effects_by_tool.get(action.tool_id)
        if variants is None:
            return PolicyDecision.deny("manifest_tool_unknown")
        version_variants = tuple(
            effect for version, effect in variants if version == action.tool_schema_version
        )
        if not version_variants:
            return PolicyDecision.deny("schema_tool_version_unknown")
        if action.declared_effect not in version_variants:
            return PolicyDecision.deny("schema_effect_unknown")
        outcome, reason_code = self._rules[
            (action.tool_id, action.tool_schema_version, action.declared_effect)
        ]
        return PolicyDecision(
            outcome=outcome,
            reason_code=reason_code,
            capability_id=action.tool_id,
            boundary_id=_safe_boundary(action),
            effect=action.declared_effect,
            argument_summary=tuple(name for name, _value in action.arguments.items),
        )


def evaluate_policy(action: object, snapshot: object) -> PolicyDecision:
    """Total public wrapper mapping every unexpected failure to a safe deny."""

    try:
        if type(action) is not ResolvedAction:
            return PolicyDecision.deny("schema_action_exact_type_required")
        if type(snapshot) is not PolicySnapshot:
            return PolicyDecision.deny("schema_policy_snapshot_exact_type_required")
        return PolicyKernel(snapshot).evaluate(action)
    except BaseException:
        return PolicyDecision.deny("internal_policy_evaluation_failed")


__all__ = [
    "POLICY_SCHEMA_VERSION",
    "PolicyDecision",
    "PolicyKernel",
    "PolicyOutcome",
    "PolicySnapshot",
    "evaluate_policy",
]
