#!/usr/bin/env python3
"""Confidentiality judge: the second LLM gate, one question only.

The relevance evaluator (drain_queue.py) decides whether a session is worth an
entry. This module decides whether that entry is RISKY: does it let a reader
identify a client or employer through the combination of sector, scale and
geography (or through names, product names, internal system names, timelines,
business metrics)? It does not judge quality — "the LLM decides what is risky,
not what is good".

Two barriers, in order:
1. Local denylist (~/.portfolio-mcp/denylist.json, if present) — a deterministic
   last barrier by NAME. A hit retains the entry without asking the model.
2. Headless `claude -p` with all hooks disabled and no tools, asked for a JSON
   verdict {"retained": bool, "reason": str}.

Fail-closed: an unreadable verdict, a non-zero exit or a timeout RETAIN the
entry (it goes to the manual-merge PR, never to the auto-merge one).

Usage (manual check of one entry file):
    python3 hooks/confidentiality_judge.py content/feed/2026-07-09-example.json
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

RAIZ = Path(__file__).resolve().parent.parent
RUBRIC_PATH = RAIZ / "rubric.md"
DEFAULT_DENYLIST = Path.home() / ".portfolio-mcp" / "denylist.json"
TIMEOUT_S = 180

PROMPT_TEMPLATE = """\
[Living Portfolio — confidentiality judge]

You are the confidentiality gate of a PUBLIC portfolio feed. A relevance judge
already decided this entry is worth publishing; you do not judge quality.

Answer ONE question only:

  Does this entry allow a reader to identify a specific client or employer —
  through the COMBINATION of industry/sector, scale and geography, or through
  any of: client/product/brand names, internal system or repository names,
  colleague names, business metrics (revenue, users, contract terms), or a
  timeline that maps to a known engagement?

Technical content is NOT a problem: problem classes, technologies, patterns,
reasoning, quantified technical outcomes and generic counterpart roles
("an enterprise client") are exactly what the portfolio is for. Retain only
when the identification risk is real, not when the text merely mentions a
domain in generic terms.

Reply with a single JSON object and nothing else:

  {{"retained": true|false, "reason": "<one sentence, in Portuguese>"}}

`retained: true` means the entry must be HELD for human review before publishing.

─────────────────────────────────────────────────────────────────────────────
SANITIZATION RULES (verbatim from rubric.md):

{rules}

─────────────────────────────────────────────────────────────────────────────
ENTRY (JSON):

{entry}
"""

Runner = Callable[..., subprocess.CompletedProcess]


@dataclass
class Veredito:
    retained: bool
    reason: str
    source: str  # "denylist" | "judge" | "fallback"

    def as_dict(self) -> dict:
        return {"retained": self.retained, "reason": self.reason, "source": self.source}


# ── Denylist (last barrier, by name) ─────────────────────────────────────────


def carregar_denylist(path: Path | None = None) -> list[str]:
    """Same shape the MCP reads: {"names": [...]} or a bare list. Missing = []."""
    path = path or Path(os.environ.get("PORTFOLIO_DENYLIST", str(DEFAULT_DENYLIST))).expanduser()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    names = data.get("names", []) if isinstance(data, dict) else data
    return [n.strip() for n in names if isinstance(n, str) and n.strip()]


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def acertos_denylist(entry: dict, denylist: list[str]) -> list[str]:
    haystack = "\n".join(_strings(entry)).lower()
    return sorted({n for n in denylist if n.lower() in haystack})


# ── LLM judge ────────────────────────────────────────────────────────────────


def regras_sanitizacao(rubric_text: str) -> str:
    """The '## Sanitization rules' section of the rubric (whole rubric if absent)."""
    m = re.search(r"^## Sanitization rules\s*$(.*?)(?=^## |\Z)", rubric_text, re.S | re.M)
    return m.group(1).strip() if m else rubric_text.strip()


def montar_prompt(entry: dict, rubric_text: str | None = None) -> str:
    rubric_text = rubric_text if rubric_text is not None else RUBRIC_PATH.read_text(encoding="utf-8")
    return PROMPT_TEMPLATE.format(
        rules=regras_sanitizacao(rubric_text),
        entry=json.dumps(entry, ensure_ascii=False, indent=2),
    )


def comando_claude(model: str) -> list[str]:
    return [
        "claude", "-p",
        "--output-format", "json",
        "--model", model,
        "--settings", '{"disableAllHooks": true}',
        "--tools", "",
    ]


def interpretar_resposta(result: str) -> tuple[bool, str] | None:
    """Parse {"retained": bool, "reason": str} from the model's text (fences tolerated)."""
    texto = result.strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto, flags=re.S).strip()
    try:
        corpo = json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, re.S)
        if not m:
            return None
        try:
            corpo = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(corpo, dict) or not isinstance(corpo.get("retained"), bool):
        return None
    return corpo["retained"], str(corpo.get("reason", "")).strip()


def julgar_llm(
    entry: dict,
    model: str = "sonnet",
    runner: Runner = subprocess.run,
    rubric_text: str | None = None,
) -> Veredito:
    """Ask the headless model. Any failure → retained (fail-closed)."""
    try:
        proc = runner(
            comando_claude(model),
            input=montar_prompt(entry, rubric_text),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return Veredito(True, f"juiz indisponível ({type(exc).__name__})", "fallback")
    if proc.returncode != 0:
        return Veredito(True, f"juiz falhou (exit {proc.returncode}): {proc.stderr[:120]}", "fallback")
    try:
        corpo = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return Veredito(True, "saída do juiz não é JSON", "fallback")
    if corpo.get("is_error"):
        return Veredito(True, f"juiz retornou erro: {corpo.get('errors') or corpo.get('subtype')}", "fallback")
    parsed = interpretar_resposta(str(corpo.get("result", "")))
    if parsed is None:
        return Veredito(True, "veredito do juiz ilegível", "fallback")
    retained, reason = parsed
    return Veredito(retained, reason or ("retida" if retained else "liberada"), "judge")


def avaliar(
    entry: dict,
    denylist: list[str] | None = None,
    model: str = "sonnet",
    runner: Runner = subprocess.run,
    rubric_text: str | None = None,
) -> Veredito:
    """Full gate: denylist first (no model call on a hit), then the LLM judge."""
    hits = acertos_denylist(entry, denylist or [])
    if hits:
        return Veredito(True, "denylist: " + ", ".join(hits), "denylist")
    return julgar_llm(entry, model=model, runner=runner, rubric_text=rubric_text)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    entry = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(avaliar(entry, carregar_denylist()).as_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
