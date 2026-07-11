# Documentation index

The design docs for the Living Portfolio. Read these before changing the engine.

| Doc | What it covers |
|-----|----------------|
| [architecture.md](architecture.md) | The pipeline (Claude Code → hook → drafts → main), repo layout, key design decisions, failure modes |
| [content-model.md](content-model.md) | The `content/` JSON schema: feed entries, projects, now, cv, profile, the i18n rule |
| [mcp-server.md](mcp-server.md) | The `portfolio-mcp` server: tools, security model, session-end hook |
| [deployment.md](deployment.md) | First deploy, verification checklist, routine operation, forking |

Product-level docs live at the repo root:

- [../README.md](../README.md) — the value proposition
- [../rubric.md](../rubric.md) — the relevance & sanitization rubric (the heart of the system)
- [../CLAUDE.md](../CLAUDE.md) — agent instructions for working on this repo
