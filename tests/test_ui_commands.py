"""Isolated contracts for the live dashboard command endpoint."""

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, call, patch

from fastapi import HTTPException

from src.api.ui_routes import (
    UIApprovalDecision,
    UICommand,
    approve_agent_current_step,
    approve_swarm_current_steps,
    cancel_agent_run,
    cancel_swarm_run,
    command,
    decide_approval,
)
from src.security.auth import (
    APPROVALS_WRITE,
    EMERGENCY_STOP,
    OPERATOR_EXECUTE,
    RUNS_CONTROL,
)


class UICommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.workspace = Path("C:/workspace/projects/aurora")
        self.workspace_registry = SimpleNamespace(resolve=Mock(return_value=self.workspace))
        self.agent_runtime = SimpleNamespace(
            submit=AsyncMock(return_value=SimpleNamespace(id="agent-new")),
            approve=AsyncMock(),
            cancel=Mock(),
            get_run=Mock(return_value=None),
            list_runs=Mock(return_value=[]),
        )
        self.swarm_runtime = SimpleNamespace(
            submit=AsyncMock(return_value=SimpleNamespace(id="swarm-new")),
            resume=AsyncMock(),
            cancel=Mock(),
            get_run=Mock(return_value=None),
            list_runs=Mock(return_value=[]),
        )
        self.jarvis = SimpleNamespace(
            workspace_registry=self.workspace_registry,
            agent_runtime=self.agent_runtime,
            swarm_runtime=self.swarm_runtime,
            chat=AsyncMock(return_value="Live JARVIS response"),
            _get_live_model_catalog=AsyncMock(return_value={"z-ai/glm-5.2"}),
            _model_catalog={"z-ai/glm-5.2"},
        )
        running = SimpleNamespace(state=SimpleNamespace(value="running"), revision=1)
        self.control_service = SimpleNamespace(
            snapshot=Mock(return_value=running),
            transition=Mock(return_value=SimpleNamespace(
                state=SimpleNamespace(value="paused"), revision=2,
            )),
            record_runtime_event=Mock(return_value="audit-screen"),
        )
        self.principal = SimpleNamespace(
            actor_id="operator-ahmed",
            session_digest="session-digest",
            scopes=(OPERATOR_EXECUTE, APPROVALS_WRITE, RUNS_CONTROL, EMERGENCY_STOP),
        )
        self.request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(
                jarvis=self.jarvis,
                control_service=self.control_service,
            )),
        )

    async def invoke(self, action: str, payload: dict | None = None):
        return await command(
            UICommand(action=action, payload=payload),
            self.request,
            principal=self.principal,
            _mutation_guard=None,
        )

    async def test_submit_goal_resolves_project_and_passes_workspace_to_agent(self) -> None:
        response = await self.invoke("submit_goal", {
            "goal": "Build the Aurora website",
            "projectId": "aurora",
            "autonomy": "full",
            "model": "z-ai/glm-5.2",
            "dispatch": "agent",
            "maxSteps": 6,
        })

        self.workspace_registry.resolve.assert_called_once_with("aurora")
        self.agent_runtime.submit.assert_awaited_once_with(
            "Build the Aurora website",
            model="z-ai/glm-5.2",
            autonomy="full",
            max_steps=6,
            workspace_root=self.workspace,
        )
        self.swarm_runtime.submit.assert_not_awaited()
        self.assertEqual(response["runId"], "agent-new")

    async def test_submit_goal_honors_cowork_dispatch_and_validated_limits(self) -> None:
        response = await self.invoke("submit_goal", {
            "goal": "Audit and repair the application",
            "projectId": "aurora",
            "autonomy": "guarded",
            "model": "auto",
            "dispatch": "cowork",
            "maxAgents": 5,
            "maxRuntimeSeconds": 900,
        })

        self.workspace_registry.resolve.assert_called_once_with("aurora")
        self.swarm_runtime.submit.assert_awaited_once_with(
            "Audit and repair the application",
            mode="cowork",
            project_id="aurora",
            autonomy="guarded",
            model="auto",
            max_agents=5,
            max_runtime_seconds=900,
        )
        self.agent_runtime.submit.assert_not_awaited()
        self.assertEqual(response["runId"], "swarm-new")

    async def test_submit_goal_rejects_unknown_project(self) -> None:
        self.workspace_registry.resolve.side_effect = KeyError("missing")

        with self.assertRaises(HTTPException) as raised:
            await self.invoke("submit_goal", {
                "goal": "Build it",
                "projectId": "missing",
            })

        self.assertEqual(raised.exception.status_code, 404)
        self.agent_runtime.submit.assert_not_awaited()
        self.swarm_runtime.submit.assert_not_awaited()

    async def test_submit_goal_rejects_invalid_autonomy(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            await self.invoke("submit_goal", {
                "goal": "Build it",
                "projectId": "aurora",
                "autonomy": "unrestricted",
            })

        self.assertEqual(raised.exception.status_code, 422)
        self.agent_runtime.submit.assert_not_awaited()
        self.swarm_runtime.submit.assert_not_awaited()

    async def test_submit_goal_rejects_non_integer_limits(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            await self.invoke("submit_goal", {
                "goal": "Build it",
                "projectId": "aurora",
                "maxAgents": "many",
            })

        self.assertEqual(raised.exception.status_code, 422)
        self.agent_runtime.submit.assert_not_awaited()
        self.swarm_runtime.submit.assert_not_awaited()

    async def test_approve_agent_run_approves_only_current_pending_step(self) -> None:
        steps = [
            SimpleNamespace(id="step-1"),
            SimpleNamespace(id="step-2"),
            SimpleNamespace(id="step-3"),
        ]
        pending = SimpleNamespace(
            id="agent-1",
            status="awaiting_confirmation",
            current_step=1,
            plan=SimpleNamespace(steps=steps),
        )
        resumed = SimpleNamespace(id="agent-1", status="running")
        self.agent_runtime.get_run.return_value = pending
        self.agent_runtime.approve.return_value = resumed

        response = await approve_agent_current_step(
            "agent-1", self.request, _principal=None, _mutation_guard=None,
        )

        self.agent_runtime.approve.assert_awaited_once_with("agent-1", ["step-2"])
        self.assertEqual(response["status"], "running")

    async def test_cancel_agent_run_requests_runtime_cancellation(self) -> None:
        self.agent_runtime.cancel.return_value = SimpleNamespace(id="agent-1", status="stopping")

        response = await cancel_agent_run(
            "agent-1", self.request, _principal=None, _mutation_guard=None,
        )

        self.agent_runtime.cancel.assert_called_once_with("agent-1")
        self.assertEqual(response["status"], "stopping")

    async def test_approve_swarm_run_advances_each_child_current_step_then_resumes(self) -> None:
        swarm = SimpleNamespace(
            id="swarm-1",
            status="awaiting_confirmation",
            tasks={
                "task-a": SimpleNamespace(
                    status="awaiting_confirmation", agent_run_id="agent-a",
                ),
                "task-b": SimpleNamespace(
                    status="awaiting_confirmation", agent_run_id="agent-b",
                ),
                "task-done": SimpleNamespace(
                    status="completed", agent_run_id="agent-done",
                ),
            },
        )
        agents = {
            "agent-a": SimpleNamespace(
                id="agent-a",
                status="awaiting_confirmation",
                current_step=1,
                plan=SimpleNamespace(steps=[
                    SimpleNamespace(id="a-1"), SimpleNamespace(id="a-2"),
                    SimpleNamespace(id="a-3"),
                ]),
            ),
            "agent-b": SimpleNamespace(
                id="agent-b",
                status="awaiting_confirmation",
                current_step=0,
                plan=SimpleNamespace(steps=[
                    SimpleNamespace(id="b-1"), SimpleNamespace(id="b-2"),
                ]),
            ),
        }
        self.swarm_runtime.get_run.return_value = swarm
        self.agent_runtime.get_run.side_effect = agents.get
        self.agent_runtime.approve.side_effect = lambda run_id, _steps: agents[run_id]
        self.swarm_runtime.resume.return_value = SimpleNamespace(id="swarm-1", status="running")

        response = await approve_swarm_current_steps(
            "swarm-1", self.request, _principal=None, _mutation_guard=None,
        )

        self.agent_runtime.approve.assert_has_awaits([
            call("agent-a", ["a-2"]),
            call("agent-b", ["b-1"]),
        ])
        self.assertEqual(self.agent_runtime.approve.await_count, 2)
        self.swarm_runtime.resume.assert_awaited_once_with("swarm-1")
        self.assertEqual(response["status"], "running")

    async def test_cancel_swarm_run_requests_runtime_cancellation(self) -> None:
        self.swarm_runtime.cancel.return_value = SimpleNamespace(id="swarm-1", status="stopping")

        response = await cancel_swarm_run(
            "swarm-1", self.request, _principal=None, _mutation_guard=None,
        )

        self.swarm_runtime.cancel.assert_called_once_with("swarm-1")
        self.assertEqual(response["status"], "stopping")

    async def test_new_router_aliases_update_validated_preferences(self) -> None:
        with patch("src.api.ui_routes._write_preferences") as write:
            route = await self.invoke("set_route", {"modelId": "z-ai/glm-5.2"})
            auto = await self.invoke("set_auto_route", {"auto": False})

        self.assertTrue(route["ok"])
        self.assertTrue(auto["ok"])
        self.assertEqual(write.call_args_list, [
            call({"primary_model": "z-ai/glm-5.2"}),
            call({"auto_mode": False}),
        ])

    async def test_auto_route_rejects_truthy_non_boolean(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            await self.invoke("set_auto_route", {"auto": "false"})
        self.assertEqual(raised.exception.status_code, 422)

    async def test_autonomy_alias_persists_level_without_claiming_policy_bypass(self) -> None:
        with patch("src.api.ui_routes._write_preferences") as write:
            response = await self.invoke("set_autonomy", {"level": 4})

        write.assert_called_once_with({"autonomy_level": 4})
        self.assertEqual(response["level"], 4)
        self.assertIn("remain enforced", response["message"])

    async def test_autonomy_rejects_boolean_and_out_of_range_level(self) -> None:
        for level in (True, 0, 5, "4"):
            with self.subTest(level=level), self.assertRaises(HTTPException) as raised:
                await self.invoke("set_autonomy_level", {"level": level})
            self.assertEqual(raised.exception.status_code, 422)

    async def test_voice_aliases_and_push_to_talk_are_explicit(self) -> None:
        with patch("src.api.ui_routes._write_preferences") as write:
            armed = await self.invoke("voice_arm")
            disarmed = await self.invoke("voice_disarm")
        ptt = await self.invoke("push_to_talk", {"ms": 6_000})

        self.assertEqual(write.call_args_list, [
            call({"auto_mic": True}), call({"auto_mic": False}),
        ])
        self.assertTrue(armed["ok"] and disarmed["ok"])
        self.assertEqual(ptt["captureMs"], 6_000)
        self.assertEqual(ptt["transcribePath"], "/api/voice/transcribe")

    async def test_send_message_dispatches_a_durable_preference_routed_agent(self) -> None:
        with patch("src.api.ui_routes._read_preferences", return_value={
            "autonomy_level": 4,
            "auto_mode": False,
            "primary_model": "z-ai/glm-5.2",
        }):
            response = await self.invoke("send_message", {"text": "Build the approved site"})

        self.workspace_registry.resolve.assert_called_once_with("jarvis")
        self.agent_runtime.submit.assert_awaited_once_with(
            "Build the approved site",
            model="z-ai/glm-5.2",
            autonomy="full",
            max_steps=8,
            workspace_root=self.workspace,
        )
        self.assertEqual(response["runId"], "agent-new")

    async def test_open_screen_and_quick_actions_return_real_client_instructions(self) -> None:
        opened = await self.invoke("open_screen", {"key": "brain"})
        quick = await self.invoke("quick_command", {"name": "file search"})

        self.assertEqual(opened["screen"], "BRAIN")
        self.assertEqual(opened["auditId"], "audit-screen")
        self.control_service.record_runtime_event.assert_called_once()
        self.assertEqual(quick["screen"], "FILES")
        with self.assertRaises(HTTPException) as raised:
            await self.invoke("open_screen", {"key": "made-up"})
        self.assertEqual(raised.exception.status_code, 422)

    async def test_hold_and_release_use_only_run_scoped_control(self) -> None:
        self.agent_runtime.list_runs.return_value = [{"id": "agent-1", "status": "running"}]
        global_running = SimpleNamespace(state=SimpleNamespace(value="running"), revision=1)
        run_running = SimpleNamespace(state=SimpleNamespace(value="running"), revision=1)
        self.control_service.snapshot.side_effect = lambda *args: run_running if args else global_running
        self.control_service.transition.return_value = SimpleNamespace(
            state=SimpleNamespace(value="paused"), revision=2,
        )

        response = await self.invoke("hold")

        transition = self.control_service.transition.call_args.args[0]
        self.assertEqual((transition.action, transition.scope_type, transition.scope_id), (
            "pause", "run", "agent-1",
        ))
        self.assertEqual(response["affectedRunIds"], ["agent-1"])

        run_paused = SimpleNamespace(state=SimpleNamespace(value="paused"), revision=2)
        self.control_service.snapshot.side_effect = lambda *args: run_paused if args else global_running
        self.control_service.transition.return_value = SimpleNamespace(
            state=SimpleNamespace(value="running"), revision=3,
        )
        released = await self.invoke("release")
        reset = self.control_service.transition.call_args.args[0]
        self.assertEqual((reset.action, reset.scope_type), ("reset", "run"))
        self.assertEqual(released["affectedRunIds"], ["agent-1"])

    async def test_emergency_stop_requires_scope_and_targets_global_control(self) -> None:
        stopped = SimpleNamespace(state=SimpleNamespace(value="emergency_stopped"), revision=2)
        self.control_service.transition.return_value = stopped
        response = await self.invoke("emergency_stop")
        transition = self.control_service.transition.call_args.args[0]
        self.assertEqual((transition.action, transition.scope_type, transition.scope_id), (
            "emergency_stop", "global", "global",
        ))
        self.assertEqual(response["controlState"], "emergency_stopped")

        self.principal = SimpleNamespace(
            actor_id="operator-ahmed",
            session_digest="session-digest",
            scopes=(OPERATOR_EXECUTE,),
        )
        with self.assertRaises(HTTPException) as raised:
            await self.invoke("emergency_stop")
        self.assertEqual(raised.exception.status_code, 403)

    async def test_generic_approval_contract_targets_exact_current_agent_step(self) -> None:
        pending = SimpleNamespace(
            id="agent-approval",
            status="awaiting_confirmation",
            current_step=0,
            plan=SimpleNamespace(steps=[SimpleNamespace(id="step-1")]),
        )
        self.agent_runtime.get_run.return_value = pending
        self.swarm_runtime.get_run.return_value = None
        self.agent_runtime.approve.return_value = SimpleNamespace(
            id="agent-approval", status="running",
        )

        response = await decide_approval(
            "agent-approval",
            UIApprovalDecision(decision="approve", note="Reviewed"),
            self.request,
            principal=self.principal,
            _mutation_guard=None,
        )

        self.agent_runtime.approve.assert_awaited_once_with("agent-approval", ["step-1"])
        self.assertEqual(response["status"], "running")

    async def test_reject_contract_cancels_only_selected_run_and_needs_run_scope(self) -> None:
        pending = SimpleNamespace(id="swarm-approval", status="awaiting_confirmation")
        self.agent_runtime.get_run.return_value = None
        self.swarm_runtime.get_run.return_value = pending
        self.swarm_runtime.cancel.return_value = SimpleNamespace(
            id="swarm-approval", status="stopping",
        )

        response = await decide_approval(
            "swarm-approval",
            UIApprovalDecision(decision="reject"),
            self.request,
            principal=self.principal,
            _mutation_guard=None,
        )

        self.swarm_runtime.cancel.assert_called_once_with("swarm-approval")
        self.agent_runtime.cancel.assert_not_called()
        self.assertEqual(response["status"], "stopping")

        approval_only = SimpleNamespace(
            actor_id="operator-ahmed", session_digest="session-digest",
            scopes=(APPROVALS_WRITE,),
        )
        with self.assertRaises(HTTPException) as raised:
            await decide_approval(
                "swarm-approval",
                UIApprovalDecision(decision="reject"),
                self.request,
                principal=approval_only,
                _mutation_guard=None,
            )
        self.assertEqual(raised.exception.status_code, 403)

    async def test_generic_command_refuses_privileged_run_actions(self) -> None:
        for action in (
            "approve_agent_run", "cancel_agent_run",
            "approve_swarm_run", "cancel_swarm_run",
        ):
            with self.subTest(action=action), self.assertRaises(HTTPException) as raised:
                await self.invoke(action, {"runId": "run-1"})
            self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
