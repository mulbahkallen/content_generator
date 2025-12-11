"""Utilities for handling golden rule embeddings and retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import tiktoken

from openai import OpenAI


@dataclass
class RuleChunk:
    text: str
    embedding: List[float]


def _get_encoder() -> tiktoken.Encoding:
    try:
        return tiktoken.encoding_for_model("text-embedding-ada-002")
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def split_into_chunks(text: str, min_tokens: int = 300, max_tokens: int = 800) -> List[str]:
    """Split text into roughly token-sized chunks within the desired bounds."""

    encoder = _get_encoder()
    tokens = encoder.encode(text)
    chunks: List[str] = []

    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        # ensure minimum token count; if remaining tokens too small, merge into previous chunk
        if end - start < min_tokens and chunks:
            chunks[-1] += encoder.decode(tokens[start:end])
            break
        chunk_text = encoder.decode(tokens[start:end])
        chunks.append(chunk_text)
        start = end

    return [c.strip() for c in chunks if c.strip()]


def embed_rule_chunks(client: OpenAI, chunks: List[str]) -> List[RuleChunk]:
    embedded: List[RuleChunk] = []
    for chunk in chunks:
        response = client.embeddings.create(model="text-embedding-ada-002", input=chunk)
        embedded.append(RuleChunk(text=chunk, embedding=response.data[0].embedding))
    return embedded


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def retrieve_relevant_rules(
    client: OpenAI, query: str, embedded_rules: List[RuleChunk], top_n: int = 12
) -> List[RuleChunk]:
    if not embedded_rules:
        return []

    query_response = client.embeddings.create(
        model="text-embedding-ada-002", input=query
    )
    query_vec = np.array(query_response.data[0].embedding)

    scored = []
    for rc in embedded_rules:
        score = _cosine_similarity(query_vec, np.array(rc.embedding))
        scored.append((score, rc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [rc for _, rc in scored[:top_n]]

