"""Centralized access to model and style defaults with safe fallbacks.

This module pulls values from ``config.py`` when available but gracefully
falls back to built-in defaults so the app can still boot if the config module
is missing or incomplete.
"""
from typing import List

# Built-in fallbacks so the UI can continue to run even if config.py is missing
# expected values.
DEFAULT_MODEL_NAME_FALLBACK = "gpt-4.1-mini"
MODEL_OPTIONS_FALLBACK: List[str] = [
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-4o-mini",
    "gpt-4o",
]
STYLE_PROFILE_OPTIONS_FALLBACK: List[str] = [
    "Default agency style",
    "Conversational expert",
    "Concise and direct",
]

try:  # noqa: SIM105 - explicitly prefer ImportError handling for clarity
    import config as user_config
except ImportError:
    user_config = None

DEFAULT_MODEL_NAME: str = getattr(
    user_config, "DEFAULT_MODEL_NAME", DEFAULT_MODEL_NAME_FALLBACK
)
MODEL_OPTIONS: List[str] = getattr(user_config, "MODEL_OPTIONS", MODEL_OPTIONS_FALLBACK)
STYLE_PROFILE_OPTIONS: List[str] = getattr(
    user_config, "STYLE_PROFILE_OPTIONS", STYLE_PROFILE_OPTIONS_FALLBACK
)
