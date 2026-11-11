# Architecture

## Principle

**The site is not alive — the content is.** There is no server running 24/7. The site is a static build; "aliveness" comes from an automated pipeline that turns real work sessions into curated content commits.

Since the veto-window redesign (issue #2) the second principle is: **the LLM decides what is risky, not what is good.** Publication is the default; the human intervenes by exception (a veto), and only where attention is actually needed (entries a confidentiality judge held back).

## Components

```
┌─────────────────────┐
│  Claude Code        │  You work here. Nothing changes about your workflow.
│  (daily work)       │
└─────────┬───────────┘
          │ session ends
          ▼
┌─────────────────────┐
│  Capture hook       │  Silent Stop hook. Queues {session, transcript} to a
│  (silent)           │  local file. Zero conversation noise, no evaluation yet.
└─────────┬───────────┘
          │ daily (LaunchAgent) or on demand: make drain
          ▼
┌─────────────────────┐
│  Drain — triage     │  Drops sessions without a transcript on disk and
│                     │  headless ones (entrypoint ≠ cli: claude -p / SDK
│                     │  workers) as `skipped`, with the reason. Only interactive
│                     │  sessions carry human decisions worth evaluating.
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  Judge 1: relevance │  Headless claude -p per session: reads the transcript,
│  (claude -p + MCP)  │  judges it against rubric.md. Most → DESCARTADO (correct).
│                     │  If worthy: two layers × two languages, sanitized by
│                     │  category, log_activity → STAGING branch. Structured
│                     │  verdict: REGISTRADO | DESCARTADO | FALHA. A FALHA (MCP
│                     │  down, token expired…) keeps the session in the queue.
└─────────┬───────────┘
          │ end of round: every staging entry not yet on main
          ▼
┌─────────────────────┐
│  Judge 2:           │  Headless claude -p, no tools, ONE question: does the
│  confidentiality    │  entry identify a client through sector + scale +
│  (claude -p)        │  geography (or names, metrics, timelines)? The local
│                     │  denylist is the last barrier, by name. Fail-closed.
└─────────┬───────────┘
          │ gh pr create (one PR per group)
          ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  PRs → main                                                               │
│   drafts/<date>        liberadas · 48h veto window                        │
│   drafts/<date>-zero   liberadas · personal/open source · label janela-zero│
│   retidas/<date>       retidas pelo juiz · label segurar · MERGE MANUAL   │
│  + digest (Slack webhook or stdout): titles, summaries, PR link,          │
│    "vai ao ar em 48h"                                                     │
└─────────┬─────────────────────────────────────────────────────────────────┘
          │ hourly GitHub Action (auto-merge-drafts.yml)
          │   merges drafts/* older than 48h without `segurar`;
          │   janela-zero on the first run; never retidas/*
          ▼
┌─────────────────────┐
│  main branch        │  Squash-merge → ci.yml (dispatched explicitly) →
│  content/           │  Cloudflare Pages rebuild. Site updates in ~1 minute.
└─────────────────────┘
```

**Veto:** put the label `segurar` on the PR, or close it. To veto a single entry, delete its file from the PR branch (GitHub UI → the file → delete). Removing `segurar` later resumes the clock (the window counts from PR creation, so an old PR merges on the next hourly run).

## Repository layout

```
portfolio/
├── site/          # Astro static site, i18n EN/PT, dark minimal theme
├── content/       # THE data. Feed, projects, now, cv. Yours, not the template's.
├── config/        # zero_window.json — projects that skip the 48h window
├── mcp/           # portfolio-mcp server (Python)
├── hooks/         # capture_session.py · drain_queue.py · confidentiality_judge.py
│                  # round_publisher.py · digest.py · LaunchAgent plist example
├── .github/workflows/  # ci.yml (validate/build/deploy) · auto-merge-drafts.yml
├── docs/          # you are here
├── rubric.md      # relevance + sanitization criteria — versioned, forkable
└── CLAUDE.md      # agent instructions for working on this repo
```

## Key design decisions

**Static site, git as database.** Content lives as JSON/Markdown in `content/`. Every change is a commit → full history, easy rollback, zero infra cost, and the deploy pipeline (push → rebuild) comes free from the host.

**Capture at session end, evaluation out of band.** The `Stop` hook is silent: it only queues the finished session (id + transcript path) to a local file. The judgment runs later — daily via a LaunchAgent, or whenever you run `make drain` — as a headless `claude -p` per queued session. The drain has to run on the Mac because the transcripts only exist on its disk; everything after the PR runs on GitHub, so publication happens even with the Mac off.

**Veto window instead of approval gate.** The first design required `review_and_publish` for every entry. In practice that gate stalled the feed (nothing published between 2026-07-21 and 2026-10-28). A second LLM *approving* would not have helped — it would just remove the human. So the human's role changed from approving to vetoing: the drain opens a PR, the digest tells you what is about to go live, and 48 hours later the Action merges unless you said no. Attention is spent only by exception.

**Two judges, two questions.** The relevance judge answers "is this worth an entry?" against `rubric.md`. The confidentiality judge answers one question only: "can a reader identify a client through the combination of sector, scale and geography?" Separating them keeps each prompt sharp, and lets the second one fail closed (anything unreadable is retained) without starving the feed. The local denylist stays as the last, deterministic barrier — but it only catches names, which is exactly why the judge exists.

**The PR *is* the veto window.** A field in the JSON plus a Slack-reaction bot would need a server listening. A PR already gives diff, history, comments, a label as the veto button and a hourly Action as the publisher, with no new infrastructure. The entries are written to the PR branch already with `status: "published"`: the site only builds `main`, so the merge itself is the publish, and the Action needs no commit step.

**Retained entries are a separate PR, never auto-merged.** `retidas/<date>` gets the label `segurar` from birth and the Action ignores the `retidas/*` prefix outright (belt and braces). The body lists the judge's reason per entry. You edit the text on the branch if needed and merge by hand — that is where the human's attention goes.

**Zero window for personal and open-source work.** Entries whose `project` is listed in `config/zero_window.json` have no client to protect; they go to `drafts/<date>-zero` with the label `janela-zero` and merge on the Action's next hourly run.

**Structured verdicts, retries, triage (issue #3).** The evaluator must end with `REGISTRADO <id>`, `DESCARTADO <reason>` or `FALHA <reason>`. Only the first two mark a session processed; a `FALHA` or an unrecognisable answer leaves it in the queue with an attempt counter (3 strikes → `skipped`, with the reason, so a broken transcript cannot block the daily round forever). Before the round, the drain checks the MCP's GitHub token against the API and aborts loudly on 401 — nothing is marked processed when the tooling is down. Headless sessions (`entrypoint` ≠ `cli`) and sessions whose transcript is gone are `skipped` on sight; of 555 queued sessions in October 2026, 338 were headless workers and 181 had no transcript.

**Staging branch, not `drafts`.** `log_activity` still writes to a buffer branch, but it is named `staging`: git cannot hold both a ref `drafts` and refs `drafts/<date>`, and the PR branches must match `drafts/*` for the Action. The MCP default moved accordingly (`PORTFOLIO_DRAFTS_BRANCH`, default `staging`); the drain forces it in the config it hands the headless evaluator, so it never depends on the owner's own MCP registration.

**GITHUB_TOKEN merges, explicit CI dispatch.** The Action merges with the default `GITHUB_TOKEN` (`contents` + `pull-requests` write), which is enough while `main` has no branch protection. Pushes made with that token do not trigger `on: push` workflows, so after merging the Action dispatches `ci.yml` explicitly (`actions: write`); `ci.yml` accepts `workflow_dispatch` and deploys from `main` on it. If you later protect `main` with required reviews, the merge step needs a PAT or a GitHub App token instead.

**Two-layer, two-language writing at log time.** Audience is "anyone who wants to verify talent" — technical and non-technical. Each feed entry carries a plain-language narrative and an expandable technical detail, both in EN and PT, written by the LLM at commit time so i18n never becomes maintenance work.

**GitHub stats at build time.** Client-side GitHub API calls hit a 60 req/h unauthenticated rate limit. Stats are fetched during build instead.

**Template/content separation.** The engine is MIT-licensed and public; the content directory is replaceable. Nothing sensitive can ever live in the engine, because the engine is public by definition.

## Failure modes considered

| Failure | Consequence | Mitigation |
|---|---|---|
| Owner stops working in Claude Code for weeks | Feed goes quiet | Site design does not depend on the feed; classic sections stand alone. "Now" shows week granularity |
| Sanitization misses something | Identifying detail in an entry | Confidentiality judge retains it (`retidas/*`, manual merge); denylist catches names; 48h digest + PR diff give a human a look before anything else goes live |
| Confidentiality judge is down or answers garbage | — | Fail-closed: the entry is retained, never auto-merged |
| MCP server or GitHub token down during the drain | Evaluator cannot log | Preflight token check aborts the round; `FALHA` verdicts keep sessions queued with an attempt counter — nothing is marked processed |
| Round crashes between evaluation and PR | Entries sit on `staging` | Next round's publish stage picks up every staging entry not on main (`--skip-eval` runs just that stage) |
| Nobody reads the digest for a week | Entries go live unreviewed | By design — the judges, not the owner, are the gate. Veto remains possible after the fact: revert the squash commit |
| Owner wants to stop everything | — | Label `segurar` on each open PR, or disable the Action in the repo's Actions tab |
| LLM logs trivia | Noise in the feed | Rubric with explicit exclusion list + the "senior engineer test" |
| GitHub token leaks | Repo write access | Fine-grained PAT, single repo, contents:write only, stored in local MCP config, never in the repo |
| Rebuild fails | Stale site (still up) | Static hosting keeps last good build; failures are non-destructive |
