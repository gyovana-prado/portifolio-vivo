"""portfolio-mcp MCP server: the tools that write curated content to the repo.

Tools:
  log_activity        write a feed entry to the drafts branch (the human gate is publish)
  review_and_publish  list pending drafts, or publish/reject a selection to main
  add_project         create/update a project (owner-invoked, writes to main)
  update_now          replace now.json items (owner-invoked, writes to main)
  get_portfolio_state read-only snapshot, so the LLM avoids duplicate logging

Security: log_activity can only reach `drafts`. Publishing to `main` happens
only through review_and_publish with an explicit selection — the human gate.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import Config, load_config
from .github import GitHubClient
from .validation import (
    ValidationError,
    validate_feed_entry,
    validate_now,
    validate_project,
)

mcp = FastMCP("portfolio-mcp")

FEED_DIR = "content/feed"
PROJECTS_DIR = "content/projects"
NOW_PATH = "content/now.json"


@lru_cache(maxsize=1)
def config() -> Config:
    return load_config()


def client() -> GitHubClient:
    cfg = config()
    return GitHubClient(cfg.repo, cfg.token)


# ── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
def log_activity(entry: dict[str, Any]) -> str:
    """Write a portfolio feed entry to the drafts branch.

    Normally called by the session-end hook, but can be invoked manually
    ("loga isso no portfólio"). The `entry` is the full feed-entry object
    (see docs/content-model.md): id, date, type, tags, narrative{en,pt},
    technical{en,pt}, optional outcome{en,pt}, status. The tool validates the
    schema, enforces bilingual completeness, and rejects denylisted names.
    Nothing written here is public until review_and_publish.
    """
    cfg = config()
    entry.setdefault("status", "draft")
    try:
        validate_feed_entry(entry, cfg.denylist)
    except ValidationError as exc:
        return f"✗ Rejected — {exc}"

    path = f"{FEED_DIR}/{entry['id']}.json"
    with client() as gh:
        existing = gh.get_file(path, cfg.drafts_branch)
        gh.put_json(
            path,
            cfg.drafts_branch,
            entry,
            message=f"feed: log {entry['id']}",
            sha=existing.sha if existing else None,
        )
    return (
        f"✓ Logged '{entry['id']}' to the {cfg.drafts_branch} branch. "
        "It is NOT public — run review_and_publish to publish it."
    )


@mcp.tool()
def review_and_publish(
    approve: list[str] | None = None, reject: list[str] | None = None
) -> str:
    """Review pending drafts, or publish/reject a selection.

    Call with no arguments to LIST pending drafts (their id, type, and narrative)
    so the owner can decide. Then call again with `approve` and/or `reject` as
    lists of entry ids:
      - approved entries are marked published and merged to the main branch,
      - rejected entries are deleted from the drafts branch.
    This is the human gate — the only path content takes to main.
    """
    cfg = config()
    with client() as gh:
        drafts = gh.list_dir(FEED_DIR, cfg.drafts_branch)
        main_names = {e["name"] for e in gh.list_dir(FEED_DIR, cfg.main_branch)}
        pending = [e for e in drafts if e["name"] not in main_names]

        if not approve and not reject:
            if not pending:
                return "No pending drafts. The feed is quiet — that's honest."
            lines = ["Pending drafts (call again with approve=[...] / reject=[...]):", ""]
            for e in pending:
                entry_id = e["name"].removesuffix(".json")
                f = gh.get_file(f"{FEED_DIR}/{e['name']}", cfg.drafts_branch)
                narrative = f.data.get("narrative", {}).get("en", "") if f else ""
                etype = f.data.get("type", "?") if f else "?"
                lines.append(f"• {entry_id}  [{etype}]")
                lines.append(f"    {narrative}")
            return "\n".join(lines)

        approve = approve or []
        reject = reject or []
        results: list[str] = []

        for entry_id in approve:
            name = f"{entry_id}.json"
            draft = gh.get_file(f"{FEED_DIR}/{name}", cfg.drafts_branch)
            if draft is None:
                results.append(f"  ? {entry_id}: not found on drafts, skipped")
                continue
            published = {**draft.data, "status": "published"}
            existing_main = gh.get_file(f"{FEED_DIR}/{name}", cfg.main_branch)
            gh.put_json(
                f"{FEED_DIR}/{name}",
                cfg.main_branch,
                published,
                message=f"publish: {entry_id}",
                sha=existing_main.sha if existing_main else None,
            )
            gh.delete_file(
                f"{FEED_DIR}/{name}",
                cfg.drafts_branch,
                draft.sha,
                message=f"publish: clear draft {entry_id}",
            )
            results.append(f"  ✓ {entry_id}: published to {cfg.main_branch}")

        for entry_id in reject:
            name = f"{entry_id}.json"
            draft = gh.get_file(f"{FEED_DIR}/{name}", cfg.drafts_branch)
            if draft is None:
                results.append(f"  ? {entry_id}: not found on drafts, skipped")
                continue
            gh.delete_file(
                f"{FEED_DIR}/{name}",
                cfg.drafts_branch,
                draft.sha,
                message=f"reject: drop draft {entry_id}",
            )
            results.append(f"  ✗ {entry_id}: rejected and deleted")

    header = "Review complete. The site rebuilds on the next push to main."
    return header + "\n" + "\n".join(results)


@mcp.tool()
def add_project(project: dict[str, Any]) -> str:
    """Create or update a project case study (writes to the main branch).

    `project` is the full project object (see docs/content-model.md): id,
    featured, title{en,pt}, summary{en,pt}, optional case_study{en,pt}, stack,
    links, period. Manual use, for case studies.
    """
    cfg = config()
    try:
        validate_project(project, cfg.denylist)
    except ValidationError as exc:
        return f"✗ Rejected — {exc}"

    path = f"{PROJECTS_DIR}/{project['id']}.json"
    with client() as gh:
        existing = gh.get_file(path, cfg.main_branch)
        verb = "update" if existing else "add"
        gh.put_json(
            path,
            cfg.main_branch,
            project,
            message=f"project: {verb} {project['id']}",
            sha=existing.sha if existing else None,
        )
    return f"✓ Project '{project['id']}' written to {cfg.main_branch}. The site will rebuild."


@mcp.tool()
def update_now(items: list[dict[str, Any]], updated: str) -> str:
    """Replace now.json items and set the updated date (writes to main).

    `items` is a list of bilingual {en, pt} objects — what you're focused on this
    week. `updated` is a YYYY-MM-DD date. Week-level granularity by design.
    """
    cfg = config()
    now = {"updated": updated, "items": items}
    try:
        validate_now(now, cfg.denylist)
    except ValidationError as exc:
        return f"✗ Rejected — {exc}"

    with client() as gh:
        existing = gh.get_file(NOW_PATH, cfg.main_branch)
        gh.put_json(
            NOW_PATH,
            cfg.main_branch,
            now,
            message=f"now: update {updated}",
            sha=existing.sha if existing else None,
        )
    return f"✓ now.json updated ({len(items)} item(s), {updated}). The site will rebuild."


@mcp.tool()
def get_portfolio_state(recent: int = 5) -> dict[str, Any]:
    """Read-only snapshot: current now items, last N published feed entries, and
    pending draft count. Use this before logging to avoid duplicates
    ("this was already logged Tuesday").
    """
    cfg = config()
    with client() as gh:
        now_file = gh.get_file(NOW_PATH, cfg.main_branch)
        published = gh.list_dir(FEED_DIR, cfg.main_branch)
        drafts = gh.list_dir(FEED_DIR, cfg.drafts_branch)
        main_names = {e["name"] for e in published}
        pending = [e for e in drafts if e["name"] not in main_names]

        recent_entries = []
        for e in sorted(published, key=lambda x: x["name"], reverse=True)[:recent]:
            f = gh.get_file(f"{FEED_DIR}/{e['name']}", cfg.main_branch)
            if f:
                recent_entries.append(
                    {
                        "id": f.data.get("id"),
                        "date": f.data.get("date"),
                        "type": f.data.get("type"),
                        "narrative_en": f.data.get("narrative", {}).get("en", ""),
                    }
                )

    return {
        "now": now_file.data if now_file else None,
        "recent_feed": recent_entries,
        "pending_drafts": [e["name"].removesuffix(".json") for e in pending],
        "pending_count": len(pending),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
