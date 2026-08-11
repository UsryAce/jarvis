from pathlib import Path

import pytest

from src.core.swarm import MultiAgentOrchestrator, SwarmRun, SwarmTask


class _FakeJarvis:
    pass


def _failed_run() -> SwarmRun:
    run = SwarmRun(
        id="swarm-terminal-invariant",
        goal="verify terminal state",
        mode="cowork",
        project_id="jarvis",
        status="failed",
    )
    queued = SwarmTask(
        id="task-queued",
        swarm_id=run.id,
        title="Queued child",
        objective="Must be closed",
        role="tester",
        status="queued",
    )
    completed = SwarmTask(
        id="task-completed",
        swarm_id=run.id,
        title="Completed child",
        objective="Must be preserved",
        role="tester",
        status="completed",
        result="verified",
    )
    run.tasks = {queued.id: queued, completed.id: completed}
    return run


def test_terminalize_remaining_tasks_preserves_completed_evidence(tmp_path: Path) -> None:
    runtime = MultiAgentOrchestrator(_FakeJarvis(), tmp_path / "swarm.db")
    run = _failed_run()
    runtime._save_run(run)
    for task in run.tasks.values():
        runtime._save_task(task)

    changed = runtime._terminalize_remaining_tasks(
        run,
        status="cancelled",
        error="Parent swarm failed",
    )

    assert changed == 1
    assert run.tasks["task-queued"].status == "cancelled"
    assert run.tasks["task-completed"].status == "completed"
    assert run.tasks["task-completed"].result == "verified"


@pytest.mark.asyncio
async def test_startup_repairs_legacy_terminal_parent_orphans(tmp_path: Path) -> None:
    database = tmp_path / "swarm.db"
    first = MultiAgentOrchestrator(_FakeJarvis(), database)
    run = _failed_run()
    first.runs[run.id] = run
    first._save_run(run)
    for task in run.tasks.values():
        first._save_task(task)

    recovered = MultiAgentOrchestrator(_FakeJarvis(), database)
    await recovered.start()

    loaded = recovered.get_run(run.id)
    assert loaded is not None
    assert loaded.tasks["task-queued"].status == "cancelled"
    assert loaded.tasks["task-completed"].status == "completed"
    assert recovered.status()["queue_depth"] == 0
    assert any(event["event_type"] == "reconciled" for event in loaded.events)
    await recovered.shutdown()
