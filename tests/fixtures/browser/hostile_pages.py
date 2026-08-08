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
