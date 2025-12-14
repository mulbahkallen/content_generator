"""Tests for OpenAI client prompt sanitation helpers."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from openai_client import _dedupe_prompt_lines, _sanitize_messages


def test_dedupe_prompt_lines_removes_duplicate_non_empty_lines():
    prompt = "Line A\nLine B\nLine A\n\nLine B\nLine C"
    assert _dedupe_prompt_lines(prompt) == "Line A\nLine B\n\nLine C"


def test_sanitize_messages_preserves_original_and_deduplicates_content():
    messages = [
        {"role": "user", "content": "Repeat\nRepeat\nUnique"},
        {"role": "system", "content": "Stay"},
    ]

    sanitized = _sanitize_messages(messages)

    assert sanitized[0]["content"] == "Repeat\nUnique"
    assert messages[0]["content"] == "Repeat\nRepeat\nUnique"


def test_sanitize_messages_dedupes_across_messages():
    messages = [
        {"role": "system", "content": "Instruction A\nInstruction B"},
        {"role": "user", "content": "Instruction A\nInstruction C"},
    ]

    sanitized = _sanitize_messages(messages)

    assert sanitized[0]["content"] == "Instruction A\nInstruction B"
    assert sanitized[1]["content"] == "Instruction C"
