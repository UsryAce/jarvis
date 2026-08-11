from __future__ import annotations

import io
import urllib.error

import pytest

from src.clients.credential_validation import validate_nvidia_credential


class _Response:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


@pytest.mark.parametrize(
    ("status", "expected"),
    [(200, "valid"), (401, "invalid_auth"), (403, "scope_forbidden"),
     (429, "rate_limited"), (503, "provider_unavailable")],
)
def test_nvidia_validator_maps_provider_status(status, expected):
    result = validate_nvidia_credential(
        provider="nvidia",
        secret=memoryview(b"nvapi-test"),
        correlation_id="test",
        opener=lambda *_args, **_kwargs: _Response(status),
    )

    assert result == expected


def test_nvidia_validator_maps_http_error_without_leaking_secret():
    def rejected(request, **_kwargs):
        raise urllib.error.HTTPError(request.full_url, 401, "denied", {}, io.BytesIO())

    result = validate_nvidia_credential(
        provider="nvidia",
        secret=memoryview(b"nvapi-secret-value"),
        correlation_id="test",
        opener=rejected,
    )

    assert result == "invalid_auth"
