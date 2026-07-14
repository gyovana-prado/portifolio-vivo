# Architecture

## Principle

**The site is not alive — the content is.** There is no server running 24/7. The site is a static build; "aliveness" comes from an automated pipeline that turns real work sessions into curated content commits.

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
          │ on demand: make drain
          ▼
┌─────────────────────┐
│  Drain (claude -p)  │  Headless per queued session: reads the transcript,
│  evaluate + write   │  judges it against rubric.md. Most → no action (correct).
│                     │  If worthy: two layers (narrative + technical), two
│                     │  languages (EN/PT), confidential info removed by category.
└─────────┬───────────┘
          │ log_activity (MCP) commits via GitHub API
          ▼
┌─────────────────────┐
│  drafts branch      │  Nothing here is public. Safe failure mode:
│  (buffer)           │  no review = no publish.
└─────────┬───────────┘
          │ review_and_publish (MCP tool, run on demand)
          ▼
┌─────────────────────┐
│  main branch        │  Merge triggers rebuild on Cloudflare Pages/Vercel.
│  content/           │  Site updates in ~1 minute.
└─────────────────────┘
```

## Repository layout

```
portfolio/
├── site/          # Astro static site, i18n EN/PT, dark minimal theme
├── content/       # THE data. Feed, projects, now, cv. Yours, not the template's.
├── mcp/           # portfolio-mcp server (Python)
├── hooks/         # capture_session.py (silent Stop hook) + drain_queue.py (evaluator)
├── docs/          # you are here
├── rubric.md      # relevance criteria — versioned, forkable, part of the product
└── CLAUDE.md      # agent instructions for working on this repo
```

## Key design decisions

**Static site, git as database.** Content lives as JSON/Markdown in `content/`. Every change is a commit → full history, easy rollback, zero infra cost, and the deploy pipeline (push → rebuild) comes free from the host.

**Capture at session end, evaluation on demand.** The `Stop` hook is silent: it only queues the finished session (id + transcript path) to a local file, so it adds zero noise to your conversations. The actual judgment runs later, out of band, when you run `make drain` — a headless `claude -p` per queued session reads the transcript and applies the rubric. This split keeps the daily loop invisible while still evaluating where the context is (the transcript), with no daily cron and no manual journaling. (An earlier design blocked at every turn to evaluate inline; it worked but printed an evaluation after every message — kept as `hooks/evaluate_session.py` for reference.)

**Drafts branch as a mandatory buffer (initially).** Between evaluation and publication there is a review step. The reason is not relevance — it is confidentiality. Client work must never auto-publish without a human glance. After the sanitization proves consistently reliable, the owner may relax this to direct publish with a 24h veto window. Start strict.

**Two-layer, two-language writing at log time.** Audience is "anyone who wants to verify talent" — technical and non-technical. Each feed entry carries a plain-language narrative (what was the problem, what was decided, why it matters) and an expandable technical detail. Both are written in EN and PT at commit time by the LLM, so i18n never becomes maintenance work for the owner.

**GitHub stats at build time.** Client-side GitHub API calls hit a 60 req/h unauthenticated rate limit. Stats are fetched during build instead — the content pipeline already triggers rebuilds frequently enough to keep them fresh.

**Template/content separation.** The engine is MIT-licensed and public; the content directory is replaceable. Forkers delete `content/`, add their own, deploy. This also enforces discipline: nothing sensitive can ever live in the engine, because the engine is public by definition.

## Failure modes considered

| Failure | Consequence | Mitigation |
|---|---|---|
| Owner stops working in Claude Code for weeks | Feed goes quiet | Site design does not depend on the feed; classic sections stand alone. "Now" section shows week granularity, not day |
| Sanitization misses something | Confidential info in drafts | Drafts are never public; review gate catches it before merge |
| LLM logs trivia | Noise in the feed | Rubric with explicit exclusion list + the "senior engineer test" (see rubric.md) |
| GitHub token leaks | Repo write access | Fine-grained PAT, single repo, contents:write only, stored in local MCP config, never in the repo |
| Rebuild fails | Stale site (still up) | Static hosting keeps last good build; failures are non-destructive |
