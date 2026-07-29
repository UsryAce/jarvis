# JARVIS Agent Contract

This repository is Ahmed's local JARVIS assistant. This file is the canonical entry point for Codex, Claude, Cursor, OpenCode, Copilot, Gemini, and other coding agents.

## Read First

1. `README.md`
2. `docs/KNOWLEDGE_SYSTEM.md`
3. `.planning/graphs/GRAPH_REPORT.md` for generated architecture evidence
4. `C:\Users\Usry\OneDrive\Documents\Codex Agent Brain\Projects\Jarvis\Home.md`

## Sources of Truth

- Runtime code: this repository.
- Generated code relationships: `.planning/graphs/` (never edit manually; run `scripts/brain.ps1 refresh`).
- Durable decisions and agent handoffs: the Obsidian vault under `Projects/Jarvis/`.
- Runtime memory and queues: `data/`; do not commit databases, logs, or secrets.

## Working Rules

- Preserve unrelated user changes in this dirty worktree.
- Never expose `.env`, API keys, tokens, private files, or raw personal memory.
- Use the guarded agent runtime for machine actions. Do not silently broaden filesystem scope.
- Keep GLM 5.2 as the preferred general route, but use health-aware fallbacks when it stalls.
- Treat catalog presence as availability metadata, not proof that inference is healthy.
- Update tests and the Jarvis vault when architecture or operating contracts change.
- Record completed work in `Projects/Jarvis/Sessions/` using the handoff template.

## Verification

```powershell
cd frontend
npm run build:checked
cd ..
python -m pytest -q
powershell -ExecutionPolicy Bypass -File scripts\brain.ps1 status
```
