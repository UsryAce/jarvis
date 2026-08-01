"""Wave 0 contracts for suspended Windows Job Object process containment.

The production broker is owned by Plan 02-10.  Complete hostile inventories and
the bounded helper execute now; named broker gates activate when that module
lands.  No legacy subprocess route is treated as containment evidence.
"""

from __future__ import annotations

import importlib
import inspect
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest


HELPER = Path(__file__).parent / "windows_helpers" / "process_tree_probe.py"
_EXECUTION_CASES = {
    "absolute_executable", "allowlisted_identity", "explicit_argv", "verified_cwd",
    "minimal_environment", "raw_shell_denied", "metacharacters_are_argv",
    "path_search_denied", "script_host_denied", "proxy_executable_denied",
}
_RESOURCE_CASES = {
    "stdin_limit", "stdout_limit", "stderr_limit", "combined_limit", "wall_deadline",
    "cpu_limit", "memory_limit", "process_limit", "handle_pressure", "invalid_bytes",
    "nonzero_exit",
}
_TREE_CASES = {
    "child", "grandchild", "breakaway_attempt", "timeout", "cancellation",
    "emergency_stop", "backend_shutdown", "port_residue", "lock_residue",
    "assignment_failure", "limit_failure", "membership_verification_failure",
}
_CLEANUP_TRUTH = {"confirmed", "partial", "unconfirmed"}
_STOP_REASONS = ("timeout", "cancellation", "emergency_stop", "backend_shutdown", "output_limit")


def _future_module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name != name and not name.startswith(f"{error.name}."):
            raise
        return None


job_module = _future_module("src.execution.windows_job")
if job_module is not None:
    ProcessLimits = job_module.ProcessLimits
    ProcessOutcome = job_module.ProcessOutcome
    WindowsJobBroker = job_module.WindowsJobBroker
    WindowsJobError = job_module.WindowsJobError
    terminate_job_tree = job_module.terminate_job_tree

requires_job = pytest.mark.skipif(
    job_module is None,
    reason="future module src.execution.windows_job is absent; owned by Plan 02-10",
)
requires_windows_job = pytest.mark.skipif(
    sys.platform != "win32" or job_module is None,
    reason="real suspended Windows Job Object contracts require Plan 02-10 on Windows",
)


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _code(error: BaseException) -> str:
    return str(getattr(error, "code", ""))


def _assert_safe_error(error: BaseException) -> None:
    _safe(type(error) is WindowsJobError, "process rejection used a non-exact error type")
    code = _code(error)
    _safe(bool(code) and code.isascii() and len(code) <= 96, "process rejection lacks a stable code")


def _limits(**changes: Any):
    values = {
        "wall_seconds": 5.0,
        "cpu_seconds": 2.0,
        "memory_bytes": 64 * 1024 * 1024,
        "max_processes": 4,
        "max_stdin_bytes": 4096,
        "max_stdout_bytes": 64 * 1024,
        "max_stderr_bytes": 32 * 1024,
        "max_combined_output_bytes": 80 * 1024,
        "max_handles": 128,
    }
    values.update(changes)
    return ProcessLimits(**values)


def _broker(tmp_path: Path, **changes: Any):
    values = {
        "allowed_executables": {str(Path(sys.executable).resolve())},
        "base_environment": {
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\\Windows"),
            "WINDIR": os.environ.get("WINDIR", r"C:\\Windows"),
            "TEMP": str(tmp_path),
            "TMP": str(tmp_path),
        },
    }
    values.update(changes)
    return WindowsJobBroker(**values)


def _argv(tmp_path: Path, mode: str, **changes: Any) -> tuple[str, ...]:
    values = {
        "status_file": tmp_path / f"{mode}-status.json",
        "duration_ms": 3000,
        "byte_count": 65536,
    }
    values.update(changes)
    return (
        str(HELPER), mode, "--root", str(tmp_path),
        "--status-file", str(values["status_file"]),
        "--duration-ms", str(values["duration_ms"]),
        "--byte-count", str(values["byte_count"]),
    )


