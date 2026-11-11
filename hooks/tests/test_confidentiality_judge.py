"""Confidentiality judge: fixed cases, the model is mocked (never called)."""

import json
import subprocess

import pytest

import confidentiality_judge as juiz

RUBRIC = (
    "# Rubric\n\n## Relevance\nstuff\n\n## Sanitization rules\n\n"
    "Never include industry + geography + scale combinations.\n\n## Entry format\nignored\n"
)

GENERALIZADA = {
    "id": "2026-07-09-batch-by-bytes",
    "date": "2026-07-09",
    "type": "decision",
    "tags": ["pipelines"],
    "title": {"en": "Cap the batch by bytes, not by records.", "pt": "Limite o lote por bytes, não por registros."},
    "narrative": {"en": "For an enterprise client, batching by record count overflowed the API. Sizing by bytes fixed it.",
                  "pt": "Para um cliente enterprise, lotes por contagem estouravam a API. Dimensionar por bytes resolveu."},
    "technical": {"en": "Python, httpx; measured payloads.", "pt": "Python, httpx; payloads medidos."},
    "status": "draft",
}

IDENTIFICAVEL = {
    **GENERALIZADA,
    "id": "2026-07-09-bi-migration",
    "narrative": {
        "en": "BI migration for the largest real-estate marketplace in São Paulo, 40M monthly users.",
        "pt": "Migração de BI para o maior marketplace imobiliário de São Paulo, 40M de usuários mensais.",
    },
}


def fake_runner(result_text: str, returncode: int = 0, is_error: bool = False):
    """A stand-in for subprocess.run that returns a `claude -p --output-format json` body."""
    calls = []

    def run(cmd, input=None, **kwargs):
        calls.append({"cmd": cmd, "input": input})
        body = {"result": result_text, "is_error": is_error}
        return subprocess.CompletedProcess(cmd, returncode, stdout=json.dumps(body), stderr="boom")

    run.calls = calls
    return run


def test_generalized_entry_passes():
    run = fake_runner(json.dumps({"retained": False, "reason": "genérica"}))
    v = juiz.avaliar(GENERALIZADA, denylist=[], runner=run, rubric_text=RUBRIC)
    assert v.retained is False
    assert v.source == "judge"


def test_sector_scale_geography_is_retained():
    run = fake_runner(json.dumps({"retained": True, "reason": "setor + escala + geografia identificam o cliente"}))
    v = juiz.avaliar(IDENTIFICAVEL, denylist=[], runner=run, rubric_text=RUBRIC)
    assert v.retained is True
    assert "setor" in v.reason
    assert v.source == "judge"


def test_prompt_carries_entry_and_only_sanitization_rules():
    run = fake_runner(json.dumps({"retained": False, "reason": "ok"}))
    juiz.avaliar(IDENTIFICAVEL, denylist=[], runner=run, rubric_text=RUBRIC)
    prompt = run.calls[0]["input"]
    assert "marketplace imobiliário" in prompt
    assert "Never include industry + geography + scale" in prompt
    assert "## Relevance" not in prompt


def test_headless_flags():
    run = fake_runner(json.dumps({"retained": False, "reason": "ok"}))
    juiz.avaliar(GENERALIZADA, denylist=[], model="haiku", runner=run, rubric_text=RUBRIC)
    cmd = run.calls[0]["cmd"]
    assert cmd[:2] == ["claude", "-p"]
    assert cmd[cmd.index("--settings") + 1] == '{"disableAllHooks": true}'
    assert cmd[cmd.index("--output-format") + 1] == "json"
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--model") + 1] == "haiku"


def test_denylist_hit_retains_without_calling_the_model():
    run = fake_runner(json.dumps({"retained": False, "reason": "would pass"}))
    entry = {**GENERALIZADA, "technical": {"en": "Work for Acme Corp.", "pt": "Trabalho para a ACME corp."}}
    v = juiz.avaliar(entry, denylist=["Acme Corp"], runner=run, rubric_text=RUBRIC)
    assert v.retained is True
    assert v.source == "denylist"
    assert "Acme Corp" in v.reason
    assert run.calls == []


def test_fenced_json_is_accepted():
    run = fake_runner('```json\n{"retained": false, "reason": "ok"}\n```')
    v = juiz.avaliar(GENERALIZADA, denylist=[], runner=run, rubric_text=RUBRIC)
    assert v.retained is False


@pytest.mark.parametrize(
    "runner",
    [
        fake_runner("I think it is fine."),  # no JSON
        fake_runner('{"retained": "yes"}'),  # wrong type
        fake_runner("", returncode=1),  # process failed
        fake_runner("", is_error=True),  # claude reported an error
    ],
)
def test_unreadable_verdict_fails_closed(runner):
    v = juiz.avaliar(GENERALIZADA, denylist=[], runner=runner, rubric_text=RUBRIC)
    assert v.retained is True
    assert v.source == "fallback"


def test_timeout_fails_closed():
    def run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 1)

    v = juiz.avaliar(GENERALIZADA, denylist=[], runner=run, rubric_text=RUBRIC)
    assert v.retained is True


def test_denylist_loader_accepts_both_shapes(tmp_path):
    p = tmp_path / "d.json"
    p.write_text('{"names": [" Acme ", "", 3]}', encoding="utf-8")
    assert juiz.carregar_denylist(p) == ["Acme"]
    p.write_text('["X", "Y"]', encoding="utf-8")
    assert juiz.carregar_denylist(p) == ["X", "Y"]
    assert juiz.carregar_denylist(tmp_path / "missing.json") == []
