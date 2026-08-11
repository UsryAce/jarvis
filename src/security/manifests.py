"""Immutable typed capability manifests and trusted action resolution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from src.security.action_contracts import (
    ACTION_SCHEMA_VERSION,
    CanonicalArguments,
    ResolvedAction,
    StrictActionEnvelope,
)


_DECISIONS = frozenset({"allow", "ask", "deny"})
_EFFECTS = frozenset(
    {"read", "local_write", "process", "network_read", "external_write"}
)
_DEFAULT_VERSION = "v1"
_SNAPSHOT_SCHEMA = "manifest-snapshot.v1"
_DOMAIN = b"jarvis.manifest-snapshot.v1\x00"


class ManifestError(ValueError):
    """Stable, non-secret manifest or resolution rejection."""

    __slots__ = ("code", "reference")

    def __init__(self, code: str, *, reference: str = "manifest") -> None:
        self.code = code
        self.reference = reference
        super().__init__(code)


def _text(value: Any, code: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str or (not allow_empty and not value):
        raise ManifestError(code)
    try:
        encoded = value.encode("ascii", errors="strict")
    except UnicodeError:
        raise ManifestError(code) from None
    if len(encoded) > 256 or any(ord(character) < 0x20 for character in value):
        raise ManifestError(code)
    return value


def _string_tuple(value: Any, code: str, *, maximum: int = 32) -> tuple[str, ...]:
    if type(value) is not tuple or len(value) > maximum:
        raise ManifestError(code)
    result = tuple(_text(item, code) for item in value)
    if len(set(result)) != len(result):
        raise ManifestError(code)
    return result


@dataclass(frozen=True, slots=True)
class ToolManifest:
    tool_id: str
    schema_version: str
    declared_effect: str
    decision: str
    argument_names: tuple[str, ...]
    relative_path_fields: tuple[str, ...] = ()
    required_argument_names: tuple[str, ...] = ()
    requires_project: bool = True
    requires_workspace: bool = True
    requires_worktree: bool = False
    requires_precondition: bool = False
    executable_ids: tuple[str, ...] = ()
    network_schemes: tuple[str, ...] = ()
    network_hosts: tuple[str, ...] = ()
    max_argument_bytes: int = 4096
    max_input_bytes: int = 0
    max_output_bytes: int = 0
    max_duration_ms: int = 0
    max_items: int = 32

    def __post_init__(self) -> None:
        if type(self) is not ToolManifest:
            raise ManifestError("schema_manifest_exact_type_required")
        _text(self.tool_id, "schema_manifest_tool_invalid")
        _text(self.schema_version, "schema_manifest_version_invalid")
        if type(self.declared_effect) is not str or self.declared_effect not in _EFFECTS:
            raise ManifestError("schema_manifest_effect_invalid")
        if type(self.decision) is not str or self.decision not in _DECISIONS:
            raise ManifestError("schema_manifest_decision_invalid")
        arguments = _string_tuple(self.argument_names, "schema_manifest_arguments_invalid")
        paths = _string_tuple(self.relative_path_fields, "schema_manifest_paths_invalid")
        required = self.required_argument_names or arguments
        required = _string_tuple(required, "schema_manifest_required_invalid")
        executables = _string_tuple(
            self.executable_ids, "schema_manifest_executables_invalid", maximum=16
        )
        schemes = _string_tuple(
            self.network_schemes, "schema_manifest_network_invalid", maximum=8
        )
        hosts = _string_tuple(
            self.network_hosts, "schema_manifest_network_invalid", maximum=32
        )
        argument_set = set(arguments)
        if not (set(paths) | set(required)) <= argument_set:
            raise ManifestError("schema_manifest_field_unknown")
        for name in (
            "requires_project",
            "requires_workspace",
            "requires_worktree",
            "requires_precondition",
        ):
            if type(getattr(self, name)) is not bool:
                raise ManifestError("schema_manifest_boolean_invalid")
        for name in (
            "max_argument_bytes",
            "max_input_bytes",
            "max_output_bytes",
            "max_duration_ms",
            "max_items",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0 or value > 2**31 - 1:
                raise ManifestError("schema_manifest_limit_invalid")
        if not 1 <= self.max_argument_bytes <= 16384 or not 1 <= self.max_items <= 32:
            raise ManifestError("schema_manifest_limit_invalid")
        object.__setattr__(self, "argument_names", arguments)
        object.__setattr__(self, "relative_path_fields", paths)
        object.__setattr__(self, "required_argument_names", required)
        object.__setattr__(self, "executable_ids", executables)
        object.__setattr__(self, "network_schemes", schemes)
        object.__setattr__(self, "network_hosts", hosts)


@dataclass(frozen=True, slots=True)
class ManifestSnapshot:
    schema_version: str
    version: str
    digest: str
    tools: tuple[ToolManifest, ...]

    def __post_init__(self) -> None:
        if type(self) is not ManifestSnapshot:
            raise ManifestError("schema_manifest_snapshot_exact_type_required")
        if self.schema_version != _SNAPSHOT_SCHEMA:
            raise ManifestError("schema_manifest_snapshot_version_unknown")
        _text(self.version, "schema_manifest_snapshot_version_invalid")
        _text(self.digest, "schema_manifest_snapshot_digest_invalid")
        if type(self.tools) is not tuple or len(self.tools) > 64:
            raise ManifestError("schema_manifest_snapshot_tools_invalid")
        keys: set[tuple[str, str]] = set()
        for tool in self.tools:
            if type(tool) is not ToolManifest:
                raise ManifestError("schema_manifest_exact_type_required")
            key = (tool.tool_id, tool.schema_version)
            if key in keys:
                raise ManifestError("schema_manifest_duplicate")
            keys.add(key)


def _manifest_payload(tool: ToolManifest) -> dict[str, Any]:
    return {
        "argument_names": list(tool.argument_names),
        "decision": tool.decision,
        "declared_effect": tool.declared_effect,
        "executable_ids": list(tool.executable_ids),
        "max_argument_bytes": tool.max_argument_bytes,
        "max_duration_ms": tool.max_duration_ms,
        "max_input_bytes": tool.max_input_bytes,
        "max_items": tool.max_items,
        "max_output_bytes": tool.max_output_bytes,
        "network_hosts": list(tool.network_hosts),
        "network_schemes": list(tool.network_schemes),
        "relative_path_fields": list(tool.relative_path_fields),
        "required_argument_names": list(tool.required_argument_names),
        "requires_precondition": tool.requires_precondition,
        "requires_project": tool.requires_project,
        "requires_workspace": tool.requires_workspace,
        "requires_worktree": tool.requires_worktree,
        "schema_version": tool.schema_version,
        "tool_id": tool.tool_id,
    }


def _snapshot_digest(version: str, tools: tuple[ToolManifest, ...]) -> str:
    payload = {
        "schema_version": _SNAPSHOT_SCHEMA,
        "tools": [
            _manifest_payload(tool)
            for tool in sorted(tools, key=lambda item: (item.tool_id, item.schema_version))
        ],
        "version": version,
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(_DOMAIN + encoded).hexdigest()


def _default_tools() -> tuple[ToolManifest, ...]:
    path_read = ToolManifest(
        "filesystem.read", "v1", "read", "allow", ("path", "encoding"),
        ("path",), ("path",), requires_precondition=True, max_output_bytes=1_048_576,
    )
    path_write = ToolManifest(
        "filesystem.write", "v1", "local_write", "ask", ("path", "content"),
        ("path",), requires_precondition=True, max_input_bytes=1_048_576,
    )
    process_common = dict(
        declared_effect="process", decision="ask",
        argument_names=("executable_id", "argv", "cwd", "stdin"),
        relative_path_fields=("cwd",), required_argument_names=("executable_id", "argv", "cwd"),
        requires_worktree=True, executable_ids=("python", "node", "git", "application"),
        max_input_bytes=65_536, max_output_bytes=1_048_576, max_duration_ms=600_000,
    )
    browser_common = dict(
        declared_effect="network_read", decision="ask", requires_worktree=False,
        network_schemes=("https",), max_output_bytes=8_388_608, max_duration_ms=120_000,
    )
    return (
        path_read,
        path_write,
        ToolManifest(tool_id="process.exec", schema_version="v1", **process_common),
        ToolManifest(tool_id="process.build", schema_version="v1", **process_common),
        ToolManifest(tool_id="process.test", schema_version="v1", **process_common),
        ToolManifest(tool_id="application.launch", schema_version="v1", **process_common),
        ToolManifest(
            tool_id="browser.navigate", schema_version="v1", argument_names=("url",),
            required_argument_names=("url",), **browser_common,
        ),
        ToolManifest(
            tool_id="browser.download", schema_version="v1",
            argument_names=("url", "filename"), required_argument_names=("url",),
            max_input_bytes=0, **browser_common,
        ),
        ToolManifest(
            tool_id="browser.capture", schema_version="v1",
            argument_names=("url", "artifact_type"), required_argument_names=("url", "artifact_type"),
            **browser_common,
        ),
        ToolManifest(
            "fixture.external_write", "v1", "external_write", "ask",
            ("target_id", "value", "idempotency_key"), (),
            ("target_id", "value", "idempotency_key"), requires_project=False,
            requires_workspace=False, requires_precondition=True,
        ),
        ToolManifest(
            "fixture.reconcile", "v1", "read", "allow", ("effect_id",), (),
            ("effect_id",), requires_project=False, requires_workspace=False,
            requires_precondition=True,
        ),
    )


def default_manifest_snapshot() -> ManifestSnapshot:
    tools = _default_tools()
    return ManifestSnapshot(
        schema_version=_SNAPSHOT_SCHEMA,
        version=_DEFAULT_VERSION,
        digest=_snapshot_digest(_DEFAULT_VERSION, tools),
        tools=tools,
    )


class ManifestRegistry:
    """Read-only exact lookup over one immutable manifest snapshot."""

    __slots__ = ("_index", "_snapshot")

    def __init__(self, snapshot: ManifestSnapshot | None = None) -> None:
        current = default_manifest_snapshot() if snapshot is None else snapshot
        if type(current) is not ManifestSnapshot:
            raise ManifestError("schema_manifest_snapshot_exact_type_required")
        object.__setattr__(self, "_snapshot", current)
        object.__setattr__(self, "_index", MappingProxyType(
            {(tool.tool_id, tool.schema_version): tool for tool in current.tools}
        ))

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("manifest_registry_frozen")

    @property
    def snapshot(self) -> ManifestSnapshot:
        return self._snapshot

    @property
    def version(self) -> str:
        return self.snapshot.version

    @property
    def digest(self) -> str:
        return self.snapshot.digest

    def get(self, tool_id: object, schema_version: object) -> ToolManifest | None:
        if type(tool_id) is not str or type(schema_version) is not str:
            return None
        return self._index.get((tool_id, schema_version))


def resolve_manifest_action(
    envelope: StrictActionEnvelope,
    registry: ManifestRegistry,
    *,
    actor_id: str,
    session_digest: str,
    request_id: str,
    run_id: str,
    project_id: str,
    workspace_id: str,
    worktree_id: str,
    policy_digest: str,
    precondition_digest: str,
) -> ResolvedAction:
    """Resolve an untrusted proposal with separately supplied trusted identity."""

    if type(envelope) is not StrictActionEnvelope:
        raise ManifestError("schema_envelope_exact_type_required")
    if type(registry) is not ManifestRegistry:
        raise ManifestError("schema_manifest_registry_exact_type_required")
    manifest = registry.get(envelope.tool_id, envelope.tool_schema_version)
    if manifest is None:
        raise ManifestError("manifest_tool_unknown", reference="tool")
    arguments = envelope.canonical_arguments()
    names = tuple(key for key, _value in arguments.items)
    if set(names) - set(manifest.argument_names):
        raise ManifestError("schema_argument_unknown", reference=manifest.tool_id)
    if set(manifest.required_argument_names) - set(names):
        raise ManifestError("schema_argument_missing", reference=manifest.tool_id)
    if manifest.requires_project and not project_id:
        raise ManifestError("scope_project_missing", reference=manifest.tool_id)
    if manifest.requires_workspace and not workspace_id:
        raise ManifestError("scope_workspace_missing", reference=manifest.tool_id)
    if manifest.requires_worktree and not worktree_id:
        raise ManifestError("scope_worktree_missing", reference=manifest.tool_id)
    if manifest.requires_precondition and not precondition_digest:
        raise ManifestError("precondition_digest_missing", reference=manifest.tool_id)
    return ResolvedAction(
        schema_version=ACTION_SCHEMA_VERSION,
        tool_id=manifest.tool_id,
        tool_schema_version=manifest.schema_version,
        actor_id=actor_id,
        session_digest=session_digest,
        request_id=request_id,
        run_id=run_id,
        project_id=project_id,
        workspace_id=workspace_id,
        worktree_id=worktree_id,
        policy_digest=policy_digest,
        manifest_digest=registry.digest,
        declared_effect=manifest.declared_effect,
        arguments=arguments,
        precondition_digest=precondition_digest,
    )


__all__ = [
    "ManifestError",
    "ManifestRegistry",
    "ManifestSnapshot",
    "ToolManifest",
    "default_manifest_snapshot",
    "resolve_manifest_action",
]
