from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="PowerShell refresh contract is Windows-only")


def _write_fake_graphify(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True)
    (bin_dir / "graphify.cmd").write_text(
        "\r\n".join(
            (
                "@echo off",
                "echo invoked>fixture-graphify-invoked",
                "if /I \"%1\"==\"tree\" goto tree",
                "if /I \"%1\"==\"cluster-only\" if /I not \"%3\"==\"--no-label\" exit /b 9",
                "if /I \"%1\"==\"cluster-only\" goto rebuild",
                "if exist fixture-update-noop exit /b 0",
                ":rebuild",
                "if not exist graphify-out mkdir graphify-out",
                "copy /Y fixture-graph.json graphify-out\\graph.json >nul",
                "copy /Y fixture-report.md graphify-out\\GRAPH_REPORT.md >nul",
                "if exist fixture-graph.html copy /Y fixture-graph.html graphify-out\\graph.html >nul",
                "exit /b 0",
                ":tree",
                "if exist fixture-tree-fail exit /b 7",
                "if /I \"%1\"==\"--output\" goto tree_output",
                "shift",
                "if not \"%1\"==\"\" goto tree",
                "exit /b 2",
                ":tree_output",
                "copy /Y fixture-tree.html \"%~2\" >nul",
                "exit /b 0",
                "",
            )
        ),
        encoding="utf-8",
    )


def _write_fake_gsd_tools(user_profile: Path) -> None:
    tool = user_profile / ".codex" / "gsd-core" / "bin" / "gsd-tools.cjs"
    tool.parent.mkdir(parents=True)
    tool.write_text(
        """
const fs = require("fs");
const path = require("path");
if (process.argv.slice(2).join(" ") !== "graphify build snapshot") process.exit(2);
const graph = JSON.parse(fs.readFileSync(path.join(process.cwd(), ".planning", "graphs", "graph.json"), "utf8"));
const target = path.join(process.cwd(), ".planning", "graphs", ".last-build-snapshot.json");
fs.writeFileSync(target, JSON.stringify({ nodes: graph.nodes || [], edges: graph.links || graph.edges || [] }));
""".strip(),
        encoding="utf-8",
    )


def _write_fake_git(bin_dir: Path) -> None:
    (bin_dir / "git.cmd").write_text(
        "@echo off\r\nif /I \"%3 %4\"==\"rev-parse HEAD\" (echo test-commit& exit /b 0)\r\nexit /b 2\r\n",
        encoding="utf-8",
    )


def _create_junction(link: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    powershell = shutil.which("powershell")
    assert powershell is not None
    env = os.environ.copy()
    env["JARVIS_TEST_JUNCTION_LINK"] = str(link)
    env["JARVIS_TEST_JUNCTION_TARGET"] = str(target)
    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-Command",
            "New-Item -ItemType Junction -Path $env:JARVIS_TEST_JUNCTION_LINK -Target $env:JARVIS_TEST_JUNCTION_TARGET | Out-Null",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def _run_refresh(
    tmp_path: Path,
    *,
    emit_html: bool,
    tree_failure: bool = False,
    noop_update: bool = False,
    unsafe_intermediate_target: Path | None = None,
    unsafe_planning_target: Path | None = None,
    unsafe_intermediate_leaf: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    project = tmp_path / "project"
    scripts = project / "scripts"
    graph_root = project / ".planning" / "graphs"
    scripts.mkdir(parents=True)
    if unsafe_planning_target is not None:
        (unsafe_planning_target / "graphs").mkdir(parents=True)
        _create_junction(project / ".planning", unsafe_planning_target)
    else:
        graph_root.mkdir(parents=True)
    shutil.copy2(Path("scripts/brain.ps1"), scripts / "brain.ps1")

    (project / "fixture-graph.json").write_text(
        json.dumps(
            {
                "nodes": [{"id": "a"}, {"id": "b"}],
                "links": [{"source": "a", "target": "b"}],
                "hyperedges": [],
                "built_at_commit": "test-commit",
            }
        ),
        encoding="utf-8",
    )
    (project / "fixture-report.md").write_text("# Fresh report\n", encoding="utf-8")
    (project / "fixture-tree.html").write_text("tree explorer", encoding="utf-8")
    if emit_html:
        (project / "fixture-graph.html").write_text("fresh explorer", encoding="utf-8")
    if tree_failure:
        (project / "fixture-tree-fail").write_text("fail", encoding="utf-8")
    if noop_update:
        (project / "fixture-update-noop").write_text("noop", encoding="utf-8")
        intermediate = project / "graphify-out"
        intermediate.mkdir()
        (intermediate / "graph.json").write_text("stale intermediate", encoding="utf-8")
        (intermediate / "GRAPH_REPORT.md").write_text("stale intermediate", encoding="utf-8")
    if unsafe_intermediate_target is not None:
        _create_junction(project / "graphify-out", unsafe_intermediate_target)
    if unsafe_intermediate_leaf:
        intermediate = project / "graphify-out"
        intermediate.mkdir()
        (intermediate / "graph.json").mkdir()

    # A skipped explorer must never leave an older canonical explorer looking current.
    (graph_root / "graph.json").write_text("old graph", encoding="utf-8")
    (graph_root / "GRAPH_REPORT.md").write_text("old report", encoding="utf-8")
    (graph_root / "graph.html").write_text("stale explorer", encoding="utf-8")

    user_profile = tmp_path / "user"
    local_app_data = tmp_path / "local-app-data"
    vault = tmp_path / "vault"
    fake_bin = tmp_path / "bin"
    _write_fake_graphify(fake_bin)
    _write_fake_git(fake_bin)
    _write_fake_gsd_tools(user_profile)

    env = os.environ.copy()
    env.update(
        {
            "USERPROFILE": str(user_profile),
            "LOCALAPPDATA": str(local_app_data),
            "JARVIS_VAULT_PATH": str(vault),
            "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
        }
    )
    powershell = shutil.which("powershell")
    assert powershell is not None
    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(scripts / "brain.ps1"),
            "refresh",
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return completed, graph_root, vault


@pytest.mark.parametrize("emit_html", (False, True))
def test_refresh_treats_graph_explorer_as_optional_without_reusing_stale_html(
    tmp_path: Path, emit_html: bool
) -> None:
    completed, graph_root, vault = _run_refresh(tmp_path, emit_html=emit_html)

    assert completed.returncode == 0, completed.stderr
    assert json.loads((graph_root / "graph.json").read_text(encoding="utf-8"))["built_at_commit"] == "test-commit"
    assert (graph_root / "GRAPH_REPORT.md").read_text(encoding="utf-8") == "# Fresh report\n"
    assert (graph_root / ".last-build-snapshot.json").is_file()

    explorer = graph_root / "graph.html"
    assert explorer.is_file()
    assert explorer.read_text(encoding="utf-8") == (
        "fresh explorer" if emit_html else "tree explorer"
    )

    status_path = vault / "Projects" / "Jarvis" / "Graph" / "graph-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8-sig"))
    assert status["explorerAvailable"] is True
    assert status["explorerMode"] == ("full" if emit_html else "tree")
    assert status["explorer"] is not None


