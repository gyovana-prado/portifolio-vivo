# MCP Server — portfolio-mcp

Python MCP server exposing the tools that write to the portfolio repo via the GitHub API. Installed in Claude Code (and optionally Claude Desktop).

## Tools

### `log_activity`
Writes a feed entry to the `staging` branch (`PORTFOLIO_DRAFTS_BRANCH`). Normally called by the drain evaluator (`make drain`), but can be invoked manually ("loga isso no portfólio").

Parameters: the full feed-entry object (see [content-model.md](content-model.md)). The tool validates the schema, enforces bilingual completeness, and rejects entries that fail sanitization checks (a denylist of configured client/employer names as the last line of defense behind the LLM's category-based sanitization and the confidentiality judge). Staged entries are picked up by the drain's publish stage, which opens the PR with the veto window — see [architecture.md](architecture.md).

### `review_and_publish`
Manual fallback. Lists staged entries with their narratives, waits for the owner's selection, writes approved entries to `main`, deletes rejected ones. Use it to publish something *now* or to drop a staged entry before the next round; the normal path is the PR + 48h veto window.

### `add_project`
Creates or updates a project file. Manual use, for case studies.

### `update_now`
Replaces `now.json` items and bumps the `updated` date.

### `get_portfolio_state`
Read-only: current now items, last N feed entries, pending draft count. Lets the LLM avoid duplicate logging ("this was already logged Tuesday").

## Security model

- **Token:** fine-grained GitHub PAT, scoped to the single portfolio repo, `contents:write` permission only. Lives in the local MCP config (`env` block), never in the repo, never in content.
- **Branches:** `log_activity` can only reach `staging`. `main` changes through the PRs the drain opens (merged by the hourly Action after the veto window), through `review_and_publish`, or by the owner directly.
- **Denylist:** a local (non-committed) config file lists client/employer names the tool must reject outright — the last barrier behind the rubric's category-based sanitization and the confidentiality judge (`hooks/confidentiality_judge.py`), which also reads it.
- **`UV_NO_ENV_FILE=1`:** if your shell exports `UV_ENV_FILE=.env`, `uv run` aborts in any directory without a `.env` and the server never starts (`CONNECTION_CLOSED`). Set `UV_NO_ENV_FILE=1` in the server's `env` block; the drain adds it automatically to the config it hands the headless evaluator.

## Capture hook + drain evaluator

Two pieces (see [hooks/README.md](../hooks/README.md) for details):

1. **`capture_session.py`** — a silent Claude Code `Stop` hook. It never blocks and
   never prints; it only appends `{session_id, transcript_path}` to a local queue
   (`~/.claude/portfolio/queue.jsonl`, deduped per session). Zero conversation noise.
2. **`drain_queue.py`** (run via `make drain`, daily via a LaunchAgent) — triages the
   queue (no transcript / headless `entrypoint` → skipped), then for each interactive
   session spawns a headless `claude -p` that reads the transcript, evaluates it against
   [rubric.md](../rubric.md) (embedded verbatim, so criteria changes need no code change),
   and — only if it clears the bar — calls `log_activity` to write a draft to `staging`.
   The evaluator ends with `REGISTRADO | DESCARTADO | FALHA`; only the first two mark
   the session processed. At the end of the round, `hooks/round_publisher.py` runs the
   confidentiality judge on every staged entry and opens the PRs (`drafts/<date>`,
   `drafts/<date>-zero`, `retidas/<date>`), then sends the digest.

The evaluator runs with all hooks disabled (`--settings '{"disableAllHooks": true}'`):
otherwise a global `Stop` hook would hijack the headless run's result and re-enqueue
the evaluator's own session in a loop. The MCP config (token + repo) is read at
runtime from the registered `portfolio` server in `~/.claude.json`.

> The original inline evaluator (`hooks/evaluate_session.py`) blocked at every turn
> and printed the evaluation into the conversation. It's kept for reference; the
> silent capture + on-demand drain is the recommended flow.
