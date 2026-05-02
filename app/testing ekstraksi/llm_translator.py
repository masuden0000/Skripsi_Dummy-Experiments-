from __future__ import annotations

import json
from typing import Any

from schema import RetrievedChunk, TranslationCandidate


def _safe_json(value: Any, *, limit: int = 2500) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


class LLMTranslator:
    def __init__(self, *, groq_api_key: str, model_name: str, temperature: float) -> None:
        from langchain_groq import ChatGroq

        self.llm = ChatGroq(
            model=model_name,
            temperature=temperature,
            api_key=groq_api_key,
        )
        self.chain = self.llm.with_structured_output(TranslationCandidate)

    def translate(
        self,
        *,
        source_field: str,
        source_value: Any,
        retrieved_chunks: list[RetrievedChunk],
    ) -> TranslationCandidate:
        allowed_paths = [chunk.path for chunk in retrieved_chunks if chunk.path]
        catalog_context = "\n\n---\n\n".join(chunk.text for chunk in retrieved_chunks)

        prompt = f"""
Kamu menerjemahkan field output.json ke target python-docx.

Aturan wajib:
- Gunakan hanya konteks dictionary di bawah ini.
- Jangan memakai pengetahuan umum atau data latih di luar konteks.
- target_path harus persis salah satu dari allowed_target_paths.
- Jika tidak ada padanan yang jelas, status harus "unmapped" dan target_path harus null.
- Jika ada padanan tetapi masih meragukan, status harus "needs_review".
- normalized_value harus nilai yang siap dicek validator.
- source_field harus sama persis dengan input.

source_field:
{source_field}

source_value:
{_safe_json(source_value)}

allowed_target_paths:
{json.dumps(allowed_paths, ensure_ascii=False, indent=2)}

dictionary_context:
{catalog_context}
""".strip()

        return self.chain.invoke(prompt)
