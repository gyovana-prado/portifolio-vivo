# Living Portfolio

A portfolio that updates itself — powered by AI, connected to your real work through MCP.

## The problem

A résumé says what you did. GitHub shows code you pushed. Neither shows **how you think** — the decisions, trade-offs, and judgment that define talent in the AI era. And every "personal site" eventually goes stale, because keeping it updated is a chore nobody sustains.

## The idea

Your portfolio becomes a **live feed of real work**, curated automatically:

1. You work normally inside Claude Code.
2. A **silent** session-end hook queues each finished session locally — zero noise in your conversations.
3. Once a day (a LaunchAgent, or `make drain` whenever you like) the drain evaluates the queued sessions against a [relevance rubric](rubric.md): did this session produce a non-obvious technical decision, a hard problem solved, something new that exists now, or a first-time applied learning?
4. Most sessions produce nothing — and that's the point. When something is portfolio-worthy, the LLM writes it up in two layers (plain-language narrative + technical detail), in two languages (EN/PT), and sanitizes client-confidential information by category.
5. A second LLM — the **confidentiality judge** — asks one question: can a reader identify a client from the combination of sector, scale and geography? Entries that pass go into a pull request with a **48-hour veto window**; entries it retains go into a separate PR that only you can merge.
6. You get a digest (Slack or terminal) with the titles and the PR link. To veto, put the label `segurar` on the PR or close it. Say nothing, and an hourly GitHub Action merges it after 48h — the site rebuilds, even with your Mac off. Personal and open-source work skips the window.

The LLM decides what is *risky*, not what is *good*; the decision about what goes in stays human — by exception. The cognitive load of "remembering to update the portfolio" is transferred to the system. If you have ADHD or just a life, this is the difference between a living portfolio and a dead one with a timestamp.

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
| Evaluation | `make drain` (headless `claude -p`, daily LaunchAgent) | Two judges: relevance against the rubric, then confidentiality |
| Veto window | PR `drafts/<date>` + hourly GitHub Action | Diff, history and a label as the veto button — no bot, no server |
| Writing | MCP server (Python) | `log_activity` (staging), `add_project`, `update_now` tools |
| Auth | Fine-grained GitHub PAT + `gh` | Single repo, `contents:write` only; PRs via your `gh` login |

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
make drain      # one drain round: triage → relevance → confidentiality → PRs (needs the MCP registered)
make drain-dry  # what the drain would evaluate (no model, no PR)
```

Repository layout:

```
├── site/       # Astro static site (i18n EN/PT, dark theme, RSS)
├── content/    # THE data — feed, projects, now, cv, profile (yours)
├── config/     # zero_window.json — projects that skip the 48h veto window
├── mcp/        # portfolio-mcp server (Python/uv) + content validator + schemas
├── hooks/      # capture (Stop hook), drain, confidentiality judge, round publisher, digest, LaunchAgent example
├── .github/    # ci.yml (validate/build/deploy) + auto-merge-drafts.yml (the veto window's publisher)
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
