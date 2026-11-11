# Session hooks

Two modes for feeding the portfolio from Claude Code sessions. **Capture +
drain is the recommended one** — the inline evaluator is kept for reference.

## Recommended: silent capture + deferred evaluation

- [`capture_session.py`](capture_session.py) — a **Stop** hook that never
  blocks and never prints: it just records `{session_id, transcript_path, cwd,
  last_stop}` in `~/.claude/portfolio/queue.jsonl` (one line per session,
  deduped). Zero conversation noise.
- [`drain_queue.py`](drain_queue.py) — runs one **round**, out of band:

  1. **Triage.** Sessions whose transcript is gone, or whose `entrypoint` is not
     `cli` (headless `claude -p` / SDK workers — no human decision to evaluate)
     are marked `skipped` with the reason. Nothing is silently dropped.
  2. **Relevance judge.** For each remaining session, a headless `claude -p`
     reads the transcript, judges it against [`rubric.md`](../rubric.md)
     (embedded verbatim) and, only if it clears the bar, logs a **draft** to the
     `staging` branch via the portfolio MCP `log_activity`. It must end with a
     structured verdict: `REGISTRADO <id>`, `DESCARTADO <reason>` or
     `FALHA <reason>`. Only the first two mark the session processed; a `FALHA`
     (MCP down, token expired, unreadable answer) keeps it in the queue with an
     attempt counter — after `--max-attempts` (3) it becomes `skipped`.
  3. **Publish stage** ([`round_publisher.py`](round_publisher.py)). Every
     staging entry not yet on `main` goes through the
     [confidentiality judge](confidentiality_judge.py) and lands in a PR:

     | branch | contents | label | merged by |
     |---|---|---|---|
     | `drafts/<date>` | liberadas | — | the Action, after 48h without veto |
     | `drafts/<date>-zero` | liberadas, `project` in [`config/zero_window.json`](../config/zero_window.json) | `janela-zero` | the Action, next hourly run |
     | `retidas/<date>` | retidas pelo juiz (reason per entry in the body) | `segurar` | **you, by hand** — never the Action |

     Entries are written to the PR branch already with `status: "published"`;
     the site only builds `main`, so the merge is the publish. A digest with
     title, summary and PR link goes to Slack if `PORTFOLIO_SLACK_WEBHOOK` is
     set, otherwise to stdout.

```bash
make drain                                   # full round
make drain-dry                               # triage + list; no model, no PR
python3 hooks/drain_queue.py --limit 1       # evaluate just one session
python3 hooks/drain_queue.py --skip-eval     # only the publish stage (staging → PRs)
python3 hooks/drain_queue.py --skip-pr       # only evaluate; leave entries on staging
python3 hooks/confidentiality_judge.py content/feed/<id>.json   # judge one entry by hand
```

**Veto:** label `segurar` on the PR, or close it. One entry only: delete its
file from the PR branch. The hourly Action
([`.github/workflows/auto-merge-drafts.yml`](../.github/workflows/auto-merge-drafts.yml))
does the rest.

### Preflight

Before evaluating anything the drain:

- reads the `portfolio` MCP server from `~/.claude.json` and checks its GitHub
  token against the API — a 401 aborts the round with a clear message, and
  **nothing is marked processed**;
- forces `PORTFOLIO_DRAFTS_BRANCH=staging` and `UV_NO_ENV_FILE=1` in the config
  it hands the headless evaluator (see [`mcp/README.md`](../mcp/README.md));
- creates `staging` from `main` if missing, and refuses to run while the legacy
  `drafts` branch exists (git cannot hold `drafts` and `drafts/<date>` at the
  same time — the error message prints the two `gh api` calls that migrate it).

### Processed log

`~/.claude/portfolio/processed.jsonl` now records
`{session_id, processed_at, status, detail}` with `status` in
`registrado | descartado | skipped | falha`. Records without `status` (written
before this change) count as processed. `make drain-dry` shows the attempt
count of sessions that failed before.

### Daily drain (LaunchAgent)

The drain must run on the Mac (transcripts live on its disk); everything after
the PR runs on GitHub, so publication happens even with the Mac off.
[`com.portfolio.drain.plist.example`](com.portfolio.drain.plist.example) runs
`make drain` daily at 19:00. To install:

```bash
sed -e "s#/ABS/PATH/portifolio-vivo#$(pwd)#g" -e "s#/ABS/PATH#$HOME#g" \
    hooks/com.portfolio.drain.plist.example > ~/Library/LaunchAgents/com.portfolio.drain.plist
# check the PATH entry: claude, gh, uv and python3 must be reachable from launchd
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.portfolio.drain.plist
launchctl kickstart -k gui/$(id -u)/com.portfolio.drain      # run once, now
tail -f ~/.claude/portfolio/drain.log
```

Remove with `launchctl bootout gui/$(id -u)/com.portfolio.drain`. Optional:
set `PORTFOLIO_SLACK_WEBHOOK` in the plist's `EnvironmentVariables` to get the
digest in Slack (an incoming-webhook URL you create yourself; nothing here
creates credentials).

### Implementation notes learned the hard way

- Headless sessions run with `--settings '{"disableAllHooks": true}'`. A global
  Stop hook would hijack the `result` field of `claude -p` (the evaluation
  prompt would replace the model's answer — observed 2026-07-12) and the
  capture hook would re-enqueue the evaluator's own session, looping forever.
- The confidentiality judge runs with `--tools ""`: it needs no tools, and a
  tool-less call cannot wander off into the repo.
- The MCP config (including the GitHub token) is read at runtime from the
  `portfolio` server registered in `~/.claude.json` — no secrets here.
- The evaluator is instructed to Grep/Read the transcript strategically, not
  to ingest it whole (transcripts of long sessions are large).
- Free-text verdicts were the bug behind issue #3: "nada registrado — o MCP
  falhou" used to count as processed. Anything that is not one of the three
  words is now a `FALHA`.

### Install

Add the snippet in [`settings.snippet.json`](settings.snippet.json) to your
Claude Code settings, replacing the path:

- **Everywhere:** `~/.claude/settings.json`
- **This project only:** `.claude/settings.json` in the repo you want captured

### Test

```bash
echo '{"session_id": "teste", "transcript_path": "/tmp/x.jsonl"}' | python3 hooks/capture_session.py
make drain-dry                           # → "skip   : teste  transcript ausente …"
uv run --project mcp pytest -q hooks     # unit tests: verdicts, triage, judge, publisher, digest
```

## Legacy: inline evaluation (noisy)

[`evaluate_session.py`](evaluate_session.py) is the original **Stop** hook: it
blocks at the end of every turn and injects the rubric evaluation into the
conversation itself. It works, but the evaluation log appears after every
message — fine for demos, tiring for daily use. Same rubric, same guarantees
(loop-safe via `stop_hook_active`, fail-safe on errors).
