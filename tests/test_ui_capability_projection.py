"""Evidence-backed capability digital-twin contracts for the live dashboard."""

import time
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from src.api.ui_routes import (
    CAPABILITY_STATES,
    _read_mobile_access_record,
    _capability_item,
    _capability_projection,
    _model_inventory,
)
from src.core.model_router import PRIMARY_MODEL


def _request(
    origin: str,
    scheme: str = "http",
    *,
    peer: str = "127.0.0.1",
    forwarded: str = "",
    direct_tls: bool = False,
) -> SimpleNamespace:
    headers = {"origin": origin}
    if forwarded:
        headers["x-forwarded-proto"] = forwarded
    return SimpleNamespace(
        headers=headers,
        url=SimpleNamespace(scheme=scheme),
        client=SimpleNamespace(host=peer),
        scope={"extensions": {"tls": {"version": "TLSv1.3"}}} if direct_tls else {},
    )


def _projection(
    *,
    origin: str = "http://127.0.0.1:4173",
    scheme: str = "http",
    mobile_access=None,
    peer: str = "127.0.0.1",
    forwarded: str = "",
    direct_tls: bool = False,
):
    jarvis = SimpleNamespace(
        _model_catalog={PRIMARY_MODEL, "moonshotai/kimi-k2.6"},
        _model_catalog_cached_at=time.monotonic(),
        _model_disabled_until={},
    )
    tools = [
        {"name": "web_search", "risk": "read", "description": "Search the web"},
        {"name": "open_url", "risk": "write", "description": "Open the default browser"},
        {"name": "workspace_read", "risk": "read", "description": "Read a workspace file"},
    ]
    return _capability_projection(
        request=_request(
            origin, scheme, peer=peer, forwarded=forwarded,
            direct_tls=direct_tls,
        ),
        jarvis=jarvis,
        tool_rows=tools,
        model_rows=_model_inventory(jarvis, PRIMARY_MODEL),
        provider_connected=True,
        preferences={"auto_mode": True, "auto_mic": True},
        agent_status={"worker_online": True},
        knowledge={
            "health": "good",
            "graph": {"node_count": 42},
            "vault": {"exists": True},
        },
        # An empty mapping deliberately means there is no published-tunnel
        # evidence and prevents the test from consulting workstation state.
        mobile_access={} if mobile_access is None else mobile_access,
    )


def _by_id(capabilities):
    return {item["id"]: item for item in capabilities}


def test_registered_primitives_do_not_claim_browser_automation_or_health() -> None:
    capabilities = _by_id(_projection())

    assert capabilities["web_search"]["state"] == "available"
    assert capabilities["url_launcher"]["state"] == "available"
    assert capabilities["browser_automation"]["state"] == "unavailable"
    assert "not browser automation" in capabilities["url_launcher"]["summary"]
    assert capabilities["model_catalog"]["state"] == "verified"
    assert capabilities["model_inference"]["state"] == "available"
    assert "no durable active health probe" in capabilities["model_inference"]["summary"]
    assert capabilities["auto_routing"]["state"] == "available"
    assert "not live health scores" in capabilities["auto_routing"]["summary"]


def test_remote_https_requires_current_transport_or_stays_configured() -> None:
    local = _by_id(_projection())
    published = _by_id(_projection(mobile_access={"published": True, "scheme": "https"}))
    https_scope = _by_id(_projection(
        origin="https://jarvis.example", scheme="https",
    ))
    secure = _by_id(_projection(
        origin="https://jarvis.example", scheme="https", direct_tls=True,
    ))

    assert local["remote_https"]["state"] == "unavailable"
    assert published["remote_https"]["state"] == "configured"
    assert "reachability are unverified" in published["remote_https"]["summary"]
    assert https_scope["remote_https"]["state"] == "configured"
    assert secure["remote_https"]["state"] == "verified"
    assert secure["remote_https"]["evidence"][0] == {
        "source": "current_request",
        "detail": "observed_scheme=https;direct_tls=true",
    }


