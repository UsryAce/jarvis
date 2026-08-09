# JARVIS Knowledge System

JARVIS uses three complementary memory layers:

1. **Graphify code graph** — generated AST relationships in `.planning/graphs/`.
2. **Obsidian agent vault** — durable, human-readable decisions and handoffs in `Codex Agent Brain/Projects/Jarvis/`.
3. **Runtime memory** — conversations, tasks, agent runs, and vector retrieval under `data/`.

Graphify answers “how is the code connected?” Obsidian answers “why did we decide this?” Runtime memory answers “what is happening now?” Keeping these responsibilities separate prevents duplicate and stale knowledge.

## Commands

```powershell
scripts\brain.ps1 status
scripts\brain.ps1 refresh
scripts\brain.ps1 sync
scripts\brain.ps1 graph
scripts\brain.ps1 vault
scripts\brain.ps1 search -Query "model routing"
```

## API

- `GET /api/brain` — combined graph and vault status.
- `POST /api/brain/search` — bounded Markdown vault search.
- `POST /api/brain/open` — explicitly open the vault, graph explorer, or report.

Generated graph files must only be changed by Graphify. Durable notes should contain decisions and evidence, not copied source code, secrets, logs, or transient chat.

`graph.json` and `GRAPH_REPORT.md` are mandatory refresh outputs. After incremental update, Brain refresh runs Graphify's local `cluster-only --no-label` pass so a no-topology-change result still rebuilds source provenance at the current commit without invoking an LLM or spending provider tokens. Graphify may skip its full `graph.html` community visualization above the node limit, so refresh generates Graphify's large-graph tree explorer as a fallback. The vault projection records `explorerAvailable` and `explorerMode` (`full`, `tree`, `existing`, or `unavailable`). A stale prior explorer is never reused: every successful refresh requires a new nonempty, non-reparse explorer together with current JSON, report, snapshot, and Obsidian status, and rejects generated paths whose directory components are reparse points or escape the canonical repository.
