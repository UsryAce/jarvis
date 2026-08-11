"""Transport evidence contracts for the dashboard capability projection."""

from types import SimpleNamespace
from unittest.mock import patch

from src.api.ui_routes import _request_transport


def _request(*, url_scheme: str, scope_scheme: str, forwarded: str = "", peer: str = "203.0.113.8"):
    headers = {"x-forwarded-proto": forwarded} if forwarded else {}
    return SimpleNamespace(
        headers=headers,
        url=SimpleNamespace(scheme=url_scheme),
        client=SimpleNamespace(host=peer),
        scope={"scheme": scope_scheme},
    )


def test_uvicorn_https_scope_is_direct_transport_evidence_without_tls_extension() -> None:
    secure, indicated, observed = _request_transport(_request(
        url_scheme="https", scope_scheme="https",
    ))

    assert secure is True
    assert indicated is True
    assert observed == "https;direct_tls=true"


def test_url_scheme_without_matching_asgi_transport_scope_is_not_verified() -> None:
    secure, indicated, observed = _request_transport(_request(
        url_scheme="https", scope_scheme="http",
    ))

    assert secure is False
    assert indicated is True
    assert observed == "https"


def test_arbitrary_forwarded_https_never_substitutes_for_direct_tls() -> None:
    request = _request(
        url_scheme="https", scope_scheme="https", forwarded="https",
    )
    with patch("src.api.ui_routes.config.get", return_value=["127.0.0.1"]):
        secure, indicated, observed = _request_transport(request)

    assert secure is False
    assert indicated is True
    assert observed == "https;forwarded=https;untrusted"


def test_forwarded_https_is_verified_only_for_an_explicit_trusted_peer() -> None:
    request = _request(
        url_scheme="http", scope_scheme="http", forwarded="https", peer="127.0.0.1",
    )
    with patch("src.api.ui_routes.config.get", return_value=["127.0.0.1"]):
        secure, indicated, observed = _request_transport(request)

    assert secure is True
    assert indicated is True
    assert observed == "http;trusted_proxy=https"
