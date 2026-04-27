# Design Spec: DOCX Generator Pipeline

**Date:** 2026-04-27
**Status:** Approved
**Scope:** Refactor and extend `model_ai/docx/` menjadi pipeline 10-modul yang memisahkan formatting spec dari content rendering.

---

## Background

Pipeline generator DOCX sudah berjalan end-to-end via `manage.py docx`, tapi `docx_renderer.py` monolitik — satu file menghandle page layout, styles, preliminary pages, body rendering, dan OOXML. Selain itu, `DocxStyleConfig` hanya cover 5 field, sisanya diambil langsung dari `DocumentMetadata` di dalam renderer. Tidak ada validasi spec sebelum rendering, tidak ada audit setelah rendering.

Tujuan refactor ini:
- `DocxFormatSpec` sebagai satu-satunya interface antara spec dan python-docx
- Content (smart placeholders dari chunks) terstruktur via `content_model.py`
- Fail-fast via `validator.py` sebelum DOCX dibuat
- Deep formatting audit via `audit.py` setelah DOCX tersimpan
- Refactor bertahap — pipeline tetap jalan di setiap tahap

---

## Architecture Overview

```
output.json
    │
    ▼
loader.py          # JSON → DocumentMetadata
    │
    ▼
resolver.py        # DocumentMetadata → DocxFormatSpec
    │                (normalisasi string→enum di sini sebagai private helpers)
    ▼
schema.py          # DocxFormatSpec definition (Pydantic)
    │
    ▼
validator.py       # business rule validation, collect-all-violations, raise sekali
    │
    ▼ DocxFormatSpec          chunks (list[ChunkSource])
    │                              │
    ▼                              ▼
docx_adapter.py           content_model.py
    │                              │
    └──────────► builder.py ◄──────┘
                     │
                 renderer.py
                 ooxml_helper.py
                     │
                     ▼
               [output.docx]
                     │
                     ▼
               audit.py
```

---

## Module Descriptions

### 1. `loader.py`

Thin wrapper di atas `metadata_loader.py` yang sudah ada. Hanya I/O — tidak ada transformasi.

```python
def load_metadata(path: Path) -> DocumentMetadata: ...
```

**Relasi ke existing:** menggantikan `metadata_loader.py` (dihapus di Tahap 4). Tidak ada logika baru.

---

### 2. `schema.py` — `DocxFormatSpec`

Pydantic model yang menjadi **satu-satunya interface** antara spec layer dan document layer. Semua field yang dibutuhkan python-docx ada di sini dalam bentuk teknis. `docx_adapter.py` dan `renderer.py` tidak boleh menyentuh `DocumentMetadata`.

**Required fields** = tipe non-optional (e.g. `float`, `int`, `str`).
**Optional fields** = `T | None`.

```python
class DocxFormatSpec(BaseModel):
    # Typography
    font_family: str
    font_size_body_pt: int
    font_size_heading_pt: int
    heading_bold: bool
    heading_all_caps: bool

    # Page layout
    margin_top_cm: float
    margin_bottom_cm: float
    margin_left_cm: float
    margin_right_cm: float
    paper_size: str                       # "A4"
    orientation: str                      # "PORTRAIT" | "LANDSCAPE"
    columns: int

    # Spacing
    line_spacing: float
    line_spacing_rule: str                # "MULTIPLE" | "EXACT" | "AT_LEAST"
    paragraph_alignment: str             # "JUSTIFY" | "LEFT" | "CENTER" | "RIGHT"
    first_line_indent_cm: float | None   # optional

    # Page numbering
    page_number_prelim_location: str     # "header" | "footer"
    page_number_prelim_alignment: str    # "LEFT" | "CENTER" | "RIGHT"
    page_number_prelim_format: str       # "lowerRoman" | "decimal"
    page_number_content_location: str
    page_number_content_alignment: str
    page_number_content_format: str

    # Numbering formats
    chapter_format: str                  # "BAB {n}"
    sub_chapter_format: str             # "{bab}.{sub}"
    figure_format: str                   # "Gambar {n}."
    table_format: str                    # "Tabel {bab}.{n}"

    # Figures & tables
    table_caption_position: str          # "ABOVE" | "BELOW"
    figure_caption_position: str         # "ABOVE" | "BELOW"
    caption_format_figure: str
    caption_format_table: str
    source_required_if_not_own: bool

    # Document structure
    proposal_sections: list[SectionItem]
    proposal_max_halaman_inti: int | None
    laporan_kemajuan_sections: list[SectionItem]
    laporan_akhir_sections: list[SectionItem]
```