def test_refresh_preserves_prior_canonical_set_when_tree_fallback_fails(tmp_path: Path) -> None:
    completed, graph_root, vault = _run_refresh(
        tmp_path, emit_html=False, tree_failure=True
    )

    assert completed.returncode != 0
    assert "Graphify tree fallback failed" in completed.stderr
    assert (graph_root / "graph.json").read_text(encoding="utf-8") == "old graph"
    assert (graph_root / "GRAPH_REPORT.md").read_text(encoding="utf-8") == "old report"
    assert (graph_root / "graph.html").read_text(encoding="utf-8") == "stale explorer"
    assert not (graph_root / ".last-build-snapshot.json").exists()
    assert not (vault / "Projects" / "Jarvis" / "Graph" / "graph-status.json").exists()


def test_refresh_rebuilds_provenance_when_incremental_update_is_a_noop(tmp_path: Path) -> None:
    completed, graph_root, vault = _run_refresh(
        tmp_path, emit_html=False, noop_update=True
    )

    assert completed.returncode == 0, completed.stderr
    graph = json.loads((graph_root / "graph.json").read_text(encoding="utf-8"))
    assert graph["built_at_commit"] == "test-commit"
    assert (graph_root / "GRAPH_REPORT.md").read_text(encoding="utf-8") == "# Fresh report\n"
    status = json.loads(
        (vault / "Projects" / "Jarvis" / "Graph" / "graph-status.json").read_text(
            encoding="utf-8-sig"
        )
    )
    assert status["sourceCommit"] == "test-commit"


def test_refresh_rejects_intermediate_junction_before_delete_or_graphify_write(tmp_path: Path) -> None:
    outside = tmp_path / "outside-intermediate"
    outside.mkdir()
    marker = outside / "graph.html"
    marker.write_text("outside must remain unchanged", encoding="utf-8")

    completed, graph_root, _ = _run_refresh(
        tmp_path,
        emit_html=False,
        unsafe_intermediate_target=outside,
    )

    try:
        assert completed.returncode != 0
        assert "unsafe directory component" in completed.stderr
        assert marker.read_text(encoding="utf-8") == "outside must remain unchanged"
        assert not (outside / "graph.json").exists()
        assert (graph_root / "graph.json").read_text(encoding="utf-8") == "old graph"
        assert not (graph_root.parents[1] / "fixture-graphify-invoked").exists()
    finally:
        os.rmdir(graph_root.parents[1] / "graphify-out")


def test_refresh_rejects_reparse_ancestor_before_any_generated_write(tmp_path: Path) -> None:
    outside = tmp_path / "outside-planning"

    completed, graph_root, _ = _run_refresh(
        tmp_path,
        emit_html=False,
        unsafe_planning_target=outside,
    )

    try:
        assert completed.returncode != 0
        assert "unsafe directory component" in completed.stderr
        assert (outside / "graphs" / "graph.json").read_text(encoding="utf-8") == "old graph"
        assert not (outside / "graphs" / ".last-build-snapshot.json").exists()
    finally:
        os.rmdir(graph_root.parents[1] / ".planning")


def test_refresh_rejects_unsafe_existing_intermediate_leaf_before_tool_invocation(tmp_path: Path) -> None:
    completed, graph_root, _ = _run_refresh(
        tmp_path,
        emit_html=False,
        unsafe_intermediate_leaf=True,
    )

    assert completed.returncode != 0
    assert "unsafe artifact" in completed.stderr
    assert not (graph_root.parents[1] / "fixture-graphify-invoked").exists()
    assert (graph_root / "graph.json").read_text(encoding="utf-8") == "old graph"
