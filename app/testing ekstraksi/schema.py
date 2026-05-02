from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


TranslationStatus = Literal["mapped", "unmapped", "needs_review"]
FinalStatus = Literal["accepted", "rejected", "unmapped", "needs_review", "retrieve_failed"]


class CatalogEntry(BaseModel):
    id: str
    section: str
    kind: str
    path: str
    value_type: str | None = None
    description: str = ""
    signature: str | None = None
    enum_name: str | None = None
    enum_members: list[str] = Field(default_factory=list)
    chunk_text: str


class RetrievedChunk(BaseModel):
    chunk_id: str
    path: str | None = None
    text: str
    score: float = 0.0


class TranslationCandidate(BaseModel):
    source_field: str
    status: TranslationStatus
    target_path: str | None = None
    normalized_value: Any = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class ValidationResult(BaseModel):
    source_field: str
    source_value: Any
    final_status: FinalStatus
    target_path: str | None = None
    target_kind: str | None = None
    normalized_value: Any = None
    confidence: float = 0.0
    llm_status: TranslationStatus | None = None
    llm_reason: str = ""
    validator_reason: str = ""
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)


class TranslationReport(BaseModel):
    generated_at: str
    inputs: dict[str, str]
    summary: dict[str, Any]
    results: list[ValidationResult]
