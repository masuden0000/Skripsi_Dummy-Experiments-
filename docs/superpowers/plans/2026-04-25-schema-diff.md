# Schema Diff Mitigation Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tambahkan lapisan mitigasi risiko yang memungkinkan LLM mengekstrak field/aturan secara bebas dari dokumen baru, lalu membandingkan hasilnya terhadap schema eksplisit yang sudah ada — menghasilkan diff report berupa `matched`, `changed`, `new`, `removed` — tanpa mengubah alur ekstraksi utama.

**Architecture:** Pipeline utama (`extract_document_metadata()`) tidak diubah sama sekali. Lapisan baru berjalan sebagai perintah CLI terpisah (`schema-diff`) yang: (1) mengambil chunks dari Supabase via broad RAG queries, (2) meminta LLM mengidentifikasi semua aturan secara bebas (tidak dibatasi schema), (3) membandingkan hasil tersebut terhadap `output.json` yang sudah ada (hasil ekstraksi eksplisit sebelumnya), dan (4) menyimpan laporan diff ke `data/schema_diff_<timestamp>.json` dan `.md`.

**Tech Stack:** Python 3.11+, Pydantic v2, LangChain Groq (`ChatGroq`), LangChain Google GenAI (embeddings), Supabase Python SDK, `python-frontmatter`, `dataclasses`, `pytest`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `model_ai/extractor/schema_differ.py` | **Create** | Core module: `SchemaDiff`, `FieldChange`, `flatten_schema()`, `load_old_schema()`, `diff_schemas()`, `fetch_broad_chunks()`, `free_extract_all_rules()`, `generate_report()`, `save_diff()`, `run_schema_diff()` |
| `model_ai/extractor/prompts/free_extraction.md` | **Create** | Prompt file yang meminta LLM mengidentifikasi semua aturan secara bebas |
| `model_ai/extractor/prompts.py` | **Modify** | Tambah konstanta `FREE_EXTRACTION = _load("free_extraction.md")` |
| `manage.py` | **Modify** | Tambah subcommand `schema-diff` yang memanggil `run_schema_diff()` |
| `tests/extractor/test_schema_differ.py` | **Create** | Unit tests untuk semua fungsi pure di `schema_differ.py` |
| `tests/extractor/test_doc_extractor.py` | **Modify** | Hapus import `load_prompt` yang sudah dihapus dari `doc_extractor.py` |

---

## Task 0: Fix Broken Test Import (Prerequisite)

Setelah refactor prompt centralization, `test_doc_extractor.py` masih mengimpor `load_prompt` dari `doc_extractor.py` — fungsi ini sudah dihapus. File akan crash saat diimport.

**Files:**
- Modify: `tests/extractor/test_doc_extractor.py:6`

- [ ] **Step 1: Jalankan tests untuk memverifikasi error**

```bash
cd experiments/pymupdf4llm
python -m pytest tests/extractor/test_doc_extractor.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name 'load_prompt' from 'model_ai.extractor.doc_extractor'`

- [ ] **Step 2: Hapus import dan test yang menggunakan `load_prompt`**

Di `tests/extractor/test_doc_extractor.py`, ganti baris 6–7:

```python
# SEBELUM
from model_ai.extractor.doc_extractor import build_sources, load_prompt, render_prompt
from model_ai.extractor.models import PageCountExtracted, Source, TypographyExtracted
```

Menjadi:

```python
# SESUDAH
from model_ai.extractor.doc_extractor import build_sources, render_prompt
from model_ai.extractor.models import PageCountExtracted, Source, TypographyExtracted
```

Kemudian hapus fungsi `test_load_prompt_single_query`, `test_load_prompt_multiple_queries`, `test_load_prompt_missing_query_raises` (baris 52–101 — ketiganya menguji `load_prompt` yang sudah tidak ada).

- [ ] **Step 3: Verifikasi tests yang tersisa tetap lulus**

```bash
python -m pytest tests/extractor/test_doc_extractor.py -v
```

