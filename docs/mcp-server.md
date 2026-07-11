# MCP Server — portfolio-mcp

Python MCP server exposing the tools that write to the portfolio repo via the GitHub API. Installed in Claude Code (and optionally Claude Desktop).

## Tools

### `log_activity`
Writes a feed entry to the `drafts` branch. Normally called by the session-end hook, but can be invoked manually ("loga isso no portfólio").

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

## Session-end hook

A Claude Code `SessionEnd`/`Stop` hook that prompts an evaluation of the finished session against [rubric.md](rubric.md):

1. Does the session meet at least one of the four criteria? If no → exit silently (the common case).
2. If yes → write the entry (two layers, two languages), apply sanitization, call `log_activity`.

The hook prompt embeds the rubric verbatim from `rubric.md` so criteria changes require no code changes.
