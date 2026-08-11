"""Windows-only secret protection and protected-path ACL primitives.

This module is deliberately free of configured protector instances and secret
state.  Callers provide plaintext and independent entropy for each operation.
"""

from __future__ import annotations

import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import ntsecuritycon
import pywintypes
import win32api
import win32con
import win32crypt
import win32security


_CRYPTPROTECT_UI_FORBIDDEN = 0x1
_ENVELOPE_MAGIC = b"JDP1"
_DESCRIPTION = "Jarvis current-user protected secret"
_SAFE_CODES = frozenset(
    {"wrong_identity_or_profile", "ciphertext_invalid", "protector_unavailable"}
)


class SecretProtectionError(RuntimeError):
    """A stable, non-secret secret-protection failure."""

    def __init__(self, code: str) -> None:
        safe_code = code if code in _SAFE_CODES else "protector_unavailable"
        self.code = safe_code
        super().__init__(safe_code)


@runtime_checkable
class SecretProtector(Protocol):
    """Byte-oriented interface for replaceable secret protectors."""

    def protect(
        self,
        plaintext: bytes | bytearray | memoryview,
        *,
        purpose: str,
        entropy: bytes | bytearray | memoryview,
    ) -> bytearray:
        """Protect plaintext for the current Windows identity."""

    def unprotect(
        self,
        ciphertext: bytes | bytearray | memoryview,
        *,
        purpose: str,
        entropy: bytes | bytearray | memoryview,
    ) -> bytearray:
        """Recover plaintext for the current Windows identity."""


def _owned_buffer(value: bytes | bytearray | memoryview, *, code: str) -> bytearray:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise SecretProtectionError(code)
    try:
        return bytearray(value)
    except (BufferError, TypeError, ValueError):
        raise SecretProtectionError(code) from None


def _zero(buffer: bytearray) -> None:
    buffer[:] = b"\x00" * len(buffer)


def _validate_purpose(purpose: str) -> None:
    if not isinstance(purpose, str) or not purpose or len(purpose) > 64:
        raise SecretProtectionError("ciphertext_invalid")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in purpose):
        raise SecretProtectionError("ciphertext_invalid")