Expected: 5 tests PASSED (build_sources x3, render_prompt x2, model validators x2)

- [ ] **Step 4: Commit**

```bash
git add tests/extractor/test_doc_extractor.py
git commit -m "fix: remove stale load_prompt import from test_doc_extractor"
```

---

## Task 1: Define `SchemaDiff` + `diff_schemas()` (Pure Functions, TDD)

Semua logika di task ini murni (pure) — tidak ada IO, tidak ada LLM. Mudah di-TDD.

**Files:**
- Create: `tests/extractor/test_schema_differ.py`
- Create: `model_ai/extractor/schema_differ.py` (stub dulu, isi bertahap)

- [ ] **Step 1: Buat file test dengan semua test case untuk `diff_schemas()`**

Buat `tests/extractor/test_schema_differ.py`:

```python
import json
import pytest

from model_ai.extractor.schema_differ import (
    FieldChange,
    SchemaDiff,
    diff_schemas,
    flatten_schema,
    generate_report,
)


# --- diff_schemas() ---

def test_diff_schemas_matched():
    old = {"typography.font_family": "Times New Roman"}
    new = {"typography.font_family": "Times New Roman"}
    diff = diff_schemas(old, new)
    assert "typography.font_family" in diff.matched
    assert diff.changed == []
    assert diff.new_fields == []
    assert diff.removed == []


def test_diff_schemas_matched_case_insensitive_and_stripped():
    old = {"spacing.paragraph_alignment": "  Justify  "}
    new = {"spacing.paragraph_alignment": "justify"}
    diff = diff_schemas(old, new)
    assert "spacing.paragraph_alignment" in diff.matched


def test_diff_schemas_changed():
    old = {"spacing.line_spacing_body": "1.5"}
    new = {"spacing.line_spacing_body": "2.0"}
    diff = diff_schemas(old, new)
    assert len(diff.changed) == 1
    assert diff.changed[0].key == "spacing.line_spacing_body"
    assert diff.changed[0].old_value == "1.5"
    assert diff.changed[0].new_value == "2.0"


def test_diff_schemas_new_field():
    old = {}
    new = {"new_rule.watermark_required": True}
    diff = diff_schemas(old, new)
    assert len(diff.new_fields) == 1
    assert diff.new_fields[0].key == "new_rule.watermark_required"
    assert diff.new_fields[0].new_value is True
    assert diff.new_fields[0].old_value is None


def test_diff_schemas_removed():
    old = {"numbering.chapter_numbering_format": "BAB I"}
    new = {}
    diff = diff_schemas(old, new)
    assert len(diff.removed) == 1
    assert diff.removed[0].key == "numbering.chapter_numbering_format"
    assert diff.removed[0].old_value == "BAB I"
    assert diff.removed[0].new_value is None


def test_diff_schemas_null_vs_value_is_changed():
    old = {"typography.font_family": None}
    new = {"typography.font_family": "Arial"}
    diff = diff_schemas(old, new)
    assert len(diff.changed) == 1


def test_diff_schemas_both_null_is_matched():
    old = {"typography.orientation": None}
    new = {"typography.orientation": None}
    diff = diff_schemas(old, new)
    assert "typography.orientation" in diff.matched


def test_diff_schemas_mixed():
    old = {
        "typography.font_family": "Times New Roman",
        "spacing.line_spacing_body": "1.5",
        "numbering.chapter_numbering_format": "BAB I",
    }
    new = {
        "typography.font_family": "Times New Roman",
        "spacing.line_spacing_body": "2.0",
        "new_rule.watermark": "required",
    }
    diff = diff_schemas(old, new)
    assert "typography.font_family" in diff.matched
    assert any(fc.key == "spacing.line_spacing_body" for fc in diff.changed)
    assert any(fc.key == "new_rule.watermark" for fc in diff.new_fields)
    assert any(fc.key == "numbering.chapter_numbering_format" for fc in diff.removed)


# --- flatten_schema() ---

def test_flatten_schema_basic():
    data = {"typography": {"font_family": "TNR", "font_size_body_pt": 12}}
    result = flatten_schema(data)
    assert result["typography.font_family"] == "TNR"
    assert result["typography.font_size_body_pt"] == 12


def test_flatten_schema_skips_sources():
    data = {
        "typography": {
            "font_family": "TNR",
            "sources": [{"chunk_index": 1}],
        }
    }
    result = flatten_schema(data)
    assert "typography.font_family" in result
    assert not any("sources" in k for k in result)


def test_flatten_schema_skips_top_level_metadata():
    data = {
        "document_type": "proposal",
        "source_document": "panduan.pdf",
        "typography": {"font_family": "TNR"},
    }
    result = flatten_schema(data)
    assert "document_type" not in result
    assert "source_document" not in result
    assert "typography.font_family" in result


def test_flatten_schema_list_serialized_as_json_string():
    data = {
        "document_structure_proposal": {
            "bab_list": [{"bab_number": "I", "title": "Pendahuluan"}]
        }
    }
    result = flatten_schema(data)
    key = "document_structure_proposal.bab_list"
    assert key in result
    parsed = json.loads(result[key])
    assert parsed[0]["title"] == "Pendahuluan"


def test_flatten_schema_bool_and_none_values_preserved():
    data = {"figures_and_tables": {"source_required_if_not_own": True, "max_width_constraint": None}}
    result = flatten_schema(data)
    assert result["figures_and_tables.source_required_if_not_own"] is True
    assert result["figures_and_tables.max_width_constraint"] is None


# --- generate_report() ---

def test_generate_report_contains_all_section_headers():
    diff = SchemaDiff(
        matched=["typography.font_family"],
        changed=[FieldChange(key="spacing.line_spacing_body", old_value="1.5", new_value="2.0")],
        new_fields=[FieldChange(key="new_rule.watermark", old_value=None, new_value=True)],
        removed=[FieldChange(key="old_rule.signatories", old_value="3", new_value=None)],
    )
    report = generate_report(diff)
    assert "Matched" in report
    assert "Changed" in report
    assert "New" in report
    assert "Removed" in report


def test_generate_report_summary_counts():
    diff = SchemaDiff(
        matched=["a", "b"],
        changed=[FieldChange("c", "x", "y")],
        new_fields=[FieldChange("d", None, "z")],
        removed=[],
    )
    report = generate_report(diff)
    assert "Matched (sama): 2" in report
    assert "Changed (berubah): 1" in report
    assert "New (baru, belum ada di schema): 1" in report
    assert "Removed (hilang dari dokumen baru): 0" in report


def test_generate_report_lists_all_keys():
    diff = SchemaDiff(
        matched=["typography.font_family"],
        changed=[FieldChange(key="spacing.line_spacing_body", old_value="1.5", new_value="2.0")],
        new_fields=[FieldChange(key="new_rule.watermark", old_value=None, new_value=True)],
        removed=[FieldChange(key="old_rule.signatories", old_value="3", new_value=None)],
    )
    report = generate_report(diff)
    assert "typography.font_family" in report
    assert "spacing.line_spacing_body" in report
    assert "new_rule.watermark" in report
    assert "old_rule.signatories" in report
```

