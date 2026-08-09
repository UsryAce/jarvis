from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import time

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="PowerShell refresh contract is Windows-only")


def _write_fake_graphify(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True)
    (bin_dir / "graphify.cmd").write_text(
        "\r\n".join(
            (
                "@echo off",
                "echo invoked>fixture-graphify-invoked",
                "if not \"%JARVIS_TEST_EVENT_LOG%\"==\"\" echo %JARVIS_TEST_INSTANCE%:%1>>\"%JARVIS_TEST_EVENT_LOG%\"",
                "if /I \"%1\"==\"update\" if not \"%JARVIS_TEST_EXPECT_PRIOR_STATUS%\"==\"\" (",
                "  %SystemRoot%\\System32\\findstr.exe /C:\"%JARVIS_TEST_EXPECT_PRIOR_STATUS%\" \"%JARVIS_TEST_VAULT_STATUS%\" >nul",
                "  if errorlevel 1 exit /b 19",
                ")",
                "if /I \"%1\"==\"update\" if /I \"%JARVIS_TEST_BLOCK_UPDATE%\"==\"1\" goto block_update",
                "goto after_block_update",
                ":block_update",
                "echo READY>\"%JARVIS_TEST_GATE_READY%\"",
                ":wait_for_release",
                "if not exist \"%JARVIS_TEST_GATE_RELEASE%\" (",
                "  %SystemRoot%\\System32\\ping.exe -n 2 127.0.0.1 >nul",
                "  goto wait_for_release",
                ")",
                ":after_block_update",
                "if /I \"%1\"==\"tree\" goto tree",
                "if /I \"%1\"==\"cluster-only\" if /I not \"%3\"==\"--no-label\" exit /b 9",
                "if /I \"%1\"==\"cluster-only\" goto rebuild",
                "if exist fixture-update-noop exit /b 0",
                ":rebuild",
                "if not exist graphify-out mkdir graphify-out",
                "set \"graphsource=fixture-graph.json\"",
                "if not \"%JARVIS_TEST_INSTANCE%\"==\"\" if exist \"fixture-graph-%JARVIS_TEST_INSTANCE%.json\" set \"graphsource=fixture-graph-%JARVIS_TEST_INSTANCE%.json\"",
                "copy /Y \"%graphsource%\" graphify-out\\graph.json >nul",
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
if (process.env.JARVIS_TEST_SNAPSHOT_MODE === "partial-fail") {
  fs.writeFileSync(target, '{"nodes":[');
  process.exit(41);
}
if (process.env.JARVIS_TEST_SNAPSHOT_MODE === "invalid-json") {
  fs.writeFileSync(target, '{"nodes":');
  process.exit(0);
}
if (process.env.JARVIS_TEST_SNAPSHOT_MODE === "wrong-topology") {
  fs.writeFileSync(target, JSON.stringify({
    nodes: [{ id: "x" }, { id: "y" }],
    edges: [{ source: "x", target: "y" }]
  }));
  process.exit(0);
}
if (process.env.JARVIS_TEST_SNAPSHOT_MODE === "wrong-endpoint") {
  fs.writeFileSync(target, JSON.stringify({
    nodes: [{ id: "a" }, { id: "b" }],
    edges: [{ source: "b", target: "a", relation: "calls" }]
  }));
  process.exit(0);
}
if (process.env.JARVIS_TEST_SNAPSHOT_MODE === "wrong-relation") {
  fs.writeFileSync(target, JSON.stringify({
    nodes: [{ id: "a" }, { id: "b" }],
    edges: [{ source: "a", target: "b", relation: "imports" }]
  }));
  process.exit(0);
}
fs.writeFileSync(target, JSON.stringify({ nodes: graph.nodes || [], edges: graph.links || graph.edges || [] }));
""".strip(),
        encoding="utf-8",
    )


def _write_fake_git(bin_dir: Path) -> None:
    (bin_dir / "git.cmd").write_text(
        (
            "@echo off\r\n"
            "if /I not \"%3 %4\"==\"rev-parse HEAD\" exit /b 2\r\n"
            "if not \"%JARVIS_TEST_COMMIT%\"==\"\" (echo %JARVIS_TEST_COMMIT%& exit /b 0)\r\n"
            "echo test-commit\r\n"
            "exit /b 0\r\n"
        ),
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
    snapshot_mode: str | None = None,
    seed_complete_old_generation: bool = False,
    lock_artifact: str | None = None,
    command: str = "refresh",
    unsafe_vault_graph_target: Path | None = None,
    omit_old_artifacts: tuple[str, ...] = (),
    named_stream_artifact: str | None = None,
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
                "links": [{"source": "a", "target": "b", "relation": "calls"}],
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
    if seed_complete_old_generation:
        (graph_root / "graph.json").write_text(
            '{"nodes":[{"id":"old"}],"links":[],"hyperedges":[],"built_at_commit":"old-commit"}',
            encoding="utf-8",
        )
        (graph_root / ".last-build-snapshot.json").write_text(
            '{"nodes":[{"id":"old"}],"edges":[]}', encoding="utf-8"
        )

    user_profile = tmp_path / "user"
    local_app_data = tmp_path / "local-app-data"
    vault = tmp_path / "vault"
    if unsafe_vault_graph_target is not None:
        (vault / "Projects" / "Jarvis").mkdir(parents=True)
        _create_junction(vault / "Projects" / "Jarvis" / "Graph", unsafe_vault_graph_target)
    if seed_complete_old_generation:
        assert unsafe_vault_graph_target is None
        vault_graph = vault / "Projects" / "Jarvis" / "Graph"
        vault_graph.mkdir(parents=True)
        (vault_graph / "Graphify Report.md").write_text(
            "# Old vault report\n", encoding="utf-8"
        )
        (vault_graph / "graph-status.json").write_text(
            '{"sourceCommit":"old-commit"}', encoding="utf-8"
        )
        old_artifacts = {
            "graph": graph_root / "graph.json",
            "report": graph_root / "GRAPH_REPORT.md",
            "explorer": graph_root / "graph.html",
            "snapshot": graph_root / ".last-build-snapshot.json",
            "vault_report": vault_graph / "Graphify Report.md",
            "vault_status": vault_graph / "graph-status.json",
        }
        for name in omit_old_artifacts:
            old_artifacts[name].unlink()
        if named_stream_artifact is not None:
            Path(f"{old_artifacts[named_stream_artifact]}:jarvis-test").write_bytes(b"hidden")
    else:
        assert named_stream_artifact is None
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
    if snapshot_mode is not None:
        env["JARVIS_TEST_SNAPSHOT_MODE"] = snapshot_mode
    powershell = shutil.which("powershell")
    assert powershell is not None
    lock_process: subprocess.Popen[str] | None = None
    try:
        if lock_artifact is not None:
            lock_targets = {
                "canonical_explorer": graph_root / "graph.html",
                "vault_status": vault / "Projects" / "Jarvis" / "Graph" / "graph-status.json",
            }
            env["JARVIS_TEST_LOCK_PATH"] = str(lock_targets[lock_artifact])
            lock_process = subprocess.Popen(
                [
                    powershell,
                    "-NoProfile",
                    "-Command",
                    (
                        "$stream=[IO.FileStream]::new($env:JARVIS_TEST_LOCK_PATH,"
                        "[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read);"
                        "[Console]::Out.WriteLine('READY');[Console]::Out.Flush();"
                        "[Console]::In.ReadLine() | Out-Null;$stream.Dispose()"
                    ),
                ],
                cwd=project,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            assert lock_process.stdout is not None
            assert lock_process.stdout.readline().strip() == "READY"
        completed = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(scripts / "brain.ps1"),
                command,
            ],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    finally:
        if lock_process is not None:
            assert lock_process.stdin is not None
            lock_process.stdin.write("\n")
            lock_process.stdin.flush()
            lock_process.wait(timeout=10)
    return completed, graph_root, vault


def _published_artifacts(graph_root: Path, vault: Path) -> tuple[Path, ...]:
    vault_graph = vault / "Projects" / "Jarvis" / "Graph"
    return (
        graph_root / "graph.json",
        graph_root / "GRAPH_REPORT.md",
        graph_root / "graph.html",
        graph_root / ".last-build-snapshot.json",
        vault_graph / "Graphify Report.md",
        vault_graph / "graph-status.json",
    )


OLD_PUBLISHED_BYTES = (
    b'{"nodes":[{"id":"old"}],"links":[],"hyperedges":[],"built_at_commit":"old-commit"}',
    b"old report",
    b"stale explorer",
    b'{"nodes":[{"id":"old"}],"edges":[]}',
    b"# Old vault report\r\n",
    b'{"sourceCommit":"old-commit"}',
)


def _assert_prior_generation_and_no_transaction_residue(graph_root: Path, vault: Path) -> None:
    assert tuple(path.read_bytes() for path in _published_artifacts(graph_root, vault)) == OLD_PUBLISHED_BYTES
    _assert_no_transaction_residue(graph_root, vault)


def _assert_no_transaction_residue(graph_root: Path, vault: Path) -> None:
    project = graph_root.parents[1]
    residue = [
        path
        for root in (project, vault)
        for path in root.rglob("*")
        if ".brain-txn-" in path.name
    ]
    assert residue == []


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


def test_refresh_snapshot_failure_preserves_complete_prior_generation(tmp_path: Path) -> None:
    completed, graph_root, vault = _run_refresh(
        tmp_path,
        emit_html=True,
        snapshot_mode="partial-fail",
        seed_complete_old_generation=True,
    )

    assert completed.returncode != 0
    assert "Graphify snapshot failed with exit code 41" in completed.stderr
    _assert_prior_generation_and_no_transaction_residue(graph_root, vault)


def test_refresh_rejects_named_stream_before_replacement_can_preserve_it(tmp_path: Path) -> None:
    completed, graph_root, vault = _run_refresh(
        tmp_path,
        emit_html=True,
        seed_complete_old_generation=True,
        named_stream_artifact="graph",
    )

    assert completed.returncode != 0
    assert "named alternate data stream" in completed.stderr
    _assert_prior_generation_and_no_transaction_residue(graph_root, vault)
    assert Path(f"{graph_root / 'graph.json'}:jarvis-test").read_bytes() == b"hidden"


@pytest.mark.parametrize(
    ("snapshot_mode", "error_fragment"),
    (
        ("invalid-json", "Invalid object passed in"),
        ("wrong-topology", "snapshot does not match the generated graph topology"),
        ("wrong-endpoint", "snapshot does not match the generated graph topology"),
        ("wrong-relation", "snapshot does not match the generated graph topology"),
    ),
)
def test_refresh_rejects_invalid_snapshot_without_publishing(
    tmp_path: Path, snapshot_mode: str, error_fragment: str
) -> None:
    completed, graph_root, vault = _run_refresh(
        tmp_path,
        emit_html=True,
        snapshot_mode=snapshot_mode,
        seed_complete_old_generation=True,
    )

    assert completed.returncode != 0
    assert error_fragment.lower() in completed.stderr.lower()
    _assert_prior_generation_and_no_transaction_residue(graph_root, vault)


def test_refresh_late_canonical_failure_rolls_back_all_six_artifacts(tmp_path: Path) -> None:
    completed, graph_root, vault = _run_refresh(
        tmp_path,
        emit_html=True,
        seed_complete_old_generation=True,
        lock_artifact="canonical_explorer",
    )

    assert completed.returncode != 0
    assert "prior artifact set was restored" in completed.stderr
    _assert_prior_generation_and_no_transaction_residue(graph_root, vault)


def test_refresh_vault_status_failure_rolls_back_all_six_artifacts(tmp_path: Path) -> None:
    completed, graph_root, vault = _run_refresh(
        tmp_path,
        emit_html=True,
        seed_complete_old_generation=True,
        lock_artifact="vault_status",
    )

    assert completed.returncode != 0
    assert "prior artifact set was restored" in completed.stderr
    _assert_prior_generation_and_no_transaction_residue(graph_root, vault)


def test_refresh_rollback_restores_original_absence_as_well_as_bytes(tmp_path: Path) -> None:
    completed, graph_root, vault = _run_refresh(
        tmp_path,
        emit_html=True,
        seed_complete_old_generation=True,
        omit_old_artifacts=("snapshot", "vault_report"),
        lock_artifact="vault_status",
    )

    assert completed.returncode != 0
    assert "prior artifact set was restored" in completed.stderr
    paths = _published_artifacts(graph_root, vault)
    assert paths[0].read_bytes() == OLD_PUBLISHED_BYTES[0]
    assert paths[1].read_bytes() == OLD_PUBLISHED_BYTES[1]
    assert paths[2].read_bytes() == OLD_PUBLISHED_BYTES[2]
    assert not paths[3].exists()
    assert not paths[4].exists()
    assert paths[5].read_bytes() == OLD_PUBLISHED_BYTES[5]
    _assert_no_transaction_residue(graph_root, vault)


def test_sync_status_failure_restores_vault_pair(tmp_path: Path) -> None:
    completed, graph_root, vault = _run_refresh(
        tmp_path,
        emit_html=True,
        seed_complete_old_generation=True,
        lock_artifact="vault_status",
        command="sync",
    )

    assert completed.returncode != 0
    assert "prior artifact set was restored" in completed.stderr
    _assert_prior_generation_and_no_transaction_residue(graph_root, vault)


def test_sync_publishes_coherent_vault_pair_and_cleans_transaction_files(tmp_path: Path) -> None:
    completed, graph_root, vault = _run_refresh(
        tmp_path,
        emit_html=True,
        seed_complete_old_generation=True,
        command="sync",
    )

    assert completed.returncode == 0, completed.stderr
    paths = _published_artifacts(graph_root, vault)
    assert tuple(path.read_bytes() for path in paths[:4]) == OLD_PUBLISHED_BYTES[:4]
    assert paths[4].read_bytes() == b"old report"
    status = json.loads(paths[5].read_text(encoding="utf-8-sig"))
    assert status["sourceCommit"] == "old-commit"
    assert status["nodes"] == 1
    assert status["edges"] == 0
    assert status["explorerAvailable"] is True
    _assert_no_transaction_residue(graph_root, vault)


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


def test_refresh_rejects_vault_junction_before_staging_or_publication(tmp_path: Path) -> None:
    outside = tmp_path / "outside-vault"
    outside.mkdir()
    marker = outside / "must-not-change.txt"
    marker.write_text("protected", encoding="utf-8")

    completed, graph_root, vault = _run_refresh(
        tmp_path,
        emit_html=True,
        unsafe_vault_graph_target=outside,
    )

    try:
        assert completed.returncode != 0
        assert "unsafe directory component" in completed.stderr
        assert marker.read_text(encoding="utf-8") == "protected"
        assert sorted(path.name for path in outside.iterdir()) == ["must-not-change.txt"]
        assert (graph_root / "graph.json").read_text(encoding="utf-8") == "old graph"
        assert not (graph_root / ".last-build-snapshot.json").exists()
    finally:
        os.rmdir(vault / "Projects" / "Jarvis" / "Graph")


def test_concurrent_refreshes_are_serialized_through_vault_publication(tmp_path: Path) -> None:
    initial, graph_root, vault = _run_refresh(tmp_path, emit_html=True)
    assert initial.returncode == 0, initial.stderr

    project = graph_root.parents[1]
    fixture_script = project / "scripts" / "brain.ps1"
    script_text = fixture_script.read_text(encoding="utf-8")
    mutex_needle = "$acquired = $mutex.WaitOne($TimeoutMilliseconds)"
    assert script_text.count(mutex_needle) == 1
    fixture_script.write_text(
        script_text.replace(
            mutex_needle,
            (
                "if ($env:JARVIS_TEST_MUTEX_READY) { "
                "[IO.File]::WriteAllText($env:JARVIS_TEST_MUTEX_READY, 'READY') }\n"
                f"            {mutex_needle}"
            ),
        ),
        encoding="utf-8",
    )
    for instance, commit in (("A", "commit-a"), ("B", "commit-b")):
        (project / f"fixture-graph-{instance}.json").write_text(
            json.dumps(
                {
                    "nodes": [{"id": instance}],
                    "links": [],
                    "hyperedges": [],
                    "built_at_commit": commit,
                }
            ),
            encoding="utf-8",
        )

    event_log = tmp_path / "events.log"
    gate_ready = tmp_path / "gate.ready"
    gate_release = tmp_path / "gate.release"
    b_ready = tmp_path / "b.ready"
    vault_status = vault / "Projects" / "Jarvis" / "Graph" / "graph-status.json"
    base_env = os.environ.copy()
    base_env.update(
        {
            "USERPROFILE": str(tmp_path / "user"),
            "LOCALAPPDATA": str(tmp_path / "local-app-data"),
            "JARVIS_VAULT_PATH": str(vault),
            "PATH": f"{tmp_path / 'bin'}{os.pathsep}{base_env['PATH']}",
            "JARVIS_TEST_EVENT_LOG": str(event_log),
        }
    )
    env_a = base_env | {
        "JARVIS_TEST_INSTANCE": "A",
        "JARVIS_TEST_COMMIT": "commit-a",
        "JARVIS_TEST_BLOCK_UPDATE": "1",
        "JARVIS_TEST_GATE_READY": str(gate_ready),
        "JARVIS_TEST_GATE_RELEASE": str(gate_release),
    }
    env_b = base_env | {
        "JARVIS_TEST_INSTANCE": "B",
        "JARVIS_TEST_COMMIT": "commit-b",
        "JARVIS_TEST_EXPECT_PRIOR_STATUS": "commit-a",
        "JARVIS_TEST_VAULT_STATUS": str(vault_status),
        "JARVIS_TEST_MUTEX_READY": str(b_ready),
    }
    powershell = shutil.which("powershell")
    assert powershell is not None
    command = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(project / "scripts" / "brain.ps1"),
        "refresh",
    ]
    process_a: subprocess.Popen[str] | None = None
    process_b: subprocess.Popen[str] | None = None
    try:
        process_a = subprocess.Popen(
            command,
            cwd=project,
            env=env_a,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 10
        while not gate_ready.exists() and time.monotonic() < deadline:
            assert process_a.poll() is None
            time.sleep(0.05)
        assert gate_ready.exists()

        process_b = subprocess.Popen(
            command,
            cwd=project,
            env=env_b,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        deadline = time.monotonic() + 10
        while not b_ready.exists() and time.monotonic() < deadline:
            assert process_b.poll() is None
            time.sleep(0.05)
        assert b_ready.exists()
        time.sleep(0.5)
        assert process_b.poll() is None
        events_while_a_holds_lock = event_log.read_text(encoding="utf-8").splitlines()
        assert events_while_a_holds_lock == ["A:update"]

        gate_release.write_text("release", encoding="utf-8")
        stdout_a, stderr_a = process_a.communicate(timeout=30)
        stdout_b, stderr_b = process_b.communicate(timeout=30)
        assert process_a.returncode == 0, stderr_a or stdout_a
        assert process_b.returncode == 0, stderr_b or stdout_b
    finally:
        gate_release.write_text("release", encoding="utf-8")
        for process in (process_a, process_b):
            if process is not None and process.poll() is None:
                try:
                    process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=10)

    events = event_log.read_text(encoding="utf-8").splitlines()
    assert events == ["A:update", "A:cluster-only", "B:update", "B:cluster-only"]
    graph = json.loads((graph_root / "graph.json").read_text(encoding="utf-8"))
    snapshot = json.loads(
        (graph_root / ".last-build-snapshot.json").read_text(encoding="utf-8")
    )
    status = json.loads(vault_status.read_text(encoding="utf-8-sig"))
    assert graph["built_at_commit"] == "commit-b"
    assert [node["id"] for node in graph["nodes"]] == ["B"]
    assert [node["id"] for node in snapshot["nodes"]] == ["B"]
    assert status["sourceCommit"] == "commit-b"
    assert status["nodes"] == 1
    _assert_no_transaction_residue(graph_root, vault)
