"""Skills Registry for Jarvis."""
import asyncio
import importlib
import inspect
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


class Skill:
    """Base skill class."""

    name: str = ""
    description: str = ""
    triggers: List[str] = []
    parameters: Dict = {}

    def __init__(self, jarvis=None):
        self.jarvis = jarvis

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        """Execute the skill."""
        raise NotImplementedError

    def matches(self, text: str) -> bool:
        """Check if skill matches input text."""
        text_lower = text.lower()
        return any(trigger.lower() in text_lower for trigger in self.triggers)


class SkillRegistry:
    """Registry for managing skills."""

    # These legacy skills combine matching, parameter inference, and mutation in
    # one unguarded call. Chat may still use read-only conversational skills, but
    # file/code work must go through AgentRuntime's workspace and approval gates.
    AUTO_EXECUTION_BLOCKED_SKILLS = frozenset({
        "files", "file_operations", "code", "code_execution",
    })

    def __init__(self):
        self.skills: Dict[str, Skill] = {}
        self._loaded = False

    async def load_skills(self, skill_names: List[str]):
        """Load skills by name."""
        for name in skill_names:
            try:
                await self.load_skill(name)
            except Exception as e:
                logger.error(f"Failed to load skill {name}: {e}")

    async def load_skill(self, name: str):
        """Load a single skill."""
        if name in self.skills:
            return

        # Try to import from skills package
        try:
            module = importlib.import_module(f"src.skills.{name}")
            skill_class = getattr(module, f"{name.title().replace('_', '')}Skill", None)
            if not skill_class:
                # Try to find any Skill subclass
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if inspect.isclass(attr) and issubclass(attr, Skill) and attr != Skill:
                        skill_class = attr
                        break

            if skill_class:
                skill = skill_class()
                self.skills[name] = skill
                logger.info(f"Loaded skill: {name}")
            else:
                logger.warning(f"No Skill class found in src.skills.{name}")

        except ImportError as e:
            logger.warning(f"Could not import skill {name}: {e}")

    def register(self, skill: Skill):
        """Register a skill instance."""
        self.skills[skill.name] = skill

    def unregister(self, name: str):
        """Unregister a skill."""
        if name in self.skills:
            del self.skills[name]

    def get(self, name: str) -> Optional[Skill]:
        """Get skill by name."""
        return self.skills.get(name)

    def list_skills(self) -> List[str]:
        """List all loaded skills."""
        return list(self.skills.keys())

    async def execute(self, name: str, params: Dict, jarvis=None) -> Any:
        """Execute a skill by name."""
        skill = self.skills.get(name)
        if not skill:
            raise ValueError(f"Skill not found: {name}")

        skill.jarvis = jarvis
        return await skill.execute(params, {"jarvis": jarvis})

    async def execute_if_applicable(self, text: str, jarvis) -> str:
        """Execute first matching skill."""
        for name, skill in self.skills.items():
            identities = {str(name).casefold(), str(skill.name or "").casefold()}
            if identities.intersection(self.AUTO_EXECUTION_BLOCKED_SKILLS):
                logger.debug("Skipped guarded legacy skill during automatic chat matching: %s", name)
                continue
            if skill.matches(text):
                try:
                    skill.jarvis = jarvis
                    result = await skill.execute({}, {"jarvis": jarvis, "text": text})
                    if result:
                        return f"[{name}] {result}"
                except Exception as e:
                    logger.error(f"Skill {name} failed: {e}")
        return ""


# Decorator for easy skill creation
def skill(name: str, description: str = "", triggers: List[str] = None):
    """Decorator to create a skill from a function."""
    def decorator(func: Callable):
        class DynamicSkill(Skill):
            def __init__(self, jarvis=None):
                super().__init__(jarvis)
                self.name = name
                self.description = description
                self.triggers = triggers or [name]

            async def execute(self, params: Dict, context: Dict = None):
                return await func(params, context)

        return DynamicSkill

    return decorator
