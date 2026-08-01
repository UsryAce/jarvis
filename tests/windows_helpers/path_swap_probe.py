"""Safe Windows reparse/TOCTOU fixture with stable, content-free status.

Every accepted path must be generated beneath one caller-owned temporary anchor.
The helper never reads file contents and never includes a path or OS exception in
its status record.  It is test infrastructure, not a production filesystem path.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


class _QuietParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - argparse callback
        del message
        raise ValueError("arguments_invalid")


def _parser() -> argparse.ArgumentParser:
    parser = _QuietParser(add_help=False)
    parser.add_argument("operation", choices=("junction", "swap-parent"))
    parser.add_argument("--anchor", required=True)
    parser.add_argument("--link", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--backup")
    parser.add_argument("--armed-file")
    parser.add_argument("--trigger-file")
    parser.add_argument("--status-file", required=True)
    parser.add_argument("--timeout-ms", type=int, default=10_000)
    return parser


def _lexical(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _inside(path: Path, anchor: Path) -> bool:
    try:
        path.relative_to(anchor)
    except ValueError:
        return False
    return path != anchor


def _validated(args: argparse.Namespace) -> dict[str, Path]:
    anchor = _lexical(args.anchor)
    temp_root = _lexical(Path(os.environ.get("TEMP", Path.cwd())))
    if not anchor.is_dir() or not _inside(anchor, temp_root):
        raise ValueError("anchor_invalid")

    names = ("link", "target", "status_file", "backup", "armed_file", "trigger_file")
    paths: dict[str, Path] = {"anchor": anchor}
    for name in names:
        value = getattr(args, name)
        if value is None:
            continue
        path = _lexical(value)
        if not _inside(path, anchor):
            raise ValueError("path_outside_anchor")
        paths[name] = path
    if args.timeout_ms < 1 or args.timeout_ms > 30_000:
        raise ValueError("timeout_invalid")
    return paths


def _junction(link: Path, target: Path) -> None:
    if sys.platform != "win32":
        raise OSError("windows_required")
    if link.exists() or not target.is_dir():
        raise OSError("fixture_state_invalid")
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0 or not link.is_dir():
        raise OSError("junction_failed")


def _wait_for(path: Path, timeout_ms: int) -> None:
    deadline = time.monotonic() + (timeout_ms / 1000)
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("trigger_timeout")
        time.sleep(0.01)


def _write_status(path: Path, code: str, operation: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"code": code, "operation": operation}, sort_keys=True),
        encoding="ascii",
    )


def run(argv: list[str] | None = None) -> int:
    operation = "invalid"
    status: Path | None = None
    try:
        args = _parser().parse_args(argv)
        operation = args.operation
        raw_status = _lexical(args.status_file)
        paths = _validated(args)
        status = paths["status_file"]
        if operation == "junction":
            _junction(paths["link"], paths["target"])
        else:
            required = {"backup", "armed_file", "trigger_file"}
            if not required.issubset(paths):
                raise ValueError("arguments_invalid")
            if not paths["link"].is_dir() or paths["backup"].exists():
                raise OSError("fixture_state_invalid")
            paths["armed_file"].touch(exist_ok=False)
            _wait_for(paths["trigger_file"], args.timeout_ms)
            paths["link"].rename(paths["backup"])
            _junction(paths["link"], paths["target"])
        _write_status(status, "ok", operation)
        return 0
    except Exception:
        if status is None:
            try:
                status = raw_status
            except UnboundLocalError:
                status = None
        if status is not None:
            try:
                _write_status(status, "probe_failed", operation)
            except OSError:
                pass
        return 2


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