`SectionItem` diimpor dari `extractor.models` (sudah ada).

**`DocxStyleConfig` (lama) di-deprecate** setelah `DocxFormatSpec` selesai dipakai oleh semua modul.

---

### 3. `resolver.py`

Mengonversi `DocumentMetadata` → `DocxFormatSpec`. Normalisasi string-ke-enum dilakukan di sini sebagai private helpers (tidak ada `normalizer.py` terpisah).

**Dua kategori field:**
- **Required**: diambil dari metadata; jika null → raise `ResolutionError` dengan nama field dan nilai asli
- **Optional**: diambil dari metadata jika ada; jika null → fallback ke konstanta `_DEFAULTS`

```python
_DEFAULTS: dict[str, Any] = {
    "font_family": "Times New Roman",
    "font_size_body_pt": 12,
    "margin_top_cm": 3.0,
    "margin_bottom_cm": 3.0,
    "margin_left_cm": 4.0,
    "margin_right_cm": 3.0,
    "line_spacing": 1.15,
    "line_spacing_rule": "MULTIPLE",
    "paragraph_alignment": "JUSTIFY",
    "page_number_prelim_location": "footer",
    "page_number_prelim_alignment": "RIGHT",
    "page_number_prelim_format": "lowerRoman",
    "page_number_content_location": "header",
    "page_number_content_alignment": "RIGHT",
    "page_number_content_format": "decimal",
    "columns": 1,              # dokumen akademik selalu 1 kolom
}

class ResolutionError(ValueError):
    def __init__(self, field: str, raw_value: Any) -> None: ...

def resolve_spec(metadata: DocumentMetadata) -> DocxFormatSpec: ...

# Private helpers (normalisasi):
def _resolve_alignment(raw: str | None) -> str: ...       # → "JUSTIFY" | "LEFT" | ...
def _resolve_orientation(raw: str | None) -> str: ...     # → "PORTRAIT" | "LANDSCAPE"
def _resolve_location(raw: str | None) -> str: ...        # → "header" | "footer"
```

---

### 4. `validator.py`

Menerima `DocxFormatSpec`, memvalidasi business rules yang tidak bisa ditangkap Pydantic.

**Rules:**
- `font_size_heading_pt >= font_size_body_pt`
- `proposal_sections` tidak boleh kosong
- Setiap `SectionItem` dengan `type == "bab"` harus punya `number` dan `title` non-null
- `margin_left_cm >= margin_right_cm` (konvensi binding dokumen akademik)
- `line_spacing > 0`

**Behavior:** collect semua violations, raise `SpecValidationError` sekali dengan list lengkap. Tidak fail pada violation pertama.

```python
class SpecValidationError(ValueError):
    violations: list[str]

def validate_spec(spec: DocxFormatSpec) -> None: ...
```

---

### 5. `docx_adapter.py`

Menerima `Document` object + `DocxFormatSpec`, menerapkan page layout dan styles. **Tidak menulis konten apapun.** Semua nilai dari `spec` — tidak ada hardcode, tidak ada fallback inline.

```python
def apply_page_layout(section, spec: DocxFormatSpec) -> None: ...
def apply_base_styles(document: Document, spec: DocxFormatSpec) -> None: ...
def add_content_section(document: Document, spec: DocxFormatSpec) -> Any: ...
    # Returns new section object setelah section break
```

Page numbering untuk preliminary dan content sections dikonfigurasi di sini via `ooxml_helper`.

---

### 6. `content_model.py`

Mendefinisikan struktur konten dokumen. Tidak tahu apa-apa tentang python-docx — murni data structure.

