from __future__ import annotations

import math
import re
from dataclasses import dataclass

from schema import CatalogEntry, RetrievedChunk


EMBEDDING_DIMENSION = 768


@dataclass
class RetrievalOutcome:
    status: str
    chunks: list[RetrievedChunk]
    error: str | None = None


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_]+", text.lower()) if token}


def _lexical_score(query: str, document_text: str) -> float:
    query_tokens = _tokenize(query)
    document_tokens = _tokenize(document_text)
    if not query_tokens or not document_tokens:
        return 0.0
    return len(query_tokens & document_tokens) / max(len(query_tokens), 1)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


class DictionaryRetriever:
    def __init__(
        self,
        entries: list[CatalogEntry],
        *,
        mode: str,
        google_api_key: str | None,
        embedding_model_name: str | None,
    ) -> None:
        self.entries = entries
        self.mode = mode
        self.google_api_key = google_api_key
        self.embedding_model_name = embedding_model_name
        self.vectors: list[list[float] | None] = [None for _ in entries]
        self.build_error: str | None = None

        if self.mode == "embedding":
            self._build_embedding_index()

    def _build_embedding_index(self) -> None:
        if not self.google_api_key or not self.embedding_model_name:
            self.build_error = "GOOGLE_API_KEY atau EMBEDDING_MODEL_NAME belum tersedia."
            return

        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            embedder = GoogleGenerativeAIEmbeddings(
                model=self.embedding_model_name,
                google_api_key=self.google_api_key,
            )
            # Embedding dibuat dari dictionary, bukan dari pengetahuan bebas model.
            embedded = embedder.embed_documents(
                [entry.chunk_text for entry in self.entries],
                output_dimensionality=EMBEDDING_DIMENSION,
            )
            self.vectors = [list(vector) for vector in embedded]
        except Exception as exc:
            self.build_error = str(exc)

    def retrieve(self, query: str, *, top_k: int) -> RetrievalOutcome:
        if self.mode == "embedding" and self.build_error:
            return RetrievalOutcome(status="retrieve_failed", chunks=[], error=self.build_error)

        if self.mode == "embedding":
            return self._retrieve_embedding(query, top_k=top_k)

        chunks = self._retrieve_lexical(query, top_k=top_k)
        return RetrievalOutcome(status="ok", chunks=chunks)

    def _retrieve_embedding(self, query: str, *, top_k: int) -> RetrievalOutcome:
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            embedder = GoogleGenerativeAIEmbeddings(
                model=self.embedding_model_name,
                google_api_key=self.google_api_key,
            )
            query_vector = embedder.embed_query(query, output_dimensionality=EMBEDDING_DIMENSION)
        except Exception as exc:
            return RetrievalOutcome(status="retrieve_failed", chunks=[], error=str(exc))

        scored: list[tuple[float, CatalogEntry]] = []
        for entry, vector in zip(self.entries, self.vectors):
            if vector is None:
                continue
            scored.append((_cosine_similarity(query_vector, vector), entry))

        scored.sort(key=lambda item: item[0], reverse=True)
        chunks = [
            RetrievedChunk(chunk_id=entry.id, path=entry.path, text=entry.chunk_text, score=score)
            for score, entry in scored[:top_k]
            if score > 0.0
        ]
        return RetrievalOutcome(status="ok", chunks=chunks)

    def _retrieve_lexical(self, query: str, *, top_k: int) -> list[RetrievedChunk]:
        scored = [(_lexical_score(query, entry.chunk_text), entry) for entry in self.entries]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RetrievedChunk(chunk_id=entry.id, path=entry.path, text=entry.chunk_text, score=score)
            for score, entry in scored[:top_k]
            if score > 0.0
        ]
