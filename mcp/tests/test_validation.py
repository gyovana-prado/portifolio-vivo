"""Unit tests for validation + sanitization. No network — pure local logic."""

import pytest

from portfolio_mcp.validation import (
    ValidationError,
    check_denylist,
    validate_feed_entry,
    validate_now,
    validate_project,
)

VALID_ENTRY = {
    "id": "2026-07-09-example",
    "date": "2026-07-09",
    "type": "shipped",
    "tags": ["astro", "mcp"],
    "narrative": {"en": "Shipped a thing.", "pt": "Entreguei uma coisa."},
    "technical": {"en": "Details.", "pt": "Detalhes."},
    "status": "draft",
}


def test_valid_entry_passes():
    validate_feed_entry(VALID_ENTRY, denylist=[])


def test_missing_translation_fails():
    bad = {**VALID_ENTRY, "narrative": {"en": "only english"}}
    with pytest.raises(ValidationError):
        validate_feed_entry(bad, denylist=[])


def test_bad_id_pattern_fails():
    bad = {**VALID_ENTRY, "id": "not-a-date-slug"}
    with pytest.raises(ValidationError):
        validate_feed_entry(bad, denylist=[])


def test_invalid_type_fails():
    bad = {**VALID_ENTRY, "type": "musing"}
    with pytest.raises(ValidationError):
        validate_feed_entry(bad, denylist=[])


def test_denylist_hit_is_rejected():
    entry = {
        **VALID_ENTRY,
        "narrative": {"en": "Work for Acme Corp.", "pt": "Trabalho para a Acme Corp."},
    }
    with pytest.raises(ValidationError, match="Acme Corp"):
        validate_feed_entry(entry, denylist=["Acme Corp"])


def test_denylist_is_case_insensitive():
    with pytest.raises(ValidationError):
        check_denylist({"x": "we migrated ACME systems"}, denylist=["Acme"])


def test_denylist_empty_is_noop():
    check_denylist(VALID_ENTRY, denylist=[])


def test_valid_project_passes():
    project = {
        "id": "living-portfolio",
        "featured": True,
        "title": {"en": "T", "pt": "T"},
        "summary": {"en": "S", "pt": "S"},
        "stack": ["astro"],
        "period": {"start": "2026-07", "end": None},
    }
    validate_project(project, denylist=[])


def test_valid_now_passes():
    now = {
        "updated": "2026-07-09",
        "items": [{"en": "Building.", "pt": "Construindo."}],
    }
    validate_now(now, denylist=[])
