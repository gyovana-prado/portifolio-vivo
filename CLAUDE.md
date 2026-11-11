# CLAUDE.md — Living Portfolio

Self-updating portfolio: static Astro site + content-as-git + MCP publishing pipeline.

- Read [README.md](README.md) for the value prop; [docs/README.md](docs/README.md) is the doc index. Search there before asking.
- `content/` is data, `site/` is template — never mix. Nothing client-identifying ever goes in `content/` or code.
- Relevance and sanitization rules live in [rubric.md](rubric.md). The hook embeds it verbatim — edit the rubric, not the hook.
- All human-readable strings are bilingual `{en, pt}` objects. Missing translation = build failure, by design.
- The `staging` branch is the only write target for `log_activity`. `main` changes via the PRs the drain opens (`drafts/<date>`, merged by the hourly Action after a 48h veto window; `retidas/<date>` only by hand) or via `review_and_publish`. See [docs/architecture.md](docs/architecture.md).
- Hooks are stdlib-only python3 scripts (`make drain` runs them without uv); their tests live in `hooks/tests/` and run with the MCP suite (`make test`).
- Site build: `cd site && npm run build`. Schema check: `python mcp/validate_content.py`.