- [ ] **Step 2: Jalankan tests — pastikan gagal karena modul belum ada**

```bash
python -m pytest tests/extractor/test_schema_differ.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'model_ai.extractor.schema_differ'`

- [ ] **Step 3: Buat stub `schema_differ.py` dengan data classes dan fungsi kosong**

Buat `model_ai/extractor/schema_differ.py`:

```python
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parents[2]
OUTPUT_PATH = APP_DIR / "data" / "output.json"
DIFF_OUTPUT_DIR = APP_DIR / "data"

_SKIP_KEYS = {"sources", "document_type", "source_document"}


@dataclass
class FieldChange:
    key: str
    old_value: Any
    new_value: Any


@dataclass
class SchemaDiff:
    matched: list[str] = field(default_factory=list)
    changed: list[FieldChange] = field(default_factory=list)
    new_fields: list[FieldChange] = field(default_factory=list)
    removed: list[FieldChange] = field(default_factory=list)


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def flatten_schema(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in data.items():
        if k in _SKIP_KEYS:
            continue
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(flatten_schema(v, prefix=full_key))
        elif isinstance(v, list):
            result[full_key] = json.dumps(v, ensure_ascii=False)
        else:
            result[full_key] = v
    return result


def diff_schemas(old: dict[str, Any], new: dict[str, Any]) -> SchemaDiff:
    diff = SchemaDiff()
    old_keys = set(old.keys())
    new_keys = set(new.keys())

    for key in old_keys & new_keys:
        if _normalize(old[key]) == _normalize(new[key]):
            diff.matched.append(key)
        else:
            diff.changed.append(FieldChange(key=key, old_value=old[key], new_value=new[key]))

    for key in new_keys - old_keys:
        diff.new_fields.append(FieldChange(key=key, old_value=None, new_value=new[key]))

    for key in old_keys - new_keys:
        diff.removed.append(FieldChange(key=key, old_value=old[key], new_value=None))

    return diff


def load_old_schema() -> dict[str, Any]:
    if not OUTPUT_PATH.exists():
        return {}
    with open(OUTPUT_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return flatten_schema(data)


def generate_report(diff: SchemaDiff) -> str:
    lines = [
        "# Schema Diff Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Ringkasan",
        f"- Matched (sama): {len(diff.matched)}",
        f"- Changed (berubah): {len(diff.changed)}",
        f"- New (baru, belum ada di schema): {len(diff.new_fields)}",
        f"- Removed (hilang dari dokumen baru): {len(diff.removed)}",
        "",
    ]

    if diff.matched:
        lines += ["## Matched — Field & Nilai Sama", ""]
        for key in diff.matched:
            lines.append(f"- `{key}`")
        lines.append("")

    if diff.changed:
        lines += ["## Changed — Nilai Berubah", ""]
        for fc in diff.changed:
            lines += [
                f"- `{fc.key}`",
                f"  - Lama: `{fc.old_value}`",
                f"  - Baru: `{fc.new_value}`",
            ]
        lines.append("")

    if diff.new_fields:
        lines += ["## New — Field Baru (Belum Ada di Schema Eksplisit)", ""]
        for fc in diff.new_fields:
            lines.append(f"- `{fc.key}`: `{fc.new_value}`")
        lines.append("")

    if diff.removed:
        lines += ["## Removed — Field Tidak Ditemukan di Dokumen Baru", ""]
        for fc in diff.removed:
            lines.append(f"- `{fc.key}` (nilai lama: `{fc.old_value}`)")
        lines.append("")

    return "\n".join(lines)


def save_diff(diff: SchemaDiff, report: str) -> None:
    DIFF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = DIFF_OUTPUT_DIR / f"schema_diff_{ts}.json"
    json_path.write_text(
        json.dumps(
            {
                "matched": diff.matched,
                "changed": [
                    {"key": fc.key, "old": fc.old_value, "new": fc.new_value}
                    for fc in diff.changed
                ],
                "new_fields": [
                    {"key": fc.key, "value": fc.new_value} for fc in diff.new_fields
                ],
                "removed": [
                    {"key": fc.key, "old_value": fc.old_value} for fc in diff.removed
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    md_path = DIFF_OUTPUT_DIR / f"schema_diff_{ts}.md"
    md_path.write_text(report, encoding="utf-8")
    print(f"[schema-diff] Laporan disimpan: {json_path}")
    print(f"[schema-diff] Laporan disimpan: {md_path}")


# Stubs untuk fungsi yang memerlukan LLM/Supabase (diimplementasi di Task 4)
def fetch_broad_chunks() -> list[dict]:  # type: ignore[empty-body]
    ...


def free_extract_all_rules(chunks: list[dict]) -> dict[str, Any]:  # type: ignore[empty-body]
    ...


def run_schema_diff() -> SchemaDiff:  # type: ignore[empty-body]
    ...
```

