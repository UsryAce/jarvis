"""Windows DPAPI identity, ACL, and non-disclosure contracts."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="current-user DPAPI contracts require Windows"
)

secret_module = pytest.importorskip(
    "src.security.secrets", reason="Plan 01-04 has not landed"
)

CurrentUserDpapiProtector = secret_module.CurrentUserDpapiProtector
ProtectedPathAcl = secret_module.ProtectedPathAcl
SecretProtectionError = secret_module.SecretProtectionError

UI_FORBIDDEN = 0x1
LOCAL_MACHINE = 0x4
HELPER = Path(__file__).parent / "helpers" / "dpapi_user_probe.py"


def _safe(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message, pytrace=False)


def _generated_material() -> tuple[bytearray, bytearray]:
    return bytearray(secrets.token_bytes(48)), bytearray(secrets.token_bytes(32))


def _code(exc: BaseException) -> str | None:
    return getattr(exc, "code", None)


def test_same_user_round_trip_requires_matching_entropy() -> None:
    protector = CurrentUserDpapiProtector()
    plaintext, entropy = _generated_material()
    wrong_entropy = bytearray(secrets.token_bytes(len(entropy)))
    try:
        ciphertext = protector.protect(
            plaintext, purpose="credential", entropy=entropy
        )
        restored = protector.unprotect(
            ciphertext, purpose="credential", entropy=entropy
        )
        _safe(bytes(restored) == bytes(plaintext), "same-user DPAPI round trip failed")
        _safe(bytes(ciphertext) != bytes(plaintext), "DPAPI returned plaintext bytes")
        with pytest.raises(SecretProtectionError) as rejected:
            protector.unprotect(
                ciphertext, purpose="credential", entropy=wrong_entropy
            )
        _safe(
            _code(rejected.value)
            in {"ciphertext_invalid", "wrong_identity_or_profile"},
            "entropy mismatch did not produce a stable protection code",
        )
    finally:
        plaintext[:] = b"\x00" * len(plaintext)
        entropy[:] = b"\x00" * len(entropy)
        wrong_entropy[:] = b"\x00" * len(wrong_entropy)


def test_dpapi_sets_ui_forbidden_without_machine_scope(monkeypatch) -> None:
    calls: list[int] = []

    def fake_protect(data, description, entropy, reserved, prompt, flags):
        calls.append(flags)
        return description, b"opaque-test-ciphertext"

    monkeypatch.setattr(secret_module.win32crypt, "CryptProtectData", fake_protect)
    protector = CurrentUserDpapiProtector()
    plaintext, entropy = _generated_material()
    try:
        protector.protect(plaintext, purpose="credential", entropy=entropy)
    finally:
        plaintext[:] = b"\x00" * len(plaintext)
        entropy[:] = b"\x00" * len(entropy)
    _safe(len(calls) == 1, "DPAPI protection call count mismatch")
    _safe(bool(calls[0] & UI_FORBIDDEN), "DPAPI did not disable UI prompts")
    _safe(not calls[0] & LOCAL_MACHINE, "DPAPI enabled machine-scope protection")


def test_damaged_ciphertext_is_a_safe_failure_without_environment_fallback(
    monkeypatch,
) -> None:
    protector = CurrentUserDpapiProtector()
    plaintext, entropy = _generated_material()
    fallback = secrets.token_urlsafe(40)
    monkeypatch.setenv("NVIDIA_API_KEY", fallback)
    try:
        ciphertext = bytearray(
            protector.protect(plaintext, purpose="credential", entropy=entropy)
        )
        ciphertext[len(ciphertext) // 2] ^= 0x01
        with pytest.raises(SecretProtectionError) as rejected:
            protector.unprotect(
                ciphertext, purpose="credential", entropy=entropy
            )
        _safe(
            _code(rejected.value) == "ciphertext_invalid",
            "damaged ciphertext did not use ciphertext_invalid",
        )
        _safe(
            fallback not in str(rejected.value),
            "secret protection failure exposed fallback material",
        )
    finally:
        plaintext[:] = b"\x00" * len(plaintext)
        entropy[:] = b"\x00" * len(entropy)


def test_protected_store_and_backup_paths_have_expected_owner_and_restrictive_dacl(
    tmp_path: Path,
) -> None:
    trust_dir = tmp_path / "trust"
    backup_dir = tmp_path / "backups"
    trust_dir.mkdir()
    backup_dir.mkdir()
    database = trust_dir / "control.db"
    database.touch()

    acl = ProtectedPathAcl()
    expected_sid = acl.current_user_sid()
    for path in (trust_dir, database, backup_dir):
        acl.apply(path)
        result = acl.verify(path, expected_owner_sid=expected_sid)
        _safe(result.owner_sid == expected_sid, f"owner SID mismatch for {path.name}")
        _safe(result.owner_matches, f"owner preflight failed for {path.name}")
        _safe(result.restrictive, f"DACL is permissive for {path.name}")
        _safe(not result.broad_access, f"broad ACL entry remains for {path.name}")


def test_same_user_subprocess_probe_emits_only_safe_status(tmp_path: Path) -> None:
    plaintext, entropy = _generated_material()
    input_file = tmp_path / "input.bin"
    output_file = tmp_path / "output.bin"
    entropy_file = tmp_path / "entropy.bin"
    status_file = tmp_path / "status.json"
    sid_file = tmp_path / "owner.sid"
    acl = ProtectedPathAcl()
    try:
        input_file.write_bytes(plaintext)
        entropy_file.write_bytes(entropy)
        sid_file.write_text(acl.current_user_sid(), encoding="ascii")
        completed = subprocess.run(
            [
                sys.executable,
                str(HELPER),
                "protect",
                "--input-file",
                str(input_file),
                "--output-file",
                str(output_file),
                "--entropy-file",
                str(entropy_file),
                "--expected-sid-file",
                str(sid_file),
                "--status-file",
                str(status_file),
            ],
            cwd=Path(__file__).parents[1],
            capture_output=True,
            check=False,
        )
        _safe(completed.returncode == 0, "same-user DPAPI helper failed")
        _safe(not completed.stdout, "DPAPI helper wrote to stdout")
        _safe(not completed.stderr, "DPAPI helper wrote to stderr")
        status = json.loads(status_file.read_text(encoding="ascii"))
        _safe(status == {"code": "ok", "sid_relation": "equal"}, "unsafe probe status")
        _safe(output_file.read_bytes() != bytes(plaintext), "probe persisted plaintext output")
    finally:
        plaintext[:] = b"\x00" * len(plaintext)
        entropy[:] = b"\x00" * len(entropy)


def test_wrong_user_dpapi_release_gate_is_explicitly_pending_without_probe(
    tmp_path: Path,
) -> None:
    """A release run supplies a safe result file produced under a second SID."""

    result_path_value = os.environ.get("JARVIS_DPAPI_CROSS_SID_RESULT_FILE")
    if not result_path_value:
        pytest.xfail(
            "MANUAL RELEASE GATE PENDING: run dpapi_user_probe.py under a second Windows SID"
        )

    result_path = Path(result_path_value)
    result = json.loads(result_path.read_text(encoding="ascii"))
    _safe(result.get("sid_relation") == "different", "cross-SID probe used the owner SID")
    _safe(
        result.get("code") == "wrong_identity_or_profile",
        "different Windows SID was not denied by current-user DPAPI",
    )