```python
class HeadingBlock(BaseModel):
    level: int                        # 1 = BAB heading, 2 = sub-bab
    text: str                         # sudah dipotong ≤ 20 kata dari chunk
    source_chunk_index: int | None

class ParagraphBlock(BaseModel):
    text: str
    source_chunk_index: int | None

class TableBlock(BaseModel):
    caption: str                      # dibangun dari caption_format_table di spec
    placeholder: str                  # "[PLACEHOLDER_TABEL]"
    source_chunk_index: int | None

class FigureBlock(BaseModel):
    caption: str
    placeholder: str
    source_chunk_index: int | None

ContentBlock = HeadingBlock | ParagraphBlock | TableBlock | FigureBlock

class Chapter(BaseModel):
    bab_number: int
    title: str                        # "PENDAHULUAN" (ALL CAPS)
    blocks: list[ContentBlock]

class ProposalDocument(BaseModel):
    preliminary_sections: list[str]   # ["DAFTAR ISI", "DAFTAR GAMBAR", ...]
    chapters: list[Chapter]
    has_daftar_pustaka: bool
    has_lampiran: bool
```

`ProposalDocument` dibangun oleh `builder.py` dari `DocxFormatSpec` + chunks — tidak diinput manual.

---

### 7. `renderer.py`

Merender satu `ContentBlock` menjadi elemen DOCX. Menerima `Document` + block + `DocxFormatSpec`. Memanggil `ooxml_helper` untuk operasi XML. Satu fungsi per block type.

```python
def render_heading(document: Document, block: HeadingBlock, spec: DocxFormatSpec) -> None: ...
def render_paragraph(document: Document, block: ParagraphBlock, spec: DocxFormatSpec) -> None: ...
def render_table_placeholder(document: Document, block: TableBlock, spec: DocxFormatSpec) -> None: ...
def render_figure_placeholder(document: Document, block: FigureBlock, spec: DocxFormatSpec) -> None: ...
```

Caption untuk tabel dan gambar di-render dengan `SEQ` field via `ooxml_helper.append_field`.

---

### 8. `ooxml_helper.py`

Pure functions untuk operasi OOXML yang tidak bisa dilakukan via python-docx API biasa. Tidak punya state, tidak tahu tentang spec.

```python
def append_field(paragraph, instruction: str) -> None: ...
    # Contoh instruction: " PAGE ", " SEQ Figure \\* ARABIC "
def set_page_number_type(section, fmt: str, start: int) -> None: ...
def add_section_break(document: Document, break_type: WD_SECTION_START) -> Any: ...
def add_toc_field(document: Document) -> None: ...
def clear_paragraph(paragraph) -> None: ...
```

Semua fungsi ini sudah ada sebagai private functions di `docx_renderer.py` — tinggal dipindahkan dan dijadikan public.

---

### 9. `builder.py`

Orkestrator utama. Menggantikan `generator.py`.

**Tugas:**
1. Buat `Document` object kosong
2. Panggil `docx_adapter` untuk setup page layout + styles preliminary section
3. Tambah section break, konfigurasi content section
4. Bangun `ProposalDocument` dari `spec` + `chunks` (chunk-to-placeholder logic ada di sini)
5. Iterasi tiap block di `ProposalDocument`, panggil `renderer` per block
6. Simpan file ke `output_path`

```python
def build_proposal(
    spec: DocxFormatSpec,
    chunks: list[ChunkSource],
    output_path: Path,
) -> Path: ...

# Private: chunk-to-content logic
def _build_proposal_document(
    spec: DocxFormatSpec,
    chunks: list[ChunkSource],
) -> ProposalDocument: ...

def _truncate_to_words(text: str, max_words: int = 20) -> str: ...
```

**Chunk-to-placeholder logic:**
- **Preliminary sections** (DAFTAR ISI, DAFTAR GAMBAR, dll): selalu heading level 1 + satu `ParagraphBlock` berisi `"[PLACEHOLDER_{NAMA_SECTION}]"`. Tidak perlu chunk sourcing.
- **Chapter sections** (`type == "bab"`): cari chunks relevan via scoring yang sudah ada di `chunk_loader.py`. Ambil teks terpanjang yang relevan, potong ke ≤ 20 kata untuk placeholder heading, buat `ParagraphBlock` dari snippet chunks terbaik.
- **DAFTAR PUSTAKA / LAMPIRAN**: heading level 1 + placeholder paragraph, sertakan source block dari chunks yang relevan.

