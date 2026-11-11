"""Round publisher: grouping, branches, PR bodies, labels — against a fake `gh`."""

import base64
import json
import subprocess

import pytest

import confidentiality_judge as juiz
import round_publisher as rp


def _entry(id_, project=None, **extra):
    e = {
        "id": id_,
        "date": id_[:10],
        "type": "shipped",
        "tags": ["x"],
        "title": {"en": f"Title {id_}", "pt": f"Título {id_}"},
        "narrative": {"en": "n", "pt": "n"},
        "technical": {"en": "t", "pt": "t"},
        "status": "draft",
    }
    if project:
        e["project"] = project
    e.update(extra)
    return e


class FakeGh:
    """Records every gh call; serves a tiny in-memory repo (main + staging)."""

    def __init__(self, staging_entries, main_names=(), existing_branches=()):
        self.staging = {f"{e['id']}.json": e for e in staging_entries}
        self.main_names = set(main_names)
        self.branches = {"main", "staging", *existing_branches}
        self.calls = []
        self.pr_counter = 0

    def __call__(self, cmd, input=None, **kwargs):
        self.calls.append((cmd, input))
        args = cmd[1:]
        if args[0] == "api":
            return self._api(args, input)
        if args[0] == "label":
            return self._ok("")
        if args[0] == "pr":
            self.pr_counter += 1
            return self._ok(f"https://github.com/o/r/pull/{self.pr_counter}\n")
        raise AssertionError(f"unexpected gh call: {args}")

    def _ok(self, out):
        return subprocess.CompletedProcess(["gh"], 0, stdout=out, stderr="")

    def _404(self):
        return subprocess.CompletedProcess(["gh"], 1, stdout="", stderr="gh: Not Found (HTTP 404)")

    def _api(self, args, stdin):
        method, path = args[2], args[3].split("repos/o/r/", 1)[1]
        body = json.loads(stdin) if stdin else None
        if path.startswith("git/ref/heads/"):
            b = path.removeprefix("git/ref/heads/")
            return self._ok(json.dumps({"object": {"sha": f"sha-{b}"}})) if b in self.branches else self._404()
        if path == "git/refs" and method == "POST":
            self.branches.add(body["ref"].removeprefix("refs/heads/"))
            return self._ok("{}")
        if path.startswith("contents/content/feed?ref="):
            branch = path.split("ref=")[1]
            if branch == "staging":
                names = self.staging
            elif branch == "main":
                names = self.main_names
            else:
                return self._404()
            return self._ok(json.dumps([{"name": n, "sha": f"blob-{n}", "type": "file"} for n in names]))
        if path.startswith("contents/content/feed/") and method == "GET":
            name = path.split("content/feed/")[1].split("?")[0]
            raw = json.dumps(self.staging[name]).encode()
            return self._ok(json.dumps({"content": base64.b64encode(raw).decode(), "sha": "s"}))
        if method in ("PUT", "DELETE"):
            return self._ok("{}")
        raise AssertionError(f"unexpected api call: {method} {path}")

    # helpers for assertions
    def puts(self):
        out = []
        for cmd, stdin in self.calls:
            if "api" in cmd and "PUT" in cmd:
                body = json.loads(stdin)
                out.append((body["branch"], json.loads(base64.b64decode(body["content"]))))
        return out

    def prs(self):
        out = []
        for cmd, stdin in self.calls:
            if cmd[1:3] == ["pr", "create"]:
                labels = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--label"]
                out.append({"head": cmd[cmd.index("--head") + 1], "base": cmd[cmd.index("--base") + 1],
                            "title": cmd[cmd.index("--title") + 1], "body": stdin, "labels": labels})
        return out

    def deletes(self):
        return [json.loads(stdin) for cmd, stdin in self.calls if "api" in cmd and "DELETE" in cmd]


def judge_by_id(retidas: set[str]):
    def judge(entry, denylist, model="sonnet"):
        if entry["id"] in retidas:
            return juiz.Veredito(True, "setor + escala + geografia", "judge")
        return juiz.Veredito(False, "ok", "judge")
    return judge


