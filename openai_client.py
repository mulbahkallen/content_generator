# openai_client.py
import json
import os
from typing import List, Dict, Optional

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

    try:
        if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass

    return None


def get_openai_client() -> OpenAI:
    """
    Initialize and return an OpenAI client.
    Ensures the API key is set either via environment or secrets.
    """
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "OpenAI API key is missing. Set OPENAI_API_KEY env var "
            "or st.secrets['OPENAI_API_KEY']."
        )

    # Ensure env var is set so the client can pick it up
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = api_key

    client = OpenAI()
    return client


def call_openai_json(client: OpenAI, messages: List[Dict[str, str]]) -> str:
    """Call the OpenAI Responses API and return the raw JSON string output."""
    try:
        response = client.responses.create(
            model=MODEL_NAME,
            input=messages,
        )
    except Exception as exc:
        raise RuntimeError(f"OpenAI request failed: {exc}") from exc

    # Prefer explicit text accessor when available
    if hasattr(response, "output_text") and response.output_text is not None:
        return response.output_text

    # Walk the output content to support different SDK structures
    try:
        for output in getattr(response, "output", []):
            for content in getattr(output, "content", []):
                if getattr(content, "json", None) is not None:
                    return json.dumps(content.json)
                if getattr(content, "text", None) is not None:
                    return content.text
    except Exception as exc:
        raise RuntimeError(f"Unexpected response format from OpenAI: {exc}") from exc

    raise RuntimeError("OpenAI response did not contain text or JSON content")
