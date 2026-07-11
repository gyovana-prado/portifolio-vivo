#!/usr/bin/env python3
"""Validate the portfolio content/ tree against the JSON schemas.

Run from the repo root:  python mcp/validate_content.py
Or with uv:              uv run --project mcp validate-content

Exit code 0 = all content valid; 1 = at least one violation (fails the build,
by design — a missing translation or a malformed entry must never ship).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"
CONTENT_DIR = REPO_ROOT / "content"


def load_registry() -> Registry:
    """Load every schema keyed by its $id so relative $ref resolves."""
    resources = []
    for schema_path in SCHEMAS_DIR.glob("*.json"):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        resources.append((schema["$id"], Resource(contents=schema, specification=DRAFT7)))
    return Registry().with_resources(resources)


def validator_for(registry: Registry, schema_id: str) -> Draft7Validator:
    schema = registry.get_or_retrieve(schema_id).value.contents
    return Draft7Validator(schema, registry=registry)


def format_error(error) -> str:
    location = "/".join(str(p) for p in error.absolute_path) or "(root)"
    return f"    at {location}: {error.message}"


def validate_file(path: Path, validator: Draft7Validator, errors: list[str]) -> None:
    rel = path.relative_to(REPO_ROOT)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"  {rel}: invalid JSON — {exc}")
        return

    file_errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if file_errors:
        errors.append(f"  {rel}:")
        errors.extend(format_error(e) for e in file_errors)

    # Feed entries: the id must match the filename (id is the source of truth).
    if validator.schema.get("$id") == "feed-entry.schema.json" and isinstance(data, dict):
        expected = path.stem
        if data.get("id") != expected:
            errors.append(
                f"  {rel}: id '{data.get('id')}' must match filename '{expected}'"
            )


def main() -> int:
    if not CONTENT_DIR.exists():
        print(f"No content/ directory at {CONTENT_DIR} — nothing to validate.")
        return 0

    registry = load_registry()
    errors: list[str] = []
    checked = 0

    # Single-file documents.
    singletons = {
        "profile.json": "profile.schema.json",
        "cv.json": "cv.schema.json",
        "now.json": "now.schema.json",
    }
    for filename, schema_id in singletons.items():
        path = CONTENT_DIR / filename
        if path.exists():
            validate_file(path, validator_for(registry, schema_id), errors)
            checked += 1

    # Directory collections.
    collections = {
        "projects": "project.schema.json",
        "feed": "feed-entry.schema.json",
    }
    for subdir, schema_id in collections.items():
        validator = validator_for(registry, schema_id)
        for path in sorted((CONTENT_DIR / subdir).glob("*.json")):
            validate_file(path, validator, errors)
            checked += 1

    if errors:
        print(f"✗ Content validation failed ({checked} files checked):\n")
        print("\n".join(errors))
        return 1

    print(f"✓ Content valid — {checked} files checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
