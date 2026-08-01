"""Bounded, generated-path-only process fixture for Windows Job Object tests.

The helper can expose observable work, descendants, bounded output/resource
pressure, a loopback port and a file lock.  Every persistent artifact is beneath
one temporary root and every otherwise-unbounded mode has a hard local deadline.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


_MAX_DURATION_MS = 15_000
_MAX_OUTPUT_BYTES = 8 * 1024 * 1024
_MAX_MEMORY_BYTES = 64 * 1024 * 1024
_MAX_HANDLES = 256


class _QuietParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover
        del message
        raise ValueError("arguments_invalid")


def _parser() -> argparse.ArgumentParser:
    parser = _QuietParser(add_help=False)
    parser.add_argument(
        "mode",
        choices=(
            "record", "env", "tree", "grandchild", "breakaway", "stdout",
            "stderr", "invalid-bytes", "nonzero", "cpu", "memory", "handles",
            "port-lock", "stdin",
        ),
    )
    parser.add_argument("--root", required=True)
    parser.add_argument("--status-file", required=True)
    parser.add_argument("--marker-file")
    parser.add_argument("--duration-ms", type=int, default=3_000)
    parser.add_argument("--byte-count", type=int, default=65_536)
    parser.add_argument("--exit-code", type=int, default=7)
    return parser


def _lexical(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return path != root


def _validate(args: argparse.Namespace) -> tuple[Path, Path, Path | None]:
    root = _lexical(args.root)
    temp_root = _lexical(Path(os.environ.get("TEMP", Path.cwd())))
    if not root.is_dir() or not _inside(root, temp_root):
        raise ValueError("root_invalid")
    status = _lexical(args.status_file)
    marker = _lexical(args.marker_file) if args.marker_file else None
    if not _inside(status, root) or (marker is not None and not _inside(marker, root)):
        raise ValueError("path_outside_root")
    if not 1 <= args.duration_ms <= _MAX_DURATION_MS:
        raise ValueError("duration_invalid")
    if not 0 <= args.byte_count <= _MAX_OUTPUT_BYTES:
        raise ValueError("byte_count_invalid")
    if not 0 <= args.exit_code <= 255:
        raise ValueError("exit_code_invalid")
    return root, status, marker


def _status(path: Path, code: str, mode: str, **safe: object) -> None:
    payload = {"code": code, "mode": mode, **safe}
    path.write_text(json.dumps(payload, sort_keys=True), encoding="ascii")


def _sleep(duration_ms: int) -> None:
    time.sleep(duration_ms / 1000)


def _spawn_grandchild(root: Path, duration_ms: int, *, breakaway: bool = False):
    status = root / "grandchild-status.json"
    command = [
        sys.executable, str(Path(__file__).resolve()), "grandchild",
        "--root", str(root), "--status-file", str(status),
        "--duration-ms", str(duration_ms),
    ]
    flags = 0
    if breakaway and sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x01000000)
    return subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )


def run(argv: list[str] | None = None) -> int:
    mode = "invalid"
    status_path: Path | None = None
    try:
        args = _parser().parse_args(argv)
        mode = args.mode
        root, status_path, marker = _validate(args)
        if marker is not None:
            marker.write_text("work-observed", encoding="ascii")

        if mode == "record":
            _status(status_path, "ok", mode)
            return 0
        if mode == "env":
            allowed = ("JARVIS_FIXTURE", "SYSTEMROOT", "TEMP", "TMP", "WINDIR")
            present = sorted(name for name in allowed if name in os.environ)
            suspicious = sorted(
                name for name in os.environ
                if any(token in name.upper() for token in ("KEY", "TOKEN", "SECRET", "PASSWORD", "COOKIE"))
            )
            _status(status_path, "ok", mode, present=present, suspicious=suspicious)
            return 0
        if mode == "grandchild":
            _status(status_path, "ready", mode, pid=os.getpid())
            _sleep(args.duration_ms)
            return 0
        if mode in {"tree", "breakaway"}:
            try:
                child = _spawn_grandchild(root, args.duration_ms, breakaway=mode == "breakaway")
                _status(status_path, "ready", mode, pid=os.getpid(), child_pid=child.pid)
                _sleep(args.duration_ms)
                child.wait(timeout=max(1.0, args.duration_ms / 1000 + 1.0))
            except (OSError, subprocess.SubprocessError):
                _status(status_path, "breakaway_denied" if mode == "breakaway" else "spawn_failed", mode)
                _sleep(args.duration_ms)
            return 0
        if mode in {"stdout", "stderr"}:
            stream = sys.stdout.buffer if mode == "stdout" else sys.stderr.buffer
            remaining = args.byte_count
            chunk = b"J" * min(4096, max(1, remaining))
            while remaining:
                current = chunk[:remaining]
                stream.write(current)
                stream.flush()
                remaining -= len(current)
            _status(status_path, "ok", mode, bytes=args.byte_count)
            _sleep(args.duration_ms)
            return 0
        if mode == "invalid-bytes":
            sys.stdout.buffer.write(b"\xff\xfe\x80JARVIS\x00")
            sys.stdout.buffer.flush()
            _status(status_path, "ok", mode)
            return 0
        if mode == "nonzero":
            _status(status_path, "ok", mode)
            return args.exit_code
        if mode == "cpu":
            deadline = time.monotonic() + args.duration_ms / 1000
            value = 1
            while time.monotonic() < deadline:
                value = ((value * 1_103_515_245) + 12_345) & 0x7FFFFFFF
            _status(status_path, "ok", mode, bounded=True)
            return value & 0
        if mode == "memory":
            allocation = bytearray(min(args.byte_count, _MAX_MEMORY_BYTES))
            if allocation:
                allocation[0] = 1
                allocation[-1] = 1
            _status(status_path, "ready", mode, bytes=len(allocation))
            _sleep(args.duration_ms)
            return 0
        if mode == "handles":
            handles = []
            for index in range(min(args.byte_count, _MAX_HANDLES)):
                path = root / f"handle-{index:03d}.tmp"
                handles.append(path.open("w+b"))
            _status(status_path, "ready", mode, handles=len(handles))
            _sleep(args.duration_ms)
            for handle in handles:
                handle.close()
            return 0
        if mode == "port-lock":
            import msvcrt

            lock_path = root / "held.lock"
            lock_handle = lock_path.open("w+b")
            lock_handle.write(b"0")
            lock_handle.flush()
            lock_handle.seek(0)
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            _status(status_path, "ready", mode, port=server.getsockname()[1], lock="held.lock")
            _sleep(args.duration_ms)
            server.close()
            lock_handle.seek(0)
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
            lock_handle.close()
            return 0
        if mode == "stdin":
            received = sys.stdin.buffer.read(args.byte_count + 1)
            _status(status_path, "ok", mode, bytes=len(received))
            return 0
        raise ValueError("mode_invalid")
    except Exception:
        if status_path is not None:
            try:
                _status(status_path, "probe_failed", mode)
            except OSError:
                pass
        return 2


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
