"""Wave 0 contracts for exact resolved actions and a total policy kernel."""

from __future__ import annotations

import importlib
import json
import math
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


_CORPUS_PATH = Path(__file__).parent / "fixtures" / "capability_policy" / "hostile_actions.json"
_DECISIONS = {"allow", "ask", "deny"}
_REQUIRED_VECTOR_NAMES = {
    "unknown_tool",
    "unknown_tool_version",
    "unknown_effect",
    "alias_field",
    "extra_field",
    "bool_as_int",
    "nan",
    "positive_infinity",
    "negative_infinity",
    "invalid_utf8",
    "unicode_surrogate",
    "excessive_depth",
    "excessive_width",
    "excessive_string_bytes",
    "excessive_total_bytes",
    "generator",
    "infinite_iterable",
    "dict_subclass",
    "model_subclass",
    "datetime_subclass",
    "callable_value",
    "input_owned_hook",
    "absolute_path",
    "escaping_path",
    "unresolved_precondition",
    "field_order_equivalence",
    "one_field_digest_mutation",
    "redaction_canary",
}


def _future_module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name != name:
            raise
        return None


action_contracts = _future_module("src.security.action_contracts")
manifests = _future_module("src.security.manifests")
policy = _future_module("src.security.policy")

if action_contracts is not None:
    CanonicalArguments = action_contracts.CanonicalArguments
    ResolvedAction = action_contracts.ResolvedAction
    StrictActionEnvelope = action_contracts.StrictActionEnvelope
    canonical_action_bytes = action_contracts.canonical_action_bytes
    resolved_action_digest = action_contracts.resolved_action_digest

if manifests is not None:
    ManifestRegistry = manifests.ManifestRegistry
    ManifestSnapshot = manifests.ManifestSnapshot
    ToolManifest = manifests.ToolManifest
    resolve_manifest_action = manifests.resolve_manifest_action

if policy is not None:
    PolicyDecision = policy.PolicyDecision
    PolicyKernel = policy.PolicyKernel
    PolicyOutcome = policy.PolicyOutcome
    PolicySnapshot = policy.PolicySnapshot
    evaluate_policy = policy.evaluate_policy

requires_actions = pytest.mark.skipif(
    action_contracts is None,
    reason="future module src.security.action_contracts is absent; owned by Plan 02-07",
)
requires_manifests = pytest.mark.skipif(
    action_contracts is None or manifests is None,
    reason="future module src.security.manifests is absent; owned by Plan 02-07",
)
requires_policy = pytest.mark.skipif(
    action_contracts is None or policy is None,
    reason="future module src.security.policy is absent; owned by Plan 02-07",
)


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _corpus() -> dict[str, Any]:
    return json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))


def _outcome(decision: Any) -> str:
    value = getattr(decision, "outcome", None)
    return str(getattr(value, "value", value))


def _reason(decision: Any) -> str:
    return str(getattr(decision, "reason_code", ""))


def _assert_safe_decision(decision: Any, expected: str | None = None) -> None:
    _safe(type(decision) is PolicyDecision, "policy returned a non-exact decision record")
    actual = _outcome(decision)
    _safe(actual in _DECISIONS, "policy returned an outcome outside allow/ask/deny")
    if expected is not None:
        _safe(actual == expected, "policy outcome did not match the hostile contract")
    reason = _reason(decision)
    _safe(bool(reason), "policy decision omitted its stable reason code")
    _safe(reason.isascii() and len(reason) <= 96, "policy reason code is not bounded ASCII")


def _arguments(items: tuple[tuple[str, Any], ...] | None = None):
    return CanonicalArguments(
        items=items
        or (
            ("encoding", "utf-8"),
            ("path", "docs/readme.txt"),
        )
    )


