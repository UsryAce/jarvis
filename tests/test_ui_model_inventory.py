"""Honest model inventory contracts for the Claude dashboard adapter."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.api import server as api_server
from src.api.ui_routes import _capability_projection, _model_inventory
from src.core.model_router import PRIMARY_MODEL


def _by_id(rows):
    return {row["id"]: row for row in rows}


def test_configured_models_remain_visible_when_runtime_is_held() -> None:
    rows = _by_id(_model_inventory(SimpleNamespace(_model_catalog=set()), PRIMARY_MODEL))

    assert PRIMARY_MODEL in rows
    assert "moonshotai/kimi-k2.6" in rows
    assert "nvidia/nemotron-3-ultra-550b-a55b" in rows
    assert rows[PRIMARY_MODEL]["health"] == "unknown"
    assert rows[PRIMARY_MODEL]["selectable"] is False
    assert rows["moonshotai/kimi-k2.6"]["catalogSource"] == "configured"


def test_only_live_chat_compatible_models_are_selectable() -> None:
    live = {
        PRIMARY_MODEL,
        "moonshotai/kimi-k2.6",
        "nvidia/nv-embedqa-e5-v5",
    }
    rows = _by_id(_model_inventory(SimpleNamespace(
        _model_catalog=live,
        _model_catalog_cached_at=time.monotonic(),
    ), PRIMARY_MODEL))

    assert rows[PRIMARY_MODEL]["selectable"] is True
    assert rows[PRIMARY_MODEL]["health"] == "unknown"
    assert rows[PRIMARY_MODEL]["capabilityState"] == "available"
    assert rows["moonshotai/kimi-k2.6"]["selectable"] is True
    assert rows["moonshotai/kimi-k2.6"]["health"] == "unknown"
    assert rows["nvidia/nv-embedqa-e5-v5"]["selectable"] is False
    assert rows["nvidia/nv-embedqa-e5-v5"]["catalogSource"] == "live"


def test_failure_cooldown_is_negative_evidence_without_inventing_latency() -> None:
    jarvis = SimpleNamespace(
        _model_catalog={PRIMARY_MODEL},
        _model_catalog_cached_at=time.monotonic(),
        _model_disabled_until={PRIMARY_MODEL: float("inf")},
    )
    rows = _by_id(_model_inventory(jarvis, PRIMARY_MODEL))

    assert rows[PRIMARY_MODEL]["selectable"] is True
    assert rows[PRIMARY_MODEL]["health"] == "degraded"
    assert rows[PRIMARY_MODEL]["capabilityState"] == "degraded"
    assert rows[PRIMARY_MODEL]["latencyMs"] == 0
    assert rows[PRIMARY_MODEL]["evidenceSource"] == "model.cooldown"


def test_stale_catalog_remains_visible_but_is_not_live_or_selectable() -> None:
    jarvis = SimpleNamespace(
        _model_catalog={PRIMARY_MODEL, "vendor/historical-chat-model"},
        _model_catalog_cached_at=time.monotonic() - 301.0,
        _model_disabled_until={},
    )

    rows = _by_id(_model_inventory(jarvis, PRIMARY_MODEL))

    for model_id in (PRIMARY_MODEL, "vendor/historical-chat-model"):
        assert rows[model_id]["selectable"] is False
        assert rows[model_id]["catalogSource"] == "stale_cache"
        assert rows[model_id]["catalogFresh"] is False
        assert rows[model_id]["catalogAgeSeconds"] >= 301.0
        assert rows[model_id]["evidenceSource"] == "nvidia.model_catalog.stale"


def test_catalog_without_valid_monotonic_timestamp_is_never_promoted_to_live() -> None:
    for cached_at in (None, "not-a-number", float("inf"), time.monotonic() + 60.0):
        rows = _by_id(_model_inventory(SimpleNamespace(
            _model_catalog={PRIMARY_MODEL},
            _model_catalog_cached_at=cached_at,
        ), PRIMARY_MODEL))

        assert rows[PRIMARY_MODEL]["selectable"] is False
        assert rows[PRIMARY_MODEL]["catalogSource"] == "cached_unverified"
        assert rows[PRIMARY_MODEL]["catalogFresh"] is False


def test_stale_catalog_capability_reports_historical_not_live_evidence() -> None:
    jarvis = SimpleNamespace(
        _model_catalog={PRIMARY_MODEL},
        _model_catalog_cached_at=time.monotonic() - 301.0,
        _model_disabled_until={},
    )
    capabilities = _by_id(_capability_projection(
        request=SimpleNamespace(
            headers={}, url=SimpleNamespace(scheme="http"),
            client=SimpleNamespace(host="127.0.0.1"), scope={"scheme": "http"},
        ),
        jarvis=jarvis,
        tool_rows=[],
        model_rows=_model_inventory(jarvis, PRIMARY_MODEL),
        provider_connected=True,
        preferences={"auto_mode": True, "auto_mic": False},
        agent_status={"worker_online": True},
        knowledge={"health": "unavailable", "graph": {}, "vault": {}},
        mobile_access={},
    ))

    catalog = capabilities["model_catalog"]
    assert catalog["state"] == "degraded"
    assert "historical evidence" in catalog["summary"]
    assert "none are selectable" in catalog["summary"]
    assert "live" not in catalog["summary"].casefold()
    assert catalog["evidence"][0]["detail"] == "selectable_chat_routes=0"


def test_models_endpoint_refreshes_router_evidence_and_marks_non_chat_inventory() -> None:
    client = SimpleNamespace(list_models=AsyncMock(return_value={"data": [
        {"id": PRIMARY_MODEL, "object": "model"},
        {"id": "nvidia/nv-embedqa-e5-v5", "object": "model"},
    ]}))
    runtime = SimpleNamespace(
        _model_catalog=set(),
        _model_catalog_cached_at=0.0,
        model_router=SimpleNamespace(normalize_catalog=lambda rows: {
            str(row["id"]) for row in rows
        }),
        _require_provider_client=AsyncMock(return_value=client),
    )
    before = time.monotonic()

    with patch.object(api_server, "jarvis", runtime):
        result = asyncio.run(api_server.models())

    rows = _by_id(result["models"])
    assert result["catalog_fresh"] is True
    assert rows[PRIMARY_MODEL]["selectable"] is True
    assert rows["nvidia/nv-embedqa-e5-v5"]["selectable"] is False
    assert runtime._model_catalog == {PRIMARY_MODEL, "nvidia/nv-embedqa-e5-v5"}
    assert runtime._model_catalog_cached_at >= before
