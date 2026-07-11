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
│  Session-end hook   │  Evaluates the session against rubric.md.
│  (evaluate)         │  Most sessions → no action. That is correct behavior.
└─────────┬───────────┘
          │ only if portfolio-worthy
          ▼
┌─────────────────────┐
│  Write + sanitize   │  Two layers (narrative + technical), two languages
│  (LLM)              │  (EN/PT), confidential info removed by category.
└─────────┬───────────┘
          │ commit via GitHub API
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
├── hooks/         # Claude Code session-end hook + evaluation prompt
├── docs/          # you are here
├── rubric.md      # relevance criteria — versioned, forkable, part of the product
└── CLAUDE.md      # agent instructions for working on this repo
```

## Key design decisions

**Static site, git as database.** Content lives as JSON/Markdown in `content/`. Every change is a commit → full history, easy rollback, zero infra cost, and the deploy pipeline (push → rebuild) comes free from the host.

**Evaluation at session end, not on a schedule.** The hook runs where the context is — Claude Code already knows what happened in the session. No daily cron asking "what did you do today?", no manual journaling. The human habit is removed from the loop entirely.

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
