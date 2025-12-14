import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from utils import SchemaValidationError, safe_json_loads, validate_against_schema


def test_safe_json_loads_extracts_first_object_when_wrapped() -> None:
    raw = "noise {\"hello\": \"world\"} trailing"
    parsed = safe_json_loads(raw)
    assert parsed == {"hello": "world"}


def test_validate_against_schema_passes_for_matching_payload() -> None:
    schema = {"root": {"items": [{"name": "", "count": 0}]}}
    payload = {"root": {"items": [{"name": "Widget", "count": 3}]}}

    validate_against_schema(schema, payload)


def test_validate_against_schema_raises_on_missing_key() -> None:
    schema = {"root": {"items": [{"name": "", "count": 0}]}}
    payload = {"root": {"items": [{"name": "Widget"}]}}

    with pytest.raises(SchemaValidationError):
        validate_against_schema(schema, payload)

