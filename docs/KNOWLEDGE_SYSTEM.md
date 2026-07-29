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
