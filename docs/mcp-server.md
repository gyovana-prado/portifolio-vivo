# MCP Server — portfolio-mcp

Python MCP server exposing the tools that write to the portfolio repo via the GitHub API. Installed in Claude Code (and optionally Claude Desktop).

## Tools

### `log_activity`
Writes a feed entry to the `drafts` branch. Normally called by the drain evaluator (`make drain`), but can be invoked manually ("loga isso no portfólio").

Parameters: the full feed-entry object (see [content-model.md](content-model.md)). The tool validates the schema, enforces bilingual completeness, and rejects entries that fail sanitization checks (a denylist of configured client/employer names as a second line of defense behind the LLM's category-based sanitization).

### `review_and_publish`
Lists pending drafts with their narratives, waits for the owner's selection, merges approved entries to `main`, deletes rejected ones. Run on demand — this is the human gate.

### `add_project`
Creates or updates a project file. Manual use, for case studies.

### `update_now`
Replaces `now.json` items and bumps the `updated` date.

### `get_portfolio_state`
Read-only: current now items, last N feed entries, pending draft count. Lets the LLM avoid duplicate logging ("this was already logged Tuesday").

## Security model

- **Token:** fine-grained GitHub PAT, scoped to the single portfolio repo, `contents:write` permission only. Lives in the local MCP config (`env` block), never in the repo, never in content.
- **Branch protection:** `main` accepts changes only via the publish tool (or the owner directly). The hook can only reach `drafts`.
- **Denylist:** a local (non-committed) config file lists client/employer names the tool must reject outright — defense in depth behind the rubric's category-based sanitization.

## Capture hook + drain evaluator

Two pieces (see [hooks/README.md](../hooks/README.md) for details):

1. **`capture_session.py`** — a silent Claude Code `Stop` hook. It never blocks and
   never prints; it only appends `{session_id, transcript_path}` to a local queue
   (`~/.claude/portfolio/queue.jsonl`, deduped per session). Zero conversation noise.
2. **`drain_queue.py`** (run via `make drain`) — for each queued session, spawns a
   headless `claude -p` that reads the transcript, evaluates it against
   [rubric.md](rubric.md) (embedded verbatim, so criteria changes need no code change),
   and — only if it clears the bar — calls `log_activity` to write a draft.

The evaluator runs with all hooks disabled (`--settings '{"disableAllHooks": true}'`):
otherwise a global `Stop` hook would hijack the headless run's result and re-enqueue
the evaluator's own session in a loop. The MCP config (token + repo) is read at
runtime from the registered `portfolio` server in `~/.claude.json`.

> The original inline evaluator (`hooks/evaluate_session.py`) blocked at every turn
> and printed the evaluation into the conversation. It's kept for reference; the
> silent capture + on-demand drain is the recommended flow.
