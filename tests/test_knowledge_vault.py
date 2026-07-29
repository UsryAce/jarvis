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

    assert status["health"] == "good"
    assert status["graph"]["node_count"] == 2
    assert status["graph"]["edge_count"] == 1
    assert status["vault"]["markdown_count"] == 1
    assert status["vault"]["obsidian_configured"] is True


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
