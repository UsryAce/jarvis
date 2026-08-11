"""Deterministic resolver, peer, transport, and scanner browser doubles."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from tests.fixtures.browser.hostile_pages import HostileDownload


PUBLIC_V4 = "93.184.216.34"
PUBLIC_V6 = "2606:2800:220:1:248:1893:25c8:1946"


@dataclass(frozen=True)
class ResolutionObservation:
    host: str
    port: int
    answers: tuple[str, ...]


@dataclass
class FakeResolver:
    """Return scripted A/AAAA sets and expose exactly when resolution occurred."""

    scripted_answers: dict[str, tuple[tuple[str, ...], ...]]
    calls: list[tuple[str, int]] = field(default_factory=list)

    def resolve_all(self, host: str, port: int) -> ResolutionObservation:
        self.calls.append((host, port))
        sequences = self.scripted_answers.get(host)
        if not sequences:
            return ResolutionObservation(host=host, port=port, answers=())
        index = min(self.calls.count((host, port)) - 1, len(sequences) - 1)
        return ResolutionObservation(host=host, port=port, answers=sequences[index])


@dataclass(frozen=True)
class PeerObservation:
    selected_ip: str
    connected_ip: str | None
    original_host: str
    sni_host: str
    certificate_checked: bool

    @property
    def peer_proven(self) -> bool:
        return (
            self.connected_ip is not None
            and self.connected_ip == self.selected_ip
            and self.original_host == self.sni_host
            and self.certificate_checked
        )


@dataclass
class FakeConnector:
    """Connect only to the selected literal IP; never performs DNS itself."""

    connected_ip: str | None = None
    certificate_checked: bool = True
    calls: list[tuple[str, int, str]] = field(default_factory=list)

    def connect_selected(
        self,
        *,
        selected_ip: str,
        port: int,
        original_host: str,
    ) -> PeerObservation:
        self.calls.append((selected_ip, port, original_host))
        return PeerObservation(
            selected_ip=selected_ip,
            connected_ip=self.connected_ip,
            original_host=original_host,
            sni_host=original_host,
            certificate_checked=self.certificate_checked,
        )


@dataclass
class FakeRouteCallback:
    """A browser route hook that intentionally has no socket-peer authority."""

    observed_urls: list[str] = field(default_factory=list)

    def observe(self, url: str) -> None:
        self.observed_urls.append(url)

    @property
    def peer_proven(self) -> bool:
        return False


@dataclass
class FakeScanner:
    """Return one deterministic verdict and record only safe fixture IDs."""

    verdict: str = "clean"
    calls: list[str] = field(default_factory=list)

    def scan(self, path: Path, *, safe_id: str) -> str:
        del path
        self.calls.append(safe_id)
        return self.verdict


@dataclass(frozen=True)
class FakeDownloadEvidence:
    safe_id: str
    sha256: str
    size: int
    media_type: str
    reference: str
    promoted: bool
    cleanup_truth: str
    code: str

    def receipt(self) -> dict[str, str | int]:
        """Project content-free, bounded metadata for durable evidence."""

        return {
            "safe_id": self.safe_id,
            "sha256": self.sha256,
            "size": self.size,
            "media_type": self.media_type,
            "reference": self.reference,
        }


class FakeQuarantinePipeline:
    """Offline contract double for stream, scan, promotion, and cleanup ordering."""

    _DEVICE_NAMES = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }

    def __init__(
        self,
        *,
        quarantine_root: Path,
        artifact_root: Path,
        scanner: FakeScanner,
        compressed_limit: int = 64,
        decompressed_limit: int = 128,
        timeout_ms: int = 1000,
    ) -> None:
        self.quarantine_root = quarantine_root
        self.artifact_root = artifact_root
        self.scanner = scanner
        self.compressed_limit = compressed_limit
        self.decompressed_limit = decompressed_limit
        self.timeout_ms = timeout_ms
        self.auto_opened: list[Path] = []

    @classmethod
    def _valid_filename(cls, filename: str) -> bool:
        if not filename or filename in {".", ".."}:
            return False
        if any(separator in filename for separator in ("/", "\\", ":")):
            return False
        stem = filename.rstrip(". ").split(".", 1)[0].upper()
        return stem not in cls._DEVICE_NAMES and filename == filename.rstrip(". ")

    def _reject(
        self,
        case: HostileDownload,
        code: str,
        quarantine_path: Path | None,
        *,
        digest: str = "",
        size: int = 0,
    ) -> FakeDownloadEvidence:
        if quarantine_path is not None:
            quarantine_path.unlink(missing_ok=True)
        residue = quarantine_path is not None and quarantine_path.exists()
        return FakeDownloadEvidence(
            safe_id=case.safe_id,
            sha256=digest,
            size=size,
            media_type=case.detected_type,
            reference="artifact:redacted",
            promoted=False,
            cleanup_truth="partial" if residue else "confirmed",
            code=code,
        )

    def process(self, case: HostileDownload) -> FakeDownloadEvidence:
        if not self._valid_filename(case.filename):
            return self._reject(case, "unsafe_filename", None)
        if case.elapsed_ms > self.timeout_ms:
            return self._reject(case, "download_timeout", None)

        self.quarantine_root.mkdir(parents=True, exist_ok=True)
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        quarantine_path = self.quarantine_root / f"{case.safe_id}.part"
        digest = hashlib.sha256()
        size = 0
        with quarantine_path.open("xb") as stream:
            for chunk in case.chunks:
                size += len(chunk)
                if size > self.compressed_limit:
                    stream.close()
                    return self._reject(
                        case, "compressed_limit", quarantine_path,
                        digest=digest.hexdigest(), size=size,
                    )
                digest.update(chunk)
                stream.write(chunk)

        hexdigest = digest.hexdigest()
        if not case.complete:
            return self._reject(
                case, "partial_response", quarantine_path,
                digest=hexdigest, size=size,
            )
        if case.decompressed_size > self.decompressed_limit:
            return self._reject(
                case, "decompressed_limit", quarantine_path,
                digest=hexdigest, size=size,
            )
        if case.declared_type != case.detected_type:
            return self._reject(
                case, "type_mismatch", quarantine_path,
                digest=hexdigest, size=size,
            )
        if self.scanner.scan(quarantine_path, safe_id=case.safe_id) != "clean":
            return self._reject(
                case, "scanner_rejected", quarantine_path,
                digest=hexdigest, size=size,
            )

        promoted_path = self.artifact_root / case.filename
        quarantine_path.replace(promoted_path)
        return FakeDownloadEvidence(
            safe_id=case.safe_id,
            sha256=hexdigest,
            size=size,
            media_type=case.detected_type,
            reference=f"artifact:{case.safe_id}",
            promoted=True,
            cleanup_truth="confirmed",
            code="clean_promoted",
        )


@dataclass(frozen=True)
class FakeArtifactEvidence:
    safe_id: str
    sha256: str
    size: int
    media_type: str
    reference: str

    def receipt(self) -> dict[str, str | int]:
        return {
            "safe_id": self.safe_id,
            "sha256": self.sha256,
            "size": self.size,
            "media_type": self.media_type,
            "reference": self.reference,
        }


@dataclass
class FakeArtifactStore:
    """Bound and redact browser artifacts before any in-memory persistence."""

    max_bytes: int = 128
    persisted: dict[str, bytes] = field(default_factory=dict)

    def capture(
        self,
        *,
        safe_id: str,
        media_type: str,
        payload: bytes,
        canary: bytes,
    ) -> FakeArtifactEvidence:
        if len(payload) > self.max_bytes:
            raise ValueError("artifact_limit")
        redacted = payload.replace(canary, b"[REDACTED]") if canary else payload
        if len(redacted) > self.max_bytes:
            raise ValueError("artifact_limit")
        self.persisted[safe_id] = redacted
        return FakeArtifactEvidence(
            safe_id=safe_id,
            sha256=hashlib.sha256(redacted).hexdigest(),
            size=len(redacted),
            media_type=media_type,
            reference=f"artifact:{safe_id}",
        )


@dataclass(frozen=True)
class FakeCleanupProbe:
    """Report cleanup honestly across each browser-owned residue class."""

    profile: bool = False
    download: bool = False
    file: bool = False
    port: bool = False
    process: bool = False
    state: bool = False
    proof_available: bool = True

    @property
    def truth(self) -> str:
        if not self.proof_available:
            return "unconfirmed"
        if any((self.profile, self.download, self.file, self.port, self.process, self.state)):
            return "partial"
        return "confirmed"


def resolver_with_answers(host: str, *answer_sets: Iterable[str]) -> FakeResolver:
    """Build a resolver whose answer may change on later connections."""

    return FakeResolver(
        scripted_answers={host: tuple(tuple(answers) for answers in answer_sets)}
    )
