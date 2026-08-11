"""Legacy code skill retained as a fail-closed compatibility boundary.

Code and command execution is implemented by AgentRuntime's ``command_run``
tool, which supplies workspace confinement, approval challenges, and receipts.
The legacy skill must never start an interpreter directly.
"""
from typing import Any, Dict

from src.skills.registry import Skill


class CodeSkill(Skill):
    """Reject unguarded code execution from generic skill dispatch."""

    name = "code"
    description = "Code execution through the guarded AgentRuntime command tool"
    triggers = [
        "run", "execute", "code", "python", "javascript", "bash", "script",
    ]

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        """Require callers to use the guarded command execution capability."""
        del params, context
        raise PermissionError(
            "Code execution is available only through the guarded command_run tool"
        )
