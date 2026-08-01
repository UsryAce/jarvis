"""Executable inventory and bypass guards for consequential execution sinks."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CALLER_FILES = (
    Path("src/core/agent.py"),
    Path("src/api/dashboard_routes.py"),
    Path("src/skills/code.py"),
    Path("src/skills/files.py"),
    Path("src/skills/system.py"),
)
ALLOWED_FUTURE_SINK_OWNERS = {
    Path("src/execution/local_adapters.py"),
    Path("src/execution/windows_job.py"),
    Path("src/execution/filesystem.py"),
    Path("src/browser/broker.py"),
}
PATH_MUTATIONS = {
    "write_text",
    "write_bytes",
    "mkdir",
    "unlink",
    "rename",
    "replace",
    "rmdir",
    "touch",
}
SHUTIL_MUTATIONS = {"copy", "copy2", "copytree", "move", "rmtree"}
PROCESS_CALLS = {
    "asyncio.create_subprocess_exec",
    "asyncio.create_subprocess_shell",
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
}


def _future_module(name: str, owner: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if name == exc.name or name.startswith(f"{exc.name}."):
            pytest.skip(f"{owner} future-module gate: {name} is not implemented yet")
        raise


def _call_name(node: ast.Call) -> str:
    parts: list[str] = []
    current: ast.AST = node.func
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _inventory(relative_path: Path) -> set[tuple[str, int, str]]:
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    findings: set[tuple[str, int, str]] = set()
    command_literals: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in {"git", "gh"}:
                command_literals.add(node.value)
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "startfile"
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
        ):
            findings.add(("desktop_launch", node.lineno, "os.startfile"))
            findings.add(("browser_launch", node.lineno, "os.startfile"))
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        leaf = name.rsplit(".", 1)[-1]
        if name in PROCESS_CALLS:
            findings.add(("process", node.lineno, name))
        elif name == "os.startfile":
            findings.add(("desktop_launch", node.lineno, name))
        elif name.startswith("shutil.") and leaf in SHUTIL_MUTATIONS:
            findings.add(("filesystem", node.lineno, name))
        elif leaf in PATH_MUTATIONS:
            findings.add(("filesystem", node.lineno, name))
        elif leaf in {"open_url", "open_path", "launch_browser"}:
            findings.add(("browser_launch", node.lineno, name))
    for command in command_literals:
        category = "github_cli" if command == "gh" else "git_cli"
        findings.add((category, 0, f"command:{command}"))
    return findings


def _categories(relative_path: Path) -> set[str]:
    return {category for category, _line, _name in _inventory(relative_path)}


def test_current_sink_seams_are_completely_classified_for_cutover():
    inventory = {path: _categories(path) for path in CALLER_FILES}

    assert {"process", "filesystem", "desktop_launch", "git_cli", "github_cli"} <= inventory[
        Path("src/core/agent.py")
    ]
    assert {"process", "filesystem", "desktop_launch"} <= inventory[
        Path("src/api/dashboard_routes.py")
    ]
    assert inventory[Path("src/skills/files.py")] == {"filesystem"}
    assert inventory[Path("src/skills/code.py")] == set()
    assert inventory[Path("src/skills/system.py")] == set()


def test_inventory_covers_every_consequential_sink_family_from_phase_pattern_map():
    all_categories = set().union(*(_categories(path) for path in CALLER_FILES))

    assert all_categories == {
        "process",
        "filesystem",
        "desktop_launch",
        "browser_launch",
        "git_cli",
        "github_cli",
    }


def test_compatibility_code_and_system_skills_are_fail_closed():
    from src.skills.code import CodeSkill
    from src.skills.system import SystemSkill

    async def exercise() -> None:
        with pytest.raises(PermissionError, match="guarded command_run"):
            await CodeSkill().execute({"code": "print('bypass')"}, {"text": "execute"})
        with pytest.raises(PermissionError, match="guarded command_run"):
            await SystemSkill().execute({"action": "shell"}, {"text": "shell"})

    import asyncio

    asyncio.run(exercise())


def test_future_cutover_leaves_no_direct_sink_in_compatibility_callers():
    _future_module("src.core.execution_gateway", "Plan 02-12 single-gateway cutover")
    _future_module("src.execution.local_adapters", "Plan 02-12 local adapter cutover")

    for caller in CALLER_FILES:
        assert _inventory(caller) == set(), f"direct sink remains in {caller}"


def test_future_callers_import_gateway_but_never_concrete_adapter_owners():
    _future_module("src.core.execution_gateway", "Plan 02-12 single-gateway cutover")
    _future_module("src.execution.local_adapters", "Plan 02-12 local adapter cutover")

    forbidden = tuple(str(path).replace("/", ".")[:-3] for path in ALLOWED_FUTURE_SINK_OWNERS)
    for caller in CALLER_FILES:
        source = (ROOT / caller).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert "src.core.execution_gateway" in imports, f"{caller} bypasses the gateway"
        assert not any(module.startswith(forbidden) for module in imports)
