"""Safe subprocess probe for current-user DPAPI release drills.

The helper accepts secret-bearing material only through files.  It never writes
plaintext or ciphertext to stdout/stderr and records only a stable status code
and whether the process SID matches the expected owner SID.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


EXIT_OK = 0
EXIT_PROTECTION_FAILED = 20
EXIT_WRONG_IDENTITY = 21
EXIT_PROBE_FAILED = 22


class _QuietParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _parser() -> argparse.ArgumentParser:
    parser = _QuietParser(add_help=False)
    parser.add_argument("operation", choices=("protect", "unprotect", "sid"))
    parser.add_argument("--input-file", type=Path)
    parser.add_argument("--output-file", type=Path)
    parser.add_argument("--entropy-file", type=Path)
    parser.add_argument("--expected-sid-file", type=Path)
    parser.add_argument("--status-file", type=Path, required=True)
    return parser


def _current_sid() -> str:
    import win32api
    import win32security

    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32security.TOKEN_QUERY
    )
    sid, _attributes = win32security.GetTokenInformation(token, win32security.TokenUser)
    return win32security.ConvertSidToStringSid(sid)


def _sid_relation(expected_sid_file: Path | None, current_sid: str) -> str:
    if expected_sid_file is None:
        return "not_compared"
    expected = expected_sid_file.read_text(encoding="ascii").strip()
    return "equal" if expected == current_sid else "different"


def _write_status(path: Path, *, code: str, sid_relation: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"code": code, "sid_relation": sid_relation}
    path.write_text(json.dumps(payload, sort_keys=True), encoding="ascii")


def _require_file(path: Path | None, option: str) -> Path:
    if path is None:
        raise ValueError(f"{option} is required")
    return path


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    current_sid = _current_sid()
    relation = _sid_relation(args.expected_sid_file, current_sid)

    if args.operation == "sid":
        _write_status(args.status_file, code="ok", sid_relation=relation)
        return EXIT_OK

    input_file = _require_file(args.input_file, "--input-file")
    output_file = _require_file(args.output_file, "--output-file")
    entropy_file = _require_file(args.entropy_file, "--entropy-file")

    from src.security.secrets import CurrentUserDpapiProtector, SecretProtectionError

    protector = CurrentUserDpapiProtector()
    source = bytearray(input_file.read_bytes())
    entropy = bytearray(entropy_file.read_bytes())
    try:
        if args.operation == "protect":
            result = protector.protect(source, purpose="credential", entropy=entropy)
        else:
            result = protector.unprotect(source, purpose="credential", entropy=entropy)
        output_file.write_bytes(bytes(result))
    except SecretProtectionError as exc:
        code = getattr(exc, "code", "secret_protection_failed")
        safe_code = (
            code
            if code
            in {
                "wrong_identity_or_profile",
                "ciphertext_invalid",
                "protector_unavailable",
            }
            else "secret_protection_failed"
        )
        _write_status(args.status_file, code=safe_code, sid_relation=relation)
        if safe_code == "wrong_identity_or_profile":
            return EXIT_WRONG_IDENTITY
        return EXIT_PROTECTION_FAILED
    finally:
        source[:] = b"\x00" * len(source)
        entropy[:] = b"\x00" * len(entropy)

    _write_status(args.status_file, code="ok", sid_relation=relation)
    return EXIT_OK


def main() -> None:
    try:
        exit_code = run()
    except Exception:
        try:
            parsed, _unknown = _parser().parse_known_args()
            _write_status(
                parsed.status_file,
                code="probe_failed",
                sid_relation="not_compared",
            )
        except Exception:
            pass
        exit_code = EXIT_PROBE_FAILED
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
