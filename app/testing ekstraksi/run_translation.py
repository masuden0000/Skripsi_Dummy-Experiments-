from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from catalog import build_catalog
from llm_translator import LLMTranslator
from retriever import DictionaryRetriever
from schema import TranslationReport, ValidationResult
from validator import validate_translation


SCRIPT_DIR = Path(__file__).resolve().parent
APP_DIR = SCRIPT_DIR.parent
DATA_DIR = APP_DIR / "data"
DEFAULT_INPUT = DATA_DIR / "output.json"
DEFAULT_DICTIONARY = DATA_DIR / "python_docx_full_dictionary.yaml"
DEFAULT_REPORT = SCRIPT_DIR / "translation_report.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Input JSON tidak ditemukan: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Input JSON harus berbentuk object/dict.")
    return data


def _flatten_parameters(data: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            # sources adalah bukti ekstraksi, bukan parameter yang perlu diterjemahkan.
            if key == "sources":
                continue
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten_parameters(value, next_prefix))
        return result

    if isinstance(data, list):
        return {prefix: data}

    return {prefix: data}


def _query_for_field(field_name: str, value: Any) -> str:
    value_text = json.dumps(value, ensure_ascii=False)
    if len(value_text) > 1200:
        value_text = value_text[:1200] + "...[truncated]"
    return f"{field_name}: {value_text}"


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return float(raw)


def _disable_blackhole_proxies() -> None:
    proxy_keys = [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]
    blackhole_targets = {"http://127.0.0.1:9", "https://127.0.0.1:9"}
    for key in proxy_keys:
        # Proxy ini membuat request AI selalu mental ke localhost:9.
        if os.getenv(key, "").strip().lower() in blackhole_targets:
            os.environ.pop(key, None)


def _build_result_for_failed_retrieval(
    *,
    field_name: str,
    value: Any,
    error: str | None,
) -> ValidationResult:
    return ValidationResult(
        source_field=field_name,
        source_value=value,
        final_status="retrieve_failed",
        validator_reason=(
            "Retrieval dictionary gagal, jadi LLM tidak dipanggil agar tidak memakai pengetahuan bebas. "
            f"Detail: {error or 'tidak ada detail'}"
        ),
    )


def _build_result_for_llm_error(
    *,
    field_name: str,
    value: Any,
    retrieved_chunks: list[Any],
    error: Exception,
) -> ValidationResult:
    return ValidationResult(
        source_field=field_name,
        source_value=value,
        final_status="needs_review",
        validator_reason=f"LLM gagal menerjemahkan field ini: {error}",
        retrieved_chunks=retrieved_chunks,
    )


def run_pipeline(args: argparse.Namespace) -> TranslationReport:
    load_dotenv(dotenv_path=APP_DIR / ".env")
    _disable_blackhole_proxies()

    input_path = Path(args.input)
    dictionary_path = Path(args.dictionary)
    output_path = Path(args.output)

    payload = _load_json(input_path)
    flattened = _flatten_parameters(payload)
    if args.max_fields:
        flattened = dict(list(flattened.items())[: args.max_fields])

    catalog_entries = build_catalog(dictionary_path)
    entries_by_path = {entry.path: entry for entry in catalog_entries}

    retriever = DictionaryRetriever(
        catalog_entries,
        mode=args.retrieval_mode,
        google_api_key=os.getenv("GOOGLE_API_KEY", "").strip() or None,
        embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", "").strip() or None,
    )

    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    model_name = args.model or os.getenv("MODEL_NAME", "").strip()
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY belum tersedia di app/.env.")
    if not model_name:
        raise ValueError("MODEL_NAME belum tersedia di app/.env atau argumen --model.")

    translator = LLMTranslator(
        groq_api_key=groq_api_key,
        model_name=model_name,
        temperature=args.temperature if args.temperature is not None else _env_float("TEMPERATURE", 0.0),
    )

    results: list[ValidationResult] = []
    for index, (field_name, value) in enumerate(flattened.items(), start=1):
        print(f"[translate] {index}/{len(flattened)} {field_name}")
        retrieval = retriever.retrieve(_query_for_field(field_name, value), top_k=args.top_k)
        if retrieval.status != "ok":
            results.append(
                _build_result_for_failed_retrieval(
                    field_name=field_name,
                    value=value,
                    error=retrieval.error,
                )
            )
            continue

        if not retrieval.chunks:
            results.append(
                ValidationResult(
                    source_field=field_name,
                    source_value=value,
                    final_status="unmapped",
                    validator_reason="Tidak ada potongan dictionary yang relevan dari RAG.",
                    retrieved_chunks=[],
                )
            )
            continue

        try:
            candidate = translator.translate(
                source_field=field_name,
                source_value=value,
                retrieved_chunks=retrieval.chunks,
            )
            results.append(
                validate_translation(
                    source_field=field_name,
                    source_value=value,
                    candidate=candidate,
                    entries_by_path=entries_by_path,
                    retrieved_chunks=retrieval.chunks,
                )
            )
        except Exception as exc:
            results.append(
                _build_result_for_llm_error(
                    field_name=field_name,
                    value=value,
                    retrieved_chunks=retrieval.chunks,
                    error=exc,
                )
            )

    counts = Counter(result.final_status for result in results)
    summary = {
        "total_fields": len(flattened),
        "catalog_entries": len(catalog_entries),
        "retrieval_mode": args.retrieval_mode,
        "accepted": counts.get("accepted", 0),
        "rejected": counts.get("rejected", 0),
        "unmapped": counts.get("unmapped", 0),
        "needs_review": counts.get("needs_review", 0),
        "retrieve_failed": counts.get("retrieve_failed", 0),
    }

    report = TranslationReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        inputs={
            "output_json": str(input_path.resolve()),
            "python_docx_dictionary": str(dictionary_path.resolve()),
            "report": str(output_path.resolve()),
        },
        summary=summary,
        results=results,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Testing ekstraksi: translate output.json ke properti python-docx dengan RAG + LLM + validator."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path output.json.")
    parser.add_argument("--dictionary", default=str(DEFAULT_DICTIONARY), help="Path python_docx_full_dictionary.yaml.")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Path laporan JSON.")
    parser.add_argument("--top-k", type=int, default=8, help="Jumlah potongan dictionary untuk setiap field.")
    parser.add_argument(
        "--retrieval-mode",
        choices=["embedding", "lexical"],
        default="lexical",
        help="Mode RAG. Default lexical agar tidak tergantung quota embedding; embedding tetap tersedia.",
    )
    parser.add_argument("--model", default=None, help="Override MODEL_NAME dari .env.")
    parser.add_argument("--temperature", type=float, default=None, help="Override TEMPERATURE dari .env.")
    parser.add_argument("--max-fields", type=int, default=None, help="Batasi jumlah field untuk smoke test.")
    return parser


def main() -> None:
    parser = build_parser()
    report = run_pipeline(parser.parse_args())
    print("[translate] selesai")
    print(json.dumps(report.summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
