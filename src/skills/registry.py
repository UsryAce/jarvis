"""Skills Registry for Jarvis."""
import importlib
import inspect
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReadOnlySkillPolicy:
    """Explicit contract for legacy skills safe outside AgentRuntime guards."""

    allow_chat_auto_route: bool = True
    allowed_actions: frozenset[str] | None = None
    default_action: str | None = None


# Absence from this map is an intentional deny.  A newly loaded skill must be
# reviewed as read-only before either the generic API or chat matching can run
# it.  Skills that mix reads with mutation remain behind AgentRuntime tools.
READ_ONLY_SKILL_POLICIES: dict[str, ReadOnlySkillPolicy] = {
    "business": ReadOnlySkillPolicy(),
    "calculator": ReadOnlySkillPolicy(),
    "design": ReadOnlySkillPolicy(),
    "education": ReadOnlySkillPolicy(),
    "system": ReadOnlySkillPolicy(
        allowed_actions=frozenset({
            "info", "cpu", "memory", "disk", "processes", "uptime", "network",
        }),
        default_action="info",
    ),
    "time_date": ReadOnlySkillPolicy(),
}


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
        """Execute read-only by default or from the owning Jarvis runtime."""
        if jarvis is None or getattr(jarvis, "skills", None) is not self:
            # An unowned registry call has no evidence that it entered through
            # an AgentRuntime tool, so apply the default-deny public policy.
            self.require_read_only_execution(name, params)
        skill = self.skills.get(name)
        if not skill:
            raise ValueError(f"Skill not found: {name}")

        skill.jarvis = jarvis
        return await skill.execute(params, {"jarvis": jarvis})

    def require_read_only_execution(self, name: str, params: Dict) -> Skill:
        """Authorize a generic caller only for an explicitly read-only skill."""
        skill = self.skills.get(name)
        if not skill:
            raise ValueError(f"Skill not found: {name}")

        requested_name = str(name).strip().casefold()
        declared_name = str(skill.name or "").strip().casefold()
        policy = READ_ONLY_SKILL_POLICIES.get(requested_name)
        if requested_name != declared_name or policy is None:
            raise PermissionError(
                "Skill requires a guarded AgentRuntime capability"
            )

        if not isinstance(params, dict):
            raise PermissionError("Skill parameters must be a mapping")
        if policy.allowed_actions is not None:
            raw_action = params.get("action", policy.default_action)
            if not isinstance(raw_action, str):
                raise PermissionError("Skill action is not read-only")
            action = raw_action.strip().casefold()
            if action not in policy.allowed_actions:
                raise PermissionError("Skill action is not read-only")
        return skill

    async def execute_read_only(self, name: str, params: Dict, jarvis=None) -> Any:
        """Execute the public generic-skill surface after default-deny review."""
        self.require_read_only_execution(name, params)
        return await self.execute(name, params, jarvis)

    async def execute_if_applicable(self, text: str, jarvis) -> str:
        """Execute the first explicitly read-only matching skill."""
        for name, skill in self.skills.items():
            requested_name = str(name).strip().casefold()
            declared_name = str(skill.name or "").strip().casefold()
            policy = READ_ONLY_SKILL_POLICIES.get(requested_name)
            if (
                requested_name != declared_name
                or policy is None
                or not policy.allow_chat_auto_route
            ):
                logger.debug(
                    "Skipped non-read-only skill during automatic chat matching: %s",
                    name,
                )
                continue
            if skill.matches(text):
                try:
                    skill.jarvis = jarvis
                    result = await skill.execute({}, {"jarvis": jarvis, "text": text})
                    if result:
                        return f"[{name}] {result}"
                except Exception as exc:
                    logger.error(
                        "Skill %s failed with %s", name, type(exc).__name__
                    )
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
