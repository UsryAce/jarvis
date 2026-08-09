import json

from src.core.knowledge_vault import KnowledgeVault


def test_status_combines_graph_and_vault(tmp_path):
    project = tmp_path / "project"
    graph_root = project / ".planning" / "graphs"
    graph_root.mkdir(parents=True)
    (graph_root / "graph.json").write_text(
        json.dumps(
            {
                "nodes": [{"id": "a"}, {"id": "b"}],
                "links": [{"source": "a", "target": "b"}],
                "hyperedges": [],
                "built_at_commit": "abc123",
            }
        ),
        encoding="utf-8",
    )
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Home.md").write_text("# Home", encoding="utf-8")

    status = KnowledgeVault(project, vault).status()

    assert status["health"] == "degraded"
    assert status["degradation_reasons"] == ["report_unavailable", "explorer_unavailable"]
    assert status["graph"]["node_count"] == 2
    assert status["graph"]["edge_count"] == 1
    assert status["graph"]["html_available"] is False
    assert status["graph"]["report_available"] is False
    assert status["vault"]["markdown_count"] == 1
    assert status["vault"]["obsidian_configured"] is True


def test_status_reports_optional_graph_artifacts_without_treating_them_as_health(tmp_path):
    project = tmp_path / "project"
    graph_root = project / ".planning" / "graphs"
    graph_root.mkdir(parents=True)
    (graph_root / "graph.json").write_text(
        json.dumps({"nodes": [], "links": [], "hyperedges": []}), encoding="utf-8"
    )
    (graph_root / "GRAPH_REPORT.md").write_text("# Report", encoding="utf-8")
    (graph_root / "graph.html").write_text("<html></html>", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()

    status = KnowledgeVault(project, vault).status()

    assert status["health"] == "good"
    assert status["degradation_reasons"] == []
    assert status["graph"]["html_available"] is True
    assert status["graph"]["report_available"] is True


def test_search_excludes_archive_and_returns_bounded_excerpt(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Routing.md").write_text(
        "# Routing\nNemotron handles deep reasoning.", encoding="utf-8"
    )
    archive = vault / "_Archive"
    archive.mkdir()
    (archive / "Old.md").write_text("Nemotron stale note", encoding="utf-8")

    results = KnowledgeVault(project, vault).search("nemotron")

    assert results == [
        {
            "title": "Routing",
            "path": "Routing.md",
            "excerpt": "Nemotron handles deep reasoning.",
        }
    ]
