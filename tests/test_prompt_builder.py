import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from prompt_builder import _format_dynamic_rules, _format_rule_block
from rule_storage import RuleChunk


def test_format_rule_block_dedupes_and_ignores_blanks():
    rules = {
        "seo": ["Rule A", "rule a", "", "Rule B"],
        "tone": ["Friendly", "Friendly  ", "Warm"],
    }

    formatted = _format_rule_block(rules)

    assert "Rule A" in formatted
    assert formatted.count("Rule A") == 1
    assert "Rule B" in formatted
    assert formatted.count("Friendly") == 1


def test_format_dynamic_rules_dedupes_by_text_case_insensitive():
    chunks = [
        RuleChunk(text="Keep it concise", embedding=[], metadata={"tags": ["seo"], "score": 0.8}),
        RuleChunk(text="keep it concise", embedding=[], metadata={"tags": ["seo"], "score": 0.7}),
        RuleChunk(text="Be specific", embedding=[], metadata={"tags": ["tone"], "score": 0.9}),
    ]

    formatted = _format_dynamic_rules(chunks)

    assert formatted.count("Keep it concise") == 1
    assert formatted.count("Be specific") == 1


def test_format_dynamic_rules_returns_fallback_when_empty_after_dedupe():
    chunks = [RuleChunk(text="  ", embedding=[], metadata={"tags": ["seo"]})]

    assert (
        _format_dynamic_rules(chunks)
        == "No dynamic golden rule snippets retrieved; rely on static core rules."
    )

