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

`graph.json` and `GRAPH_REPORT.md` are mandatory refresh outputs. After incremental update, Brain refresh runs Graphify's local `cluster-only --no-label` pass so a no-topology-change result still rebuilds source provenance at the current commit without invoking an LLM or spending provider tokens. Graphify may skip its full `graph.html` community visualization above the node limit, so refresh generates Graphify's large-graph tree explorer as a fallback. The vault projection records `explorerAvailable` and `explorerMode` (`full`, `tree`, `existing`, or `unavailable`). A stale prior explorer is never reused: every successful refresh requires a new nonempty explorer together with current JSON, report, snapshot, and Obsidian status.

Refresh and sync share a current-user-protected, repository-scoped global mutex. Refresh generates the snapshot in an isolated repository stage, validates provenance plus the exact node-ID and typed edge-endpoint topology, prepares durable same-directory swap files, and only then publishes the four canonical files plus the two vault projections. Each existing target replacement has a unique backup; a previously absent target uses a same-volume move and rollback-by-delete. Every published default stream is hash-verified and the journal rolls back in reverse order if any later replacement fails; the vault status is published last. Successful publication and successful rollback remove only the transaction's exact known files and empty directories. An incomplete rollback fails closed and retains its uniquely named recovery artifacts instead of deleting evidence.

Repository paths reject every reparse point. The explicitly configured OneDrive vault permits only Cloud Files placeholders whose reparse tag is not a name surrogate; junctions, symbolic links, mounted-folder redirects, unknown reparse tags, named alternate data streams, root escapes, missing output, empty output, stale provenance, malformed snapshots, and topology drift are rejected. The mutex and replacement journal provide coherent caught-exception recovery for cooperating local processes. Path checks and replacements are still separate Windows operations, so the canonical repository and vault must remain writable only by the trusted operator, SYSTEM, and administrators; the mutex does not defend against a hostile same-authority process racing directory entries. The transaction does not claim one-operation atomic visibility to readers that ignore the mutex or power-loss/crash atomicity across repository and OneDrive volumes; a future versioned-bundle pointer or durable recovery journal is required for that stronger guarantee.