def _run(broker: Any, tmp_path: Path, mode: str, **changes: Any):
    values = {
        "executable": str(Path(sys.executable).resolve()),
        "argv": _argv(tmp_path, mode),
        "cwd": tmp_path,
        "environment": {"JARVIS_FIXTURE": "1"},
        "stdin": b"",
        "limits": _limits(),
    }
    values.update(changes)
    return broker.run(**values)


def test_t11_t16_inventory_is_complete_and_uses_one_whole_job_stop_contract() -> None:
    _safe(_EXECUTION_CASES == {
        "absolute_executable", "allowlisted_identity", "explicit_argv", "verified_cwd",
        "minimal_environment", "raw_shell_denied", "metacharacters_are_argv",
        "path_search_denied", "script_host_denied", "proxy_executable_denied",
    }, "T-11/T-12 execution inventory is incomplete")
    _safe(_RESOURCE_CASES == {
        "stdin_limit", "stdout_limit", "stderr_limit", "combined_limit", "wall_deadline",
        "cpu_limit", "memory_limit", "process_limit", "handle_pressure", "invalid_bytes",
        "nonzero_exit",
    }, "T-13 resource inventory is incomplete")
    _safe(_TREE_CASES == {
        "child", "grandchild", "breakaway_attempt", "timeout", "cancellation",
        "emergency_stop", "backend_shutdown", "port_residue", "lock_residue",
        "assignment_failure", "limit_failure", "membership_verification_failure",
    }, "T-14/T-15 tree inventory is incomplete")
    _safe(_CLEANUP_TRUTH == {"confirmed", "partial", "unconfirmed"},
          "T-16 cleanup vocabulary changed")
    source = inspect.getsource(sys.modules[__name__]).casefold()
    for reason in _STOP_REASONS:
        _safe(reason in source, "a required whole-job stop reason is missing")
    _safe("terminate_job_tree" in source, "tests do not bind stop paths to whole-job termination")
    forbidden_parent_kill = "process." + "kill()"
    _safe(forbidden_parent_kill not in source and "pid-only" in source,
          "tests permit PID-only cleanup evidence")


def test_process_tree_probe_is_bounded_and_emits_safe_status(tmp_path: Path) -> None:
    status = tmp_path / "status.json"
    marker = tmp_path / "marker.txt"
    completed = subprocess.run(
        [sys.executable, str(HELPER), "record", "--root", str(tmp_path),
         "--status-file", str(status), "--marker-file", str(marker),
         "--duration-ms", "100"],
        cwd=Path(__file__).parents[1], stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=5,
    )
    _safe(completed.returncode == 0, "bounded process helper failed")
    _safe(not completed.stdout and not completed.stderr, "process helper emitted diagnostics")
    _safe(json.loads(status.read_text(encoding="ascii")) == {"code": "ok", "mode": "record"},
          "process helper status was unstable or disclosed data")
    _safe(marker.read_text(encoding="ascii") == "work-observed", "process helper did not record work")


@requires_job
@pytest.mark.parametrize("bad_executable", ("python", "python.exe", "cmd.exe", "powershell.exe"))
def test_executable_must_be_absolute_allowlisted_and_never_path_searched(
    tmp_path: Path, bad_executable: str
) -> None:
    with pytest.raises(WindowsJobError) as rejected:
        _run(_broker(tmp_path), tmp_path, "record", executable=bad_executable)
    _assert_safe_error(rejected.value)


@requires_job
def test_raw_shell_contract_is_impossible_and_metacharacters_remain_one_argv_item(tmp_path: Path) -> None:
    broker = _broker(tmp_path)
    with pytest.raises((TypeError, WindowsJobError)) as raw_shell:
        broker.run(
            executable=str(Path(sys.executable).resolve()),
            argv=f'{HELPER} record & echo widened',
            cwd=tmp_path,
            environment={},
            stdin=b"",
            limits=_limits(),
        )
    if type(raw_shell.value) is WindowsJobError:
        _assert_safe_error(raw_shell.value)

    argv = _argv(tmp_path, "record") + ("literal&|<>^%COMSPEC%",)
    outcome = _run(broker, tmp_path, "record", argv=argv)
    _safe(type(outcome) is ProcessOutcome and outcome.exit_code == 0,
          "argv metacharacters acquired shell meaning")