class CurrentUserDpapiProtector:
    """Protect secrets with current-user DPAPI and UI prompts disabled."""

    def protect(
        self,
        plaintext: bytes | bytearray | memoryview,
        *,
        purpose: str,
        entropy: bytes | bytearray | memoryview,
    ) -> bytearray:
        _validate_purpose(purpose)
        owned_plaintext = _owned_buffer(plaintext, code="protector_unavailable")
        owned_entropy = _owned_buffer(entropy, code="protector_unavailable")
        try:
            if not owned_entropy:
                raise SecretProtectionError("protector_unavailable")
            owner_sid = ProtectedPathAcl.current_user_sid().encode("ascii")
            protected = win32crypt.CryptProtectData(
                owned_plaintext,
                _DESCRIPTION,
                owned_entropy,
                None,
                None,
                _CRYPTPROTECT_UI_FORBIDDEN,
            )
            # pywin32 312 returns bytes.  Accept the legacy tuple shape as well
            # so the adapter remains straightforward to fault-inject in tests.
            if isinstance(protected, tuple):
                protected = protected[-1]
            protected_bytes = bytearray(protected)
            try:
                if len(owner_sid) > 0xFFFF:
                    raise SecretProtectionError("protector_unavailable")
                return bytearray(
                    _ENVELOPE_MAGIC
                    + struct.pack(">H", len(owner_sid))
                    + owner_sid
                    + protected_bytes
                )
            finally:
                _zero(protected_bytes)
        except SecretProtectionError:
            raise
        except (ImportError, AttributeError):
            raise SecretProtectionError("protector_unavailable") from None
        except (pywintypes.error, OSError, TypeError, ValueError):
            raise SecretProtectionError("protector_unavailable") from None
        finally:
            _zero(owned_plaintext)
            _zero(owned_entropy)

    def unprotect(
        self,
        ciphertext: bytes | bytearray | memoryview,
        *,
        purpose: str,
        entropy: bytes | bytearray | memoryview,
    ) -> bytearray:
        _validate_purpose(purpose)
        owned_ciphertext = _owned_buffer(ciphertext, code="ciphertext_invalid")
        owned_entropy = _owned_buffer(entropy, code="ciphertext_invalid")
        protected_payload = bytearray()
        try:
            if not owned_entropy:
                raise SecretProtectionError("ciphertext_invalid")
            owner_sid, protected_payload = self._parse_envelope(owned_ciphertext)
            if owner_sid != ProtectedPathAcl.current_user_sid():
                raise SecretProtectionError("wrong_identity_or_profile")
            try:
                unprotected = win32crypt.CryptUnprotectData(
                    protected_payload,
                    owned_entropy,
                    None,
                    None,
                    _CRYPTPROTECT_UI_FORBIDDEN,
                )
            except pywintypes.error as exc:
                # DPAPI reports invalid data for damaged blobs.  Access/profile
                # failures are identity failures; neither path exposes OS text.
                code = getattr(exc, "winerror", None)
                stable = (
                    "wrong_identity_or_profile"
                    if code in {5, 1312, 1326}
                    else "ciphertext_invalid"
                )
                raise SecretProtectionError(stable) from None
            if isinstance(unprotected, tuple):
                unprotected = unprotected[-1]
            return bytearray(unprotected)
        except SecretProtectionError:
            raise
        except (ImportError, AttributeError):
            raise SecretProtectionError("protector_unavailable") from None
        except (OSError, TypeError, ValueError, struct.error):
            raise SecretProtectionError("ciphertext_invalid") from None
        finally:
            _zero(owned_ciphertext)
            _zero(owned_entropy)
            _zero(protected_payload)

    @staticmethod
    def _parse_envelope(ciphertext: bytearray) -> tuple[str, bytearray]:
        if len(ciphertext) < len(_ENVELOPE_MAGIC) + 2:
            raise SecretProtectionError("ciphertext_invalid")
        if ciphertext[: len(_ENVELOPE_MAGIC)] != _ENVELOPE_MAGIC:
            raise SecretProtectionError("ciphertext_invalid")
        sid_length = struct.unpack(
            ">H", ciphertext[len(_ENVELOPE_MAGIC) : len(_ENVELOPE_MAGIC) + 2]
        )[0]
        sid_start = len(_ENVELOPE_MAGIC) + 2
        sid_end = sid_start + sid_length
        if sid_length == 0 or sid_end >= len(ciphertext):
            raise SecretProtectionError("ciphertext_invalid")
        try:
            owner_sid = bytes(ciphertext[sid_start:sid_end]).decode("ascii")
            win32security.ConvertStringSidToSid(owner_sid)
        except (UnicodeDecodeError, pywintypes.error):
            raise SecretProtectionError("ciphertext_invalid") from None
        return owner_sid, bytearray(ciphertext[sid_end:])


@dataclass(frozen=True)
class ProtectedPathAclResult:
    """Non-secret ACL preflight metadata."""

    owner_sid: str
    owner_matches: bool
    restrictive: bool
    broad_access: bool


