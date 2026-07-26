"""Bounded provider credential probes used before activation."""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Callable

from src.config import config


def validate_nvidia_credential(
    *,
    provider: str,
    secret: memoryview,
    correlation_id: str,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> str:
    """Validate an NVIDIA key without retaining or returning secret material."""
    del correlation_id
    if str(provider).casefold() != "nvidia":
        return "indeterminate"

    key = bytes(secret).decode("utf-8")
    base_url = str(
        config.get("nvidia.api_base", "https://integrate.api.nvidia.com/v1")
    ).rstrip("/")
    request = urllib.request.Request(
        f"{base_url}/models",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with opener(request, timeout=10) as response:
            return _category(int(getattr(response, "status", 0)))
    except urllib.error.HTTPError as exc:
        return _category(int(exc.code))
    except (OSError, TimeoutError, urllib.error.URLError):
        return "indeterminate"
    except Exception:
        return "indeterminate"
    finally:
        key = ""


def _category(status: int) -> str:
    if 200 <= status < 300:
        return "valid"
    if status == 401:
        return "invalid_auth"
    if status == 403:
        return "scope_forbidden"
    if status == 429:
        return "rate_limited"
    if status in {500, 502, 503, 504}:
        return "provider_unavailable"
    return "indeterminate"


__all__ = ["validate_nvidia_credential"]