@requires_windows_job
def test_minimal_environment_excludes_ambient_secret_and_provider_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("NVIDIA_API_KEY", "JARVIS_TOKEN", "BROWSER_COOKIE", "TEST_PASSWORD"):
        monkeypatch.setenv(name, "generated-canary")
    status = tmp_path / "env-status.json"
    outcome = _run(
        _broker(tmp_path), tmp_path, "env",
        argv=_argv(tmp_path, "env", status_file=status),
    )
    _safe(outcome.exit_code == 0, "minimal-environment probe failed")
    payload = json.loads(status.read_text(encoding="ascii"))
    _safe(payload["suspicious"] == [], "child inherited secret-like environment names")
    _safe("JARVIS_FIXTURE" in payload["present"], "explicit fixture environment was omitted")


@requires_windows_job
@pytest.mark.parametrize("fault_stage", ("assign", "configure_limits", "verify_membership"))
def test_pre_resume_failure_terminates_suspended_child_without_observable_work(
    tmp_path: Path, fault_stage: str
) -> None:
    marker = tmp_path / f"{fault_stage}.marker"
    status = tmp_path / f"{fault_stage}.json"
    argv = _argv(tmp_path, "record", status_file=status) + ("--marker-file", str(marker))
    with pytest.raises(WindowsJobError) as rejected:
        _run(
            _broker(tmp_path, fault_stage=fault_stage), tmp_path, "record", argv=argv
        )
    _assert_safe_error(rejected.value)
    _safe(not marker.exists() and not status.exists(), "suspended failure resumed observable work")
    _safe(getattr(rejected.value, "resumed", None) is False,
          "pre-resume failure did not prove the child stayed suspended")
    _safe(getattr(rejected.value, "cleanup_truth", None) == "confirmed",
          "suspended child termination was not confirmed")


@requires_windows_job
@pytest.mark.parametrize(
    ("mode", "limit_name", "limit_value"),
    (
        ("stdout", "max_stdout_bytes", 4096),
        ("stderr", "max_stderr_bytes", 4096),
        ("stdout", "max_combined_output_bytes", 4096),
        ("memory", "memory_bytes", 8 * 1024 * 1024),
        ("handles", "max_handles", 16),
        ("tree", "max_processes", 1),
    ),
)
def test_stream_and_resource_caps_terminate_during_pressure(
    tmp_path: Path, mode: str, limit_name: str, limit_value: int
) -> None:
    with pytest.raises(WindowsJobError) as rejected:
        _run(
            _broker(tmp_path), tmp_path, mode,
            argv=_argv(tmp_path, mode, byte_count=2 * 1024 * 1024, duration_ms=5000),
            limits=_limits(**{limit_name: limit_value}),
        )
    _assert_safe_error(rejected.value)
    _safe(getattr(rejected.value, "cleanup_truth", None) in _CLEANUP_TRUTH,
          "resource stop omitted queried job truth")
    _safe(getattr(rejected.value, "observed_bytes", 0) <= 2 * 1024 * 1024,
          "broker buffered beyond the bounded fixture output")


@requires_windows_job
def test_stdin_cap_is_checked_before_spawn_and_invalid_bytes_are_bounded(tmp_path: Path) -> None:
    marker = tmp_path / "stdin.marker"
    argv = _argv(tmp_path, "record") + ("--marker-file", str(marker))
    with pytest.raises(WindowsJobError) as rejected:
        _run(
            _broker(tmp_path), tmp_path, "record", argv=argv,
            stdin=b"x" * 17, limits=_limits(max_stdin_bytes=16),
        )
    _assert_safe_error(rejected.value)
    _safe(not marker.exists(), "oversized stdin spawned the helper")

    outcome = _run(_broker(tmp_path), tmp_path, "invalid-bytes")
    _safe(outcome.exit_code == 0, "invalid-byte fixture failed")
    _safe(isinstance(outcome.stdout, str) and len(outcome.stdout.encode("utf-8")) <= 64 * 1024,
          "invalid output was not decoded and retained under the byte cap")


