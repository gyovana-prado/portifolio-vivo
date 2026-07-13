# Session hooks

Two modes for feeding the portfolio from Claude Code sessions. **Capture +
drain is the recommended one** — the inline evaluator is kept for reference.

## Recommended: silent capture + deferred evaluation

- [`capture_session.py`](capture_session.py) — a **Stop** hook that never
  blocks and never prints: it just records `{session_id, transcript_path, cwd,
  last_stop}` in `~/.claude/portfolio/queue.jsonl` (one line per session,
  deduped). Zero conversation noise.
- [`drain_queue.py`](drain_queue.py) — evaluates the queue **out of band**:
  for each pending session it spawns a headless `claude -p` that reads the
  transcript, judges it against [`rubric.md`](../rubric.md) (embedded verbatim)
  and, only if it clears the bar, logs a **draft** via the portfolio MCP
  `log_activity`. Run it when you want:

```bash
make drain                              # evaluate everything pending
python3 hooks/drain_queue.py --dry-run  # see what's queued
python3 hooks/drain_queue.py --limit 1  # evaluate just one
```

Nothing is ever published by automation: drafts land on the `drafts` branch
and only `review_and_publish` (you, on the site/MCP) promotes them to `main`.

Implementation notes learned the hard way:

- Headless sessions run with `--settings '{"disableAllHooks": true}'`. A global
  Stop hook would hijack the `result` field of `claude -p` (the evaluation
  prompt would replace the model's answer — observed 2026-07-12) and the
  capture hook would re-enqueue the evaluator's own session, looping forever.
- The MCP config (including the GitHub token) is read at runtime from the
  `portfolio` server registered in `~/.claude.json` — no secrets here.
- The evaluator is instructed to Grep/Read the transcript strategically, not
  to ingest it whole (transcripts of long sessions are large).

### Install

Add the snippet in [`settings.snippet.json`](settings.snippet.json) to your
Claude Code settings, replacing the path:

- **Everywhere:** `~/.claude/settings.json`
- **This project only:** `.claude/settings.json` in the repo you want captured

### Test

```bash
echo '{"session_id": "teste", "transcript_path": "/tmp/x.jsonl"}' | python3 hooks/capture_session.py
python3 hooks/drain_queue.py --dry-run   # → "pendente: teste …"
```

## Legacy: inline evaluation (noisy)

[`evaluate_session.py`](evaluate_session.py) is the original **Stop** hook: it
blocks at the end of every turn and injects the rubric evaluation into the
conversation itself. It works, but the evaluation log appears after every
message — fine for demos, tiring for daily use. Same rubric, same guarantees
(loop-safe via `stop_hook_active`, fail-safe on errors).