def _action(**changes: Any):
    values = {
        "schema_version": "resolved-action.v1",
        "tool_id": "fixture.read",
        "tool_schema_version": "v1",
        "actor_id": "actor-fixture",
        "session_digest": "session-digest-fixture",
        "request_id": "request-fixture",
        "run_id": "run-fixture",
        "project_id": "project-fixture",
        "workspace_id": "workspace-fixture",
        "worktree_id": "worktree-fixture",
        "policy_digest": "policy-digest-fixture",
        "manifest_digest": "manifest-digest-fixture",
        "declared_effect": "read",
        "arguments": _arguments(),
        "precondition_digest": "precondition-digest-fixture",
    }
    values.update(changes)
    return ResolvedAction(**values)


def _policy_snapshot():
    return PolicySnapshot(
        schema_version="policy-snapshot.v1",
        policy_id="policy-fixture",
        version="v1",
        digest="policy-digest-fixture",
        manifest_digest="manifest-digest-fixture",
        rules=(
            ("fixture.read", "v1", "read", "allow", "policy_fixture_read_allowed"),
            ("fixture.write", "v1", "local_write", "ask", "policy_fixture_write_approval"),
        ),
    )


def test_hostile_corpus_is_bounded_complete_and_secret_safe() -> None:
    corpus = _corpus()
    _safe(corpus.get("schema_version") == "hostile-actions.v1", "corpus version mismatch")
    limits = corpus.get("limits", {})
    _safe(
        limits == {
            "max_depth": 8,
            "max_width": 32,
            "max_string_bytes": 4096,
            "max_total_bytes": 16384,
        },
        "hostile corpus bounds changed",
    )
    vectors = corpus.get("hostile_vectors", [])
    names = {item.get("name") for item in vectors}
    _safe(names == _REQUIRED_VECTOR_NAMES, "T-01/T-02 hostile vector inventory is incomplete")
    _safe(len(vectors) == len(names), "hostile corpus contains duplicate vector names")
    serialized = json.dumps(corpus, ensure_ascii=True, sort_keys=True)
    forbidden = ("nvapi-", "bearer ", "private_key", "api_key", "password")
    _safe(not any(item in serialized.casefold() for item in forbidden), "corpus contains secret material")


@requires_actions
def test_exact_resolved_action_is_frozen_and_canonical_bytes_are_domain_separated() -> None:
    action = _action()
    _safe(type(action) is ResolvedAction, "resolved action is not the exact module-owned type")
    with pytest.raises((AttributeError, TypeError, ValueError)):
        action.tool_id = "fixture.changed"
    encoded = canonical_action_bytes(action)
    _safe(type(encoded) is bytes, "canonical action output is not exact bytes")
    _safe(encoded.startswith(b"jarvis.resolved-action.v1\x00"), "canonical bytes lack domain separation")
    digest = resolved_action_digest(action)
    _safe(type(digest) is str and len(digest) == 64, "action digest is not SHA-256 hex")


@requires_actions
def test_field_order_equivalence_preserves_digest() -> None:
    corpus = _corpus()
    first, second = corpus["equivalent_argument_orders"]
    left = _action(arguments=_arguments(tuple((key, value) for key, value in first)))
    right = _action(arguments=_arguments(tuple((key, value) for key, value in second)))
    _safe(resolved_action_digest(left) == resolved_action_digest(right), "field order changed digest")
    _safe(canonical_action_bytes(left) == canonical_action_bytes(right), "field order changed bytes")


@requires_actions
def test_every_semantic_field_mutation_changes_digest_or_is_rejected() -> None:
    mutations: dict[str, Any] = {
        "tool_id": "fixture.read.changed",
        "tool_schema_version": "v2",
        "actor_id": "actor-changed",
        "session_digest": "session-digest-changed",
        "request_id": "request-changed",
        "run_id": "run-changed",
        "project_id": "project-changed",
        "workspace_id": "workspace-changed",
        "worktree_id": "worktree-changed",
        "policy_digest": "policy-digest-changed",
        "manifest_digest": "manifest-digest-changed",
        "declared_effect": "network_read",
        "arguments": _arguments((("encoding", "utf-8"), ("path", "docs/changed.txt"))),
        "precondition_digest": "precondition-digest-changed",
    }
    _safe(set(mutations) == set(_corpus()["semantic_mutations"]), "mutation inventory drifted")
    baseline = resolved_action_digest(_action())
    for field, value in mutations.items():
        try:
            changed = _action(**{field: value})
        except (TypeError, ValueError):
            continue
        _safe(resolved_action_digest(changed) != baseline, "semantic mutation preserved digest")