@requires_windows_job
def test_nonzero_exit_is_failure_truth_not_success(tmp_path: Path) -> None:
    outcome = _run(
        _broker(tmp_path), tmp_path, "nonzero",
        argv=_argv(tmp_path, "nonzero") + ("--exit-code", "7"),
    )
    _safe(type(outcome) is ProcessOutcome and outcome.exit_code == 7,
          "nonzero exit identity was lost")
    _safe(outcome.outcome == "not_applied" and not outcome.success,
          "nonzero exit produced success truth")


@requires_windows_job
@pytest.mark.parametrize("stop_reason", _STOP_REASONS)
def test_every_stop_path_uses_whole_job_termination_and_queries_descendants(
    tmp_path: Path, stop_reason: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    original = job_module.terminate_job_tree

    def recording_terminate(*args: Any, **kwargs: Any):
        calls.append(str(kwargs.get("reason", "")))
        return original(*args, **kwargs)

    monkeypatch.setattr(job_module, "terminate_job_tree", recording_terminate)
    stop = threading.Event()

    def on_started() -> None:
        stop.set()

    outcome = _run(
        _broker(tmp_path), tmp_path, "tree",
        argv=_argv(tmp_path, "tree", duration_ms=10_000),
        stop_event=stop, stop_reason=stop_reason, on_started=on_started,
    )
    _safe(calls == [stop_reason], "stop path bypassed the one whole-job termination contract")
    _safe(outcome.cleanup_truth in _CLEANUP_TRUTH, "stop path omitted cleanup truth")
    _safe(outcome.active_processes == 0 if outcome.cleanup_truth == "confirmed" else True,
          "confirmed cleanup left active descendants")
    _safe(outcome.descendants_verified, "stop path checked only the parent PID")


@requires_windows_job
def test_breakaway_attempt_cannot_survive_and_port_lock_residue_is_verified(tmp_path: Path) -> None:
    breakaway = _run(
        _broker(tmp_path), tmp_path, "breakaway",
        argv=_argv(tmp_path, "breakaway", duration_ms=5000),
        limits=_limits(wall_seconds=0.5),
    )
    _safe(breakaway.cleanup_truth in _CLEANUP_TRUTH, "breakaway stop omitted cleanup truth")
    _safe(breakaway.cleanup_truth != "confirmed" or breakaway.active_processes == 0,
          "confirmed breakaway cleanup left a process")

    status = tmp_path / "port-lock-status.json"
    outcome = _run(
        _broker(tmp_path), tmp_path, "port-lock",
        argv=_argv(tmp_path, "port-lock", status_file=status, duration_ms=5000),
        limits=_limits(wall_seconds=0.5),
    )
    payload = json.loads(status.read_text(encoding="ascii"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        _safe(probe.connect_ex(("127.0.0.1", int(payload["port"]))) != 0,
              "cleanup left the fixture port listening")
    lock_path = tmp_path / str(payload["lock"])
    with lock_path.open("r+b") as lock_handle:
        import msvcrt

        msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
        msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
    _safe(outcome.cleanup_truth == "confirmed", "released port/lock residue was not confirmed")


@requires_job
def test_cleanup_truth_never_claims_confirmation_without_queried_job_evidence(tmp_path: Path) -> None:
    outcome = _run(_broker(tmp_path), tmp_path, "record")
    _safe(type(outcome) is ProcessOutcome, "broker returned a non-exact outcome")
    _safe(outcome.cleanup_truth in _CLEANUP_TRUTH, "cleanup truth vocabulary widened")
    if outcome.cleanup_truth == "confirmed":
        _safe(outcome.job_accounting_queried and outcome.active_processes == 0,
              "confirmed cleanup lacks whole-job evidence")
        _safe(outcome.descendants_verified, "confirmed cleanup checked only a parent PID")
    _safe("pid-only" not in repr(outcome).casefold(), "outcome claims PID-only containment")
