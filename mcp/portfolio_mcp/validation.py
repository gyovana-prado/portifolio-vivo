"""Schema validation, bilingual completeness, and denylist sanitization.

Three lines of defense, in order:
1. JSON Schema — structural correctness (bilingual objects are enforced here).
2. Bilingual completeness — every {en, pt} present and non-empty.
3. Denylist — reject entries mentioning configured client/employer names.

The LLM's category-based sanitization (see rubric.md) is the real first line;
these are the deterministic backstop the tool refuses to write past.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

def _find_schemas_dir() -> Path:
    """Schemas ship at mcp/schemas/ (source) or portfolio_mcp/schemas/ (wheel)."""
    here = Path(__file__).resolve().parent
    for candidate in (here / "schemas", here.parent / "schemas"):
        if candidate.is_dir():
            return candidate
    raise RuntimeError("Could not locate the JSON schemas directory.")


SCHEMAS_DIR = _find_schemas_dir()


class ValidationError(Exception):
    """Raised when content fails validation, bilingual, or sanitization."""


def _load_registry() -> Registry:
    resources = []
    for schema_path in SCHEMAS_DIR.glob("*.json"):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        resources.append((schema["$id"], Resource(contents=schema, specification=DRAFT7)))
    return Registry().with_resources(resources)


_REGISTRY = _load_registry()


def _validator(schema_id: str) -> Draft7Validator:
    schema = _REGISTRY.get_or_retrieve(schema_id).value.contents
    return Draft7Validator(schema, registry=_REGISTRY)


def validate_schema(data: dict, schema_id: str) -> None:
    validator = _validator(schema_id)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        lines = []
        for e in errors:
            loc = "/".join(str(p) for p in e.absolute_path) or "(root)"
            lines.append(f"  at {loc}: {e.message}")
        raise ValidationError("Schema validation failed:\n" + "\n".join(lines))


def _iter_strings(value) -> list[str]:
    """Every string reachable in a nested dict/list — for the denylist scan."""
    out: list[str] = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_iter_strings(v))
    elif isinstance(value, list):
        for v in value:
            out.extend(_iter_strings(v))
    return out


def check_denylist(data: dict, denylist: list[str]) -> None:
    """Reject if any denied name appears anywhere in the entry (case-insensitive)."""
    if not denylist:
        return
    haystack = "\n".join(_iter_strings(data)).lower()
    hits = sorted({name for name in denylist if name.lower() in haystack})
    if hits:
        raise ValidationError(
            "Sanitization failed — entry mentions denylisted name(s): "
            + ", ".join(hits)
            + ". Generalize up one level (see rubric.md) and try again."
        )


def validate_feed_entry(entry: dict, denylist: list[str]) -> None:
    validate_schema(entry, "feed-entry.schema.json")
    check_denylist(entry, denylist)


def validate_project(project: dict, denylist: list[str]) -> None:
    validate_schema(project, "project.schema.json")
    check_denylist(project, denylist)


def validate_now(now: dict, denylist: list[str]) -> None:
    validate_schema(now, "now.schema.json")
    check_denylist(now, denylist)
