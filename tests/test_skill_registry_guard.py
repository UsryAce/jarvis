from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from src.skills.registry import Skill, SkillRegistry


class _RecordingSkill(Skill):
    def __init__(self, name: str, trigger: str, result: str):
        super().__init__()
        self.name = name
        self.triggers = [trigger]
        self.result = result
        self.calls = 0

    async def execute(self, params, context=None):
        del params, context
        self.calls += 1
        return self.result


@pytest.mark.asyncio
async def test_legacy_file_and_code_skills_never_auto_execute_from_chat():
    registry = SkillRegistry()
    files = _RecordingSkill("files", "delete", "deleted")
    code = _RecordingSkill("code", "python", "executed")
    registry.skills = {"file_operations": files, "code_execution": code}

    assert await registry.execute_if_applicable("delete a file", object()) == ""
    assert await registry.execute_if_applicable("run this python code", object()) == ""
    assert files.calls == 0
    assert code.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("name", "trigger", "message"),
    (
        ("calendar", "schedule", "schedule a meeting"),
        ("email", "email", "email the report"),
        ("memory", "remember", "remember this secret"),
        ("note", "note", "take a note"),
        ("productivity", "todo", "add a todo"),
        ("reminder", "remind", "remind me tomorrow"),
    ),
)
async def test_mutating_skills_never_auto_execute_from_chat(name, trigger, message):
    registry = SkillRegistry()
    mutating = _RecordingSkill(name, trigger, "mutated")
    registry.skills = {name: mutating}

    assert await registry.execute_if_applicable(message, object()) == ""
    assert mutating.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    (
        "knowledge", "news", "search", "trading", "translation", "weather",
        "web_search",
    ),
)
async def test_external_provider_skills_never_auto_execute_from_chat(name):
    registry = SkillRegistry()
    provider = _RecordingSkill(name, name, "provider result")
    registry.skills = {name: provider}

    assert await registry.execute_if_applicable(f"use {name}", object()) == ""
    assert provider.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    (
        "code", "files", "calendar", "email", "knowledge", "memory", "news",
        "note", "productivity", "reminder", "search", "trading", "translation",
        "weather", "web_search",
    ),
)
async def test_consequential_skills_are_denied_by_direct_public_dispatch(name):
    registry = SkillRegistry()
    consequential = _RecordingSkill(name, name, "executed")
    registry.skills = {name: consequential}

    with pytest.raises(PermissionError, match="guarded AgentRuntime"):
        await registry.execute_read_only(name, {"action": "mutate"})
    assert consequential.calls == 0


@pytest.mark.asyncio
async def test_unreviewed_skill_is_default_denied_for_public_and_chat_dispatch():
    registry = SkillRegistry()
    unreviewed = _RecordingSkill("future_plugin", "future", "executed")
    registry.skills = {"future_plugin": unreviewed}

    with pytest.raises(PermissionError, match="guarded AgentRuntime"):
        await registry.execute_read_only("future_plugin", {})
    assert await registry.execute_if_applicable("future action", object()) == ""
    assert unreviewed.calls == 0


@pytest.mark.asyncio
async def test_owned_internal_dispatch_remains_available_to_guarded_runtime():
    registry = SkillRegistry()
    note = _RecordingSkill("note", "note", "created through guarded tool")
    registry.skills = {"note": note}
    jarvis = SimpleNamespace(skills=registry)

    result = await registry.execute("note", {"action": "create"}, jarvis)

    assert result == "created through guarded tool"
    assert note.calls == 1


@pytest.mark.asyncio
async def test_read_only_conversational_skill_can_still_auto_execute():
    registry = SkillRegistry()
    calculator = _RecordingSkill("calculator", "calculate", "four")
    registry.skills = {"calculator": calculator}

    result = await registry.execute_if_applicable("calculate two plus two", object())

    assert result == "[calculator] four"
    assert calculator.calls == 1


@pytest.mark.asyncio
async def test_auto_dispatch_logs_exception_type_without_exception_text(caplog):
    secret = "provider-secret-should-not-be-logged"

    class _FailingCalculator(_RecordingSkill):
        async def execute(self, params, context=None):
            del params, context
            raise RuntimeError(secret)

    registry = SkillRegistry()
    registry.skills = {
        "calculator": _FailingCalculator("calculator", "calculate", "unused")
    }

    with caplog.at_level(logging.ERROR, logger="src.skills.registry"):
        assert await registry.execute_if_applicable("calculate this", object()) == ""

    assert "RuntimeError" in caplog.text
    assert secret not in caplog.text
