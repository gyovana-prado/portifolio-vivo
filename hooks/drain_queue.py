#!/usr/bin/env python3
"""Batch evaluator for captured sessions (the offline half of the capture hook).

Reads ~/.claude/portfolio/queue.jsonl (written by `capture_session.py`) and runs
one round:

1. Triage: sessions whose transcript is gone, or whose `entrypoint` is not an
   interactive CLI session (headless `claude -p` / SDK workers), are marked
   `skipped` with a reason — never evaluated, never silently dropped.
2. Relevance: for each remaining session a headless `claude -p` reads the
   transcript, judges it against rubric.md and, only if it clears the bar,
   logs a draft to the STAGING branch via the portfolio MCP `log_activity`.
   The evaluator must end with a structured verdict:
       REGISTRADO <id>  |  DESCARTADO <motivo>  |  FALHA <motivo>
   Only REGISTRADO/DESCARTADO mark the session processed. FALHA, an MCP
   error or an unrecognisable answer leave it in the queue with an attempt
   counter (after --max-attempts it is marked skipped, with the reason).
3. Publish (hooks/round_publisher.py): every staging entry not yet on main goes
   through the confidentiality judge and lands in a PR — `drafts/<date>` (48h
   veto window), `drafts/<date>-zero` (personal/open source, label janela-zero)
   or `retidas/<date>` (label segurar, manual merge). A digest goes to Slack
   (PORTFOLIO_SLACK_WEBHOOK) or stdout. The hourly GitHub Action does the merge.

Usage:
    python3 hooks/drain_queue.py               # full round
    python3 hooks/drain_queue.py --dry-run     # triage + list, no model, no PR
    python3 hooks/drain_queue.py --limit 3     # cap evaluations this round
    python3 hooks/drain_queue.py --skip-eval   # only the publish stage (staging → PRs)
    python3 hooks/drain_queue.py --skip-pr     # only evaluate; leave entries on staging

Notes:
- The MCP config (including the GitHub token) is read at runtime from the
  `portfolio` server registered in ~/.claude.json — no secrets in this repo.
  The staging branch is forced via PORTFOLIO_DRAFTS_BRANCH in the config the
  headless evaluator receives, so it never depends on the owner's own setting.
- Headless sessions run with ALL hooks disabled: a global Stop hook would
  hijack the `result` field of `claude -p` (observed 2026-07-12) and would
  also re-enqueue the evaluator's own session, looping forever.
- Stdlib only: `make drain` runs this with plain python3.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import confidentiality_judge as juiz  # noqa: E402
import round_publisher  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
RUBRIC_PATH = RAIZ / "rubric.md"
PROJECTS_DIR = RAIZ / "content" / "projects"
DIR_FILA = Path.home() / ".claude" / "portfolio"
QUEUE = DIR_FILA / "queue.jsonl"
PROCESSED = DIR_FILA / "processed.jsonl"
CLAUDE_JSON = Path.home() / ".claude.json"

STAGING_BRANCH = "staging"
MAIN_BRANCH = "main"
LEGACY_DRAFTS_BRANCH = "drafts"  # conflicts with drafts/<date> refs — must be renamed
ENTRYPOINTS_INTERATIVOS = {"cli"}
MAX_TENTATIVAS = 3
LINHAS_ENTRYPOINT = 200  # the field sits in the first events of a transcript
TERMINAIS = {"registrado", "descartado", "skipped"}

FERRAMENTAS = "Read,Grep,mcp__portfolio__get_portfolio_state,mcp__portfolio__log_activity"

PROMPT_TEMPLATE = """\
[Living Portfolio — deferred session evaluation]

You are evaluating a FINISHED Claude Code session for the Living Portfolio.
The session transcript (JSONL, one event per line) is at:

  {transcript}

It may be long, and long sessions usually contain SEVERAL work streams — do not
judge by the opening topic. Cover the whole span before concluding:

- Check the size first (`Grep` with count, or Read with offsets), then sample
  the beginning, middle and END of the file. The most substantive work is often
  in the second half.
- Grep for markers of substance across the file: `git commit`, `feat:`, `fix:`,
  `decision`, `decisão`, `trade-off`, `bug`, `measured`, `medido`.
- Evaluate the BEST candidate story in the session, not the first one you see.

Then decide whether the session produced anything portfolio-worthy. Most
sessions produce NOTHING — that is the correct and common outcome. Do not pad
the feed.

