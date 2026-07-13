#!/usr/bin/env python3
"""Batch evaluator for captured sessions (the offline half of the capture hook).

Reads ~/.claude/portfolio/queue.jsonl (written by `capture_session.py`), and for
each pending session spawns a headless `claude -p` that reads the transcript,
judges it against rubric.md and — only if it clears the bar — logs a draft via
the portfolio MCP `log_activity`. Publication still requires the owner running
`review_and_publish` (the human gate is untouched).

Usage:
    python3 hooks/drain_queue.py               # evaluate all pending sessions
    python3 hooks/drain_queue.py --dry-run     # list what would be evaluated
    python3 hooks/drain_queue.py --limit 3     # cap evaluations this run
    python3 hooks/drain_queue.py --model opus  # override the evaluator model

Notes:
- The MCP config (including the GitHub token) is read at runtime from the
  `portfolio` server registered in ~/.claude.json — no secrets in this repo.
- Headless sessions run with ALL hooks disabled: a global Stop hook would
  hijack the `result` field of `claude -p` (observed 2026-07-12) and would
  also re-enqueue the evaluator's own session, looping forever.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUBRIC_PATH = RAIZ / "rubric.md"
DIR_FILA = Path.home() / ".claude" / "portfolio"
QUEUE = DIR_FILA / "queue.jsonl"
PROCESSED = DIR_FILA / "processed.jsonl"
CLAUDE_JSON = Path.home() / ".claude.json"

FERRAMENTAS = "Read,Grep,mcp__portfolio__get_portfolio_state,mcp__portfolio__log_activity"

PROMPT_TEMPLATE = """\
[Living Portfolio — deferred session evaluation]

You are evaluating a FINISHED Claude Code session for the Living Portfolio.
The session transcript (JSONL, one event per line) is at:

  {transcript}

It may be long. Read it strategically: user messages and the assistant's final
summaries tell you what was actually accomplished — Grep for keywords and Read
targeted ranges instead of the whole file.

Then decide whether the session produced anything portfolio-worthy. Most
sessions produce NOTHING — that is the correct and common outcome. Do not pad
the feed.

1. Judge the session against the rubric below. Apply the final test honestly:
   would a senior engineer think "interesting — how did she do that?" or scroll
   past? If scroll: reply with a single short line saying nothing was logged.

2. If it clears the bar: call `get_portfolio_state` and check recent_feed and
   pending_drafts. If the work is already covered by an existing entry, stop —
   duplicates bury the signal.

3. Otherwise construct ONE feed entry and call `log_activity` with it:
   - id: "YYYY-MM-DD-slug" · date: "YYYY-MM-DD" (the session's date)
   - type: decision | problem-solved | shipped | learning
   - tags: 2-5 lowercase kebab-case tags
   - narrative: {{en, pt}} — 2-4 sentences for a non-technical reader
   - technical: {{en, pt}} — stack, approach, trade-offs (markdown ok)
   - outcome: {{en, pt}} — one measurable line, when one exists (optional)
   - status: "draft"
   Write BOTH languages now. Apply the sanitization rules by CATEGORY — the
   entry goes to the public-facing drafts branch. When in doubt, generalize up.

Your final message must be ONE line: either "nada registrado — <motivo curto>"
or "draft registrado: <id> — <título curto>".

─────────────────────────────────────────────────────────────────────────────
RUBRIC (verbatim from rubric.md):

{rubric}
"""


def carregar_jsonl(caminho: Path) -> dict[str, dict]:
    registros: dict[str, dict] = {}
    if caminho.exists():
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(linha)
                registros[d["session_id"]] = d
            except (json.JSONDecodeError, KeyError):
                continue
    return registros


def config_mcp() -> str:
    cfg = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
    servidor = cfg.get("mcpServers", {}).get("portfolio")
    if not servidor:
        sys.exit(
            "erro: servidor MCP 'portfolio' não registrado em ~/.claude.json — "
            "veja mcp/README.md"
        )
    return json.dumps({"mcpServers": {"portfolio": servidor}})


def pendentes() -> list[dict]:
    fila = carregar_jsonl(QUEUE)
    processadas = carregar_jsonl(PROCESSED)
    resultado = []
    for sid, entrada in fila.items():
        marca = processadas.get(sid, {}).get("processed_at", "")
        if entrada.get("last_stop", "") > marca:
            resultado.append(entrada)
    return sorted(resultado, key=lambda e: e.get("last_stop", ""))


def avaliar(entrada: dict, mcp_config: str, rubric: str, model: str) -> str:
    prompt = PROMPT_TEMPLATE.format(
        transcript=entrada["transcript_path"], rubric=rubric
    )
    proc = subprocess.run(
        [
            "claude", "-p",
            "--output-format", "json",
            "--model", model,
            "--settings", '{"disableAllHooks": true}',
            "--mcp-config", mcp_config,
            "--allowedTools", FERRAMENTAS,
        ],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=900,
    )
    if proc.returncode != 0:
        return f"ERRO (exit {proc.returncode}): {proc.stderr[:200]}"
    corpo = json.loads(proc.stdout)
    if corpo.get("is_error"):
        return f"ERRO: {corpo.get('errors') or corpo.get('subtype')}"
    return str(corpo.get("result", "")).strip()


def marcar_processada(session_id: str) -> None:
    with PROCESSED.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "session_id": session_id,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            + "\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="só lista as pendentes")
    parser.add_argument("--limit", type=int, default=0, help="máx. de sessões nesta rodada")
    parser.add_argument("--model", default="sonnet", help="modelo do avaliador")
    args = parser.parse_args()

    fila = pendentes()
    if args.limit:
        fila = fila[: args.limit]
    if not fila:
        print("fila vazia — nada a avaliar.")
        return 0

    if args.dry_run:
        for e in fila:
            print(f"pendente: {e['session_id']}  (último stop {e['last_stop']}, cwd {e.get('cwd', '?')})")
        return 0

    rubric = RUBRIC_PATH.read_text(encoding="utf-8")
    mcp = config_mcp()
    DIR_FILA.mkdir(parents=True, exist_ok=True)
    for e in fila:
        print(f"avaliando {e['session_id'][:8]}… ", end="", flush=True)
        veredito = avaliar(e, mcp, rubric, args.model)
        print(veredito)
        if not veredito.startswith("ERRO"):
            marcar_processada(e["session_id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
