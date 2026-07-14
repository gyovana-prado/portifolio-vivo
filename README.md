# Living Portfolio

A portfolio that updates itself — powered by AI, connected to your real work through MCP.

## The problem

A résumé says what you did. GitHub shows code you pushed. Neither shows **how you think** — the decisions, trade-offs, and judgment that define talent in the AI era. And every "personal site" eventually goes stale, because keeping it updated is a chore nobody sustains.

## The idea

Your portfolio becomes a **live feed of real work**, curated automatically:

1. You work normally inside Claude Code.
2. A **silent** session-end hook queues each finished session locally — zero noise in your conversations.
3. Whenever you feel like it, you run `make drain`. It evaluates the queued sessions against a [relevance rubric](rubric.md): did this session produce a non-obvious technical decision, a hard problem solved, something new that exists now, or a first-time applied learning?
4. Most sessions produce nothing — and that's the point. When something is portfolio-worthy, the LLM writes it up in two layers (plain-language narrative + technical detail), in two languages (EN/PT), sanitizes client-confidential information, and commits it to a `drafts` branch.
5. You review and publish drafts with one command whenever you want. Unreviewed drafts never go live — the failure mode is safe.
6. Every publish triggers a rebuild. The site is always static, always fast, always shareable.

The cognitive load of "remembering to update the portfolio" is transferred to the system. If you have ADHD or just a life, this is the difference between a living portfolio and a dead one with a timestamp.

## What the site shows

- **Now** — what I'm working on this week
- **Activity feed** — the live, curated log of real technical work
- **Projects** — case studies with stack, context, and outcomes
- **Classic sections** — experience, skills, education, certifications
- **GitHub stats** — generated at build time (no client-side rate limits)
- **RSS** — so people can subscribe to your work

## Stack

| Layer | Choice | Why |
|---|---|---|
| Site | Astro (static, i18n EN/PT) | Fast, zero runtime, content-driven |
| Hosting | Cloudflare Pages / Vercel | Free tier, deploy-on-push, public URL |
| Content | JSON + Markdown in `content/` | Git is the database; template and content are separate |
| Capture | Claude Code `Stop` hook (silent) | Queues sessions with zero conversation noise |
| Evaluation | `make drain` (headless `claude -p`) | Judges queued sessions against the rubric, on demand |
| Publishing | MCP server (Python) | `review_and_publish`, `add_project`, `update_now` tools |
| Auth | Fine-grained GitHub PAT | Single repo, `contents:write` only |

## Quickstart

```bash
gh repo fork <owner>/portifolio-vivo --clone && cd portifolio-vivo
make install                       # site (npm) + mcp (uv) deps
# then: edit content/, deploy site/ to Cloudflare/Vercel, register the MCP
# server + capture hook in Claude Code. Work. Run `make drain` when you feel
# like it. The portfolio takes care of itself.
```

**Copy-pasteable, step by step (token, MCP command, hook snippet, deploy):
[docs/deployment.md](docs/deployment.md).**

## Local development

```bash
make install    # site (npm) + mcp (uv) dependencies
make dev        # Astro dev server — EN at /, PT at /pt
make validate   # validate content/ against the schemas
make check      # full gate: validate content + run MCP tests
make build      # validate, then build the static site to site/dist
make drain      # evaluate queued sessions → write drafts (needs the MCP registered)
```

Repository layout:

```
├── site/       # Astro static site (i18n EN/PT, dark theme, RSS)
├── content/    # THE data — feed, projects, now, cv, profile (yours)
├── mcp/        # portfolio-mcp server (Python/uv) + content validator + schemas
├── hooks/      # capture_session.py (silent Stop hook) + drain_queue.py (make drain)
├── docs/       # architecture, content model, MCP spec, deployment
├── rubric.md   # relevance & sanitization criteria (the heart of the system)
└── CLAUDE.md   # agent instructions for working on this repo
```

`content/` is data, `site/` is template — never mix. Nothing client-identifying
ever goes in `content/` or code.

## Make it yours

This repo is a template. The engine (site + MCP + hook + rubric) is open source under MIT; the content is yours. Fork it, delete `content/`, add your own, deploy. The [rubric](rubric.md) — how to decide what's portfolio-worthy — is part of the product: adapt it to your own bar.

## Documentation

See [docs/README.md](docs/README.md) for the full index: architecture, content model, MCP server spec, rubric, and deployment guide.

## License

MIT
