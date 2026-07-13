#!/usr/bin/env python3
"""Silent capture hook for the Living Portfolio.

Registered as a Claude Code `Stop` hook. Unlike `evaluate_session.py` (which
blocks every turn and injects the evaluation INTO the conversation), this hook
is invisible: it only records that the session produced work, into a local
queue at ~/.claude/portfolio/queue.jsonl. Evaluation happens later, out of
band, via `hooks/drain_queue.py` (or `make drain`).

Design guarantees:
- Zero conversation noise: never blocks, never prints to the transcript.
- One queue line per session (deduped; the last Stop wins).
- Fail-safe: any error exits 0 — a broken hook never traps you.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

QUEUE = Path.home() / ".claude" / "portfolio" / "queue.jsonl"


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        return 0

    session_id = payload.get("session_id")
    transcript = payload.get("transcript_path")
    if not session_id or not transcript:
        return 0

    try:
        QUEUE.parent.mkdir(parents=True, exist_ok=True)
        entradas: dict[str, dict] = {}
        if QUEUE.exists():
            for linha in QUEUE.read_text(encoding="utf-8").splitlines():
                try:
                    d = json.loads(linha)
                    entradas[d["session_id"]] = d
                except (json.JSONDecodeError, KeyError):
                    continue
        entradas[session_id] = {
            "session_id": session_id,
            "transcript_path": transcript,
            "cwd": payload.get("cwd", ""),
            "last_stop": datetime.now(timezone.utc).isoformat(),
        }
        QUEUE.write_text(
            "\n".join(json.dumps(d, ensure_ascii=False) for d in entradas.values())
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass  # fail-safe
    return 0


if __name__ == "__main__":
    sys.exit(main())
