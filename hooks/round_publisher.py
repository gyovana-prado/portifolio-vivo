#!/usr/bin/env python3
"""End-of-round publisher: staging entries → one PR per group, labelled.

After the relevance evaluator has written its drafts to the STAGING branch
(via the MCP `log_activity`), this module:

1. lists the entries on staging that are not on main (the round's candidates —
   including leftovers from a round that crashed before this stage);
2. runs the confidentiality judge on each (denylist first, then `claude -p`);
3. groups them:
     drafts/<date>        liberadas, janela de 48h   → merged by the Action after 48h
     drafts/<date>-zero   liberadas, janela zero     → label `janela-zero`, merged on the
                                                       Action's next run (personal/open source)
     retidas/<date>       retidas pelo juiz          → label `segurar`, "merge manual",
                                                       the Action never touches retidas/*
4. for each non-empty group: branch from main, write the entries with
   status "published" (the site only builds main, so nothing shows before the
   merge), open the PR via `gh pr create`, remove the files from staging;
5. sends the digest (Slack webhook if configured, stdout otherwise).

Everything goes through `gh` (the owner's auth) — no local checkout is
touched, so `make drain` never dirties the working tree.
"""

from __future__ import annotations

import base64
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import confidentiality_judge as juiz
import digest

RAIZ = Path(__file__).resolve().parent.parent
ZERO_WINDOW_CONFIG = RAIZ / "config" / "zero_window.json"
FEED_DIR = "content/feed"

LABELS = {
    "segurar": ("d73a4a", "Veto: a Action não faz merge enquanto esta label existir"),
    "janela-zero": ("0e8a16", "Projeto pessoal/open source: merge na próxima execução da Action"),
}


# ── gh wrapper ───────────────────────────────────────────────────────────────


class GhError(RuntimeError):
    pass


