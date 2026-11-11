#!/usr/bin/env python3
"""Round digest: what the drain is about to publish, and where to veto it.

Posted to Slack when PORTFOLIO_SLACK_WEBHOOK is set (an incoming-webhook URL);
printed to stdout otherwise. No credential is created or stored here.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

ENV_WEBHOOK = "PORTFOLIO_SLACK_WEBHOOK"


def _titulo(entry: dict) -> str:
    t = entry.get("title") or {}
    return t.get("pt") or t.get("en") or entry.get("id", "?")


def _resumo(entry: dict) -> str:
    n = entry.get("narrative") or {}
    texto = (n.get("pt") or n.get("en") or "").strip()
    return texto if len(texto) <= 240 else texto[:237].rstrip() + "…"


def montar(pr_url: str, entries: list[dict], modo: str) -> str:
    """modo: "veto" (auto-merge after 48h), "zero" (next Action run), "retidas" (manual)."""
    rodape = {
        "veto": "Vai ao ar em 48h, salvo veto (label `segurar` ou fechar o PR).",
        "zero": "Janela zero: vai ao ar na próxima execução da Action (até 1h).",
        "retidas": "RETIDAS pelo juiz de confidencialidade — merge manual, a Action nunca mergeia.",
    }[modo]
    cabecalho = {
        "veto": "Portfólio vivo — rodada com {n} entrada(s) liberada(s)",
        "zero": "Portfólio vivo — {n} entrada(s) de projeto pessoal/open source",
        "retidas": "Portfólio vivo — {n} entrada(s) retida(s)",
    }[modo].format(n=len(entries))
    linhas = [f"*{cabecalho}*", ""]
    for e in entries:
        linhas.append(f"• *{_titulo(e)}*")
        linhas.append(f"  {_resumo(e)}")
        motivo = e.get("_retention_reason")
        if motivo:
            linhas.append(f"  _motivo:_ {motivo}")
    linhas += ["", f"PR: {pr_url}", rodape]
    return "\n".join(linhas)


def enviar(texto: str, webhook: str | None = None, opener=urllib.request.urlopen) -> str:
    """Post to Slack if a webhook is configured; otherwise print. Returns the channel used."""
    webhook = webhook if webhook is not None else os.environ.get(ENV_WEBHOOK, "")
    if not webhook:
        print(texto)
        return "stdout"
    req = urllib.request.Request(
        webhook,
        data=json.dumps({"text": texto}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(req, timeout=15) as resp:
            resp.read()
    except (urllib.error.URLError, OSError) as exc:
        print(f"aviso: digest não enviado ao Slack ({exc}); segue no stdout:\n{texto}", file=sys.stderr)
        return "stdout"
    return "slack"
