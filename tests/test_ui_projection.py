from datetime import datetime, timezone

from src.api.ui_routes import (
    _active_swarm_task_count,
    _agent_card_action,
    _agent_projection,
    _agent_topology,
    _events,
    _graph_viz_from_payload,
    _hourly_series,
    _mission_topology,
    _project_topology,
    _swarm_card_action,
    _tool_event_times,
    _tool_topology,
)


def test_agent_projection_ignores_historical_terminal_failure() -> None:
    state, detail, _since = _agent_projection(
        [
            {"status": "failed", "goal": "old failure", "updated_at": "2026-07-22"},
            {
                "status": "awaiting_confirmation",
                "goal": "approval needed",
                "updated_at": "2026-07-21",
            },
        ],
        held=False,
    )

    assert state == "awaiting_approval"
    assert detail == "approval needed"


def test_agent_projection_is_ready_when_only_terminal_history_exists() -> None:
    state, detail, _since = _agent_projection(
        [{"status": "failed", "goal": "old failure", "updated_at": "2026-07-22"}],
        held=False,
    )

    assert state == "idle"
    assert detail == "Ready for Ahmed's directive."


def test_active_swarm_parent_goal_hides_internal_child_prompt() -> None:
    state, detail, _since = _agent_projection(
        [{
            "status": "running",
            "goal": "INTERNAL SPECIALIST PROMPT WITH PRIVATE COORDINATION",
            "record_conversation": False,
        }],
        held=False,
        swarm_runs=[{
            "id": "swarm-1",
            "status": "running",
            "goal": "Build Ahmed's approved storefront",
            "updated_at": "2026-07-29T08:00:00Z",
        }],
    )

    assert state == "delegating"
    assert detail == "Build Ahmed's approved storefront"
    assert "INTERNAL" not in detail


def test_events_filter_internal_child_prompts_and_project_parent_swarm() -> None:
    events = _events(
        [],
        [{
            "id": "agent-child",
            "status": "running",
            "goal": "INTERNAL ROLE PROMPT",
            "updated_at": "2026-07-29T08:00:01Z",
            "record_conversation": False,
        }],
        [{
            "id": "swarm-1",
            "status": "running",
            "goal": "Audit the approved project",
            "updated_at": "2026-07-29T08:00:02Z",
        }],
    )

    assert [event["who"] for event in events] == ["SWARM"]
    assert events[0]["text"] == "Audit the approved project"
    assert all("INTERNAL ROLE PROMPT" not in event["text"] for event in events)


def test_active_swarm_tasks_exclude_terminal_parent_orphans() -> None:
    runs = [
        {"status": "failed", "tasks": [{"status": "queued"}] * 43},
        {
            "status": "running",
            "tasks": [
                {"status": "running"},
                {"status": "queued"},
                {"status": "completed"},
            ],
        },
    ]

    assert _active_swarm_task_count(runs) == 2


def test_agent_card_exposes_only_current_guarded_approval_or_live_cancel() -> None:
    approval = _agent_card_action({"id": "agent-1", "status": "awaiting_confirmation"})
    cancel = _agent_card_action({"id": "agent-2", "status": "running"})

    assert approval == {
        "command": "approve_agent_run",
        "payload": {"runId": "agent-1"},
        "confirm": "Approve the currently pending guarded step for this agent run?",
    }
    assert cancel and cancel["command"] == "cancel_agent_run"
    assert _agent_card_action({"id": "agent-3", "status": "completed"}) is None


def test_swarm_card_exposes_guarded_approval_and_live_cancel() -> None:
    approval = _swarm_card_action({"id": "swarm-1", "status": "awaiting_confirmation"})
    cancel = _swarm_card_action({"id": "swarm-2", "status": "queued"})

    assert approval and approval["command"] == "approve_swarm_run"
    assert approval["payload"] == {"runId": "swarm-1"}
    assert cancel and cancel["command"] == "cancel_swarm_run"
    assert _swarm_card_action({"id": "swarm-3", "status": "failed"}) is None


