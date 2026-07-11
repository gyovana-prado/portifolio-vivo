# CLAUDE.md — Living Portfolio

Self-updating portfolio: static Astro site + content-as-git + MCP publishing pipeline.

- Read [README.md](README.md) for the value prop; [docs/README.md](docs/README.md) is the doc index. Search there before asking.
- `content/` is data, `site/` is template — never mix. Nothing client-identifying ever goes in `content/` or code.
- Relevance and sanitization rules live in [rubric.md](rubric.md). The hook embeds it verbatim — edit the rubric, not the hook.
- All human-readable strings are bilingual `{en, pt}` objects. Missing translation = build failure, by design.
- Drafts branch is the only write target for automation. `main` changes only via `review_and_publish`.
- Site build: `cd site && npm run build`. Schema check: `python mcp/validate_content.py`.
