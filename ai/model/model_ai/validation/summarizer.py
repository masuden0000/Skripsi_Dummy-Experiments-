"""Ringkasan naratif hasil validasi dokumen via LLM (Groq primary, Gemini fallback).

Dipakai oleh endpoint POST /api/validation/summarize untuk memberi reviewer
catatan siap-pakai bergaya penilai dosen.
"""
from __future__ import annotations

import time
from typing import Any

from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

from model_ai.config import get_config

CONFIG = get_config()

MAX_OCCURRENCES_PER_ISSUE = 3
TEXT_PREVIEW_LEN = 80
MAX_RATE_LIMIT_WAIT = 60

SYSTEM_PROMPT = (
    "Anda adalah dosen penilai proposal PKM. Tugas Anda menulis catatan ringkas "
    "untuk lembar penilaian, berdasarkan daftar kesalahan format yang ditemukan "
    "oleh validator otomatis. Gaya bahasa: formal, lugas, langsung ke poin, "
    "menyerupai komentar dosen. Wajib menyebut lokasi kesalahan (bab, halaman, "
    "atau elemen) bila tersedia. Boleh berbentuk paragraf pendek atau poin-poin. "
    "Jangan menambah saran perbaikan teknis yang tidak ada datanya. "
    "Jangan menulis salam pembuka/penutup. Maksimal sekitar 150 kata."
)


def _compact_occurrence(occ: dict[str, Any]) -> dict[str, Any]:
    text = (occ.get("text") or "").strip()
    if len(text) > TEXT_PREVIEW_LEN:
        text = text[:TEXT_PREVIEW_LEN].rstrip() + "..."
    return {
        k: v for k, v in {
            "page": occ.get("page"),
            "bab": occ.get("bab"),
            "para_idx": occ.get("para_idx"),
            "style": occ.get("style"),
            "text": text or None,
        }.items() if v is not None and v != ""
    }


def _compact_issue(issue: dict[str, Any]) -> dict[str, Any]:
    occurrences = issue.get("occurrences") or []
    return {
        k: v for k, v in {
            "severity": issue.get("severity"),
            "category": issue.get("category"),
            "field": issue.get("field"),
            "message": issue.get("message"),
            "location": issue.get("location"),
            "expected": issue.get("expected"),
            "actual": issue.get("actual"),
            "occurrences": [
                _compact_occurrence(o) for o in occurrences[:MAX_OCCURRENCES_PER_ISSUE]
            ] or None,
        }.items() if v is not None and v != ""
    }


def _build_llm():
    CONFIG.disable_blackhole_proxies()
    api_key, model_name = CONFIG.get_llm_api_key()
    if model_name.startswith("gemini"):
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=CONFIG.temperature,
        )
    return ChatGroq(
        model=model_name,
        api_key=api_key,
        temperature=CONFIG.temperature,
    )


def _render_user_prompt(issues: list[dict[str, Any]], schema_name: str | None) -> str:
    import json

    compact = [_compact_issue(i) for i in issues]
    header = f"Skema dokumen: {schema_name}\n" if schema_name else ""
    return (
        f"{header}"
        f"Jumlah kesalahan: {len(compact)}\n\n"
        f"Daftar kesalahan (JSON):\n{json.dumps(compact, ensure_ascii=False, indent=2)}\n\n"
        "Tulis catatan penilaian sekarang."
    )


def summarize_issues(
    issues: list[dict[str, Any]] | None,
    schema_name: str | None = None,
) -> str:
    """Panggil LLM untuk membuat catatan ringkas dari list issue.

    Return string kosong bila issues kosong/None. Lempar exception bila
    semua key LLM habis — caller (endpoint) yang menerjemahkannya ke HTTP error.
    """
    if not issues:
        return ""

    prompt = _render_user_prompt(issues, schema_name)
    max_retries = len(CONFIG.groq_api_keys) + len(CONFIG.google_api_keys) + 2

    groq_keys_tried = 0
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            llm = _build_llm()
            response = llm.invoke([
                ("system", SYSTEM_PROMPT),
                ("human", prompt),
            ])
            content = getattr(response, "content", response)
            return str(content).strip()
        except Exception as e:
            last_err = e
            err_str = str(e)
            is_rate = (
                "429" in err_str
                or "rate_limit" in err_str.lower()
                or "quota" in err_str.lower()
                or "ResourceExhausted" in type(e).__name__
            )
            if not is_rate:
                raise

            if not CONFIG._groq_exhausted:
                groq_keys_tried += 1
                if groq_keys_tried < len(CONFIG.groq_api_keys):
                    CONFIG.rotate_groq_key()
                    print(f"[summarize] Rate limit Groq, rotasi key ({groq_keys_tried}/{len(CONFIG.groq_api_keys)})...")
                else:
                    CONFIG._groq_exhausted = True
                    print("[summarize] Semua Groq key exhausted, switch ke Gemini...")
            else:
                if len(CONFIG.google_api_keys) > 1:
                    CONFIG.rotate_google_key()
                wait_secs = min(30, MAX_RATE_LIMIT_WAIT)
                print(f"[summarize] Rate limit Gemini, tunggu {wait_secs}s...")
                time.sleep(wait_secs)

    raise RuntimeError(
        f"Gagal generate ringkasan setelah {max_retries} percobaan: {last_err}"
    )
