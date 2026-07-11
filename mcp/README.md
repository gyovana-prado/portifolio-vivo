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
| `log_activity` | `drafts` | Write a feed entry (session-end hook, or manual). Never public. |
| `review_and_publish` | `main` | List pending drafts, or publish/reject a selection — the human gate. |
| `add_project` | `main` | Create/update a project case study. |
| `update_now` | `main` | Replace `now.json` items. |
| `get_portfolio_state` | — | Read-only snapshot; avoids duplicate logging. |

`log_activity` can only reach `drafts`. Content reaches `main` only through
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
| `PORTFOLIO_DRAFTS_BRANCH` | no | `drafts` | Buffer branch for unpublished entries |
| `PORTFOLIO_MAIN_BRANCH` | no | `main` | Production branch |
| `PORTFOLIO_DENYLIST` | no | `~/.portfolio-mcp/denylist.json` | Local file of names to reject |

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
        "GITHUB_TOKEN": "github_pat_..."
      }
    }
  }
}
```

## Tests

```bash
uv run --project mcp pytest -q
```