class ProtectedPathAcl:
    """Apply and verify a protected NTFS DACL for trust data and backups."""

    @staticmethod
    def current_user_sid() -> str:
        try:
            token = win32security.OpenProcessToken(
                win32api.GetCurrentProcess(), win32security.TOKEN_QUERY
            )
            sid, _attributes = win32security.GetTokenInformation(
                token, win32security.TokenUser
            )
            return win32security.ConvertSidToStringSid(sid)
        except (pywintypes.error, AttributeError):
            raise SecretProtectionError("protector_unavailable") from None

    def apply(self, path: str | os.PathLike[str]) -> None:
        protected_path = self._validated_path(path)
        current_sid = win32security.ConvertStringSidToSid(self.current_user_sid())
        system_sid = win32security.CreateWellKnownSid(
            win32security.WinLocalSystemSid, None
        )
        administrators_sid = win32security.CreateWellKnownSid(
            win32security.WinBuiltinAdministratorsSid, None
        )
        ace_flags = 0
        if protected_path.is_dir():
            ace_flags = win32con.OBJECT_INHERIT_ACE | win32con.CONTAINER_INHERIT_ACE

        dacl = win32security.ACL()
        for sid in (current_sid, system_sid, administrators_sid):
            dacl.AddAccessAllowedAceEx(
                win32security.ACL_REVISION_DS,
                ace_flags,
                ntsecuritycon.FILE_ALL_ACCESS,
                sid,
            )
        try:
            win32security.SetNamedSecurityInfo(
                str(protected_path),
                win32security.SE_FILE_OBJECT,
                win32security.OWNER_SECURITY_INFORMATION
                | win32security.DACL_SECURITY_INFORMATION
                | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
                current_sid,
                None,
                dacl,
                None,
            )
        except (pywintypes.error, OSError):
            raise SecretProtectionError("protector_unavailable") from None

    def verify(
        self,
        path: str | os.PathLike[str],
        *,
        expected_owner_sid: str | None = None,
    ) -> ProtectedPathAclResult:
        protected_path = self._validated_path(path)
        expected = expected_owner_sid or self.current_user_sid()
        try:
            win32security.ConvertStringSidToSid(expected)
            descriptor = win32security.GetNamedSecurityInfo(
                str(protected_path),
                win32security.SE_FILE_OBJECT,
                win32security.OWNER_SECURITY_INFORMATION
                | win32security.DACL_SECURITY_INFORMATION,
            )
            owner = descriptor.GetSecurityDescriptorOwner()
            dacl = descriptor.GetSecurityDescriptorDacl()
            if owner is None or dacl is None or not dacl.IsValid():
                raise SecretProtectionError("protector_unavailable")
            owner_sid = win32security.ConvertSidToStringSid(owner)
            current_sid = self.current_user_sid()
            allowed_sids = {
                current_sid,
                win32security.ConvertSidToStringSid(
                    win32security.CreateWellKnownSid(
                        win32security.WinLocalSystemSid, None
                    )
                ),
                win32security.ConvertSidToStringSid(
                    win32security.CreateWellKnownSid(
                        win32security.WinBuiltinAdministratorsSid, None
                    )
                ),
            }
            present_allowed: set[str] = set()
            broad_access = False
            valid_allow_entries = True
            for index in range(dacl.GetAceCount()):
                ace = dacl.GetAce(index)
                ace_type = ace[0][0]
                sid = ace[-1]
                sid_string = win32security.ConvertSidToStringSid(sid)
                if ace_type == win32security.ACCESS_ALLOWED_ACE_TYPE:
                    if sid_string not in allowed_sids:
                        broad_access = True
                    else:
                        present_allowed.add(sid_string)
                else:
                    valid_allow_entries = False
            owner_matches = owner_sid == expected == current_sid
            restrictive = (
                owner_matches
                and not broad_access
                and valid_allow_entries
                and present_allowed == allowed_sids
            )
            return ProtectedPathAclResult(
                owner_sid=owner_sid,
                owner_matches=owner_matches,
                restrictive=restrictive,
                broad_access=broad_access,
            )
        except SecretProtectionError:
            raise
        except (pywintypes.error, OSError, TypeError, ValueError):
            raise SecretProtectionError("protector_unavailable") from None

    @staticmethod
    def _validated_path(path: str | os.PathLike[str]) -> Path:
        if sys.platform != "win32":
            raise SecretProtectionError("protector_unavailable")
        try:
            protected_path = Path(path).resolve(strict=True)
            drive, _tail = os.path.splitdrive(str(protected_path))
            if not drive:
                raise SecretProtectionError("protector_unavailable")
            volume_root = drive + os.sep
            filesystem_name = win32api.GetVolumeInformation(volume_root)[-1]
        except SecretProtectionError:
            raise
        except (OSError, TypeError, ValueError, pywintypes.error):
            raise SecretProtectionError("protector_unavailable") from None
        if str(filesystem_name).upper() != "NTFS":
            raise SecretProtectionError("protector_unavailable")
        return protected_path


__all__ = [
    "CurrentUserDpapiProtector",
    "ProtectedPathAcl",
    "ProtectedPathAclResult",
    "SecretProtectionError",
    "SecretProtector",
]