def test_remote_https_ignores_forged_origin_and_requires_configured_proxy_peer() -> None:
    forged_origin = _by_id(_projection(origin="https://forged.example"))
    untrusted_forwarded = _by_id(_projection(forwarded="https", peer="203.0.113.8"))
    with patch("src.api.ui_routes.config.get", return_value=["127.0.0.1"]):
        trusted_forwarded = _by_id(_projection(forwarded="https", peer="127.0.0.1"))

    assert forged_origin["remote_https"]["state"] == "unavailable"
    assert untrusted_forwarded["remote_https"]["state"] == "configured"
    assert trusted_forwarded["remote_https"]["state"] == "verified"


def test_stale_mobile_access_record_expires(tmp_path: Path) -> None:
    record = tmp_path / "mobile-access.json"
    origin = "https://example.trycloudflare.com"
    record.write_text(json.dumps({
        "url": f"{origin}/mobile",
        "tunnel": origin,
        "updated_at": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
    }), encoding="utf-8")

    with patch("src.api.ui_routes.MOBILE_ACCESS_FILE", record):
        assert _read_mobile_access_record() is None


def test_every_capability_has_bounded_runtime_evidence_and_screen_semantics() -> None:
    capabilities = _projection()

    assert capabilities
    for capability in capabilities:
        assert capability["state"] in CAPABILITY_STATES
        assert capability["evidence"]
        assert all(row["source"] and row["detail"] for row in capability["evidence"])
        item = _capability_item(capability)
        assert item["tag"] == capability["state"].upper()
        assert item["meta"][0][0] == "EVIDENCE"


def test_exact_design_controllers_consume_capability_evidence() -> None:
    root = Path(__file__).resolve().parents[1]
    adapter = (root / "frontend/public/claude-design/jarvis-adapter.js").read_text(encoding="utf-8")
    core = (root / "frontend/public/claude-design/JARVIS Core.dc.html").read_text(encoding="utf-8")
    mobile = (root / "frontend/public/claude-design/JARVIS Mobile.dc.html").read_text(encoding="utf-8")
    routes = (root / "src/api/ui_routes.py").read_text(encoding="utf-8")

    assert "CAPABILITY_STATES" in adapter
    assert "capabilities: arr(raw.capabilities)" in adapter
    assert "HEALTH UNVERIFIED" in core
    assert "p.latencyVerified" in core
    assert ">{{ p.state }}</div>" in core
    assert ">ONLINE</div>" not in core
    assert "out.voiceState = L.voice.armed ? 'ARMED'" not in core
    assert "stale ? 'STALE' : remoteCapability" in mobile
    assert "TRANSPORT EVIDENCE EXPIRED" in mobile
    assert "this secure origin" not in mobile
    assert "Waiting for live transport evidence" in mobile
    assert "armed:snap && snap.voice" not in mobile
    assert '"circuit": "unknown"' in routes


def test_exact_voice_runtime_does_not_conflate_preference_with_microphone_readiness() -> None:
    root = Path(__file__).resolve().parents[1]
    hook = (root / "frontend/src/hooks/useExactJarvisVoice.ts").read_text(
        encoding="utf-8",
    )
    core = (root / "frontend/public/claude-design/JARVIS Core.dc.html").read_text(
        encoding="utf-8",
    )
    mobile = (root / "frontend/public/claude-design/JARVIS Mobile.dc.html").read_text(
        encoding="utf-8",
    )

    assert "ready: boolean;" in hook
    assert "armed: false,\n    ready: false," in hook
    assert "ready: true,\n        capturing: true," in hook
    assert 'error: "Microphone device became unavailable"' in hook
    assert "voice:{...s.voice,...data.value,ready:true}" not in core
    assert "voice:{...s.voice,...data.value,connected:true}" in core
    assert "voiceReady = !!(V.connected && V.ready)" in core
    assert "voiceReady?'READY':'CONFIGURED'" in core
    assert "voice:{...s.voice,...data.value,connected:true}" in mobile
    assert "s.voice.ready ?" in mobile
    assert ": 'CONFIGURED'" in mobile


