from src.api.ui_routes import _active_swarm_task_count, _agent_projection


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
