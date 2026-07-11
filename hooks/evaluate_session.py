#!/usr/bin/env python3
"""Session-end evaluation hook for the Living Portfolio.

Registered as a Claude Code `Stop` hook. When a session ends, it asks the
assistant to evaluate the finished work against rubric.md and, ONLY if it clears
the bar, write a feed entry via the portfolio MCP `log_activity` tool.

Design guarantees:
- The rubric is read verbatim from rubric.md at runtime — edit the rubric, not
  this hook (criteria changes require no code changes).
- Loop-safe: it blocks (injects the evaluation prompt) once; when the assistant
  finishes the evaluation, `stop_hook_active` is true and the hook exits quietly.
- Fail-safe: any error exits 0 without blocking, so a broken hook never traps you.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# rubric.md lives at the repo root, one level above hooks/.
RUBRIC_PATH = Path(__file__).resolve().parent.parent / "rubric.md"

PROMPT_TEMPLATE = """\
[Living Portfolio — session-end evaluation]

The work session just ended. Evaluate it against the relevance rubric below and \
decide whether it produced anything portfolio-worthy. Most sessions produce \
NOTHING — that is the correct and common outcome. Do not pad the feed.

Do this silently and briefly:

1. Judge this session against the rubric. Apply the final test honestly: would a \
senior engineer think "interesting — how did she do that?" or scroll past? If \
scroll: you are done. Reply with a single short line saying nothing was logged, \
and stop. Do NOT call any tool.

2. If it clears the bar: call the portfolio MCP `get_portfolio_state` tool first \
and check recent_feed and pending_drafts. If this session's work is already \
covered by an existing entry ("this was already logged Tuesday"), stop — reply \
that it was already logged. Duplicates bury the signal.

3. Otherwise: construct ONE feed entry and call the portfolio MCP \
`log_activity` tool with it. The entry object:
   - id: "YYYY-MM-DD-slug" (today's date + a short kebab-case slug)
   - date: "YYYY-MM-DD" (today)
   - type: one of decision | problem-solved | shipped | learning (match the \
criterion it met)
   - tags: 2-5 lowercase kebab-case tags
   - narrative: {{en, pt}} — 2-4 sentences a non-technical reader understands: \
the problem, the decision, why it matters
   - technical: {{en, pt}} — expandable detail: stack, approach, trade-offs (markdown ok)
   - outcome: {{en, pt}} — one measurable line, when one exists (optional)
   - status: "draft"

   Write BOTH languages now — never leave a translation as a TODO. Apply the \
sanitization rules below by CATEGORY before writing: the entry goes to the \
public-facing drafts branch. When in doubt, generalize up one level.

The entry is written to the drafts branch — never public until the owner runs \
review_and_publish. If the portfolio MCP server is not connected, just report \
what you WOULD have logged and stop.

─────────────────────────────────────────────────────────────────────────────
RUBRIC (verbatim from rubric.md):

{rubric}
"""


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return 0  # fail-safe: don't block on malformed input

    # Loop guard: if we already injected the evaluation, don't block again.
    if payload.get("stop_hook_active"):
        return 0

    try:
        rubric = RUBRIC_PATH.read_text(encoding="utf-8")
    except OSError:
        return 0  # fail-safe: no rubric, no evaluation

    reason = PROMPT_TEMPLATE.format(rubric=rubric)
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
