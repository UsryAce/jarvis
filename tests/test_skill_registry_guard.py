from __future__ import annotations

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
async def test_read_only_conversational_skill_can_still_auto_execute():
    registry = SkillRegistry()
    weather = _RecordingSkill("weather", "weather", "clear skies")
    registry.skills = {"weather": weather}

    result = await registry.execute_if_applicable("what is the weather?", object())

    assert result == "[weather] clear skies"
    assert weather.calls == 1
