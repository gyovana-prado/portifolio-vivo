# Session-end hook

`evaluate_session.py` is a Claude Code **Stop** hook. When a session ends, it
asks the assistant to evaluate the finished work against [`rubric.md`](../rubric.md)
and — only if it clears the bar — write a feed entry via the portfolio MCP
`log_activity` tool (which lands on the `drafts` branch, never public).

## How it works

1. On `Stop`, the hook injects an evaluation prompt with the rubric embedded
   **verbatim** — so changing the criteria means editing `rubric.md`, not this hook.
2. The assistant judges the session. Most sessions log nothing (correct behavior).
3. If worthy, it builds the entry (two layers, two languages, sanitized by
   category) and calls `log_activity`.

**Loop-safe:** it injects the prompt once; when the assistant finishes the
evaluation, `stop_hook_active` is true and the hook exits quietly.
**Fail-safe:** any error exits 0 without blocking — a broken hook never traps you.

## Install

Add the snippet in [`settings.snippet.json`](settings.snippet.json) to your
Claude Code settings, replacing the path with the absolute path to this file.

- **Everywhere:** `~/.claude/settings.json`
- **This project only:** `.claude/settings.json` in the repo you want evaluated

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "python3 /abs/path/to/portfolio/hooks/evaluate_session.py" }
        ]
      }
    ]
  }
}
```

The hook needs the portfolio MCP server connected (see [`../mcp/README.md`](../mcp/README.md))
for `log_activity` to be callable. Without it, the assistant reports what it
*would* have logged and stops.

## Test

```bash
echo '{"stop_hook_active": false}' | python3 hooks/evaluate_session.py   # → blocks, injects rubric
echo '{"stop_hook_active": true}'  | python3 hooks/evaluate_session.py   # → empty (loop guard)
```
