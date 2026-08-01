"""Wave 0 contracts for handle-verified Windows filesystem mutation.

The production broker is intentionally absent until Plan 02-10.  Inventory and
helper-safety tests execute now; named broker gates activate without test edits
when ``src.execution.filesystem`` lands.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest


HELPER = Path(__file__).parent / "windows_helpers" / "path_swap_probe.py"
_NAMESPACE_CASES = {
    "dot": ".",
    "dotdot": "..\\escape.txt",
    "absolute": "C:\\Windows\\Temp\\escape.txt",
    "drive_relative": "C:escape.txt",
    "unc": "\\\\server\\share\\escape.txt",
    "extended": "\\\\?\\C:\\escape.txt",
    "device": "\\\\.\\PhysicalDrive0",
    "native": "\\??\\C:\\escape.txt",
    "ads": "document.txt:stream",
    "reserved_con": "CON",
    "reserved_extension": "aux.txt",
    "trailing_dot": "folder.\\file.txt",
    "trailing_space": "folder \\file.txt",
    "control": "folder\\bad\x1f.txt",
    "nul": "folder\\bad\x00.txt",
    "surrogate": "folder\\bad\ud800.txt",
}
_OBJECT_CASES = {
    "symlink",
    "junction",
    "mount_point",
    "reparse_point",
    "hard_link_write",
    "volume_change",
    "ambiguous_case",
}
_MUTATION_PROOFS = {
    "held_root_handle",
    "held_parent_handle",
    "same_volume",
    "same_directory_stage",
    "bounded_bytes",
    "sha256",
    "precondition_rechecked",
    "final_identity_verified",
    "atomic_replace",
    "reconciliation_truth",
}


def _future_module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name != name and not name.startswith(f"{error.name}."):
            raise
        return None


filesystem_module = _future_module("src.execution.filesystem")
if filesystem_module is not None:
    FileMutationEvidence = filesystem_module.FileMutationEvidence
    FilesystemBroker = filesystem_module.FilesystemBroker
    FilesystemBrokerError = filesystem_module.FilesystemBrokerError
    VerifiedPath = filesystem_module.VerifiedPath

requires_filesystem = pytest.mark.skipif(
    filesystem_module is None,
    reason="future module src.execution.filesystem is absent; owned by Plan 02-10",
)
requires_windows_filesystem = pytest.mark.skipif(
    sys.platform != "win32" or filesystem_module is None,
    reason="real Windows filesystem broker contracts require Plan 02-10 on Windows",
)


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _code(error: BaseException) -> str:
    return str(getattr(error, "code", ""))


def _broker(root: Path, **changes: Any):
    values = {"max_bytes": 4096, "max_depth": 16, "max_path_chars": 512}
    values.update(changes)
    return FilesystemBroker(root, **values)


def _assert_safe_rejection(error: BaseException) -> None:
    _safe(type(error) is FilesystemBrokerError, "filesystem rejection used a non-exact error type")
    code = _code(error)
    _safe(bool(code) and code.isascii() and len(code) <= 96, "filesystem rejection lacks a stable code")


def test_t08_t10_inventory_requires_namespace_object_race_and_evidence_families() -> None:
    _safe(set(_NAMESPACE_CASES) == {
        "dot", "dotdot", "absolute", "drive_relative", "unc", "extended",
        "device", "native", "ads", "reserved_con", "reserved_extension",
        "trailing_dot", "trailing_space", "control", "nul", "surrogate",
    }, "T-08/T-09 namespace inventory is incomplete")
    _safe(_OBJECT_CASES == {
        "symlink", "junction", "mount_point", "reparse_point", "hard_link_write",
        "volume_change", "ambiguous_case",
    }, "T-09/T-10 object inventory is incomplete")
    _safe(_MUTATION_PROOFS == {
        "held_root_handle", "held_parent_handle", "same_volume",
        "same_directory_stage", "bounded_bytes", "sha256",
        "precondition_rechecked", "final_identity_verified", "atomic_replace",
        "reconciliation_truth",
    }, "T-10 mutation proof inventory is incomplete")
    source = inspect.getsource(sys.modules[__name__]).casefold()
    for required in ("swap-parent", "before_stage", "outside", "path.resolve()"):
        _safe(required in source, "race or string-only containment guard is missing")


def test_path_swap_probe_rejects_non_generated_paths_with_stable_status(tmp_path: Path) -> None:
    status = tmp_path / "status.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(HELPER),
            "junction",
            "--anchor", str(tmp_path),
            "--link", str(tmp_path / "link"),
            "--target", str(tmp_path.parent),
            "--status-file", str(status),
        ],
        cwd=Path(__file__).parents[1],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    _safe(completed.returncode == 2, "path-swap helper accepted a target outside its anchor")
    _safe(not completed.stdout and not completed.stderr, "path-swap helper emitted diagnostics")
    _safe(
        json.loads(status.read_text(encoding="ascii"))
        == {"code": "probe_failed", "operation": "junction"},
        "path-swap helper status was unstable or disclosed a path",
    )


@requires_filesystem
@pytest.mark.parametrize("safe_case", tuple(_NAMESPACE_CASES), ids=tuple(_NAMESPACE_CASES))
def test_relative_canonical_segments_reject_every_namespace_and_name_escape(
    tmp_path: Path, safe_case: str
) -> None:
    broker = _broker(tmp_path)
    with pytest.raises(FilesystemBrokerError) as rejected:
        broker.verify_path(_NAMESPACE_CASES[safe_case], for_write=True)
    _assert_safe_rejection(rejected.value)
    _safe(not any(tmp_path.iterdir()), "invalid path validation mutated the grant")


@requires_windows_filesystem
def test_verified_path_uses_handle_identity_not_path_resolve(tmp_path: Path) -> None:
    target = tmp_path / "Folder" / "item.txt"
    target.parent.mkdir()
    target.write_bytes(b"fixture")
    verified = _broker(tmp_path).verify_path("Folder\\item.txt", for_write=False)
    _safe(type(verified) is VerifiedPath, "verification returned a non-exact record")
    _safe(bool(verified.held_root_handle), "verified path omitted its held root handle")
    _safe(bool(verified.held_parent_handle), "verified path omitted its held parent handle")
    _safe(bool(verified.final_file_id), "verified path omitted final file identity")
    _safe(verified.same_volume and verified.final_identity_verified,
          "verified path did not prove same-volume final identity")


@requires_windows_filesystem
@pytest.mark.parametrize("object_case", ("symlink", "junction"))
def test_links_and_reparse_points_are_rejected_on_real_windows_objects(
    tmp_path: Path, object_case: str
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    if object_case == "symlink":
        try:
            os.symlink(target, link, target_is_directory=True)
        except OSError:
            pytest.xfail("MANUAL RELEASE GATE PENDING: Windows symlink privilege unavailable")
    else:
        status = tmp_path / "junction-status.json"
        completed = subprocess.run(
            [sys.executable, str(HELPER), "junction", "--anchor", str(tmp_path),
             "--link", str(link), "--target", str(target), "--status-file", str(status)],
            cwd=Path(__file__).parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False,
        )
        _safe(completed.returncode == 0, "safe junction fixture could not be created")
    with pytest.raises(FilesystemBrokerError) as rejected:
        _broker(tmp_path).verify_path(f"link\\escaped.txt", for_write=True)
    _assert_safe_rejection(rejected.value)


@requires_windows_filesystem
def test_multi_link_destination_and_ambiguous_case_are_not_writable(tmp_path: Path) -> None:
    original = tmp_path / "Original.txt"
    original.write_bytes(b"before")
    os.link(original, tmp_path / "Second.txt")
    broker = _broker(tmp_path)
    with pytest.raises(FilesystemBrokerError) as hard_link_write:
        broker.verify_path("Original.txt", for_write=True)
    _assert_safe_rejection(hard_link_write.value)
    with pytest.raises(FilesystemBrokerError) as ambiguous_case:
        broker.verify_path("original.txt", for_write=False)
    _assert_safe_rejection(ambiguous_case.value)
    _safe(original.read_bytes() == b"before", "rejected object validation changed bytes")


@requires_windows_filesystem
def test_write_is_bounded_hashed_same_directory_and_precondition_checked(tmp_path: Path) -> None:
    target = tmp_path / "output.bin"
    target.write_bytes(b"before")
    before = hashlib.sha256(b"before").hexdigest()
    payload = b"after"
    evidence = _broker(tmp_path).write_bytes(
        "output.bin", payload, precondition_sha256=before
    )
    _safe(type(evidence) is FileMutationEvidence, "write returned a non-exact evidence record")
    _safe(evidence.outcome == "applied", "bounded write did not report applied truth")
    _safe(evidence.bytes_count == len(payload), "write evidence has the wrong byte count")
    _safe(evidence.sha256 == hashlib.sha256(payload).hexdigest(), "write hash is incorrect")
    _safe(evidence.same_directory_stage and evidence.same_volume, "stage escaped destination volume")
    _safe(evidence.precondition_rechecked and evidence.final_identity_verified,
          "write omitted precondition or final identity proof")
    _safe(evidence.atomic_replace, "same-volume replacement was not atomic")
    _safe(target.read_bytes() == payload, "applied write has the wrong bytes")
    _safe(payload not in repr(evidence).encode("utf-8"), "evidence exposed file contents")

    with pytest.raises(FilesystemBrokerError) as oversized:
        _broker(tmp_path, max_bytes=4).write_bytes("too-large.bin", b"12345")
    _assert_safe_rejection(oversized.value)
    _safe(not (tmp_path / "too-large.bin").exists(), "oversized write created a destination")


@requires_windows_filesystem
def test_parent_swap_between_validation_and_stage_cannot_escape_grant(tmp_path: Path) -> None:
    grant = tmp_path / "grant"
    outside = tmp_path / "outside"
    parent = grant / "parent"
    backup = outside / "held-parent"
    grant.mkdir()
    outside.mkdir()
    parent.mkdir()
    armed = tmp_path / "armed"
    trigger = tmp_path / "trigger"
    status = tmp_path / "swap-status.json"
    attacker = subprocess.Popen(
        [sys.executable, str(HELPER), "swap-parent", "--anchor", str(tmp_path),
         "--link", str(parent), "--target", str(outside), "--backup", str(backup),
         "--armed-file", str(armed), "--trigger-file", str(trigger),
         "--status-file", str(status)],
        cwd=Path(__file__).parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 10
    while not armed.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    _safe(armed.exists(), "parent-swap helper did not arm")

    def before_stage() -> None:
        trigger.touch()
        wait_until = time.monotonic() + 10
        while not status.exists() and time.monotonic() < wait_until:
            time.sleep(0.01)

    with pytest.raises(FilesystemBrokerError) as raced:
        _broker(grant).write_bytes("parent\\escaped.bin", b"blocked", before_stage=before_stage)
    stdout, stderr = attacker.communicate(timeout=10)
    _assert_safe_rejection(raced.value)
    _safe(attacker.returncode == 0 and not stdout and not stderr, "parent-swap helper failed")
    _safe(not (outside / "escaped.bin").exists(), "raced write escaped the registered grant")
    _safe(not any(path.name.startswith(".jarvis-stage-") for path in outside.iterdir()),
          "raced write left staging residue outside the grant")


@requires_windows_filesystem
def test_precondition_failure_is_not_applied_and_has_explicit_truth(tmp_path: Path) -> None:
    target = tmp_path / "guarded.txt"
    target.write_bytes(b"current")
    broker = _broker(tmp_path)
    try:
        evidence = broker.write_bytes("guarded.txt", b"changed", precondition_sha256="0" * 64)
    except FilesystemBrokerError as rejected:
        _assert_safe_rejection(rejected)
        _safe(target.read_bytes() == b"current", "failed precondition changed destination")
        return
    _safe(type(evidence) is FileMutationEvidence, "failure returned unsafe evidence")
    _safe(evidence.outcome in {"not_applied", "needs_reconciliation"},
          "failed precondition claimed an unsupported outcome")
    _safe(evidence.reconciliation_truth in {"not_required", "pending", "unconfirmed"},
          "failure omitted reconciliation truth")
    _safe(target.read_bytes() == b"current", "failed precondition changed destination")
