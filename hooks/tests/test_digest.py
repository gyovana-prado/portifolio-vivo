"""Digest: formatting and the webhook/stdout switch (no network)."""

import json

import digest

ENTRIES = [
    {"id": "2026-11-10-a", "title": {"pt": "Título A", "en": "Title A"},
     "narrative": {"pt": "Resumo A.", "en": "Summary A."}},
    {"id": "2026-11-10-b", "title": {"en": "Title B"}, "narrative": {"en": "x" * 300},
     "_retention_reason": "setor + escala"},
]


def test_veto_digest_lists_titles_summaries_and_link():
    texto = digest.montar("https://github.com/o/r/pull/7", ENTRIES, "veto")
    assert "2 entrada(s) liberada(s)" in texto
    assert "Título A" in texto and "Resumo A." in texto
    assert "Title B" in texto  # falls back to EN
    assert "…" in texto  # long narrative truncated
    assert "https://github.com/o/r/pull/7" in texto
    assert "Vai ao ar em 48h" in texto


def test_retidas_digest_has_reasons_and_no_48h_promise():
    texto = digest.montar("u", ENTRIES, "retidas")
    assert "merge manual" in texto
    assert "setor + escala" in texto
    assert "48h" not in texto


def test_without_webhook_prints_to_stdout(capsys, monkeypatch):
    monkeypatch.delenv(digest.ENV_WEBHOOK, raising=False)
    assert digest.enviar("olá") == "stdout"
    assert "olá" in capsys.readouterr().out


def test_with_webhook_posts_json(monkeypatch):
    sent = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"ok"

    def opener(req, timeout):
        sent["url"] = req.full_url
        sent["body"] = json.loads(req.data)
        return Resp()

    assert digest.enviar("texto", webhook="https://hooks.slack.test/x", opener=opener) == "slack"
    assert sent == {"url": "https://hooks.slack.test/x", "body": {"text": "texto"}}


def test_webhook_failure_falls_back_to_stdout(capsys):
    def opener(req, timeout):
        raise OSError("down")

    assert digest.enviar("texto", webhook="https://hooks.slack.test/x", opener=opener) == "stdout"
    assert "texto" in capsys.readouterr().err