def test_graph_viz_projects_only_real_nodes_links_with_normalized_layout() -> None:
    payload = {
        "nodes": [
            {"id": "core", "label": "Core", "community": 1},
            {"id": "router", "label": "Router", "community": 1},
            {"id": "vault", "label": "Vault", "community": 2},
        ],
        "links": [
            {"source": "core", "target": "router"},
            {"source": "core", "target": "vault"},
            {"source": "missing", "target": "vault"},
        ],
    }

    first = _graph_viz_from_payload(payload)
    second = _graph_viz_from_payload(payload)

    assert first == second
    assert first and first["kind"] == "graph"
    assert {node["id"] for node in first["nodes"]} == {"core", "router", "vault"}
    assert all(-1 <= node[axis] <= 1 for node in first["nodes"] for axis in ("x", "y", "z"))
    assert len(first["edges"]) == 2
    assert all(
        0 <= endpoint < len(first["nodes"])
        for edge in first["edges"] for endpoint in edge
    )


def test_count_only_or_invalid_graph_does_not_claim_live_visualization() -> None:
    assert _graph_viz_from_payload({"node_count": 3475, "edge_count": 8504}) is None
    assert _graph_viz_from_payload({"nodes": [], "links": []}) is None


def test_agent_and_mission_topologies_use_persisted_runtime_roles_and_goals() -> None:
    swarm = {
        "id": "swarm-1",
        "goal": "Repair the checkout service",
        "status": "running",
        "agents": [
            {"name": "DEVELOPER", "status": "running"},
            {"name": "REVIEWER", "status": "idle"},
        ],
    }

    agents = _agent_topology([], [swarm])
    missions = _mission_topology([swarm])

    assert agents and agents["hub"] == {
        "label": "JARVIS ORCHESTRATOR", "state": "running",
    }
    assert agents["spokes"] == [
        {"label": "DEVELOPER", "state": "running", "ring": 1},
        {"label": "REVIEWER", "state": "idle", "ring": 2},
    ]
    assert missions and missions["spokes"][0]["label"] == "Repair the checkout service"
    assert missions["spokes"][0]["state"] == "running"


def test_project_and_tool_topologies_preserve_registry_and_policy_provenance() -> None:
    projects = _project_topology([
        {"id": "jarvis", "name": "JARVIS", "protected": True},
        {"id": "site", "name": "Website", "protected": False},
    ])
    tools = _tool_topology([
        {"name": "workspace_read", "risk": "read"},
        {"name": "workspace_write", "risk": "write"},
    ])
    security = _tool_topology([
        {"name": "workspace_write", "risk": "write"},
    ], security=True)

    assert projects and [spoke["state"] for spoke in projects["spokes"]] == ["sealed", "granted"]
    assert tools and [spoke["state"] for spoke in tools["spokes"]] == ["granted", "gated"]
    assert security and security["hub"]["label"] == "TRUST POLICY"


def test_hourly_series_counts_observed_events_and_omits_unavailable_data() -> None:
    now = datetime(2026, 7, 29, 12, 30, tzinfo=timezone.utc)
    series = _hourly_series([
        "2026-07-29T12:05:00+00:00",
        "2026-07-29T12:25:00+00:00",
        "2026-07-29T11:59:00+00:00",
        "not-a-time",
    ], unit="requests", now=now)

    assert series and series["kind"] == "series"
    assert series["unit"] == "requests"
    assert len(series["points"]) == 24
    assert len(series["axis"]) == 5
    assert series["points"][-1] == {"t": "12:00", "v": 2}
    assert series["points"][-2] == {"t": "11:00", "v": 1}
    assert _hourly_series([], unit="requests", now=now) is None


def test_tool_activity_series_uses_only_matching_real_tool_start_events() -> None:
    runs = [{
        "events": [
            {"timestamp": "2026-07-29T12:00:00Z", "stage": "tool", "event_type": "start", "data": {"tool": "workspace_read"}},
            {"timestamp": "2026-07-29T12:00:01Z", "stage": "tool", "event_type": "end", "data": {"tool": "workspace_read"}},
            {"timestamp": "2026-07-29T12:00:02Z", "stage": "tool", "event_type": "start", "data": {"tool": "git_commit"}},
        ],
    }]

    assert _tool_event_times(runs, {"workspace_read"}) == ["2026-07-29T12:00:00Z"]
