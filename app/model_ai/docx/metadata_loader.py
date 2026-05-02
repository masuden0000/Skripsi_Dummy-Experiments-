"""
Fungsi: Memuat metadata hasil ekstraksi yang dibutuhkan untuk mengisi placeholder DOCX.

Digunakan oleh: model_ai/docx/generator.py

Tujuan: Menjaga pemetaan metadata ke template tetap konsisten dan terverifikasi.
"""
import json
from pathlib import Path

from model_ai.extractor.models import DocumentMetadata


# ---------------------------------------------------------------------------
# Digunakan oleh: model_ai/docx/generator.py
# Menjalankan fungsi `load_document_metadata` sebagai bagian alur `metadata_loader`.
# ---------------------------------------------------------------------------
def load_document_metadata(path: Path) -> DocumentMetadata:
    if not path.exists():
        raise FileNotFoundError(f"File metadata tidak ditemukan: {path}")

    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    return DocumentMetadata.model_validate(payload)
