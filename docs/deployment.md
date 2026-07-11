# Deployment

## For the owner (first deploy)

1. **Create the repo** from this template on your personal GitHub account. Public.
2. **Replace `content/`** with your own data. Minimum viable: `profile.json`, `cv.json`, one project, `now.json`. The feed can start empty — it will fill itself.
3. **Create the `drafts` branch** from `main`.
4. **Deploy the site.** Cloudflare Pages or Vercel, both free tier:
   - Connect the repo, set build root to `site/`, framework preset Astro.
   - Production branch: `main`. (Do not add `drafts` as a preview branch unless you want private preview URLs of unpublished content.)
   - Add your custom domain if you have one (e.g. `yourname.dev`).
5. **Create the GitHub token.** Fine-grained PAT → only this repo → Contents: Read and write. Nothing else.
6. **Install the MCP server** in Claude Code, with the token and repo in the env config.
7. **Install the session-end hook** (`hooks/` has the config snippet for `settings.json`).
8. **Configure the denylist** (`~/.portfolio-mcp/denylist.json`, local only): the client and employer names that must never appear in content.

## Verify before going live

- [ ] Contracts reviewed: you may disclose *that* the work exists, not just its details ([rubric.md](rubric.md), "Contract awareness")
- [ ] Denylist covers every current client and employer
- [ ] Token is fine-grained and single-repo
- [ ] A test entry logged to `drafts` does **not** appear on the live site
- [ ] `review_and_publish` merges it and the site rebuilds

## Routine operation

There is none — that's the point. Work normally. When you feel like it (weekly is plenty), run `review_and_publish` in Claude Code and approve/reject drafts in under a minute. Update `now.json` when your focus shifts.

## For forkers

Same steps. Delete `content/`, add yours, adapt `rubric.md` to your own bar, deploy. The engine is MIT — the only thing that's not yours in a fork is the original owner's content, which you deleted in step one.
