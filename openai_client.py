# openai_client.py
import os
from typing import List, Dict, Any, Optional

import streamlit as st
from openai import OpenAI

from config import MODEL_NAME


def get_api_key() -> Optional[str]:
    """
    Retrieve the OpenAI API key from environment or Streamlit secrets.
    """
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key

    secrets_key = None
    try:
        if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
            secrets_key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        secrets_key = None

    return secrets_key


def get_openai_client() -> OpenAI:
    """
    Initialize and return an OpenAI client.
    Ensures the API key is set either via environment or secrets.
    """
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "OpenAI API key is missing. Set OPENAI_API_KEY env var or st.secrets['OPENAI_API_KEY']."
        )

    # Ensure env var is set so the client can pick it up
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = api_key

    client = OpenAI()
    return client


def call_openai_json(client: OpenAI, messages: List[Dict[str, str]]) -> str:
    """
    Call the OpenAI Responses API expecting a JSON object.
    Returns the raw JSON string content using the correct 'format' parameter.
    """
    try:
        response = client.responses.create(
            model=MODEL_NAME,
            input=messages,
            format="json",
        )
    except TypeError as exc:
        raise RuntimeError(
            "Your OpenAI SDK version does not support 'response_format'. "
            "Use 'format=\"json\"' instead."
        ) from exc

    try:
        # Newer OpenAI SDK gives clean text here
        return response.output_text
    except Exception as exc:
        raise RuntimeError(f"Unexpected response format: {exc}")