class _DictSubclass(dict):
    pass


class _DateTimeSubclass(datetime):
    pass


class _ModelSubclass:
    def model_dump(self):
        raise AssertionError("input-owned model hook executed")


class _HookedInput:
    def __iter__(self):
        raise AssertionError("input-owned iterator executed")

    def __str__(self):
        raise AssertionError("input-owned string hook executed")


class _InfiniteIterable:
    def __iter__(self):
        while True:
            yield "bounded-contract-must-not-iterate"


def _nested_tuple(depth: int) -> tuple[Any, ...]:
    value: Any = "x"
    for _ in range(depth):
        value = (value,)
    return value


@requires_actions
@pytest.mark.parametrize(
    ("safe_case", "value"),
    (
        ("bool_as_int", True),
        ("nan", math.nan),
        ("positive_infinity", math.inf),
        ("negative_infinity", -math.inf),
        ("invalid_utf8", b"\xff"),
        ("unicode_surrogate", "\ud800"),
        ("generator", (item for item in ("one", "two"))),
        ("infinite_iterable", _InfiniteIterable()),
        ("dict_subclass", _DictSubclass(value="x")),
        ("model_subclass", _ModelSubclass()),
        ("datetime_subclass", _DateTimeSubclass(2030, 1, 1, tzinfo=timezone.utc)),
        ("callable_value", lambda: None),
        ("input_owned_hook", _HookedInput()),
    ),
    ids=lambda item: item if isinstance(item, str) else None,
)
def test_polymorphic_callable_and_noncanonical_values_are_rejected_without_hooks(
    safe_case: str, value: Any
) -> None:
    canary = secrets.token_urlsafe(32)
    with pytest.raises((TypeError, ValueError)) as rejected:
        _arguments((("safe_case", safe_case), ("value", value), ("canary", canary)))
    error = rejected.value
    _safe(bool(getattr(error, "code", "")), "canonical rejection lacks a stable safe code")
    _safe(canary not in str(error), "canonical rejection exposed hostile input")


@requires_actions
@pytest.mark.parametrize(
    ("safe_case", "value"),
    (
        ("excessive_depth", _nested_tuple(9)),
        ("excessive_width", tuple(range(33))),
        ("excessive_string_bytes", "x" * 4097),
        ("excessive_total_bytes", tuple("x" * 1024 for _ in range(17))),
    ),
)
def test_depth_width_and_byte_limits_fail_closed(safe_case: str, value: Any) -> None:
    with pytest.raises((TypeError, ValueError)) as rejected:
        _arguments((("safe_case", safe_case), ("value", value)))
    _safe(bool(getattr(rejected.value, "code", "")), "bounded rejection lacks a safe code")


@requires_manifests
def test_manifest_records_are_exact_frozen_and_unknown_capabilities_are_absent() -> None:
    read = ToolManifest(
        tool_id="fixture.read",
        schema_version="v1",
        declared_effect="read",
        decision="allow",
        argument_names=("encoding", "path"),
        relative_path_fields=("path",),
        requires_precondition=True,
        max_argument_bytes=4096,
    )
    snapshot = ManifestSnapshot(
        schema_version="manifest-snapshot.v1",
        version="v1",
        digest="manifest-digest-fixture",
        tools=(read,),
    )
    registry = ManifestRegistry(snapshot)
    _safe(type(snapshot) is ManifestSnapshot, "manifest snapshot is not exact")
    with pytest.raises((AttributeError, TypeError, ValueError)):
        snapshot.version = "changed"
    for tool_id in ("shell.raw", "github.mutate", "project.autonomous_write"):
        _safe(registry.get(tool_id, "v1") is None, "deferred capability appeared in manifest")


