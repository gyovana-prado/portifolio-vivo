# Deployment & setup

End-to-end setup, copy-pasteable. Two audiences, same steps: the **owner** (first
deploy of this repo) and a **forker** (someone building their own from a fork).
The only difference is step 2 — forkers replace the content; the owner already has it.

## Prerequisites

- **Node.js ≥ 18** and **npm** — builds the Astro site.
- **[uv](https://docs.astral.sh/uv/)** — runs the Python MCP server and validator.
- A **GitHub account** and the **[`gh` CLI](https://cli.github.com/)** (optional, but handy).
- **[Claude Code](https://claude.com/claude-code)** — where the automation lives.
- A **Cloudflare** or **Vercel** account — free tier, hosts the static site.

## 1. Fork and clone

```bash
# Fork this repo to your account (via the GitHub UI, or:)
gh repo fork <owner>/portifolio-vivo --clone
cd portifolio-vivo

make install          # installs site deps (npm) + mcp deps (uv)
```

## 2. Make the content yours (forkers)

`content/` is your data; `site/` is the template — never mix them. Minimum viable
content to build: `profile.json`, `cv.json`, one file in `projects/`, and `now.json`.
The feed can start empty — it fills itself.

```bash
# edit the JSON in content/ with your own data
make validate         # checks every file against the schemas
```

> **Bilingual by design.** Every human-readable string is a `{ "en": "...", "pt": "..." }`
> object, and a **missing translation fails the build** on purpose. If you want a
> single language, either put the same text in both fields, or drop `pt` from the
> schemas in `mcp/schemas/` and the `t()` helper in `site/src/lib/content.ts`.

## 3. Create the `drafts` branch

The automation writes here; `main` is only reached through the human gate.

```bash
git switch -c drafts && git push -u origin drafts && git switch main
```

## 4. Deploy the site

Cloudflare Pages or Vercel — both free, both deploy-on-push:

- Connect your fork; set the **build root to `site/`**, framework preset **Astro**
  (build command `npm run build`, output `dist`).
- **Production branch: `main`.** Do *not* add `drafts` as a preview branch unless
  you want private preview URLs of unpublished content.
- Add a custom domain if you have one.

This repo ships a GitHub Actions workflow (`.github/workflows/`) that validates,
tests, and deploys to Cloudflare Pages on push to `main`. If you use it, add the
`CLOUDFLARE_API_TOKEN` repo secret (scoped to Pages Edit). On Vercel, its own
git integration replaces the workflow.

## 5. Create the GitHub token

Fine-grained PAT → **only this repo** → **Contents: Read and write**. Nothing else.
Copy it; you'll paste it into the MCP config next.

## 6. Register the MCP server in Claude Code

The server writes to your repo via the GitHub API. Register it once, at user scope,
with the token and repo in the env (never in the repo):

```bash
claude mcp add portfolio --scope user \
  -e GITHUB_TOKEN=github_pat_YOUR_TOKEN \
  -e PORTFOLIO_REPO=YOUR_USER/YOUR_REPO \
  -- uv run --project "$(pwd)/mcp" portfolio-mcp
```

Env vars the server reads: `GITHUB_TOKEN` and `PORTFOLIO_REPO` (required);
`PORTFOLIO_DENYLIST`, `PORTFOLIO_DRAFTS_BRANCH`, `PORTFOLIO_MAIN_BRANCH` (optional,
sensible defaults). Verify with `claude mcp list` — `portfolio` should be connected.

## 7. Configure the denylist

Local file (never committed), your safety net: the client and employer names that
must never appear in published content. The validator rejects any entry containing them.

```bash
mkdir -p ~/.portfolio-mcp
printf '{ "names": ["Acme Corp", "Some Client"] }\n' > ~/.portfolio-mcp/denylist.json
```

## 8. Install the capture hook

A silent `Stop` hook records each finished session into a local queue — **no output
in the conversation**. Evaluation happens later, on demand (step 9), so your chats
stay clean. Merge the snippet from [`hooks/settings.snippet.json`](../hooks/settings.snippet.json)
into `~/.claude/settings.json`, replacing the path with your absolute path:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "python3 /ABS/PATH/portifolio-vivo/hooks/capture_session.py" }
        ]
      }
    ]
  }
}
```

## Verify before going live

- [ ] Contracts reviewed: you may disclose *that* the work exists, not just its details ([rubric.md](../rubric.md), "Contract awareness")
- [ ] Denylist covers every current client and employer
- [ ] Token is fine-grained and single-repo
- [ ] `make drain` on a real session either logs nothing or writes a draft — and the draft does **not** appear on the live site
- [ ] `review_and_publish` merges an approved draft and the site rebuilds in ~1 min

## Routine operation

The daily loop is: **you just work.** The capture hook queues sessions silently.
Then, whenever you feel like it (weekly is plenty):

```bash
make drain            # evaluates queued sessions → writes drafts (via claude -p + MCP)
```

`make drain` spawns a headless `claude -p` per pending session that reads the
transcript, judges it against `rubric.md`, and — only if it clears the bar — writes
a **draft**. Then, in Claude Code, run **`review_and_publish`** to approve or reject
drafts (under a minute), and **`update_now`** when your focus shifts. Nothing reaches
the live site without that human approval.

See [hooks/README.md](../hooks/README.md) for the capture/drain internals and the
`--dry-run` / `--limit` flags.
