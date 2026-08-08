"""Offline browser pages that exercise every governed request channel.

These fixtures are inert strings.  Importing this module never opens a socket,
starts a browser, or writes outside a pytest-owned temporary directory.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HostilePage:
    """One deterministic page and the browser channels it attempts to use."""

    safe_id: str
    html: str
    channels: tuple[str, ...]


@dataclass(frozen=True)
class HostileDownload:
    """One bounded offline stream and the checks it is meant to exercise."""

    safe_id: str
    filename: str
    chunks: tuple[bytes, ...]
    declared_type: str
    detected_type: str
    decompressed_size: int
    elapsed_ms: int
    complete: bool
    scanner_verdict: str
    should_promote: bool = False


REDIRECT_CHAIN = (
    "https://allowed.example/start",
    "https://redirect.example/next",
    "http://169.254.169.254/latest/meta-data",
)

EVERY_REQUEST_CHANNELS = (
    "top_level",
    "redirect",
    "iframe",
    "popup",
    "image",
    "script",
    "fetch",
    "websocket",
    "service_worker",
)

SUBRESOURCE_PAGE = HostilePage(
    safe_id="subresource-fanout",
    channels=("iframe", "image", "script", "fetch", "websocket", "service_worker"),
    html="""<!doctype html>
<meta charset="utf-8">
<iframe src="http://127.0.0.1/private-frame"></iframe>
<img src="http://169.254.169.254/latest/meta-data/identity-credentials/">
<script src="http://[::1]/private-script.js"></script>
<script>
fetch("http://10.0.0.1/private-fetch");
new WebSocket("ws://192.168.1.1/private-socket");
navigator.serviceWorker.register("/hostile-worker.js");
</script>
""",
)

POPUP_PAGE = HostilePage(
    safe_id="popup-fanout",
    channels=("popup",),
    html="""<!doctype html>
<button id="open" onclick="window.open('http://127.0.0.1/private-popup')">
open
</button>
""",
)

REDIRECT_PAGE = HostilePage(
    safe_id="redirect-to-metadata",
    channels=("redirect",),
    html="""<!doctype html><meta http-equiv="refresh"
content="0;url=http://169.254.169.254/latest/meta-data">""",
)

SERVICE_WORKER_SCRIPT = """
self.addEventListener('fetch', event => {
  event.respondWith(fetch('http://127.0.0.1/service-worker-bypass'));
});
""".strip()


DOWNLOAD_CASES = (
    HostileDownload(
        safe_id="oversized",
        filename="large.bin",
        chunks=(b"x" * 65,),
        declared_type="application/octet-stream",
        detected_type="application/octet-stream",
        decompressed_size=65,
        elapsed_ms=10,
        complete=True,
        scanner_verdict="clean",
    ),
    HostileDownload(
        safe_id="chunked-over-limit",
        filename="chunks.bin",
        chunks=(b"a" * 24, b"b" * 24, b"c" * 24),
        declared_type="application/octet-stream",
        detected_type="application/octet-stream",
        decompressed_size=72,
        elapsed_ms=10,
        complete=True,
        scanner_verdict="clean",
    ),
    HostileDownload(
        safe_id="compressed-bomb",
        filename="archive.txt.gz",
        chunks=(b"bounded-compressed-fixture",),
        declared_type="application/gzip",
        detected_type="application/gzip",
        decompressed_size=4096,
        elapsed_ms=10,
        complete=True,
        scanner_verdict="clean",
    ),
    HostileDownload(
        safe_id="partial-response",
        filename="partial.txt",
        chunks=(b"partial",),
        declared_type="text/plain",
        detected_type="text/plain",
        decompressed_size=7,
        elapsed_ms=10,
        complete=False,
        scanner_verdict="clean",
    ),
    HostileDownload(
        safe_id="mime-mismatch",
        filename="report.pdf",
        chunks=(b"not-a-pdf",),
        declared_type="application/pdf",
        detected_type="text/plain",
        decompressed_size=9,
        elapsed_ms=10,
        complete=True,
        scanner_verdict="clean",
    ),
    HostileDownload(
        safe_id="traversal-name",
        filename="..\\outside.exe",
        chunks=(b"bounded",),
        declared_type="application/octet-stream",
        detected_type="application/octet-stream",
        decompressed_size=7,
        elapsed_ms=10,
        complete=True,
        scanner_verdict="clean",
    ),
    HostileDownload(
        safe_id="device-name",
        filename="CON.txt",
        chunks=(b"bounded",),
        declared_type="text/plain",
        detected_type="text/plain",
        decompressed_size=7,
        elapsed_ms=10,
        complete=True,
        scanner_verdict="clean",
    ),
    HostileDownload(
        safe_id="timeout",
        filename="slow.txt",
        chunks=(b"bounded",),
        declared_type="text/plain",
        detected_type="text/plain",
        decompressed_size=7,
        elapsed_ms=1001,
        complete=True,
        scanner_verdict="clean",
    ),
    HostileDownload(
        safe_id="malicious-scan",
        filename="payload.bin",
        chunks=(b"bounded-malicious-fixture",),
        declared_type="application/octet-stream",
        detected_type="application/octet-stream",
        decompressed_size=25,
        elapsed_ms=10,
        complete=True,
        scanner_verdict="malicious",
    ),
    HostileDownload(
        safe_id="clean-promotion",
        filename="report.txt",
        chunks=(b"bounded ", b"clean fixture"),
        declared_type="text/plain",
        detected_type="text/plain",
        decompressed_size=21,
        elapsed_ms=10,
        complete=True,
        scanner_verdict="clean",
        should_promote=True,
    ),
)


def hostile_pages() -> tuple[HostilePage, ...]:
    """Return immutable pages without consulting the host environment."""

    return (REDIRECT_PAGE, SUBRESOURCE_PAGE, POPUP_PAGE)


def observed_channels() -> frozenset[str]:
    """Return the complete channel inventory represented by the pages."""

    return frozenset(
        channel
        for page in hostile_pages()
        for channel in page.channels
    ) | {"top_level"}


def download_cases() -> tuple[HostileDownload, ...]:
    """Return every bounded download case without network or browser access."""

    return DOWNLOAD_CASES