- [ ] **Step 4: Jalankan tests — harus lulus semua**

```bash
python -m pytest tests/extractor/test_schema_differ.py -v
```

Expected: semua test PASSED

- [ ] **Step 5: Commit**

```bash
git add model_ai/extractor/schema_differ.py tests/extractor/test_schema_differ.py
git commit -m "feat: add SchemaDiff data model, diff_schemas(), flatten_schema(), generate_report() with tests"
```

---

## Task 2: Buat Prompt File Free Extraction + Register di `prompts.py`

Prompt ini meminta LLM mengidentifikasi semua aturan yang ditemukan dalam chunks secara bebas (tidak dibatasi schema yang sudah ada).

**Files:**
- Create: `model_ai/extractor/prompts/free_extraction.md`
- Modify: `model_ai/extractor/prompts.py` (tambah 1 baris)

- [ ] **Step 1: Buat `free_extraction.md`**

Buat file `model_ai/extractor/prompts/free_extraction.md`:

```markdown
---
queries:
  - "aturan format penulisan dokumen PKM tipografi huruf"
  - "ketentuan struktur bab lampiran penomoran halaman"
  - "persyaratan teknis layout ukuran kertas margin"
  - "ketentuan gambar tabel caption sumber referensi"
  - "batas halaman jumlah halaman format nama file"
top_k: 10
---

# Free Extraction — Identifikasi Semua Aturan Dokumen

Kamu adalah asisten AI yang bertugas menganalisis panduan penulisan dokumen akademik Indonesia (PKM).

Berikut adalah potongan konten dari buku panduan:

{context}

## Tugas

Baca seluruh konten di atas dan identifikasi **semua aturan, ketentuan, dan parameter format penulisan** yang kamu temukan — tanpa batasan field tertentu.

Keluarkan hasil sebagai JSON flat (key-value) menggunakan konvensi:
- Gunakan nama field yang sesuai dengan schema yang sudah ada bila relevan, contoh:
  - `typography.font_family`, `typography.font_size_body_pt`
  - `page_layout.margin_top_cm`, `page_layout.paper_size`
  - `spacing.line_spacing_body`, `spacing.paragraph_alignment`
  - `numbering.chapter_numbering_format`, `numbering.preliminary_page_format`
  - `figures_and_tables.caption_format_figure`, `figures_and_tables.source_required_if_not_own`
  - `page_count_limits.proposal_halaman_inti_maks`
  - `document_structure_proposal.max_halaman_inti`, `document_structure_proposal.format_nama_file`
- Gunakan nama deskriptif baru dengan prefix `new_rule.` untuk aturan yang tidak ada di schema di atas, contoh:
  - `new_rule.watermark_required`, `new_rule.digital_signature_count`

Aturan output:
- Value berupa string, angka integer, float, atau boolean sesuai isi aturan
- Jika aturan tidak ditemukan dalam konteks, jangan sertakan key-nya (jangan return null)
- Keluarkan HANYA JSON tanpa penjelasan tambahan
- Mulai respons langsung dengan karakter `{`

Contoh format output:
```json
{
  "typography.font_family": "Times New Roman",
  "typography.font_size_body_pt": 12,
  "page_layout.margin_top_cm": 4.0,
  "page_count_limits.proposal_halaman_inti_maks": 10,
  "new_rule.digital_submission_required": true
}
```
```

- [ ] **Step 2: Tambahkan `FREE_EXTRACTION` ke `prompts.py`**

Buka `model_ai/extractor/prompts.py`, tambahkan di akhir file:

```python
# ---------------------------------------------------------------------------
# Digunakan oleh: free_extract_all_rules() di schema_differ.py
# Prompt untuk ekstraksi bebas semua aturan dokumen tanpa batasan schema.
# ---------------------------------------------------------------------------
FREE_EXTRACTION = _load("free_extraction.md")
```

- [ ] **Step 3: Verifikasi `FREE_EXTRACTION` bisa diimport**

```bash
python -c "from model_ai.extractor.prompts import FREE_EXTRACTION; print(FREE_EXTRACTION.queries[:1])"
```

Expected: `['aturan format penulisan dokumen PKM tipografi huruf']`

- [ ] **Step 4: Commit**

```bash
git add model_ai/extractor/prompts/free_extraction.md model_ai/extractor/prompts.py
git commit -m "feat: add FREE_EXTRACTION prompt for LLM-driven free schema discovery"
```

---

## Task 3: Implementasi `fetch_broad_chunks()` + `free_extract_all_rules()` di `schema_differ.py`

Kedua fungsi ini memerlukan koneksi ke Supabase dan LLM — tidak di-unit-test secara langsung, tapi kita test parsing JSON-nya.

**Files:**
- Modify: `model_ai/extractor/schema_differ.py`
- Modify: `tests/extractor/test_schema_differ.py` (tambah test untuk JSON parsing)

- [ ] **Step 1: Tambahkan test untuk JSON parsing di `free_extract_all_rules()`**

Tambahkan ke `tests/extractor/test_schema_differ.py`:

```python
from unittest.mock import MagicMock, patch


# --- free_extract_all_rules() JSON parsing ---

def test_free_extract_parses_plain_json(monkeypatch):
    """LLM mengembalikan JSON polos tanpa code fence."""
    fake_response = MagicMock()
    fake_response.content = '{"typography.font_family": "TNR", "page_layout.paper_size": "A4"}'

    with patch("model_ai.extractor.schema_differ.ChatGroq") as MockLLM:
        MockLLM.return_value.invoke.return_value = fake_response
        from model_ai.extractor.schema_differ import free_extract_all_rules
        result = free_extract_all_rules([{"content": "dummy chunk"}])

    assert result["typography.font_family"] == "TNR"
    assert result["page_layout.paper_size"] == "A4"


def test_free_extract_parses_json_code_fence(monkeypatch):
    """LLM mengembalikan JSON di dalam code fence markdown."""
    fake_response = MagicMock()
    fake_response.content = '```json\n{"typography.font_size_body_pt": 12}\n```'

    with patch("model_ai.extractor.schema_differ.ChatGroq") as MockLLM:
        MockLLM.return_value.invoke.return_value = fake_response
        from model_ai.extractor.schema_differ import free_extract_all_rules
        result = free_extract_all_rules([{"content": "dummy chunk"}])

    assert result["typography.font_size_body_pt"] == 12


def test_free_extract_returns_empty_dict_on_invalid_json(monkeypatch):
    """LLM mengembalikan respons yang tidak bisa di-parse → return {}."""
    fake_response = MagicMock()
    fake_response.content = "Maaf, saya tidak dapat mengekstrak aturan dari konteks ini."

    with patch("model_ai.extractor.schema_differ.ChatGroq") as MockLLM:
        MockLLM.return_value.invoke.return_value = fake_response
        from model_ai.extractor.schema_differ import free_extract_all_rules
        result = free_extract_all_rules([{"content": "dummy chunk"}])

    assert result == {}


def test_free_extract_returns_empty_dict_for_empty_chunks():
    """Jika tidak ada chunks, tidak perlu memanggil LLM."""
    from model_ai.extractor.schema_differ import free_extract_all_rules
    result = free_extract_all_rules([])
    assert result == {}
```

- [ ] **Step 2: Jalankan test baru — pastikan gagal dulu**

```bash
python -m pytest tests/extractor/test_schema_differ.py::test_free_extract_parses_plain_json -v
```

Expected: test fail (fungsi masih berupa stub `...`)

- [ ] **Step 3: Implementasi `fetch_broad_chunks()` dan `free_extract_all_rules()` di `schema_differ.py`**

Tambahkan import di atas `schema_differ.py` (setelah import `json`):

```python
import re
from typing import Any

from langchain_groq import ChatGroq

from model_ai.config import get_config
from model_ai.extractor.doc_extractor import (
    _build_embedder,
    _build_supabase,
    _expand_to_full_headers,
    _format_vector,
    render_prompt,
)
from model_ai.extractor.prompts import FREE_EXTRACTION

CONFIG = get_config()
EMBEDDING_DIMENSION = 768
_BROAD_QUERIES = [
    "aturan format penulisan dokumen PKM tipografi huruf",
    "ketentuan struktur bab lampiran penomoran halaman",
    "persyaratan teknis layout ukuran kertas margin",
    "ketentuan gambar tabel caption sumber referensi",
    "batas halaman jumlah halaman format nama file",
]
```

Ganti stub `fetch_broad_chunks()` dengan implementasi:

```python
def fetch_broad_chunks() -> list[dict]:
    """Retrieve representative chunks via broad RAG queries covering all document domains."""
    embedder = _build_embedder()
    client = _build_supabase()

    seen: dict[int, dict] = {}
    for query in _BROAD_QUERIES:
        vector = embedder.embed_query(query, output_dimensionality=EMBEDDING_DIMENSION)
        formatted = _format_vector(vector)
        result = client.rpc(
            "match_document_chunks",
            {"query_embedding": formatted, "match_count": FREE_EXTRACTION.top_k or 10},
        ).execute()
        for chunk in (result.data or []):
            idx = int(chunk["chunk_index"])
            if idx not in seen:
                seen[idx] = chunk

    seed_chunks = sorted(seen.values(), key=lambda c: c["chunk_index"])
    return _expand_to_full_headers(seed_chunks, client)
```

Ganti stub `free_extract_all_rules()` dengan implementasi:

```python
def free_extract_all_rules(chunks: list[dict]) -> dict[str, Any]:
    """Ask LLM to freely identify all extractable rules from chunks as flat key-value JSON."""
    if not chunks:
        return {}

    prompt = render_prompt(FREE_EXTRACTION.template, chunks)
    CONFIG.disable_blackhole_proxies()
    llm = ChatGroq(
        model=CONFIG.model_name,
        api_key=CONFIG.groq_api_key.get_secret_value(),
    )
    result = llm.invoke(prompt)
    raw = str(result.content).strip()

    # Coba parse JSON dari code fence dulu, lalu plain JSON
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if json_match:
        raw = json_match.group(1)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}
```

Ganti stub `run_schema_diff()` dengan implementasi:

```python
def run_schema_diff() -> SchemaDiff:
    """Orchestrate the full schema diff pipeline."""
    print("[schema-diff] Memuat schema lama dari output.json...")
    old = load_old_schema()
    print(f"[schema-diff] {len(old)} field ditemukan di schema lama.")

    print("[schema-diff] Mengambil chunks dari Supabase...")
    chunks = fetch_broad_chunks()
    print(f"[schema-diff] {len(chunks)} chunk ditemukan.")

    print("[schema-diff] Menjalankan free extraction via LLM...")
    new = free_extract_all_rules(chunks)
    print(f"[schema-diff] {len(new)} field diekstrak secara bebas.")

    diff = diff_schemas(old, new)
    report = generate_report(diff)
    save_diff(diff, report)

    print(
        f"[schema-diff] Selesai — "
        f"Matched: {len(diff.matched)}, "
        f"Changed: {len(diff.changed)}, "
        f"New: {len(diff.new_fields)}, "
        f"Removed: {len(diff.removed)}"
    )
    return diff
```

- [ ] **Step 4: Jalankan semua tests di `test_schema_differ.py`**

```bash
python -m pytest tests/extractor/test_schema_differ.py -v
```

Expected: semua test PASSED (termasuk 4 test baru untuk `free_extract_all_rules`)

- [ ] **Step 5: Commit**

```bash
git add model_ai/extractor/schema_differ.py tests/extractor/test_schema_differ.py
git commit -m "feat: implement fetch_broad_chunks() and free_extract_all_rules() in schema_differ"
```

---

## Task 4: Tambah CLI Command `schema-diff` ke `manage.py`

**Files:**
- Modify: `manage.py`

- [ ] **Step 1: Tambahkan fungsi `run_schema_diff_cmd()` ke `manage.py`**

Tambahkan fungsi baru setelah `run_extract()` di baris 39:

```python
def run_schema_diff_cmd() -> None:
    from model_ai.extractor.schema_differ import run_schema_diff

    run_schema_diff()
```

- [ ] **Step 2: Tambahkan subparser `schema-diff`**

Di dalam `main()`, setelah blok `subparsers.add_parser("extract", ...)` (sekitar baris 68), tambahkan:

```python
subparsers.add_parser(
    "schema-diff",
    help=(
        "Jalankan free extraction via LLM lalu bandingkan terhadap output.json. "
        "Simpan laporan diff ke data/schema_diff_<timestamp>.json dan .md."
    ),
)
```

- [ ] **Step 3: Tambahkan handler `schema-diff` di bagian `if args.command`**

Setelah blok `if args.command == "extract":` (baris 81-83), tambahkan:

```python
if args.command == "schema-diff":
    run_schema_diff_cmd()
    return
```

- [ ] **Step 4: Verifikasi perintah terdaftar di help output**

```bash
python manage.py --help
```

Expected output mencakup:
```
  schema-diff         Jalankan free extraction via LLM lalu bandingkan terhadap output.json.
```

- [ ] **Step 5: Verifikasi `--help` subcommand**

```bash
python manage.py schema-diff --help
```

Expected: menampilkan help tanpa error

- [ ] **Step 6: Commit**

```bash
git add manage.py
git commit -m "feat: add schema-diff CLI command to manage.py"
```

---

## Task 5: Jalankan Full Test Suite + Smoke Test Manual

- [ ] **Step 1: Jalankan seluruh test suite**

```bash
python -m pytest tests/ -v
```

Expected: semua test PASSED, tidak ada warnings terkait import

- [ ] **Step 2: Verifikasi import chain tidak ada circular dependency**

```bash
python -c "from model_ai.extractor.schema_differ import run_schema_diff; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Verifikasi `load_old_schema()` bekerja dengan output.json yang ada**

```bash
python -c "
from model_ai.extractor.schema_differ import load_old_schema
schema = load_old_schema()
print(f'Fields ditemukan: {len(schema)}')
for k in list(schema.keys())[:5]:
    print(f'  {k}: {schema[k]}')
"
```

Expected: menampilkan beberapa field dari `output.json` dalam format dotted key

- [ ] **Step 4: Final commit jika ada perubahan kecil**

```bash
git add -p  # review perubahan jika ada
git commit -m "chore: verify schema-diff pipeline integration"
```

---

## Catatan Implementasi

### Cara Menggunakan

```bash
# Setelah ada guidebook baru di-ingest (via setup) dan di-extract (via extract):
python manage.py schema-diff
```

Output: `experiments/pymupdf4llm/data/schema_diff_<timestamp>.json` dan `.md`

### Interpretasi Laporan

| Kategori | Artinya | Tindakan |
|----------|---------|---------|
| **Matched** | Aturan sama persis | Tidak perlu tindakan |
| **Changed** | Aturan ada, tapi nilainya berubah | Update prompt dan re-ekstrak |
| **New** | LLM menemukan aturan baru yang belum ada di schema | Tambahkan field baru ke Pydantic model + KEY_REGISTRY |
| **Removed** | Aturan lama tidak ditemukan LLM di dokumen baru | Verifikasi manual apakah aturan memang dihapus dari panduan |

### Keterbatasan

- Free extraction hanya mencakup chunks yang diambil via 5 broad queries × top_k=10 — bukan seluruh dokumen
- LLM bisa menggunakan nama key yang tidak persis sama dengan schema → beberapa "new" sebenarnya adalah "changed" dengan nama berbeda
- Laporan adalah panduan untuk developer, bukan auto-update schema
