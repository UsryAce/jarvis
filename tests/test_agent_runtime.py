import asyncio
import hashlib
import json
import sqlite3
import sys
import unittest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.core.agent import (
    AgentPlan,
    AgentRun,
    AgentRuntime,
    AgentStep,
    InFlightEffectReceipt,
    PendingApprovalChallenge,
    ToolProcessError,
)
from src.core.model_router import RouteDecision


class FakeJarvis:
    system_prompt = "You are Jarvis."
    memory = None

    def __init__(self):
        self.conversation_history = []

    async def route_model(self, goal, model):
        return RouteDecision(model="z-ai/glm-5.2", task_category="general", reason="test", auto_mode=True)

    async def execute_skill(self, name, params):
        return {"skill": name, "params": params}

    async def recall(self, query, limit):
        return []


class AgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def runtime(self):
        return AgentRuntime(FakeJarvis(), Path(self.tempdir.name) / "agent.db")

    async def test_read_tool_run_completes_with_trace(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="inspect system", summary="Inspect live state",
            steps=[AgentStep(id="step-1", description="Read system", tool="system_info", arguments={"action": "cpu"})],
        ))
        runtime._synthesize = AsyncMock(return_value="System inspected.")

        run = await runtime.run("inspect system")

        self.assertEqual(run.status, "completed")
        self.assertIn("Executed 1 verified tool step: system_info", run.result)
        self.assertIn("System evidence", run.result)
        runtime._synthesize.assert_not_awaited()
        self.assertEqual(run.observations[0]["tool"], "system_info")
        self.assertTrue(any(event["stage"] == "tool" for event in run.events))

    async def test_write_tool_requires_approval_then_resumes(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save note", summary="Save requested note",
            steps=[AgentStep(id="step-1", description="Create note", tool="note_create", arguments={"title": "Test", "content": "Agent note"})],
        ))
        runtime._execute_tool = AsyncMock(return_value="Note saved")
        runtime._synthesize = AsyncMock(return_value="The note was saved.")

        run = await runtime.run("save note")
        self.assertEqual(run.status, "awaiting_confirmation")
        runtime._execute_tool.assert_not_awaited()

        resumed = await runtime.approve(
            run.id, ["step-1"], run.pending_approval.challenge_id,
        )
        self.assertEqual(resumed.status, "completed")
        runtime._execute_tool.assert_awaited_once()

    async def test_approval_rejects_argument_drift(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save note", summary="Save requested note",
            steps=[AgentStep(
                id="step-1", description="Create note", tool="note_create",
                arguments={"title": "Expected", "content": "Safe content"},
            )],
        ))
        runtime._execute_tool = AsyncMock(return_value="Note saved")

        run = await runtime.run("save note")
        original_id = run.pending_approval.challenge_id
        original_digest = run.pending_approval.action_digest
        original_expiry = run.pending_approval.expires_at
        run.plan.steps[0].arguments["content"] = "Changed after prompt"

        with self.assertRaisesRegex(ValueError, "changed after approval was requested"):
            await runtime.approve(run.id, ["step-1"], original_id)

        self.assertEqual(run.status, "awaiting_confirmation")
        self.assertNotEqual(run.pending_approval.challenge_id, original_id)
        self.assertNotEqual(run.pending_approval.action_digest, original_digest)
        self.assertGreater(run.pending_approval.expires_at, original_expiry)
        self.assertEqual(
            run.to_dict()["pending_approval"]["challenge_id"],
            run.pending_approval.challenge_id,
        )

        refreshed_id = run.pending_approval.challenge_id
        with self.assertRaisesRegex(ValueError, "current pending approval"):
            await runtime.approve(run.id, ["step-1"], original_id)

        resumed = await runtime.approve(run.id, ["step-1"], refreshed_id)
        self.assertEqual(resumed.status, "completed")
        runtime._execute_tool.assert_awaited_once()

    async def test_approval_rejects_expired_challenge(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save note", summary="Save requested note",
            steps=[AgentStep(id="step-1", description="Create note", tool="note_create")],
        ))
        runtime._execute_tool = AsyncMock(return_value="Note saved")

        run = await runtime.run("save note")
        original_id = run.pending_approval.challenge_id
        original_digest = run.pending_approval.action_digest
        run.pending_approval.expires_at = (datetime.now() - timedelta(seconds=1)).isoformat()
        expired_at = run.pending_approval.expires_at

        with self.assertRaisesRegex(ValueError, "expired"):
            await runtime.approve(run.id, ["step-1"], original_id)

        self.assertEqual(run.status, "awaiting_confirmation")
        self.assertNotEqual(run.pending_approval.challenge_id, original_id)
        self.assertEqual(run.pending_approval.action_digest, original_digest)
        self.assertGreater(run.pending_approval.expires_at, expired_at)
        self.assertGreater(run.pending_approval.expires_at, datetime.now().isoformat())

        refreshed_id = run.pending_approval.challenge_id
        with self.assertRaisesRegex(ValueError, "current pending approval"):
            await runtime.approve(run.id, ["step-1"], original_id)

        resumed = await runtime.approve(run.id, ["step-1"], refreshed_id)
        self.assertEqual(resumed.status, "completed")
        runtime._execute_tool.assert_awaited_once()

    async def test_durable_approval_rejects_local_expiry_extension(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save note", summary="Save requested note",
            steps=[AgentStep(id="step-1", description="Create note", tool="note_create")],
        ))
        runtime._execute_tool = AsyncMock(return_value="must not execute")

        run = await runtime.run("save note")
        challenge_id = run.pending_approval.challenge_id
        durable_expiry = run.pending_approval.expires_at
        run.pending_approval.expires_at = (
            datetime.now() + timedelta(days=1)
        ).isoformat()

        with self.assertRaisesRegex(ValueError, "already claimed|no longer current"):
            await runtime.approve(run.id, ["step-1"], challenge_id)

        runtime._execute_tool.assert_not_awaited()
        self.assertEqual(run.status, "awaiting_confirmation")
        self.assertEqual(run.pending_approval.expires_at, durable_expiry)
        connection = sqlite3.connect(runtime.store.path)
        try:
            claims = connection.execute(
                "SELECT COUNT(*) FROM agent_approval_claims WHERE run_id = ?",
                (run.id,),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(claims, 0)

    async def test_approval_rejects_future_or_multiple_steps(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save two notes", summary="Save requested notes",
            steps=[
                AgentStep(id="step-1", description="Create first note", tool="note_create"),
                AgentStep(id="step-2", description="Create second note", tool="note_create"),
            ],
        ))
        runtime._execute_tool = AsyncMock(return_value="Note saved")

        run = await runtime.run("save two notes")
        challenge_id = run.pending_approval.challenge_id
        with self.assertRaisesRegex(ValueError, "current step"):
            await runtime.approve(run.id, ["step-2"], challenge_id)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            await runtime.approve(run.id, ["step-1", "step-2"], challenge_id)

        self.assertEqual(run.current_step, 0)
        self.assertEqual(run.pending_approval.step_id, "step-1")
        runtime._execute_tool.assert_not_awaited()

    async def test_approval_is_single_use_and_replay_is_rejected(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save note", summary="Save requested note",
            steps=[AgentStep(id="step-1", description="Create note", tool="note_create")],
        ))
        runtime._execute_tool = AsyncMock(return_value="Note saved")

        run = await runtime.run("save note")
        challenge_id = run.pending_approval.challenge_id
        await runtime.approve(run.id, ["step-1"], challenge_id)
        with self.assertRaisesRegex(ValueError, "not awaiting approval"):
            await runtime.approve(run.id, ["step-1"], challenge_id)

        self.assertEqual(run.status, "completed")
        self.assertIsNone(run.pending_approval)
        runtime._execute_tool.assert_awaited_once()

    async def test_stale_runtime_cannot_replay_durably_claimed_approval(self):
        database = Path(self.tempdir.name) / "stale-approval.db"
        winner = AgentRuntime(FakeJarvis(), database)
        winner._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save note", summary="Save requested note",
            steps=[AgentStep(id="step-1", description="Create note", tool="note_create")],
        ))
        winner._execute_tool = AsyncMock(return_value="Note saved")
        run = await winner.run("save note")
        challenge_id = run.pending_approval.challenge_id

        loser = AgentRuntime(FakeJarvis(), database)
        loser._execute_tool = AsyncMock(return_value="must not execute")
        await loser.start()
        try:
            stale_run = loser.get_run(run.id)
            self.assertEqual(stale_run.pending_approval.challenge_id, challenge_id)

            completed = await winner.approve(run.id, ["step-1"], challenge_id)
            with self.assertRaisesRegex(ValueError, "already claimed|no longer current"):
                await loser.approve(run.id, ["step-1"], challenge_id)

            self.assertEqual(completed.status, "completed")
            winner._execute_tool.assert_awaited_once()
            loser._execute_tool.assert_not_awaited()
            self.assertEqual(loser.get_run(run.id).status, "completed")
        finally:
            await loser.shutdown()

    async def test_simultaneous_runtime_approval_attempts_execute_once(self):
        database = Path(self.tempdir.name) / "simultaneous-approval.db"
        first = AgentRuntime(FakeJarvis(), database)
        first._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save note", summary="Save requested note",
            steps=[AgentStep(id="step-1", description="Create note", tool="note_create")],
        ))
        run = await first.run("save note")
        challenge_id = run.pending_approval.challenge_id

        second = AgentRuntime(FakeJarvis(), database)
        await second.start()
        effect_started = asyncio.Event()
        release_effect = asyncio.Event()
        executions = 0

        async def blocking_effect(*_args):
            nonlocal executions
            executions += 1
            effect_started.set()
            await release_effect.wait()
            return "Note saved"

        first._execute_tool = AsyncMock(side_effect=blocking_effect)
        second._execute_tool = AsyncMock(side_effect=blocking_effect)
        attempts = [
            asyncio.create_task(first.approve(run.id, ["step-1"], challenge_id)),
            asyncio.create_task(second.approve(run.id, ["step-1"], challenge_id)),
        ]
        try:
            await asyncio.wait_for(effect_started.wait(), timeout=2)
            done, pending = await asyncio.wait(
                attempts, timeout=2, return_when=asyncio.FIRST_COMPLETED,
            )
            self.assertEqual(len(done), 1)
            self.assertEqual(len(pending), 1)
            self.assertIsInstance(next(iter(done)).exception(), ValueError)
            self.assertEqual(executions, 1)
            release_effect.set()
            results = await asyncio.gather(*attempts, return_exceptions=True)
            self.assertEqual(sum(isinstance(item, ValueError) for item in results), 1)
            self.assertEqual(executions, 1)
        finally:
            release_effect.set()
            await asyncio.gather(*attempts, return_exceptions=True)
            await second.shutdown()

    async def test_pending_approval_challenge_persists_across_restart(self):
        database = Path(self.tempdir.name) / "approval-agent.db"
        runtime = AgentRuntime(FakeJarvis(), database)
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save note", summary="Save requested note",
            steps=[AgentStep(id="step-1", description="Create note", tool="note_create")],
        ))

        run = await runtime.run("save note")
        challenge_id = run.pending_approval.challenge_id

        recovered = AgentRuntime(FakeJarvis(), database)
        await recovered.start()
        try:
            recovered_run = recovered.get_run(run.id)
            self.assertEqual(recovered_run.status, "awaiting_confirmation")
            self.assertEqual(recovered_run.pending_approval.challenge_id, challenge_id)
            self.assertEqual(
                recovered_run.pending_approval.action_digest,
                run.pending_approval.action_digest,
            )
        finally:
            await recovered.shutdown()

    async def test_approval_requires_the_presented_challenge_id(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save note", summary="Save requested note",
            steps=[AgentStep(id="step-1", description="Create note", tool="note_create")],
        ))
        runtime._execute_tool = AsyncMock(return_value="Note saved")

        run = await runtime.run("save note")
        with self.assertRaisesRegex(ValueError, "challenge id is required"):
            await runtime.approve(run.id, ["step-1"])

        self.assertEqual(run.status, "awaiting_confirmation")
        runtime._execute_tool.assert_not_awaited()

    async def test_write_tool_is_attempted_once_even_when_retries_are_enabled(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save note", summary="Save requested note",
            steps=[AgentStep(id="step-1", description="Create note", tool="note_create")],
        ))
        runtime._execute_tool = AsyncMock(side_effect=RuntimeError("unknown write outcome"))

        run = await runtime.run("save note", autonomy="full", max_retries=5)

        self.assertEqual(run.status, "needs_attention")
        self.assertEqual(run.error, "ambiguous_write_outcome")
        self.assertEqual(runtime._execute_tool.await_count, 1)
        self.assertEqual(run.attempts, 0)
        self.assertEqual(run.current_step, 0)
        self.assertFalse(run.observations[0]["ok"])
        self.assertIsNotNone(run.in_flight_effect)

        recovered = AgentRuntime(FakeJarvis(), runtime.store.path)
        recovered._execute_tool = AsyncMock(return_value="must not execute")
        await recovered.start()
        try:
            recovered_run = recovered.get_run(run.id)
            self.assertEqual(recovered_run.status, "needs_attention")
            self.assertEqual(recovered_run.error, "ambiguous_write_outcome")
            self.assertIsNotNone(recovered_run.in_flight_effect)
            self.assertEqual(recovered_run.current_step, 0)
            recovered._execute_tool.assert_not_awaited()
        finally:
            await recovered.shutdown()

    async def test_restart_does_not_duplicate_ambiguous_in_flight_write(self):
        class SimulatedProcessCrash(BaseException):
            pass

        database = Path(self.tempdir.name) / "crash-agent.db"
        runtime = AgentRuntime(FakeJarvis(), database)
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save note", summary="Save requested note",
            steps=[AgentStep(id="step-1", description="Create note", tool="note_create")],
        ))
        runtime._execute_tool = AsyncMock(side_effect=SimulatedProcessCrash())

        run = await runtime.run("save note")
        challenge_id = run.pending_approval.challenge_id
        with self.assertRaises(SimulatedProcessCrash):
            await runtime.approve(run.id, ["step-1"], challenge_id)

        self.assertIsNotNone(run.in_flight_effect)
        self.assertEqual(run.observations, [])
        self.assertEqual(runtime._execute_tool.await_count, 1)

        recovered = AgentRuntime(FakeJarvis(), database)
        recovered._execute_tool = AsyncMock(return_value="must not execute")
        await recovered.start()
        try:
            recovered_run = recovered.get_run(run.id)
            self.assertEqual(recovered_run.status, "needs_attention")
            self.assertEqual(recovered_run.error, "ambiguous_in_flight_effect")
            self.assertIsNotNone(recovered_run.in_flight_effect)
            self.assertEqual(recovered._queue.qsize(), 0)
            recovered._execute_tool.assert_not_awaited()
        finally:
            await recovered.shutdown()

    async def test_duplicate_step_id_cannot_falsely_reconcile_in_flight_write(self):
        database = Path(self.tempdir.name) / "receipt-binding.db"
        runtime = AgentRuntime(FakeJarvis(), database)
        run = runtime._new_run("save two notes", "z-ai/glm-5.2", 2, "full", 0)
        run.plan = AgentPlan(
            goal="save two notes",
            summary="Legacy plan with duplicate ids",
            steps=[
                AgentStep(id="duplicate", description="First note", tool="note_create"),
                AgentStep(id="duplicate", description="Second note", tool="note_create"),
            ],
        )
        run.status = "running"
        run.current_step = 1
        run.observations = [{
            "step_id": "duplicate",
            "step_index": 0,
            "tool": "note_create",
            "action_digest": "a" * 64,
            "ok": True,
        }]
        run.in_flight_effect = InFlightEffectReceipt(
            step_id="duplicate",
            step_index=1,
            tool="note_create",
            action_digest="b" * 64,
            started_at=datetime.now().isoformat(),
        )
        runtime.store.save_run(run.to_dict())

        recovered = AgentRuntime(FakeJarvis(), database)
        await recovered.start()
        try:
            recovered_run = recovered.get_run(run.id)
            self.assertEqual(recovered_run.status, "needs_attention")
            self.assertEqual(recovered_run.error, "ambiguous_in_flight_effect")
            self.assertIsNotNone(recovered_run.in_flight_effect)
            self.assertEqual(recovered._queue.qsize(), 0)
        finally:
            await recovered.shutdown()

    async def test_new_plan_rejects_duplicate_step_ids_before_effect(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save two notes",
            summary="Invalid duplicate ids",
            steps=[
                AgentStep(id="duplicate", description="First", tool="note_create"),
                AgentStep(id="duplicate", description="Second", tool="note_create"),
            ],
        ))
        runtime._execute_tool = AsyncMock(return_value="must not execute")

        run = await runtime.run("save two notes", autonomy="full")

        self.assertEqual(run.status, "failed")
        runtime._execute_tool.assert_not_awaited()

    async def test_two_runtimes_cannot_execute_same_full_auto_queued_run(self):
        database = Path(self.tempdir.name) / "worker-claim.db"
        source = AgentRuntime(FakeJarvis(), database)
        queued = source._new_run("write proof", "z-ai/glm-5.2", 1, "full", 0)
        queued.plan = AgentPlan(
            goal="write proof",
            summary="Write one proof",
            steps=[AgentStep(
                id="step-1", description="Write proof", tool="workspace_write",
                arguments={"path": "proof.txt", "content": "ready"},
            )],
        )
        source.store.save_run(queued.to_dict())
        payload = source.store.load_run(queued.id)

        first = AgentRuntime(FakeJarvis(), database)
        second = AgentRuntime(FakeJarvis(), database)
        first_run = AgentRun.from_dict(payload)
        second_run = AgentRun.from_dict(payload)
        first.runs[first_run.id] = first_run
        second.runs[second_run.id] = second_run
        effect_started = asyncio.Event()
        release_effect = asyncio.Event()
        executions = 0

        async def blocking_effect(*_args):
            nonlocal executions
            executions += 1
            effect_started.set()
            await release_effect.wait()
            return {"path": "proof.txt", "written_chars": 5}

        first._execute_tool = AsyncMock(side_effect=blocking_effect)
        second._execute_tool = AsyncMock(side_effect=blocking_effect)
        attempts = [
            asyncio.create_task(first._run_existing(first_run)),
            asyncio.create_task(second._run_existing(second_run)),
        ]
        try:
            await asyncio.wait_for(effect_started.wait(), timeout=2)
            await asyncio.sleep(0)
            self.assertEqual(executions, 1)
            self.assertTrue(any(task.done() for task in attempts))
            release_effect.set()
            await asyncio.gather(*attempts)
            self.assertEqual(executions, 1)
        finally:
            release_effect.set()
            await asyncio.gather(*attempts, return_exceptions=True)

    async def test_write_losing_lease_after_await_is_persisted_as_ambiguous(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="write proof", summary="Write one proof",
            steps=[AgentStep(
                id="step-1", description="Write proof", tool="workspace_write",
                arguments={"path": "proof.txt", "content": "ready"},
            )],
        ))

        async def lose_lease(*_args):
            active = next(iter(runtime.runs.values()))
            runtime.store.release_run_execution(
                active.id, owner_id=runtime._runtime_id,
            )
            await asyncio.sleep(0)
            return {"path": "proof.txt", "written_chars": 5}

        runtime._execute_tool = AsyncMock(side_effect=lose_lease)
        run = await runtime.run("write proof", autonomy="full", max_retries=0)

        self.assertEqual(run.status, "needs_attention")
        self.assertEqual(run.error, "ambiguous_write_outcome")
        self.assertIsNotNone(run.in_flight_effect)
        self.assertEqual(run.observations, [])
        stored = runtime.store.load_run(run.id)
        self.assertEqual(stored["status"], "needs_attention")
        self.assertIsNotNone(stored["in_flight_effect"])

    async def test_legacy_waiting_run_receives_a_fresh_approval_challenge(self):
        database = Path(self.tempdir.name) / "legacy-agent.db"
        runtime = AgentRuntime(FakeJarvis(), database)
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="save note", summary="Save requested note",
            steps=[AgentStep(id="step-1", description="Create note", tool="note_create")],
        ))
        run = await runtime.run("save note")
        payload = run.to_dict()
        payload["pending_approval"] = None
        payload["approved_steps"] = ["step-1"]
        runtime.store.save_run(payload)

        recovered = AgentRuntime(FakeJarvis(), database)
        await recovered.start()
        try:
            recovered_run = recovered.get_run(run.id)
            self.assertEqual(recovered_run.status, "awaiting_confirmation")
            self.assertIsNotNone(recovered_run.pending_approval)
            self.assertEqual(recovered_run.pending_approval.step_id, "step-1")
            self.assertEqual(recovered_run.approved_steps, set())
            self.assertTrue(any(
                event["stage"] == "approval" and event["event_type"] == "migrated"
                for event in recovered_run.events
            ))
        finally:
            await recovered.shutdown()

    def test_agent_events_are_redacted_before_persistence(self):
        runtime = self.runtime()
        run = runtime._new_run("record safe event", "auto", 2, "guarded", 0)
        generated_secret = "nvapi-" + ("A" * 32)

        runtime._event(
            run,
            "approval",
            "required",
            f"Do not persist {generated_secret}",
            {
                "step": {
                    "arguments": {
                        "api_key": generated_secret,
                        "description": f"credential={generated_secret}",
                    }
                }
            },
        )

        rendered = str(run.events[-1])
        self.assertNotIn(generated_secret, rendered)
        self.assertIn("[REDACTED]", rendered)

    def test_public_and_stored_run_projection_redacts_all_credential_forms(self):
        runtime = self.runtime()
        nvapi = "nvapi-" + ("N" * 32)
        smtp_pass = "mail-password-canary"
        database_password = "database-password-canary"
        database_url = f"postgresql://jarvis:{database_password}@db.example/jarvis"
        signature = "signed-url-canary-value"
        signed_url = f"https://example.test/object?X-Amz-Signature={signature}&part=1"
        run = runtime._new_run("safe projection test", "z-ai/glm-5.2", 1, "guarded", 0)
        run.plan = AgentPlan(
            goal="safe projection test",
            summary="Project safely",
            steps=[AgentStep(
                id="step-1",
                description="Use provider output",
                tool="note_create",
                arguments={
                    "api_key": nvapi,
                    "SMTP_PASS": smtp_pass,
                    "database_url": database_url,
                    "url": signed_url,
                },
            )],
        )
        run.status = "awaiting_confirmation"
        run.result = f"result {database_url} SMTP_PASS={smtp_pass} {nvapi} {signed_url}"
        run.observations = [{
            "tool": "command_run",
            "ok": True,
            "data": {
                "DATABASE_URL": database_url,
                "SMTP_PASS": smtp_pass,
                "stdout": f"{nvapi}\n{signed_url}\n{database_url}",
            },
        }]

        projection = run.to_dict()
        runtime.store.save_run(projection)
        rendered = json.dumps(projection, ensure_ascii=False)
        connection = sqlite3.connect(runtime.store.path)
        try:
            stored_json = connection.execute(
                "SELECT payload FROM agent_runs WHERE id = ?", (run.id,)
            ).fetchone()[0]
        finally:
            connection.close()

        forbidden = (nvapi, smtp_pass, database_password, signature)
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, rendered)
                self.assertNotIn(value, stored_json)
        secret_hash = hashlib.sha256(nvapi.encode("utf-8")).hexdigest()
        self.assertNotIn(secret_hash, rendered)
        self.assertNotIn(secret_hash, stored_json)
        self.assertEqual(projection["redacted_step_indices"], [0])
        self.assertIn("REDACTED", json.dumps(projection["plan"]))
        self.assertIn("REDACTED", json.dumps(projection["pending_step"]))

    async def test_exact_token_field_clears_authority_and_secret_derived_digests(self):
        database = Path(self.tempdir.name) / "legacy-token.db"
        runtime = AgentRuntime(FakeJarvis(), database)
        raw_token = "plain-token-canary-that-must-never-persist"
        run = runtime._new_run("legacy token recovery", "z-ai/glm-5.2", 1, "guarded", 0)
        step = AgentStep(
            id="step-1",
            description="Legacy credential-bearing action",
            tool="note_create",
            arguments={"token": raw_token, "token_count": 37},
        )
        run.plan = AgentPlan(
            goal="legacy token recovery",
            summary="Legacy plan",
            steps=[step],
        )
        run.status = "awaiting_confirmation"
        action_digest = runtime._approval_action_digest(run, step)
        token_digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        issued_at = datetime.now().isoformat()
        run.pending_approval = PendingApprovalChallenge(
            challenge_id="legacy-token-challenge",
            step_id=step.id,
            action_digest=action_digest,
            issued_at=issued_at,
            expires_at=(datetime.now() + timedelta(minutes=10)).isoformat(),
        )
        run.in_flight_effect = InFlightEffectReceipt(
            step_id=step.id,
            step_index=0,
            tool=str(step.tool),
            action_digest=action_digest,
            started_at=issued_at,
        )
        run.approved_steps = {step.id}
        run.result = f"derived {action_digest} {token_digest}"
        run.events = [{
            "stage": "legacy",
            "event_type": "unsafe",
            "message": "legacy payload",
            "data": {
                "step_index": 0,
                "nested": {
                    "action_digest": action_digest,
                    "token_hash": {"action_digest": token_digest},
                },
            },
        }]

        projection = run.to_dict()
        # Simulate authority left behind by a pre-redaction build. Saving the
        # sanitized run must revoke it as well as scrub the public payload.
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                """INSERT INTO agent_approval_claims(
                       run_id, challenge_id, step_id, action_digest, claimed_at
                   ) VALUES(?, ?, ?, ?, ?)""",
                (run.id, "legacy-claim", step.id, action_digest, issued_at),
            )
            connection.commit()
        finally:
            connection.close()
        runtime.store.save_run(projection)
        connection = sqlite3.connect(database)
        try:
            stored_json = connection.execute(
                "SELECT payload FROM agent_runs WHERE id = ?", (run.id,),
            ).fetchone()[0]
            remaining_claims = connection.execute(
                "SELECT COUNT(*) FROM agent_approval_claims WHERE run_id = ?", (run.id,),
            ).fetchone()[0]
        finally:
            connection.close()
        public_json = json.dumps(projection, ensure_ascii=False)

        for forbidden in (raw_token, action_digest, token_digest):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, public_json)
                self.assertNotIn(forbidden, stored_json)
        self.assertEqual(
            projection["plan"]["steps"][0]["arguments"]["token_count"], 37,
        )
        self.assertIn("REDACTED", projection["plan"]["steps"][0]["arguments"]["token"])
        self.assertEqual(projection["status"], "needs_attention")
        self.assertEqual(projection["error"], "secret_reentry_required")
        self.assertIsNone(projection["pending_approval"])
        self.assertIsNone(projection["in_flight_effect"])
        self.assertEqual(projection["approved_steps"], [])
        self.assertEqual(projection["events"][0]["data"]["nested"]["action_digest"], "0" * 64)
        self.assertEqual(remaining_claims, 0)

        recovered = AgentRuntime(FakeJarvis(), database)
        recovered._execute_tool = AsyncMock(return_value="must not execute")
        await recovered.start()
        try:
            recovered_run = recovered.get_run(run.id)
            self.assertEqual(recovered_run.status, "needs_attention")
            self.assertEqual(recovered_run.error, "secret_reentry_required")
            self.assertIsNone(recovered_run.pending_approval)
            self.assertIsNone(recovered_run.in_flight_effect)
            self.assertEqual(recovered._queue.qsize(), 0)
            recovered._execute_tool.assert_not_awaited()
        finally:
            await recovered.shutdown()

    async def test_secret_bearing_goal_and_model_plan_are_rejected_before_effect(self):
        runtime = self.runtime()
        nvapi = "nvapi-" + ("G" * 32)
        runtime.jarvis.route_model = AsyncMock()
        with self.assertRaisesRegex(ValueError, "must not contain credentials"):
            await runtime.run(f"inspect system with NVIDIA_API_KEY={nvapi}")
        runtime.jarvis.route_model.assert_not_awaited()
        self.assertEqual(runtime.store.load_runs(), [])
        runtime.jarvis.route_model = AsyncMock(return_value=RouteDecision(
            model="z-ai/glm-5.2", task_category="general", reason="test", auto_mode=True,
        ))

        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="safe goal",
            summary="Unsafe provider plan",
            steps=[AgentStep(
                id="step-1", description="Unsafe action", tool="note_create",
                arguments={"SMTP_PASS": "provider-secret-canary"},
            )],
        ))
        runtime._execute_tool = AsyncMock(return_value="must not execute")
        run = await runtime.run("safe goal", autonomy="full")
        runtime._execute_tool.assert_not_awaited()
        self.assertEqual(run.status, "failed")
        rendered = json.dumps(run.to_dict(), ensure_ascii=False)
        self.assertNotIn("provider-secret-canary", rendered)

    def test_schedule_goal_rejects_credentials_and_legacy_projection_is_disabled(self):
        runtime = self.runtime()
        nvapi = "nvapi-" + ("S" * 32)
        with self.assertRaisesRegex(ValueError, "must not contain credentials"):
            runtime.create_schedule(
                f"run backup with API_KEY={nvapi}", datetime.now().isoformat(),
            )
        self.assertEqual(runtime.list_schedules(), [])

        legacy = {
            "id": "schedule-legacy",
            "goal": f"legacy DATABASE_URL=postgresql://user:{nvapi}@db/jarvis",
            "next_run_at": datetime.now().isoformat(),
            "interval_seconds": None,
            "model": "auto",
            "max_steps": 1,
            "autonomy": "guarded",
            "enabled": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "last_run_id": None,
        }
        runtime.schedules[legacy["id"]] = legacy
        runtime.store.save_schedule(legacy)
        public = runtime.list_schedules()[0]
        stored = runtime.store.load_schedules()[0]
        self.assertFalse(public["enabled"])
        self.assertFalse(stored["enabled"])
        self.assertNotIn(nvapi, json.dumps(public))
        self.assertNotIn(nvapi, json.dumps(stored))

    async def test_schedule_occurrence_survives_post_transaction_crash_without_duplicate(self):
        class SimulatedProcessCrash(BaseException):
            pass

        class CrashingQueue:
            async def put(self, _run_id):
                raise SimulatedProcessCrash()

            def qsize(self):
                return 0

        database = Path(self.tempdir.name) / "schedule-occurrence.db"
        runtime = AgentRuntime(FakeJarvis(), database)
        due_at = (datetime.now() - timedelta(seconds=1)).isoformat()
        schedule = runtime.create_schedule("inspect system", due_at)
        runtime._queue = CrashingQueue()

        with self.assertRaises(SimulatedProcessCrash):
            await runtime._claim_due_schedule(
                runtime.schedules[schedule["id"]],
                runtime._parse_schedule_time(due_at),
                datetime.now(),
            )

        self.assertEqual(len(runtime.store.load_runs()), 1)
        self.assertFalse(runtime.store.load_schedules()[0]["enabled"])

        recovered = AgentRuntime(FakeJarvis(), database)
        recovered._run_existing = AsyncMock(return_value=None)
        await recovered.start()
        try:
            await asyncio.sleep(0.05)
            self.assertEqual(len(recovered.store.load_runs()), 1)
            self.assertFalse(recovered.list_schedules()[0]["enabled"])
            recovered._run_existing.assert_awaited_once()
        finally:
            await recovered.shutdown()

    async def test_live_peer_recovers_occurrence_after_pre_enqueue_crash(self):
        class SimulatedProcessCrash(BaseException):
            pass

        class CrashingQueue:
            async def put(self, _run_id):
                raise SimulatedProcessCrash()

            def qsize(self):
                return 0

        database = Path(self.tempdir.name) / "schedule-live-peer.db"
        winner = AgentRuntime(FakeJarvis(), database)
        due_at = (datetime.now() - timedelta(seconds=1)).isoformat()
        schedule = winner.create_schedule("inspect system", due_at)

        peer = AgentRuntime(FakeJarvis(), database)
        scheduler_parked = asyncio.Event()

        async def park_scheduler():
            await scheduler_parked.wait()

        peer._scheduler_loop = park_scheduler
        peer._run_existing = AsyncMock(return_value=None)
        await peer.start()
        stale_schedule = dict(peer.schedules[schedule["id"]])
        winner._queue = CrashingQueue()
        try:
            with self.assertRaises(SimulatedProcessCrash):
                await winner._claim_due_schedule(
                    winner.schedules[schedule["id"]],
                    winner._parse_schedule_time(due_at),
                    datetime.now(),
                )

            committed_payload = winner.store.load_schedule_occurrence_run(
                schedule_id=schedule["id"], due_at=due_at,
            )
            self.assertIsNotNone(committed_payload)
            self.assertEqual(committed_payload["status"], "queued")

            recovered = await peer._claim_due_schedule(
                stale_schedule,
                peer._parse_schedule_time(due_at),
                datetime.now(),
            )
            repeated = await peer._claim_due_schedule(
                stale_schedule,
                peer._parse_schedule_time(due_at),
                datetime.now(),
            )
            await asyncio.wait_for(peer._queue.join(), timeout=2)

            self.assertIsNotNone(recovered)
            self.assertEqual(recovered.id, committed_payload["id"])
            self.assertEqual(repeated.id, committed_payload["id"])
            self.assertEqual(len(peer.store.load_runs()), 1)
            peer._run_existing.assert_awaited_once()
        finally:
            scheduler_parked.set()
            await peer.shutdown()

    def test_tool_catalog_marks_mutations(self):
        tools = {item["name"]: item["risk"] for item in self.runtime().list_tools()}
        self.assertEqual(tools["web_search"], "read")
        self.assertEqual(tools["note_create"], "write")
        self.assertEqual(tools["project_create"], "write")
        self.assertEqual(tools["github_status"], "read")

    async def test_read_only_capability_rejects_injected_write_plan(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="malicious researcher plan",
            summary="Attempt a forbidden write",
            steps=[AgentStep(
                id="step-1", description="Write outside the role boundary",
                tool="workspace_write", arguments={"path": "owned.txt", "content": "bad"},
            )],
        ))
        runtime._execute_tool = AsyncMock(return_value={"path": "owned.txt"})

        run = await runtime.run(
            "malicious researcher plan",
            autonomy="full",
            max_retries=0,
            capability_profile="read_only",
        )

        self.assertEqual(run.status, "failed")
        self.assertEqual(run.error, "tool_capability_error")
        self.assertEqual(run.capability_profile, "read_only")
        self.assertEqual(run.allowed_tools, AgentRuntime.READ_TOOLS)
        runtime._execute_tool.assert_not_awaited()
        self.assertFalse((Path(self.tempdir.name) / "owned.txt").exists())

    async def test_internal_agent_run_does_not_record_specialist_prompt(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="internal specialist prompt", summary="Read evidence",
            steps=[AgentStep(id="step-1", description="Read system", tool="system_info")],
        ))

        run = await runtime.run(
            "internal specialist prompt",
            capability_profile="read_only",
            record_conversation=False,
        )

        self.assertEqual(run.status, "completed")
        self.assertFalse(run.record_conversation)
        self.assertEqual(runtime.jarvis.conversation_history, [])

    async def test_full_auto_can_write_only_inside_workspace(self):
        runtime = self.runtime()
        runtime.workspace_root = Path(self.tempdir.name).resolve()
        result = await runtime._execute_tool("workspace_write", {"path": "demo.txt", "content": "ready"})
        self.assertEqual(result["written_chars"], 5)
        self.assertEqual((runtime.workspace_root / "demo.txt").read_text(), "ready")
        with self.assertRaises(PermissionError):
            await runtime._execute_tool("workspace_write", {"path": "../escape.txt", "content": "blocked"})

    async def test_full_auto_still_pauses_for_local_process_execution(self):
        cases = (
            ("command_run", {"command": "Write-Output safe"}),
            ("app_launch", {"app": "notepad"}),
        )
        for tool, arguments in cases:
            with self.subTest(tool=tool):
                runtime = self.runtime()
                runtime._create_plan = AsyncMock(return_value=AgentPlan(
                    goal=f"execute {tool}", summary="Execute local process",
                    steps=[AgentStep(
                        id="step-1",
                        description=f"Execute {tool}",
                        tool=tool,
                        arguments=arguments,
                    )],
                ))
                runtime._execute_tool = AsyncMock(return_value={"launched": True})

                run = await runtime.run(
                    f"execute {tool}",
                    autonomy="full",
                    max_retries=0,
                )

                self.assertEqual(run.status, "awaiting_confirmation")
                self.assertEqual(run.to_dict()["pending_step"]["tool"], tool)
                runtime._execute_tool.assert_not_awaited()

    async def test_app_launch_rejects_shell_script_host_and_proxy_executables(self):
        runtime = self.runtime()
        runtime.workspace_root = Path(self.tempdir.name).resolve()
        blocked = (
            "powershell", "PowerShell.EXE", "pwsh", "PWSH.exe", "cmd", "cmd.exe",
            "wscript", "wscript.exe", "cscript", "cscript.exe", "mshta", "mshta.exe",
            "rundll32", "rundll32.exe", "regsvr32", "regsvr32.exe",
        )

        for executable in blocked:
            with self.subTest(executable=executable):
                with self.assertRaises(PermissionError):
                    await runtime._execute_tool("app_launch", {"app": executable})

    async def test_project_creator_builds_runnable_website_inside_workspace(self):
        runtime = self.runtime()
        runtime.workspace_root = Path(self.tempdir.name).resolve()
        result = await runtime._execute_tool(
            "project_create",
            {"name": "Launch Site", "kind": "website", "description": "A real starter site."},
        )
        project = runtime.workspace_root / "projects" / "launch-site"
        self.assertTrue(result["created"])
        self.assertTrue((project / "index.html").is_file())
        self.assertIn("Launch Site", (project / "index.html").read_text(encoding="utf-8"))
        self.assertTrue((project / "styles.css").is_file())

    def test_project_goal_generates_real_execution_plan(self):
        plan = self.runtime()._fallback_plan("Create a website called Aurora and put it on GitHub")
        self.assertEqual([step.tool for step in plan.steps], [
            "project_create", "git_init", "git_commit", "github_status", "github_create_repo", "github_push",
        ])
        full_run = type("Run", (), {"autonomy": "full", "goal": "Create Aurora and put it on GitHub"})()
        guarded_run = type("Run", (), {"autonomy": "guarded", "goal": "Create Aurora and put it on GitHub"})()
        self.assertFalse(self.runtime()._requires_confirmation(full_run, plan.steps[4]))
        self.assertTrue(self.runtime()._requires_confirmation(guarded_run, plan.steps[4]))
        self.assertEqual(plan.steps[0].arguments["name"], "aurora")

    async def test_known_github_goal_uses_deterministic_fast_plan(self):
        plan = await self.runtime()._create_plan("Check my GitHub connection", "z-ai/glm-5.2", 3)
        self.assertEqual([step.tool for step in plan.steps], ["github_status"])

    async def test_git_status_goal_uses_read_only_fast_plan(self):
        plan = await self.runtime()._create_plan(
            "Report the current Git branch and working-tree status without changing files",
            "z-ai/glm-5.2",
            3,
        )
        self.assertEqual([step.tool for step in plan.steps], ["git_status"])

    async def test_open_google_uses_local_fast_plan_without_model(self):
        runtime = self.runtime()
        plan = await runtime._create_plan("Jarvis, can you open Google for me?", "z-ai/glm-5.2", 3)
        self.assertEqual([step.tool for step in plan.steps], ["open_url"])
        self.assertEqual(plan.steps[0].arguments["url"], "https://www.google.com/")

    async def test_workspace_search_has_python_fallback_without_ripgrep(self):
        runtime = self.runtime()
        runtime.workspace_root = Path(self.tempdir.name).resolve()
        (runtime.workspace_root / "src").mkdir()
        (runtime.workspace_root / "src" / "sample.py").write_text("alpha\nneedle here\nomega\n", encoding="utf-8")
        with patch("src.core.agent.shutil.which", return_value=None):
            result = await runtime._execute_tool("workspace_search", {"query": "needle", "path": "src", "glob": "*.py"})
        self.assertEqual(result["fallback"], "python")
        self.assertIn("src\\sample.py:2:needle here", result["stdout"])

    def test_execution_receipt_uses_verified_tool_data(self):
        runtime = self.runtime()
        run = type("Run", (), {
            "goal": "Check my GitHub connection",
            "workspace_root": str(Path(self.tempdir.name).resolve()),
            "observations": [{"tool": "github_status", "ok": True, "data": {"authenticated": True}}],
        })()
        receipt = runtime._execution_receipt(run)
        self.assertIn("GitHub CLI is authenticated", receipt)

    def test_action_intent_detects_real_work(self):
        self.assertTrue(AgentRuntime.is_action_goal("Fix the dashboard and run its tests"))
        self.assertTrue(AgentRuntime.is_action_goal("Create a GitHub repository"))
        self.assertFalse(AgentRuntime.is_action_goal("What is a GitHub repository?"))

    def test_file_and_code_actions_are_delegated_but_advice_is_not(self):
        self.assertTrue(AgentRuntime.should_delegate_chat_action("Delete the temporary file demo.txt"))
        self.assertTrue(AgentRuntime.should_delegate_chat_action("Run the Python test suite"))
        self.assertFalse(AgentRuntime.should_delegate_chat_action("How can I structure a Python project?"))
        self.assertFalse(AgentRuntime.should_delegate_chat_action("What is the weather today?"))

    async def test_process_nonzero_exit_fails_unless_explicitly_allowed(self):
        runtime = self.runtime()
        runtime.workspace_root = Path(self.tempdir.name).resolve()
        command = [sys.executable, "-c", "raise SystemExit(7)"]

        with self.assertRaises(ToolProcessError) as raised:
            await runtime._run_process(command, timeout=10, cwd=runtime.workspace_root)
        self.assertEqual(raised.exception.exit_code, 7)

        result = await runtime._run_process(
            command,
            timeout=10,
            cwd=runtime.workspace_root,
            allowed_exit_codes={0, 7},
        )
        self.assertEqual(result["exit_code"], 7)

    async def test_nonzero_mutation_cannot_produce_a_success_receipt(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="commit failing mutation", summary="Commit mutation",
            steps=[AgentStep(
                id="step-1", description="Commit mutation", tool="git_commit",
                arguments={"message": "Expected failure"},
            )],
        ))
        runtime._execute_tool = AsyncMock(side_effect=ToolProcessError(9))

        run = await runtime.run(
            "commit failing mutation",
            autonomy="full",
            max_retries=0,
        )

        self.assertEqual(run.status, "needs_attention")
        self.assertEqual(run.error, "ambiguous_write_outcome")
        self.assertEqual(run.current_step, 0)
        self.assertIsNotNone(run.in_flight_effect)
        self.assertFalse(run.observations[0]["ok"])
        self.assertEqual(run.observations[0]["code"], "tool_exit_9")
        self.assertEqual(run.result, "")

    async def test_content_read_uses_provider_synthesis_when_available(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="research evidence", summary="Research evidence",
            steps=[AgentStep(
                id="step-1", description="Search sources", tool="web_search",
                arguments={"query": "evidence"},
            )],
        ))
        runtime._execute_tool = AsyncMock(return_value={
            "items": [{"title": "Primary source", "url": "https://example.test/source"}],
        })
        runtime._synthesize = AsyncMock(return_value="Synthesized primary-source evidence.")

        run = await runtime.run("research evidence", max_retries=0)

        self.assertEqual(run.status, "completed")
        self.assertEqual(run.result, "Synthesized primary-source evidence.")
        runtime._synthesize.assert_awaited_once()
        self.assertIn("Primary source", run.observations[0]["result"])

    async def test_content_read_returns_evidence_receipt_when_provider_is_unavailable(self):
        runtime = self.runtime()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="research evidence", summary="Research evidence",
            steps=[AgentStep(
                id="step-1", description="Search sources", tool="web_search",
                arguments={"query": "evidence"},
            )],
        ))
        runtime._execute_tool = AsyncMock(return_value={
            "items": [{"title": "Fallback source", "url": "https://example.test/fallback"}],
        })
        runtime._synthesize = AsyncMock(side_effect=RuntimeError("provider unavailable"))

        run = await runtime.run("research evidence", max_retries=0)

        self.assertEqual(run.status, "completed")
        self.assertIn("web_search evidence", run.result)
        self.assertIn("Fallback source", run.result)
        self.assertTrue(any(
            event["stage"] == "synthesis" and event["event_type"] == "warning"
            for event in run.events
        ))

    async def test_adaptive_loop_can_add_and_execute_verification_step(self):
        runtime = self.runtime()
        runtime.workspace_root = Path(self.tempdir.name).resolve()
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="create proof", summary="Create proof",
            steps=[AgentStep(id="step-1", description="Write proof", tool="workspace_write", arguments={"path": "proof.txt", "content": "ready"})],
        ))
        runtime._continue_plan = AsyncMock(side_effect=[
            [AgentStep(id="step-2", description="Verify proof", tool="workspace_read", arguments={"path": "proof.txt"})],
            [],
        ])
        runtime._synthesize = AsyncMock(return_value="Proof created and verified.")
        run = await runtime.run("Build proof project", autonomy="full", max_steps=3)
        self.assertEqual(run.status, "completed")
        self.assertEqual([item["tool"] for item in run.observations], ["workspace_write", "workspace_read"])
        self.assertIn("ready", run.observations[1]["result"])

    def test_created_project_path_flows_into_later_git_steps(self):
        runtime = self.runtime()
        runtime.workspace_root = Path(self.tempdir.name).resolve()
        project = runtime.workspace_root / "projects" / "agent-power-proof"
        project.mkdir(parents=True)
        run = type("Run", (), {
            "workspace_root": str(runtime.workspace_root),
            "observations": [{
                "tool": "project_create", "ok": True,
                "data": {"path": "projects/agent-power-proof"},
            }],
        })()
        step = AgentStep(
            id="step-2", description="Initialize git", tool="git_init",
            arguments={"path": "Agent Power Proof"},
        )
        runtime._resolve_step_context(run, step)
        self.assertEqual(step.arguments["path"], "projects/agent-power-proof")

    async def test_run_persists_and_loads_after_restart(self):
        database = Path(self.tempdir.name) / "agent.db"
        runtime = AgentRuntime(FakeJarvis(), database)
        runtime._create_plan = AsyncMock(return_value=AgentPlan(
            goal="persist", summary="Persist run",
            steps=[AgentStep(id="step-1", description="Reason")],
        ))
        runtime._synthesize = AsyncMock(return_value="Persisted.")
        run = await runtime.run("persist")

        recovered = AgentRuntime(FakeJarvis(), database)
        await recovered.start()
        try:
            self.assertEqual(recovered.get_run(run.id).result, "Persisted.")
            self.assertEqual(recovered.get_run(run.id).status, "completed")
        finally:
            await recovered.shutdown()


if __name__ == "__main__":
    unittest.main()