---

### 10. `audit.py`

Membaca ulang `.docx` yang tersimpan dan memverifikasi terhadap `DocxFormatSpec`.

**Level 1 — Structural** (python-docx API):
- Semua heading level 1 dari `spec.proposal_sections` hadir
- Tidak ada teks `[PLACEHOLDER_` yang belum tergantikan (untuk future use)
- Jumlah chapter sesuai spec

**Level 2 — Formatting** (baca `_element` XML):
- Font name dan size pada Normal dan Heading 1 style sesuai spec
- Margin (top, bottom, left, right) sesuai spec ±0.1 cm toleransi
- Page number format dan start value sesuai spec
- Line spacing value sesuai spec

```python
@dataclass
class AuditViolation:
    field: str
    expected: str
    actual: str
    level: Literal["structural", "formatting"]

@dataclass
class AuditResult:
    passed: bool
    violations: list[AuditViolation]

def audit_docx(docx_path: Path, spec: DocxFormatSpec) -> AuditResult: ...
```

`audit.py` tidak raise exception — hanya return `AuditResult`. Dipanggil opsional via `manage.py docx --audit`.

---

## Refactor Strategy (Gradual — Pipeline Tetap Jalan)

### Tahap 1 — Spec layer (tidak menyentuh renderer)
Buat `schema.py`, `resolver.py`, `validator.py`.
`generator.py` tetap pakai `DocxStyleConfig` lama sampai tahap selesai.
Test: unit test untuk resolver dan validator.

### Tahap 2 — Ekstrak OOXML dan adapter
Buat `ooxml_helper.py` ← pindahkan private functions dari `docx_renderer.py`.
Buat `docx_adapter.py` ← pindahkan `_configure_page_layout`, `_apply_base_styles`, `_apply_page_numbering`.
`docx_renderer.py` memanggil adapter (tidak lagi memiliki logic tersebut).
Test: pipeline end-to-end tetap hijau.

### Tahap 3 — Content model dan renderer baru
Buat `content_model.py`.
Buat `renderer.py` dengan per-block functions.
`docx_renderer.py` masih ada tapi mulai memanggil renderer baru untuk block rendering.
Test: unit test per block type.

### Tahap 4 — Builder, hapus renderer lama
Buat `builder.py` menggantikan `generator.py` dan sisa `docx_renderer.py`.
Hubungkan ke spec layer: `loader → resolver → validator → builder`.
Hapus `docx_renderer.py` dan `generator.py` setelah semua tests hijau.
Update `manage.py` untuk pakai `builder.py`.

### Tahap 5 — Audit
Buat `audit.py`.
Tambah flag `--audit` ke `manage.py docx`.
Test: integration test yang generate DOCX lalu audit hasilnya.

---

## File Layout Akhir

```
model_ai/docx/
    __init__.py
    loader.py               # (renamed/wrapped metadata_loader.py)
    schema.py               # DocxFormatSpec
    resolver.py             # DocumentMetadata → DocxFormatSpec
    validator.py            # business rule validation
    docx_adapter.py         # apply layout & styles to Document
    content_model.py        # HeadingBlock, ParagraphBlock, Chapter, ProposalDocument
    renderer.py             # render ContentBlock → DOCX elements
    ooxml_helper.py         # pure OOXML functions
    builder.py              # orchestrator
    audit.py                # post-generation verification
    chunk_loader.py         # (tidak berubah)
```

`metadata_loader.py` dan `style_translator_llm.py` dihapus di Tahap 4 setelah semua consumer sudah migrasi.

---

## Constraints & Principles

- `docx_adapter.py` dan `renderer.py` tidak boleh mengimpor `DocumentMetadata`
- Tidak ada fallback inline di `docx_adapter.py` — semua nilai dari `DocxFormatSpec`
- `ooxml_helper.py` tidak boleh mengimpor models apapun
- `audit.py` tidak raise exception — hanya return `AuditResult`
- `builder.py` adalah satu-satunya tempat chunk-to-content logic
- `resolver.py` adalah satu-satunya tempat normalisasi string-ke-enum
