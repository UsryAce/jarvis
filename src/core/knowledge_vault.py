"""Shared Graphify and Obsidian knowledge layer for JARVIS."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class KnowledgeVault:
    """Expose the project code graph and the portable Markdown agent vault."""

    def __init__(self, project_root: Path, vault_root: Path | None = None) -> None:
        self.project_root = project_root.resolve()
        self.graph_root = self.project_root / ".planning" / "graphs"
        configured = os.getenv("JARVIS_VAULT_PATH", "").strip()
        self.vault_root = (vault_root or self._default_vault(configured)).resolve()

    @staticmethod
    def _default_vault(configured: str) -> Path:
        if configured:
            return Path(configured).expanduser()
        home = Path.home()
        candidates = (
            home / "OneDrive" / "Documents" / "Codex Agent Brain",
            home / "Documents" / "Codex Agent Brain",
        )
        return next((path for path in candidates if path.exists()), candidates[0])

    def _graph(self) -> dict[str, Any]:
        path = self.graph_root / "graph.json"
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _markdown_files(self) -> list[Path]:
        if not self.vault_root.is_dir():
            return []
        return sorted(
            path
            for path in self.vault_root.rglob("*.md")
            if ".obsidian" not in path.parts and "_Archive" not in path.parts
        )

    def status(self) -> dict[str, Any]:
        graph = self._graph()
        nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
        links = graph.get("links") if isinstance(graph.get("links"), list) else []
        hyperedges = (
            graph.get("hyperedges") if isinstance(graph.get("hyperedges"), list) else []
        )
        markdown = self._markdown_files()
        graph_path = self.graph_root / "graph.json"
        return {
            "health": "good" if graph and self.vault_root.is_dir() else "degraded",
            "graph": {
                "path": str(graph_path),
                "report_path": str(self.graph_root / "GRAPH_REPORT.md"),
                "html_path": str(self.graph_root / "graph.html"),
                "node_count": len(nodes),
                "edge_count": len(links),
                "hyperedge_count": len(hyperedges),
                "built_at_commit": graph.get("built_at_commit"),
                "updated_at": graph_path.stat().st_mtime if graph_path.exists() else None,
            },
            "vault": {
                "path": str(self.vault_root),
                "exists": self.vault_root.is_dir(),
                "markdown_count": len(markdown),
                "obsidian_configured": (self.vault_root / ".obsidian").is_dir(),
                "home": str(self.vault_root / "Home.md"),
            },
        }

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        needle = " ".join(query.casefold().split())
        if not needle:
            return []
        results: list[dict[str, Any]] = []
        for path in self._markdown_files():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            normalized = " ".join(text.casefold().split())
            if needle not in normalized and needle not in path.name.casefold():
                continue
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            excerpt = next(
                (line for line in lines if needle in line.casefold()),
                lines[0] if lines else "",
            )
            results.append(
                {
                    "title": path.stem,
                    "path": str(path.relative_to(self.vault_root)).replace("\\", "/"),
                    "excerpt": excerpt[:360],
                }
            )
            if len(results) >= max(1, min(limit, 100)):
                break
        return results