1. Judge the session against the rubric below. Apply the final test honestly:
   would a senior engineer think "interesting — how did she do that?" or scroll
   past? If scroll: answer DESCARTADO.

2. If it clears the bar: call `get_portfolio_state` and check recent_feed and
   pending_drafts. If the SAME work is already covered by an existing entry,
   answer DESCARTADO — duplicates bury the signal. Same topic is not the same
   work: compare what was actually done, not the subject or the id.

3. Otherwise construct ONE feed entry and call `log_activity` with it:
   - id: "YYYY-MM-DD-slug" · date: "YYYY-MM-DD" (the session's date)
   - type: decision | problem-solved | shipped | learning
   - tags: 2-5 lowercase kebab-case tags
   - title: {{en, pt}} — one short headline sentence (~60 chars) that states
     the insight, not the topic ("Cap the batch by bytes, not by records.")
   - narrative: {{en, pt}} — 2-4 sentences for a non-technical reader
   - technical: {{en, pt}} — stack, approach, trade-offs (markdown ok)
   - outcome: {{en, pt}} — one measurable line, when one exists (optional)
   - project: ONLY if the session clearly belongs to one of these portfolio
     projects, its id: {projects}. Otherwise omit the field.
   - status: "draft"
   Write BOTH languages now. Apply the sanitization rules by CATEGORY — the
   entry will be reviewed by a confidentiality judge and then published after
   a veto window. When in doubt, generalize up.

Your final message must be ONE line starting with exactly one of these words:
  REGISTRADO <id>            — log_activity succeeded (quote the id it confirmed)
  DESCARTADO <short reason>  — nothing worth logging, or already covered
  FALHA <short reason>       — you could NOT complete the evaluation (MCP tool
                               unavailable or erroring, transcript unreadable…)
Never answer DESCARTADO when the real cause is a tool failure.

─────────────────────────────────────────────────────────────────────────────
RUBRIC (verbatim from rubric.md):

{rubric}
"""


# ── Queue bookkeeping ────────────────────────────────────────────────────────


def carregar_jsonl(caminho: Path) -> list[dict]:
    registros: list[dict] = []
    if caminho.exists():
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            try:
                registros.append(json.loads(linha))
            except json.JSONDecodeError:
                continue
    return registros


def carregar_fila(caminho: Path = QUEUE) -> dict[str, dict]:
    fila: dict[str, dict] = {}
    for d in carregar_jsonl(caminho):
        if "session_id" in d:
            fila[d["session_id"]] = d
    return fila


def pendentes(fila: dict[str, dict], registros: list[dict]) -> list[dict]:
    """Queue entries without a terminal record newer than their last stop.

    Legacy records (no `status`) count as terminal. `falha` records never do:
    they only feed the `attempts` counter the caller sees.
    """
    por_sessao: dict[str, list[dict]] = {}
    for r in registros:
        if "session_id" in r:
            por_sessao.setdefault(r["session_id"], []).append(r)

    resultado = []
    for sid, entrada in fila.items():
        last_stop = entrada.get("last_stop", "")
        recentes = [r for r in por_sessao.get(sid, []) if r.get("processed_at", "") > last_stop]
        if any(r.get("status", "processada") in TERMINAIS | {"processada"} for r in recentes):
            continue
        tentativas = sum(1 for r in recentes if r.get("status") == "falha")
        resultado.append({**entrada, "attempts": tentativas})
    return sorted(resultado, key=lambda e: e.get("last_stop", ""))


def registrar(session_id: str, status: str, detail: str = "", caminho: Path = PROCESSED) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "session_id": session_id,
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "detail": detail[:300],
        }, ensure_ascii=False) + "\n")


# ── Triage ───────────────────────────────────────────────────────────────────


def ler_entrypoint(transcript: Path, max_linhas: int = LINHAS_ENTRYPOINT) -> str | None:
    """First `entrypoint` value in the transcript's leading events (None if absent)."""
    try:
        with transcript.open(encoding="utf-8") as f:
            for i, linha in enumerate(f):
                if i >= max_linhas:
                    break
                try:
                    d = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if isinstance(d, dict) and "entrypoint" in d:
                    return str(d["entrypoint"])
    except OSError:
        return None
    return None


def triar(entrada: dict) -> tuple[bool, str]:
    """(evaluate?, reason). Missing transcript or headless entrypoint → skip."""
    transcript = Path(entrada.get("transcript_path", ""))
    if not transcript.is_file():
        return False, "transcript ausente"
    ep = ler_entrypoint(transcript)
    if ep is not None and ep not in ENTRYPOINTS_INTERATIVOS:
        return False, f"entrypoint={ep}"
    return True, ep or "entrypoint desconhecido (tratado como cli)"


# ── Verdict ──────────────────────────────────────────────────────────────────


def interpretar_veredito(texto: str) -> tuple[str, str]:
    """('registrado'|'descartado'|'falha', detail). Anything unrecognised is a falha."""
    linha = next((l.strip() for l in texto.strip().splitlines() if l.strip()), "")
    palavra, _, resto = linha.partition(" ")
    palavra = palavra.strip(" :—-*`").upper()
    if palavra in {"REGISTRADO", "DESCARTADO", "FALHA"}:
        return palavra.lower(), resto.strip(" —-:")
    return "falha", f"veredito irreconhecível: {linha[:160]}"


# ── MCP config + preflight ───────────────────────────────────────────────────


def config_mcp() -> tuple[str, dict]:
    """(mcp-config JSON for the headless evaluator, server env). Forces the staging branch."""
    cfg = json.loads(CLAUDE_JSON.read_text(encoding="utf-8"))
    servidor = cfg.get("mcpServers", {}).get("portfolio")
    if not servidor:
        sys.exit("erro: servidor MCP 'portfolio' não registrado em ~/.claude.json — veja mcp/README.md")
    servidor = json.loads(json.dumps(servidor))
    env = servidor.setdefault("env", {})
    env["PORTFOLIO_DRAFTS_BRANCH"] = STAGING_BRANCH
    env.setdefault("UV_NO_ENV_FILE", "1")
    return json.dumps({"mcpServers": {"portfolio": servidor}}), env


def verificar_token(repo: str, token: str) -> str | None:
    """Reach the repo with the MCP's own token. Returns an error message, or None if OK."""
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "User-Agent": "portfolio-drain"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return f"token do GitHub rejeitado ({exc.code}) — expirado? renove em ~/.claude.json"
        return f"GitHub respondeu {exc.code} para {repo}"
    except urllib.error.URLError as exc:
        return f"sem acesso à API do GitHub ({exc.reason})"
    return None


def verificar_branches(gh: round_publisher.GitHub) -> str | None:
    """Staging must exist; the legacy `drafts` branch must be gone (ref conflict)."""
    if gh.branch_sha(LEGACY_DRAFTS_BRANCH) is not None:
        return (
            f"a branch '{LEGACY_DRAFTS_BRANCH}' ainda existe e conflita com as refs "
            f"'{LEGACY_DRAFTS_BRANCH}/<data>' dos PRs. Migre uma vez:\n"
            f"  gh api -X POST repos/{gh.repo}/git/refs -f ref=refs/heads/{STAGING_BRANCH} "
            f"-f sha=$(gh api repos/{gh.repo}/git/ref/heads/{LEGACY_DRAFTS_BRANCH} --jq .object.sha)\n"
            f"  gh api -X DELETE repos/{gh.repo}/git/refs/heads/{LEGACY_DRAFTS_BRANCH}"
        )
    if gh.branch_sha(STAGING_BRANCH) is None:
        main_sha = gh.branch_sha(MAIN_BRANCH)
        if main_sha is None:
            return f"branch '{MAIN_BRANCH}' não encontrada em {gh.repo}"
        gh.create_branch(STAGING_BRANCH, main_sha)
        print(f"branch '{STAGING_BRANCH}' criada a partir de {MAIN_BRANCH}.")
    return None


def ids_projetos() -> list[str]:
    ids = []
    for p in sorted(PROJECTS_DIR.glob("*.json")):
        try:
            ids.append(json.loads(p.read_text(encoding="utf-8"))["id"])
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    return ids


# ── Evaluation ───────────────────────────────────────────────────────────────


def avaliar(entrada: dict, mcp_config: str, rubric: str, model: str, projetos: list[str]) -> str:
    prompt = PROMPT_TEMPLATE.format(
        transcript=entrada["transcript_path"],
        rubric=rubric,
        projects=", ".join(projetos) or "(none)",
    )
    try:
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
    except subprocess.TimeoutExpired:
        return "FALHA avaliador excedeu 900s"
    if proc.returncode != 0:
        return f"FALHA exit {proc.returncode}: {proc.stderr[:200]}"
    try:
        corpo = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return "FALHA saída do claude não é JSON"
    if corpo.get("is_error"):
        return f"FALHA {corpo.get('errors') or corpo.get('subtype')}"
    return str(corpo.get("result", "")).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="triagem + lista; não chama modelo nem abre PR")
    parser.add_argument("--limit", type=int, default=0, help="máx. de sessões avaliadas nesta rodada")
    parser.add_argument("--model", default="sonnet", help="modelo do avaliador de relevância")
    parser.add_argument("--judge-model", default="sonnet", help="modelo do juiz de confidencialidade")
    parser.add_argument("--max-attempts", type=int, default=MAX_TENTATIVAS,
                        help="falhas seguidas até marcar a sessão como skipped")
    parser.add_argument("--skip-eval", action="store_true", help="só a etapa de PR (staging → PRs)")
    parser.add_argument("--skip-pr", action="store_true", help="só avalia; deixa as entradas em staging")
    args = parser.parse_args()

    fila = pendentes(carregar_fila(), carregar_jsonl(PROCESSED))
    if args.dry_run:
        for e in fila:
            ok, motivo = triar(e)
            estado = "pendente" if ok else "skip   "
            extra = f", {e['attempts']} falha(s)" if e.get("attempts") else ""
            print(f"{estado}: {e['session_id'][:8]}  {motivo}  (último stop {e['last_stop']}, cwd {e.get('cwd', '?')}{extra})")
        if not fila:
            print("fila vazia — nada a avaliar.")
        return 0

    mcp, env = config_mcp()
    repo = env.get("PORTFOLIO_REPO", "")
    if not repo or "/" not in repo:
        sys.exit("erro: PORTFOLIO_REPO ausente no env do servidor MCP em ~/.claude.json")
    erro = verificar_token(repo, env.get("GITHUB_TOKEN", ""))
    if erro:
        sys.exit(f"erro (preflight): {erro}. Nada foi marcado como processado.")
    gh = round_publisher.GitHub(repo)
    erro = verificar_branches(gh)
    if erro:
        sys.exit(f"erro (preflight): {erro}")

    if not args.skip_eval:
        avaliaveis = []
        for e in fila:
            ok, motivo = triar(e)
            if ok:
                avaliaveis.append(e)
            else:
                registrar(e["session_id"], "skipped", motivo)
                print(f"skip {e['session_id'][:8]}: {motivo}")
        if args.limit:
            avaliaveis = avaliaveis[: args.limit]
        if not avaliaveis:
            print("nenhuma sessão interativa pendente.")
        rubric = RUBRIC_PATH.read_text(encoding="utf-8")
        projetos = ids_projetos()
        for e in avaliaveis:
            print(f"avaliando {e['session_id'][:8]}… ", end="", flush=True)
            status, detalhe = interpretar_veredito(avaliar(e, mcp, rubric, args.model, projetos))
            print(f"{status.upper()} {detalhe}")
            if status == "falha":
                tentativas = e.get("attempts", 0) + 1
                if tentativas >= args.max_attempts:
                    registrar(e["session_id"], "skipped", f"{tentativas} falhas: {detalhe}")
                    print(f"  → {tentativas} falhas, marcada como skipped")
                else:
                    registrar(e["session_id"], "falha", detalhe)
                    print(f"  → fica na fila (tentativa {tentativas}/{args.max_attempts})")
            else:
                registrar(e["session_id"], status, detalhe)

    if args.skip_pr:
        return 0

    denylist = juiz.carregar_denylist(
        Path(env["PORTFOLIO_DENYLIST"]).expanduser() if env.get("PORTFOLIO_DENYLIST") else None
    )
    resumo = round_publisher.publicar_rodada(
        gh,
        staging=STAGING_BRANCH,
        main=MAIN_BRANCH,
        data=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        denylist=denylist,
        zero_projects=round_publisher.carregar_zero_window(),
        judge_model=args.judge_model,
    )
    if not resumo["candidatas"]:
        print("staging vazia — nenhum PR aberto.")
    for pr in resumo["prs"]:
        print(f"PR {pr['modo']}: {pr['url']}  ({', '.join(pr['entries'])}; digest → {pr['digest']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