class GitHub:
    """Thin wrapper over the `gh` CLI. Injectable runner so tests never hit the network."""

    def __init__(self, repo: str, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run):
        self.repo = repo
        self._run = runner

    def run(self, args: list[str], stdin: str | None = None) -> str:
        proc = self._run(["gh", *args], input=stdin, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise GhError(f"gh {' '.join(args[:3])}… falhou (exit {proc.returncode}): {proc.stderr.strip()[:300]}")
        return proc.stdout

    def api(self, path: str, method: str = "GET", body: dict | None = None):
        args = ["api", "-X", method, f"repos/{self.repo}/{path}"]
        stdin = None
        if body is not None:
            args += ["--input", "-"]
            stdin = json.dumps(body)
        out = self.run(args, stdin)
        return json.loads(out) if out.strip() else None

    def branch_sha(self, branch: str) -> str | None:
        try:
            ref = self.api(f"git/ref/heads/{branch}")
        except GhError as exc:
            if "404" in str(exc) or "Not Found" in str(exc):
                return None
            raise
        if not isinstance(ref, dict):  # prefix match list, never an exact ref
            return None
        return ref["object"]["sha"]

    def create_branch(self, name: str, sha: str) -> None:
        self.api("git/refs", "POST", {"ref": f"refs/heads/{name}", "sha": sha})

    def list_feed(self, branch: str) -> dict[str, str]:
        """{filename: blob sha} of content/feed on a branch ({} if absent)."""
        try:
            entries = self.api(f"contents/{FEED_DIR}?ref={branch}")
        except GhError as exc:
            if "404" in str(exc) or "Not Found" in str(exc):
                return {}
            raise
        return {e["name"]: e["sha"] for e in entries or [] if e.get("type") == "file"}

    def get_json(self, path: str, branch: str) -> dict:
        payload = self.api(f"contents/{path}?ref={branch}")
        return json.loads(base64.b64decode(payload["content"]).decode("utf-8"))

    def put_json(self, path: str, branch: str, data: dict, message: str) -> None:
        content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        self.api(
            f"contents/{path}",
            "PUT",
            {
                "message": message,
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": branch,
            },
        )

    def delete_file(self, path: str, branch: str, sha: str, message: str) -> None:
        self.api(f"contents/{path}", "DELETE", {"message": message, "sha": sha, "branch": branch})

    def ensure_label(self, name: str) -> None:
        color, description = LABELS[name]
        self.run(["label", "create", name, "--repo", self.repo, "--color", color,
                  "--description", description, "--force"])

    def create_pr(self, head: str, base: str, title: str, body: str, labels: list[str]) -> str:
        args = ["pr", "create", "--repo", self.repo, "--head", head, "--base", base,
                "--title", title, "--body-file", "-"]
        for label in labels:
            args += ["--label", label]
        return self.run(args, stdin=body).strip()


# ── Grouping ─────────────────────────────────────────────────────────────────


@dataclass
class Grupo:
    modo: str  # "veto" | "zero" | "retidas"
    prefixo: str
    labels: list[str]
    entries: list[dict] = field(default_factory=list)

    @property
    def titulo_pr(self) -> str:
        n = len(self.entries)
        return {
            "veto": f"drafts: {n} entrada(s) — janela de veto 48h",
            "zero": f"drafts: {n} entrada(s) — janela zero",
            "retidas": f"retidas: {n} entrada(s) — merge manual",
        }[self.modo]


def carregar_zero_window(path: Path = ZERO_WINDOW_CONFIG) -> set[str]:
    """Project ids whose entries skip the 48h window (config/zero_window.json)."""
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {p for p in data.get("projects", []) if isinstance(p, str)}


def agrupar(julgadas: list[tuple[dict, juiz.Veredito]], zero_projects: set[str], data: str) -> list[Grupo]:
    veto = Grupo("veto", f"drafts/{data}", [])
    zero = Grupo("zero", f"drafts/{data}-zero", ["janela-zero"])
    retidas = Grupo("retidas", f"retidas/{data}", ["segurar"])
    for entry, veredito in julgadas:
        if veredito.retained:
            retidas.entries.append({**entry, "_retention_reason": veredito.reason})
        elif entry.get("project") in zero_projects:
            zero.entries.append(entry)
        else:
            veto.entries.append(entry)
    return [g for g in (veto, zero, retidas) if g.entries]


def montar_corpo(grupo: Grupo, data: str) -> str:
    linhas = [f"Rodada do drain de {data} — {len(grupo.entries)} entrada(s).", ""]
    linhas += ["| id | tipo | título |", "|---|---|---|"]
    for e in grupo.entries:
        titulo = (e.get("title") or {}).get("pt") or (e.get("title") or {}).get("en") or ""
        linhas.append(f"| `{e['id']}` | {e.get('type', '?')} | {titulo} |")
    linhas.append("")
    if grupo.modo == "retidas":
        linhas.append("**Merge manual.** Retidas pelo juiz de confidencialidade; a Action nunca mergeia `retidas/*`.")
        linhas.append("Revise, generalize o texto se preciso (edite o arquivo nesta branch) e faça o merge você mesma.")
        linhas.append("")
        linhas.append("Motivos:")
        for e in grupo.entries:
            linhas.append(f"- `{e['id']}`: {e.get('_retention_reason', '?')}")
    elif grupo.modo == "zero":
        linhas.append("**Janela zero.** Projeto pessoal/open source (`config/zero_window.json`): "
                      "a Action faz merge na próxima execução (até 1h).")
    else:
        linhas.append("**Janela de veto: 48h.** Sem veto, a Action faz squash-merge e o site rebuilda.")
    linhas += [
        "",
        "Como vetar: ponha a label `segurar` ou feche o PR. Para vetar uma única entrada, "
        "remova o arquivo dela desta branch.",
        "",
        "_Aberto automaticamente por `hooks/drain_queue.py`._",
    ]
    return "\n".join(linhas)


def nome_branch(gh: GitHub, prefixo: str) -> str:
    """First free name among prefixo, prefixo-2, prefixo-3… (a second round the same day)."""
    nome, n = prefixo, 1
    while gh.branch_sha(nome) is not None:
        n += 1
        nome = f"{prefixo}-{n}"
    return nome


# ── The round ────────────────────────────────────────────────────────────────


def candidatas(gh: GitHub, staging: str, main: str) -> list[tuple[str, str, dict]]:
    """(filename, staging blob sha, entry) for every staging entry not on main."""
    em_main = gh.list_feed(main)
    out = []
    for name, sha in sorted(gh.list_feed(staging).items()):
        if name in em_main:
            continue
        out.append((name, sha, gh.get_json(f"{FEED_DIR}/{name}", staging)))
    return out


def publicar_rodada(
    gh: GitHub,
    *,
    staging: str,
    main: str,
    data: str,
    denylist: list[str],
    zero_projects: set[str],
    judge_model: str = "sonnet",
    judge: Callable[..., juiz.Veredito] = juiz.avaliar,
    notify: Callable[[str], str] = digest.enviar,
    dry_run: bool = False,
) -> dict:
    """Judge, group, branch, PR, digest. Returns a summary dict (also printed by the drain)."""
    pendentes = candidatas(gh, staging, main)
    resumo: dict = {"candidatas": [n for n, _, _ in pendentes], "prs": []}
    if not pendentes:
        return resumo

    julgadas = [(entry, judge(entry, denylist, model=judge_model)) for _, _, entry in pendentes]
    sha_por_nome = {name: sha for name, sha, _ in pendentes}
    grupos = agrupar(julgadas, zero_projects, data)
    resumo["vereditos"] = {e["id"]: v.as_dict() for e, v in julgadas}
    if dry_run:
        resumo["grupos"] = {g.prefixo: [e["id"] for e in g.entries] for g in grupos}
        return resumo

    main_sha = gh.branch_sha(main)
    if main_sha is None:
        raise GhError(f"branch '{main}' não existe")

    for grupo in grupos:
        branch = nome_branch(gh, grupo.prefixo)
        gh.create_branch(branch, main_sha)
        for e in grupo.entries:
            publicavel = {k: v for k, v in e.items() if not k.startswith("_")}
            publicavel["status"] = "published"
            gh.put_json(f"{FEED_DIR}/{e['id']}.json", branch, publicavel, message=f"feed: {e['id']}")
        for label in grupo.labels:
            gh.ensure_label(label)
        url = gh.create_pr(branch, main, grupo.titulo_pr, montar_corpo(grupo, data), grupo.labels)
        for e in grupo.entries:
            name = f"{e['id']}.json"
            gh.delete_file(f"{FEED_DIR}/{name}", staging, sha_por_nome[name],
                           message=f"staging: moved {e['id']} to {branch}")
        canal = notify(digest.montar(url, grupo.entries, grupo.modo))
        resumo["prs"].append({"branch": branch, "url": url, "modo": grupo.modo,
                              "entries": [e["id"] for e in grupo.entries], "digest": canal})
    return resumo
