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

## 3. Create the `staging` branch

`log_activity` writes here; the drain moves entries from `staging` into PRs
against `main`. (The drain creates it on first run if missing — this just makes
it explicit.)

```bash
git switch -c staging && git push -u origin staging && git switch main
```

> **Migrating from the old `drafts` branch?** Git cannot hold a branch `drafts`
> and the PR refs `drafts/<date>` at the same time. Rename it once:
> `gh api -X POST repos/OWNER/REPO/git/refs -f ref=refs/heads/staging -f sha=$(gh api repos/OWNER/REPO/git/ref/heads/drafts --jq .object.sha)`
> then `gh api -X DELETE repos/OWNER/REPO/git/refs/heads/drafts`. The drain
> refuses to run while `drafts` exists and prints these two commands.

### 3b. Labels and the auto-merge Action

The drain creates the labels `segurar` and `janela-zero` on first use. The hourly
Action ([`.github/workflows/auto-merge-drafts.yml`](../.github/workflows/auto-merge-drafts.yml))
runs with the default `GITHUB_TOKEN` and needs nothing else while `main` is
unprotected. If you add branch protection with required reviews, the merge step
will need a PAT or GitHub App token — see [architecture.md](architecture.md).

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
  -e UV_NO_ENV_FILE=1 \
  -- uv run --project "$(pwd)/mcp" portfolio-mcp
```

Env vars the server reads: `GITHUB_TOKEN` and `PORTFOLIO_REPO` (required);
`PORTFOLIO_DENYLIST`, `PORTFOLIO_DRAFTS_BRANCH` (default `staging`),
`PORTFOLIO_MAIN_BRANCH` (optional, sensible defaults). `UV_NO_ENV_FILE=1` keeps
`uv run` from aborting when your shell exports `UV_ENV_FILE` (see
[mcp/README.md](../mcp/README.md)). Verify with `claude mcp list` — `portfolio`
should be connected. The drain also needs the [`gh` CLI](https://cli.github.com/)
logged in as the repo owner: it opens the PRs with your `gh` auth.

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
- [ ] `make drain` on a real session either discards it or opens a `drafts/<date>` PR — and the entry does **not** appear on the live site before the merge
- [ ] An entry written with sector + scale + geography lands in a `retidas/<date>` PR with the label `segurar`
- [ ] `config/zero_window.json` lists only projects with no client to protect
- [ ] The Action ran at least once (Actions tab → "Auto-merge drafts") and the merged PR's entry is on the site in ~1 min

## Routine operation

The daily loop is: **you just work.** The capture hook queues sessions silently.
Once a day the LaunchAgent (or you, with `make drain`) runs a round:

```bash
make drain            # triage → relevance judge → confidentiality judge → PRs + digest
make drain-dry        # see what is queued (no model, no PR)
```

Each round opens at most three PRs: `drafts/<date>` (liberadas, 48h veto window),
`drafts/<date>-zero` (personal/open source, merges on the next hourly run) and
`retidas/<date>` (held by the confidentiality judge, label `segurar`, **manual
merge**). The digest — Slack if `PORTFOLIO_SLACK_WEBHOOK` is set, stdout otherwise —
lists titles, summaries and the PR link.

Your job is the veto: read the digest, and if something must not go live, put the
label `segurar` on the PR (or close it; to drop one entry, delete its file from the
branch). Otherwise do nothing — the Action merges after 48h and the site rebuilds.
Review the `retidas/*` PRs when you have a minute: edit the text on the branch if
needed, then merge by hand. Run **`update_now`** when your focus shifts.

See [hooks/README.md](../hooks/README.md) for the round internals, the LaunchAgent
install and the `--skip-eval` / `--skip-pr` / `--limit` flags.
