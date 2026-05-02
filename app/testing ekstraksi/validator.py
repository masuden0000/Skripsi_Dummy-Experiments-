from __future__ import annotations

from typing import Any

from schema import CatalogEntry, RetrievedChunk, TranslationCandidate, ValidationResult


def _coerce_enum_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip().upper()
    return str(value).strip().upper()


def _matches_declared_type(value: Any, declared_type: str | None, enum_members: list[str]) -> bool:
    if declared_type is None:
        return True

    type_text = declared_type.lower()
    if enum_members:
        return _coerce_enum_value(value) in {member.upper() for member in enum_members}
    if "bool" in type_text or "boolean" in type_text:
        return isinstance(value, bool)
    if "int" in type_text and "float" not in type_text:
        return isinstance(value, int) and not isinstance(value, bool)
    if "float" in type_text:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if "length" in type_text:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if "string" in type_text or "str" in type_text:
        return isinstance(value, str)
    return True


def validate_translation(
    *,
    source_field: str,
    source_value: Any,
    candidate: TranslationCandidate,
    entries_by_path: dict[str, CatalogEntry],
    retrieved_chunks: list[RetrievedChunk],
) -> ValidationResult:
    if candidate.status == "unmapped":
        return ValidationResult(
            source_field=source_field,
            source_value=source_value,
            final_status="unmapped",
            confidence=candidate.confidence,
            llm_status=candidate.status,
            llm_reason=candidate.reason,
            validator_reason="LLM menyatakan tidak ada properti python-docx yang cocok dari konteks RAG.",
            retrieved_chunks=retrieved_chunks,
        )

    if not candidate.target_path:
        return ValidationResult(
            source_field=source_field,
            source_value=source_value,
            final_status="rejected",
            confidence=candidate.confidence,
            llm_status=candidate.status,
            llm_reason=candidate.reason,
            validator_reason="target_path kosong.",
            retrieved_chunks=retrieved_chunks,
        )

    entry = entries_by_path.get(candidate.target_path)
    if entry is None:
        return ValidationResult(
            source_field=source_field,
            source_value=source_value,
            final_status="rejected",
            target_path=candidate.target_path,
            normalized_value=candidate.normalized_value,
            confidence=candidate.confidence,
            llm_status=candidate.status,
            llm_reason=candidate.reason,
            validator_reason="target_path tidak ada di python_docx_full_dictionary.yaml.",
            retrieved_chunks=retrieved_chunks,
        )

    if not _matches_declared_type(candidate.normalized_value, entry.value_type, entry.enum_members):
        return ValidationResult(
            source_field=source_field,
            source_value=source_value,
            final_status="rejected",
            target_path=candidate.target_path,
            target_kind=entry.kind,
            normalized_value=candidate.normalized_value,
            confidence=candidate.confidence,
            llm_status=candidate.status,
            llm_reason=candidate.reason,
            validator_reason=f"Tipe nilai tidak cocok dengan tipe dictionary: {entry.value_type}.",
            retrieved_chunks=retrieved_chunks,
        )

    if candidate.status == "needs_review" or candidate.confidence < 0.55:
        return ValidationResult(
            source_field=source_field,
            source_value=source_value,
            final_status="needs_review",
            target_path=candidate.target_path,
            target_kind=entry.kind,
            normalized_value=candidate.normalized_value,
            confidence=candidate.confidence,
            llm_status=candidate.status,
            llm_reason=candidate.reason,
            validator_reason="Target valid, tetapi confidence rendah atau LLM minta review.",
            retrieved_chunks=retrieved_chunks,
        )

    return ValidationResult(
        source_field=source_field,
        source_value=source_value,
        final_status="accepted",
        target_path=candidate.target_path,
        target_kind=entry.kind,
        normalized_value=candidate.normalized_value,
        confidence=candidate.confidence,
        llm_status=candidate.status,
        llm_reason=candidate.reason,
        validator_reason="target_path ada di dictionary dan nilai lolos validasi tipe dasar.",
        retrieved_chunks=retrieved_chunks,
    )
