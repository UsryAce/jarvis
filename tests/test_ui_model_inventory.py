"""Honest model inventory contracts for the Claude dashboard adapter."""

from types import SimpleNamespace

from src.api.ui_routes import _model_inventory
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
    rows = _by_id(_model_inventory(SimpleNamespace(_model_catalog=live), PRIMARY_MODEL))

    assert rows[PRIMARY_MODEL]["selectable"] is True
    assert rows["moonshotai/kimi-k2.6"]["selectable"] is True
    assert rows["nvidia/nv-embedqa-e5-v5"]["selectable"] is False
    assert rows["nvidia/nv-embedqa-e5-v5"]["catalogSource"] == "live"