def test_adapter_normalize_does_not_throw_on_non_array_capability_shapes() -> None:
    root = Path(__file__).resolve().parents[1]
    adapter = root / "frontend/public/claude-design/jarvis-adapter.js"
    script = f"""
global.window = {{ location: {{ origin: 'http://localhost' }}, addEventListener() {{}}, removeEventListener() {{}} }};
window.parent = window;
require({json.dumps(str(adapter))});
const result = window.JarvisAdapter.normalize({{
  agent: {{}}, telemetry: {{}}, router: {{ models: {{}}, evidence: {{}} }},
  providers: {{}}, capabilities: {{}}, flow: {{}}, events: {{}},
  screens: {{}}, viz: {{}}
}});
if (!result.data || !Array.isArray(result.data.capabilities)) process.exit(2);
"""
    completed = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_adapter_normalize_rejects_non_array_graph_edges_without_throwing() -> None:
    root = Path(__file__).resolve().parents[1]
    adapter = root / "frontend/public/claude-design/jarvis-adapter.js"
    script = f"""
global.window = {{ location: {{ origin: 'http://localhost' }}, addEventListener() {{}}, removeEventListener() {{}} }};
window.parent = window;
require({json.dumps(str(adapter))});
const result = window.JarvisAdapter.normalize({{
  agent: {{}}, telemetry: {{}}, providers: [], capabilities: [], flow: [], events: [],
  screens: {{}}, viz: {{ BRAIN: {{ kind: 'graph', nodes: [], edges: {{ hostile: true }} }} }}
}});
if (!result.data || !Array.isArray(result.data.viz.BRAIN.edges)) process.exit(2);
"""
    completed = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_standalone_adapter_preserves_partial_swarm_approval_receipt() -> None:
    root = Path(__file__).resolve().parents[1]
    adapter = root / "frontend/public/claude-design/jarvis-adapter.js"
    script = f"""
global.window = {{ location: {{ origin: 'http://localhost' }}, addEventListener() {{}}, removeEventListener() {{}} }};
window.parent = window;
global.WebSocket = undefined;
global.fetch = async function(url) {{
  if (url.endsWith('/api/ui/snapshot')) return {{ ok:true, status:200, json:async()=>({{agent:{{}},telemetry:{{}},providers:[],capabilities:[],flow:[],events:[],screens:{{}},viz:{{}}}}) }};
  if (url.endsWith('/api/auth/session')) return {{ ok:true, status:200, json:async()=>({{csrf_token:'test-csrf'}}) }};
  if (url.includes('/approve-current')) return {{ ok:false, status:409, json:async()=>({{
    ok:false, code:'swarm_approval_partial', applied:true, partial:true,
    applied_count:1, requested_count:2, applied_ids:['agent-1:step-1'],
    reconciliation:{{required:true, action:'refresh_before_retry', guidance:'do not retry a stale challenge', resume_attempted:true, resume_status:'failed'}}
  }}) }};
  throw new Error('unexpected URL ' + url);
}};
require({json.dumps(str(adapter))});
(async function() {{
  const store = window.JarvisAdapter.connect({{baseUrl:'http://localhost', onChange:function(){{}}, pollMs:60000}});
  const result = await store.command('approve_swarm_run', {{
    runId:'swarm-1', approvals:[{{agentRunId:'agent-1',stepId:'step-1',challengeId:'challenge-1'}}]
  }});
  store.dispose();
  if (result.ok !== false || result.applied !== true || result.partial !== true) process.exit(2);
  if (result.applied_count !== 1 || result.applied_ids[0] !== 'agent-1:step-1') process.exit(3);
  if (!result.reconciliation || result.reconciliation.required !== true) process.exit(4);
  if (!result.reconciliation.guidance.includes('do not retry')) process.exit(5);
}})().catch(function(error) {{ console.error(error); process.exit(6); }});
"""
    completed = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
