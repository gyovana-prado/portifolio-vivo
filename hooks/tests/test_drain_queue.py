"""Drain bookkeeping (issue #3): verdicts, retries, triage. No model, no network."""

import json

import drain_queue as dq


def _linha(**campos) -> str:
    return json.dumps(campos) + "\n"


# ── Verdict parsing ──────────────────────────────────────────────────────────


def test_verdicts_are_recognised():
    assert dq.interpretar_veredito("REGISTRADO 2026-07-09-x — título") == ("registrado", "2026-07-09-x — título")
    assert dq.interpretar_veredito("descartado: trivial") == ("descartado", "trivial")
    assert dq.interpretar_veredito("FALHA mcp down") == ("falha", "mcp down")


def test_free_text_mcp_failure_is_a_falha_not_a_discard():
    status, detalhe = dq.interpretar_veredito("nada registrado — o MCP falhou ao conectar")
    assert status == "falha"
    assert "irreconhecível" in detalhe


def test_verdict_uses_first_non_empty_line():
    assert dq.interpretar_veredito("\n\n  REGISTRADO abc\nmore text")[0] == "registrado"


# ── Pending logic / attempt counter ──────────────────────────────────────────

FILA = {"s1": {"session_id": "s1", "transcript_path": "/x", "last_stop": "2026-11-01T00:00:00+00:00"}}


def test_falha_keeps_session_pending_and_counts_attempts():
    registros = [
        {"session_id": "s1", "processed_at": "2026-11-02T00:00:00+00:00", "status": "falha"},
        {"session_id": "s1", "processed_at": "2026-11-03T00:00:00+00:00", "status": "falha"},
    ]
    pend = dq.pendentes(FILA, registros)
    assert [p["session_id"] for p in pend] == ["s1"]
    assert pend[0]["attempts"] == 2


def test_terminal_statuses_remove_from_queue():
    for status in ("registrado", "descartado", "skipped"):
        registros = [{"session_id": "s1", "processed_at": "2026-11-02T00:00:00+00:00", "status": status}]
        assert dq.pendentes(FILA, registros) == []


def test_legacy_record_without_status_counts_as_processed():
    registros = [{"session_id": "s1", "processed_at": "2026-11-02T00:00:00+00:00"}]
    assert dq.pendentes(FILA, registros) == []


def test_new_stop_after_processing_reopens_the_session():
    registros = [{"session_id": "s1", "processed_at": "2026-10-01T00:00:00+00:00", "status": "registrado"}]
    assert len(dq.pendentes(FILA, registros)) == 1


def test_registrar_appends_status_and_detail(tmp_path):
    caminho = tmp_path / "processed.jsonl"
    dq.registrar("s1", "falha", "x" * 500, caminho=caminho)
    rec = json.loads(caminho.read_text().splitlines()[0])
    assert rec["status"] == "falha"
    assert len(rec["detail"]) == 300
    assert rec["processed_at"].endswith("+00:00")


# ── Triage ───────────────────────────────────────────────────────────────────


def _transcript(tmp_path, entrypoint):
    p = tmp_path / "t.jsonl"
    primeira = {"type": "last-prompt", "sessionId": "s"}
    evento = {"type": "user", "cwd": "/x", "sessionId": "s"}
    if entrypoint is not None:
        evento["entrypoint"] = entrypoint
    p.write_text(_linha(**primeira) + "not json\n" + _linha(**evento), encoding="utf-8")
    return p


def test_missing_transcript_is_skipped(tmp_path):
    ok, motivo = dq.triar({"transcript_path": str(tmp_path / "gone.jsonl")})
    assert ok is False
    assert "ausente" in motivo


def test_headless_entrypoint_is_skipped(tmp_path):
    ok, motivo = dq.triar({"transcript_path": str(_transcript(tmp_path, "sdk-cli"))})
    assert ok is False
    assert motivo == "entrypoint=sdk-cli"


def test_cli_entrypoint_is_evaluated(tmp_path):
    ok, motivo = dq.triar({"transcript_path": str(_transcript(tmp_path, "cli"))})
    assert ok is True
    assert motivo == "cli"


def test_unknown_entrypoint_is_kept(tmp_path):
    ok, _ = dq.triar({"transcript_path": str(_transcript(tmp_path, None))})
    assert ok is True


def test_entrypoint_scan_is_bounded(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text("{}\n" * 300 + _linha(entrypoint="cli"), encoding="utf-8")
    assert dq.ler_entrypoint(p, max_linhas=200) is None


# ── Prompt contract ──────────────────────────────────────────────────────────


def test_prompt_demands_structured_verdict():
    prompt = dq.PROMPT_TEMPLATE.format(transcript="/t", rubric="R", projects="a, b")
    for palavra in ("REGISTRADO", "DESCARTADO", "FALHA"):
        assert palavra in prompt
    assert "a, b" in prompt
    assert "R" in prompt
