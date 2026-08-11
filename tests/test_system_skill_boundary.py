"""Security boundary tests for the legacy system diagnostics skill."""

import asyncio
import importlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api import server
from src.skills.code import CodeSkill
from src.skills.registry import SkillRegistry
from src.skills.system import SystemSkill


def test_system_skill_rejects_direct_shell_execution() -> None:
    skill = SystemSkill()

    with pytest.raises(PermissionError, match="guarded command_run"):
        asyncio.run(skill.execute({"action": "shell", "command": "echo bypass"}))


def test_chat_language_cannot_auto_select_shell_execution() -> None:
    skill = SystemSkill()

    assert skill._detect_action("run this shell command") == "info"


def test_generic_skill_api_denies_code_execution(monkeypatch) -> None:
    registry = SkillRegistry()
    registry.register(CodeSkill())
    monkeypatch.setattr(server, "jarvis", SimpleNamespace(skills=registry))

    with pytest.raises(HTTPException) as captured:
        asyncio.run(
            server.execute_skill(
                "code",
                server.ExecuteSkillRequest(
                    params={"language": "python", "code": "print('bypass')"}
                ),
            )
        )

    assert captured.value.status_code == 403
    assert captured.value.detail == "Skill action is outside the guarded capability boundary"


def test_direct_public_dispatch_denies_code_execution() -> None:
    registry = SkillRegistry()
    registry.register(CodeSkill())

    with pytest.raises(PermissionError, match="guarded AgentRuntime"):
        asyncio.run(
            registry.execute(
                "code", {"language": "python", "code": "print('bypass')"}
            )
        )


def test_code_skill_itself_fails_closed() -> None:
    with pytest.raises(PermissionError, match="guarded command_run"):
        asyncio.run(CodeSkill().execute({"code": "print('bypass')"}))


def test_generic_skill_api_preserves_read_only_system_diagnostics(monkeypatch) -> None:
    registry = SkillRegistry()
    registry.register(SystemSkill())
    monkeypatch.setattr(server, "jarvis", SimpleNamespace(skills=registry))

    response = asyncio.run(
        server.execute_skill(
            "system", server.ExecuteSkillRequest(params={"action": "uptime"})
        )
    )

    assert "Uptime" in response["result"]


def test_generic_skill_api_rejects_non_diagnostic_system_action(monkeypatch) -> None:
    registry = SkillRegistry()
    registry.register(SystemSkill())
    monkeypatch.setattr(server, "jarvis", SimpleNamespace(skills=registry))

    with pytest.raises(HTTPException) as captured:
        asyncio.run(
            server.execute_skill(
                "system",
                server.ExecuteSkillRequest(
                    params={"action": "shell", "command": "echo bypass"}
                ),
            )
        )

    assert captured.value.status_code == 403


def test_legacy_ui_skill_dispatch_uses_the_same_read_only_boundary(monkeypatch) -> None:
    legacy_ui = importlib.import_module("src.ui.app")
    registry = SkillRegistry()
    registry.register(CodeSkill())
    monkeypatch.setattr(legacy_ui, "jarvis", SimpleNamespace(skills=registry))

    with pytest.raises(HTTPException) as captured:
        asyncio.run(
            legacy_ui.execute_skill(
                "code", {"language": "python", "code": "print('bypass')"}
            )
        )

    assert captured.value.status_code == 403
    assert captured.value.detail == "Skill action is outside the guarded capability boundary"
