"""Rule storage and retrieval utilities for hybrid golden rule framework."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from openai import OpenAI

try:  # pragma: no cover - optional dependency for performance
    import faiss
except ImportError:  # pragma: no cover
    faiss = None

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


@dataclass
class RuleChunk:
    """Represents a rule snippet with metadata for retrieval."""

    text: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "embedding": self.embedding, "metadata": self.metadata}

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RuleChunk":
        return cls(
            text=payload.get("text", ""),
            embedding=payload.get("embedding", []),
            metadata=payload.get("metadata", {}),
        )


def _embed_texts(client: OpenAI, texts: Sequence[str], model: str = DEFAULT_EMBEDDING_MODEL) -> List[List[float]]:
    if not texts:
        return []
    response = client.embeddings.create(model=model, input=list(texts))
    return [item.embedding for item in response.data]


def _guess_tags_from_text(text: str) -> List[str]:
    lowered = text.lower()
    tags = set()
    if any(keyword in lowered for keyword in ["seo", "search", "keyword", "serp", "aeo"]):
        tags.add("seo")
    if any(keyword in lowered for keyword in ["structure", "layout", "sections", "heading", "outline"]):
        tags.add("structure")
    if any(keyword in lowered for keyword in ["cta", "call to action", "conversion", "button"]):
        tags.add("cta")
    if any(keyword in lowered for keyword in ["tone", "voice", "empathy", "personality", "brand"]):
        tags.add("tone")
    if not tags:
        tags.add("general")
    return sorted(tags)


def chunk_golden_rules(text: str, chunk_size_words: int = 260, overlap_words: int = 40) -> List[str]:
    """Chunk the golden rule framework into overlapping segments for retrieval."""

    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []

    words = cleaned.split(" ")
    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + chunk_size_words)
        chunk_words = words[start:end]
        chunk = " ".join(chunk_words).strip()
        if chunk:
            chunks.append(chunk)
        if end == len(words):
            break
        start = max(end - overlap_words, end) if overlap_words >= chunk_size_words else end - overlap_words
    # De-duplicate minor overlaps if any
    unique_chunks: List[str] = []
    seen = set()
    for chunk in chunks:
        if chunk not in seen:
            unique_chunks.append(chunk)
            seen.add(chunk)
    return unique_chunks


class RuleStore:
    """Lightweight FAISS-backed store for golden rule retrieval."""

    def __init__(self, embedding_model: str = DEFAULT_EMBEDDING_MODEL) -> None:
        self.embedding_model = embedding_model
        self.index: Optional["faiss.IndexFlatIP"] = None
        self.chunks: List[RuleChunk] = []
        self._vectors: Optional[np.ndarray] = None

    @property
    def is_ready(self) -> bool:
        return len(self.chunks) > 0

    def build(self, client: OpenAI, raw_text: str, tags: Optional[List[str]] = None) -> List[RuleChunk]:
        tags = tags or []
        chunk_texts = chunk_golden_rules(raw_text)
        if not chunk_texts:
            self.index = None
            self.chunks = []
            return []

        embeddings = _embed_texts(client, chunk_texts, model=self.embedding_model)
        vectors = np.array(embeddings).astype("float32")
        self._vectors = vectors
        if faiss is not None:
            index = faiss.IndexFlatIP(vectors.shape[1])
            faiss.normalize_L2(vectors)
            index.add(vectors)
            self.index = index
        else:
            self.index = None
        self.chunks = []
        for text, embedding in zip(chunk_texts, embeddings):
            chunk_tags = sorted(set(tags) | set(_guess_tags_from_text(text)))
            self.chunks.append(RuleChunk(text=text, embedding=embedding, metadata={"tags": chunk_tags}))
        return self.chunks

    def query(
        self,
        client: OpenAI,
        query: str,
        top_k: int = 5,
        required_tags: Optional[List[str]] = None,
    ) -> List[RuleChunk]:
        if not self.is_ready:
            return []

        try:
            query_vec = _embed_texts(client, [query], model=self.embedding_model)[0]
        except Exception:
            return []

        if self.index is not None:
            query_np = np.array([query_vec]).astype("float32")
            faiss.normalize_L2(query_np)
            scores, indices = self.index.search(query_np, top_k)
            scored = list(zip(scores[0], indices[0]))
        else:
            vectors = self._vectors or np.array([chunk.embedding for chunk in self.chunks]).astype("float32")
            if vectors.size == 0:
                return []
            query_np = np.array(query_vec).astype("float32")
            # cosine similarity
            norms = np.linalg.norm(vectors, axis=1) * np.linalg.norm(query_np)
            scores_raw = vectors @ query_np / np.maximum(norms, 1e-12)
            scored = sorted([(score, idx) for idx, score in enumerate(scores_raw)], key=lambda x: x[0], reverse=True)[:top_k]

        top_chunks: List[RuleChunk] = []
        for score, idx in scored:
            if idx == -1 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx]
            if required_tags:
                chunk_tags = chunk.metadata.get("tags", [])
                if not any(tag in chunk_tags for tag in required_tags):
                    continue
            chunk_copy = RuleChunk(
                text=chunk.text,
                embedding=chunk.embedding,
                metadata={**chunk.metadata, "score": float(score)},
            )
            top_chunks.append(chunk_copy)
        return top_chunks

    def save(self, path_prefix: str) -> None:
        if not self.is_ready:
            return
        os.makedirs(os.path.dirname(path_prefix), exist_ok=True)
        if self.index is not None and faiss is not None:
            faiss.write_index(self.index, f"{path_prefix}.faiss")
        with open(f"{path_prefix}.json", "w", encoding="utf-8") as f:
            json.dump([chunk.to_dict() for chunk in self.chunks], f)

    @classmethod
    def load(cls, path_prefix: str) -> "RuleStore":
        store = cls()
        faiss_path = f"{path_prefix}.faiss"
        meta_path = f"{path_prefix}.json"
        if not os.path.exists(meta_path):
            return store
        try:
            if faiss is not None and os.path.exists(faiss_path):
                store.index = faiss.read_index(faiss_path)
            with open(meta_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            store.chunks = [RuleChunk.from_dict(item) for item in payload]
            store._vectors = np.array([chunk.embedding for chunk in store.chunks]).astype("float32")
        except Exception:
            store.index = None
            store.chunks = []
        return store


def load_core_rules(core_path: str) -> Dict[str, Any]:
    if not os.path.exists(core_path):
        return {}
    with open(core_path, "r", encoding="utf-8") as f:
        return json.load(f)
