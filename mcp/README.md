# portfolio-mcp

The MCP server and content validator for the Living Portfolio.

## Content validator

```bash
python mcp/validate_content.py          # from repo root
# or
uv run --project mcp python mcp/validate_content.py
```

Exit 0 = valid, 1 = violation. A missing translation or malformed entry fails
the build, by design. Schemas live in `mcp/schemas/`.

## MCP server

Five tools that write curated content to the portfolio repo via the GitHub API:

| Tool | Writes to | Purpose |
|------|-----------|---------|
| `log_activity` | `staging` | Write a feed entry (drain evaluator, or manual). Never public. |
| `review_and_publish` | `main` | Manual fallback: list staged entries, publish/reject a selection. |
| `add_project` | `main` | Create/update a project case study. |
| `update_now` | `main` | Replace `now.json` items. |
| `get_portfolio_state` | — | Read-only snapshot; avoids duplicate logging. |

`log_activity` can only reach `staging`. Content reaches `main` through the PRs
the drain opens (`drafts/<date>`, merged by the hourly Action after a 48h veto
window — see [docs/architecture.md](../docs/architecture.md)) or through
`review_and_publish` with an explicit selection.

### Run

```bash
uv run --project mcp portfolio-mcp        # stdio MCP server
```

### Environment

Set in the MCP client's `env` block (never in the repo):

| Var | Required | Default | Meaning |
|-----|----------|---------|---------|
| `PORTFOLIO_REPO` | yes | — | `owner/name` of the portfolio repo |
| `GITHUB_TOKEN` | yes | — | Fine-grained PAT, single repo, contents:write |
| `PORTFOLIO_DRAFTS_BRANCH` | no | `staging` | Buffer branch for unpublished entries (was `drafts`; renamed because `drafts/<date>` PR refs cannot coexist with a `drafts` branch) |
| `PORTFOLIO_MAIN_BRANCH` | no | `main` | Production branch |
| `PORTFOLIO_DENYLIST` | no | `~/.portfolio-mcp/denylist.json` | Local file of names to reject |
| `UV_NO_ENV_FILE` | recommended | — | Set to `1` if your shell exports `UV_ENV_FILE`: otherwise `uv run` aborts in directories without a `.env` and the server never starts (`CONNECTION_CLOSED`) |

### Denylist

Local-only file, never committed — defense in depth behind the rubric's
category-based sanitization:

```json
{ "names": ["Acme Corp", "Client X", "Employer Y"] }
```

Any entry mentioning a listed name (case-insensitive, anywhere in the content)
is rejected outright.

### Claude Code config (`.mcp.json` or settings)

```json
{
  "mcpServers": {
    "portfolio": {
      "command": "uv",
      "args": ["run", "--project", "/abs/path/to/portfolio/mcp", "portfolio-mcp"],
      "env": {
        "PORTFOLIO_REPO": "you/living-portfolio",
        "GITHUB_TOKEN": "github_pat_...",
        "UV_NO_ENV_FILE": "1"
      }
    }
  }
}
```

## Tests

```bash
uv run --project mcp pytest -q
```
