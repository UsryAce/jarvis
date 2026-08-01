"""Wave-0 contracts for the single governed execution gateway.

The production gateway is delivered by later Phase 2 plans.  The live tests in
this module pin its ordering, audit, receipt, and fail-closed boundary now; the
module gates activate independently as those implementation slices land.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from src.api import server
from src.security import auth


APP_ORIGIN = "http://localhost:4173"
GATE_ERROR = {
    "code": "phase_2_execution_gate_closed",
    "message": (
        "Direct code execution is locked; execution must flow through the Phase 2 "
        "governed execution broker when it is available."
    ),
    "retryable": False,
    "applied": False,
}
REQUIRED_AUDIT_ORDER = (
    "execution.proposed",
    "execution.resolved",
    "execution.policy_decided",
    "execution.effect_reserved",
    "execution.dispatch_started",
    "execution.dispatch_finished",
    "execution.receipt_persisted",
)
DEFERRED_IDENTITIES = ("github_write", "autonomous_project_write")
SAFE_RECEIPT_FIELDS = {
    "receipt_id",
    "request_id",
    "tool_id",
    "action_digest",
    "effect_idempotency_key",
    "policy_outcome",
    "effect_state",
    "applied",
    "reason_code",
}


def _future_module(name: str, owner: str):
    """Import a future slice or skip only when that exact slice is absent."""
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if name == exc.name or name.startswith(f"{exc.name}."):
            pytest.skip(f"{owner} future-module gate: {name} is not implemented yet")
        raise


@dataclass
class _ReferenceGateway:
    """Small executable oracle for the ordering contract, not production code."""

    audit: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    adapter_calls: list[dict[str, Any]] = field(default_factory=list)

    def _event(self, name: str, **safe: Any) -> None:
        self.audit.append((name, safe))

    def execute(self, proposal: dict[str, Any]) -> dict[str, Any]:
        request_id = proposal["request_id"]
        tool_id = proposal["tool_id"]
        digest = proposal["action_digest"]
        self._event("execution.proposed", request_id=request_id, tool_id=tool_id)
        self._event("execution.resolved", request_id=request_id, action_digest=digest)
        if tool_id in DEFERRED_IDENTITIES:
            self._event(
                "execution.policy_decided",
                request_id=request_id,
                outcome="deny",
                reason_code="capability_not_activated",
            )
            return {
                "receipt_id": f"receipt:{request_id}",
                "request_id": request_id,
                "tool_id": tool_id,
                "action_digest": digest,
                "effect_idempotency_key": proposal["effect_idempotency_key"],
                "policy_outcome": "deny",
                "effect_state": "not_applied",
                "applied": False,
                "reason_code": "capability_not_activated",
            }

        self._event("execution.policy_decided", request_id=request_id, outcome="allow")
        self._event("execution.effect_reserved", request_id=request_id)
        self._event("execution.dispatch_started", request_id=request_id)
        self.adapter_calls.append({"tool_id": tool_id, "arguments": proposal["arguments"]})
        self._event("execution.dispatch_finished", request_id=request_id, applied=True)
        receipt = {
            "receipt_id": f"receipt:{request_id}",
            "request_id": request_id,
            "tool_id": tool_id,
            "action_digest": digest,
            "effect_idempotency_key": proposal["effect_idempotency_key"],
            "policy_outcome": "allow",
            "effect_state": "applied",
            "applied": True,
            "reason_code": "executed",
        }
        self._event("execution.receipt_persisted", request_id=request_id)
        return receipt


def _proposal(tool_id: str = "fixture.write") -> dict[str, Any]:
    return {
        "request_id": "request-001",
        "tool_id": tool_id,
        "action_digest": "sha256:action-digest",
        "effect_idempotency_key": "sha256:effect-key",
        "arguments": {"path": "workspace/result.txt", "content": "secret-canary"},
    }


def test_reference_fixture_executes_once_with_safe_receipt_and_exact_audit_order():
    gateway = _ReferenceGateway()

    receipt = gateway.execute(_proposal())

    assert [name for name, _ in gateway.audit] == list(REQUIRED_AUDIT_ORDER)
    assert len(gateway.adapter_calls) == 1
    assert set(receipt) == SAFE_RECEIPT_FIELDS
    assert receipt["applied"] is True
    assert receipt["effect_state"] == "applied"
    serialized = json.dumps({"receipt": receipt, "audit": gateway.audit})
    assert "secret-canary" not in serialized
    assert "workspace/result.txt" not in serialized


@pytest.mark.parametrize("tool_id", DEFERRED_IDENTITIES)
def test_deferred_capability_identities_remain_closed_without_dispatch(tool_id: str):
    gateway = _ReferenceGateway()

    receipt = gateway.execute(_proposal(tool_id))

    assert gateway.adapter_calls == []
    assert receipt["policy_outcome"] == "deny"
    assert receipt["reason_code"] == "capability_not_activated"
    assert receipt["effect_state"] == "not_applied"
    assert [name for name, _ in gateway.audit] == [
        "execution.proposed",
        "execution.resolved",
        "execution.policy_decided",
    ]


def test_future_gateway_exports_one_narrow_verifier_only_entrypoint():
    gateway_module = _future_module(
        "src.core.execution_gateway", "Plan 02-12 single-gateway cutover"
    )
    gateway_type = gateway_module.ExecutionGateway
    signature = inspect.signature(gateway_type.__init__)

    assert "approval_verifier" in signature.parameters
    forbidden = {"approval_issuer", "approval_signer", "private_key", "mint_approval"}
    assert forbidden.isdisjoint(signature.parameters)
    execute = inspect.signature(gateway_type.execute)
    assert {"context", "proposal"}.issubset(execute.parameters)


def test_future_gateway_dependencies_exist_before_integration_contract_activates():
    required = {
        "src.security.action_contracts": "Plan 02-07 canonical action contracts",
        "src.security.manifests": "Plan 02-07 manifest resolution",
        "src.security.policy": "Plan 02-07 policy kernel",
        "src.security.approvals": "Plan 02-09 approval verifier",
        "src.core.capability_store": "Plan 02-08 durable capability store",
        "src.execution.receipts": "Plan 02-08 safe execution receipts",
        "src.core.execution_gateway": "Plan 02-12 single-gateway cutover",
    }
    for module_name, owner in required.items():
        _future_module(module_name, owner)


def test_raw_code_route_rejects_malformed_and_oversized_bodies_before_any_sink(
    isolated_control_path,
    fake_clock,
    operator_session_factory,
    monkeypatch,
):
    app = server.create_app(
        control_path=isolated_control_path,
        clock=fake_clock.now,
        allowed_origins=(APP_ORIGIN,),
        testing=True,
    )
    material = operator_session_factory(scopes=(auth.OPERATOR_EXECUTE,))
    app.state.session_service.configure_bootstrap(material.bootstrap_secret)
    issued = app.state.session_service.create_session(
        material.bootstrap_secret,
        actor_id=material.actor_id,
        scopes=material.scopes,
    )
    sink_calls: list[str] = []

    async def deny_async_process(*_args: Any, **_kwargs: Any):
        sink_calls.append("asyncio.create_subprocess_exec")
        raise AssertionError("raw execution route reached a subprocess sink")

    def deny_sync_sink(*_args: Any, **_kwargs: Any):
        sink_calls.append("sync execution sink")
        raise AssertionError("raw execution route reached a synchronous sink")

    bodies = (
        b'{"code":"unterminated',
        json.dumps({"code": "canary" + "x" * 30_000}).encode(),
    )
    with TestClient(app) as client:
        client.cookies.set(auth.SESSION_COOKIE_NAME, issued.cookie)
        monkeypatch.setattr(asyncio, "create_subprocess_exec", deny_async_process)
        monkeypatch.setattr(subprocess, "run", deny_sync_sink)
        monkeypatch.setattr(subprocess, "Popen", deny_sync_sink)
        if hasattr(os, "startfile"):
            monkeypatch.setattr(os, "startfile", deny_sync_sink)
        for body in bodies:
            response = client.post(
                "/api/code/execute",
                headers={
                    "Origin": APP_ORIGIN,
                    auth.CSRF_HEADER_NAME: issued.csrf_token,
                    "Content-Type": "application/json",
                },
                content=body,
            )
            assert response.status_code == 423
            assert response.json() == GATE_ERROR
            assert "canary" not in response.text

    assert sink_calls == []