def test_full_round_splits_into_three_prs():
    entries = [
        _entry("2026-11-10-client-work"),
        _entry("2026-11-10-oss-work", project="living-portfolio"),
        _entry("2026-11-10-risky"),
    ]
    fake = FakeGh(entries)
    gh = rp.GitHub("o/r", runner=fake)
    digests = []

    resumo = rp.publicar_rodada(
        gh, staging="staging", main="main", data="2026-11-11", denylist=[],
        zero_projects={"living-portfolio"}, judge=judge_by_id({"2026-11-10-risky"}),
        notify=lambda texto: digests.append(texto) or "stdout",
    )

    prs = fake.prs()
    assert [p["head"] for p in prs] == ["drafts/2026-11-11", "drafts/2026-11-11-zero", "retidas/2026-11-11"]
    assert all(p["base"] == "main" for p in prs)
    assert prs[0]["labels"] == []
    assert prs[1]["labels"] == ["janela-zero"]
    assert prs[2]["labels"] == ["segurar"]
    assert "merge manual" in prs[2]["title"]
    assert "Merge manual" in prs[2]["body"]
    assert "setor + escala + geografia" in prs[2]["body"]
    assert "48h" in prs[0]["body"]
    assert "`2026-11-10-client-work`" in prs[0]["body"]

    # entries land on the PR branch already published, without internal fields
    puts = fake.puts()
    assert {b for b, _ in puts} == {"drafts/2026-11-11", "drafts/2026-11-11-zero", "retidas/2026-11-11"}
    assert all(e["status"] == "published" for _, e in puts)
    assert all(not any(k.startswith("_") for k in e) for _, e in puts)

    # branches created from main's sha; staging cleaned up
    creates = [json.loads(s) for c, s in fake.calls if "git/refs" in " ".join(c) and "POST" in c]
    assert all(c["sha"] == "sha-main" for c in creates)
    assert sorted(d["branch"] for d in fake.deletes()) == ["staging"] * 3

    assert [p["modo"] for p in resumo["prs"]] == ["veto", "zero", "retidas"]
    assert len(digests) == 3
    assert "48h" in digests[0] and "Janela zero" in digests[1] and "RETIDAS" in digests[2]


def test_entries_already_on_main_are_not_candidates():
    fake = FakeGh([_entry("2026-11-10-a"), _entry("2026-11-10-b")], main_names=["2026-11-10-a.json"])
    resumo = rp.publicar_rodada(
        rp.GitHub("o/r", runner=fake), staging="staging", main="main", data="2026-11-11",
        denylist=[], zero_projects=set(), judge=judge_by_id(set()), notify=lambda t: "stdout",
    )
    assert resumo["candidatas"] == ["2026-11-10-b.json"]
    assert [p["head"] for p in fake.prs()] == ["drafts/2026-11-11"]


def test_empty_staging_opens_nothing():
    fake = FakeGh([])
    resumo = rp.publicar_rodada(
        rp.GitHub("o/r", runner=fake), staging="staging", main="main", data="2026-11-11",
        denylist=[], zero_projects=set(), judge=judge_by_id(set()), notify=lambda t: "stdout",
    )
    assert resumo == {"candidatas": [], "prs": []}
    assert fake.prs() == []


def test_second_round_same_day_gets_a_suffix():
    fake = FakeGh([_entry("2026-11-10-a")], existing_branches=["drafts/2026-11-11"])
    rp.publicar_rodada(
        rp.GitHub("o/r", runner=fake), staging="staging", main="main", data="2026-11-11",
        denylist=[], zero_projects=set(), judge=judge_by_id(set()), notify=lambda t: "stdout",
    )
    assert fake.prs()[0]["head"] == "drafts/2026-11-11-2"


def test_denylist_reaches_the_judge():
    seen = {}

    def judge(entry, denylist, model="sonnet"):
        seen["denylist"] = denylist
        return juiz.Veredito(False, "ok", "judge")

    fake = FakeGh([_entry("2026-11-10-a")])
    rp.publicar_rodada(
        rp.GitHub("o/r", runner=fake), staging="staging", main="main", data="2026-11-11",
        denylist=["Acme"], zero_projects=set(), judge=judge, notify=lambda t: "stdout",
    )
    assert seen["denylist"] == ["Acme"]


def test_dry_run_judges_but_writes_nothing():
    fake = FakeGh([_entry("2026-11-10-a"), _entry("2026-11-10-b")])
    resumo = rp.publicar_rodada(
        rp.GitHub("o/r", runner=fake), staging="staging", main="main", data="2026-11-11",
        denylist=[], zero_projects=set(), judge=judge_by_id({"2026-11-10-b"}),
        notify=lambda t: "stdout", dry_run=True,
    )
    assert resumo["grupos"] == {"drafts/2026-11-11": ["2026-11-10-a"], "retidas/2026-11-11": ["2026-11-10-b"]}
    assert fake.prs() == [] and fake.puts() == []


def test_zero_window_config(tmp_path):
    p = tmp_path / "zero_window.json"
    p.write_text('{"projects": ["a", "b", 3]}', encoding="utf-8")
    assert rp.carregar_zero_window(p) == {"a", "b"}
    assert rp.carregar_zero_window(tmp_path / "missing.json") == set()


def test_gh_error_surfaces():
    def failing(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="gh: HTTP 500")

    with pytest.raises(rp.GhError, match="500"):
        rp.GitHub("o/r", runner=failing).branch_sha("main")