@requires_policy
def test_policy_returns_exact_allow_ask_and_deny_results() -> None:
    snapshot = _policy_snapshot()
    allowed = evaluate_policy(_action(), snapshot)
    asked = evaluate_policy(
        _action(
            tool_id="fixture.write",
            declared_effect="local_write",
            arguments=_arguments((("path", "docs/output.txt"),)),
        ),
        snapshot,
    )
    denied = evaluate_policy(_action(tool_id="fixture.unknown"), snapshot)
    _assert_safe_decision(allowed, "allow")
    _assert_safe_decision(asked, "ask")
    _assert_safe_decision(denied, "deny")


@requires_policy
@pytest.mark.parametrize(
    ("safe_case", "hostile"),
    (
        ("plain_mapping", {"tool_id": "fixture.read"}),
        ("mapping_subclass", _DictSubclass(tool_id="fixture.read")),
        ("hooked_object", _HookedInput()),
        ("callable", lambda: None),
        ("generator", (item for item in ("fixture.read",))),
    ),
)
def test_policy_is_total_for_malformed_and_polymorphic_inputs_and_never_dispatches(
    safe_case: str, hostile: Any
) -> None:
    class _Adapter:
        calls = 0

        def execute(self) -> None:
            self.calls += 1

    adapter = _Adapter()
    decision = evaluate_policy(hostile, _policy_snapshot())
    _assert_safe_decision(decision, "deny")
    if _outcome(decision) == "allow":
        adapter.execute()
    _safe(adapter.calls == 0, "malformed policy input reached an adapter")
    _safe(_reason(decision).startswith(("schema_", "internal_")), "malformed deny code is unstable")


@requires_policy
@pytest.mark.parametrize(
    ("safe_case", "changes", "reason_prefix"),
    (
        ("unknown_version", {"tool_schema_version": "v999"}, "schema_"),
        ("unknown_effect", {"declared_effect": "ambient_machine_control"}, "schema_"),
        ("absolute_path", {"arguments": None}, "path_"),
        ("escaping_path", {"arguments": None}, "path_"),
        ("unresolved_precondition", {"precondition_digest": ""}, "precondition_"),
    ),
)
def test_unknown_path_and_precondition_cases_deny_or_reject_safely(
    safe_case: str, changes: dict[str, Any], reason_prefix: str
) -> None:
    if safe_case == "absolute_path":
        changes["arguments"] = _arguments((("path", "C:/Windows/System32/config"),))
    elif safe_case == "escaping_path":
        changes["arguments"] = _arguments((("path", "../outside.txt"),))
    try:
        action = _action(**changes)
    except (TypeError, ValueError) as rejected:
        _safe(bool(getattr(rejected, "code", "")), "pre-policy rejection lacks safe code")
        return
    decision = evaluate_policy(action, _policy_snapshot())
    _assert_safe_decision(decision, "deny")
    _safe(_reason(decision).startswith(reason_prefix), "deny reason family mismatch")


@requires_policy
def test_policy_failure_maps_to_safe_deny_without_exception_or_canary_text(monkeypatch) -> None:
    canary = secrets.token_urlsafe(32)

    def _fail(*_args: Any, **_kwargs: Any):
        raise RuntimeError(canary)

    monkeypatch.setattr(PolicyKernel, "evaluate", _fail)
    decision = evaluate_policy(_action(), _policy_snapshot())
    _assert_safe_decision(decision, "deny")
    _safe(_reason(decision) == "internal_policy_evaluation_failed", "failure code mismatch")
    _safe(canary not in repr(decision), "policy failure exposed exception text")
