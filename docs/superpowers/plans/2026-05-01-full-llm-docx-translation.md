# Full LLM→python-docx Translation Pipeline — Scoped Property Map

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the narrow `DocxStyleConfig` (5 field hardcoded) dengan `ScopedPropertyMap` — sebuah model di mana **scope-nya fixed** (Normal style, Heading style, page layout, dll) namun **property dalam setiap scope bebas ditentukan LLM** berdasarkan python-docx dictionary. Ini memberikan fleksibilitas penuh tanpa kehilangan struktur.

**Architecture:** LLM menerima semua field `output.json` + catalog python-docx sebagai konteks RAG, lalu menghasilkan `ScopedPropertyMap` — dict bertingkat di mana setiap scope (misal `normal_style`) berisi property path bebas (`font.name`, `paragraph_format.line_spacing`, dll). Renderer memiliki dispatcher per scope yang tahu cara mengeksekusi property path tersebut ke python-docx API. `DocumentMetadata` tetap dipakai hanya untuk struktur konten (BAB, section titles, dll).

**Key Design Principle:** Scope = fixed (developer), Property dalam scope = dynamic (LLM dari dictionary).

**Tech Stack:** Python 3.11+, python-docx 1.2+, Pydantic v2, LangChain Groq (structured output), LangChain Google Generative AI (embeddings), pytest

---

## Scopes yang Didefinisikan

| Scope | python-docx Object | Contoh property |
|-------|-------------------|-----------------|
| `normal_style` | `document.styles["Normal"]` | `font.name`, `font.size_pt`, `paragraph_format.line_spacing` |
| `heading_1_style` | `document.styles["Heading 1"]` | `font.bold`, `font.all_caps`, `paragraph_format.space_after_pt` |
| `heading_2_style` | `document.styles["Heading 2"]` | `font.bold`, `font.size_pt` |
| `page_layout` | `section` | `margin_top_cm`, `margin_left_cm`, `orientation` |
| `page_number_prelim` | `section.footer` / `section.header` | `position`, `format`, `start` |
| `page_number_content` | `section.footer` / `section.header` | `position`, `format`, `start` |
| `caption_figure` | paragraph template | `template`, `position` |
| `caption_table` | paragraph template | `template`, `position` |

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `model_ai/docx/style_mapping_pipeline.py` | Modify | Tambah `ScopedPropertyMap`; ganti `DocxStyleConfig` + LLM chain lama; tambah `build_base_scoped_map()`, `validate_scoped_map()`, `propose_scoped_map_with_llm()`, `build_docx_scoped_map()` |
| `model_ai/docx/scope_executor.py` | Create | Dispatcher per scope — mengeksekusi `dict[str, Any]` ke python-docx API |
| `model_ai/docx/docx_renderer.py` | Modify | Terima `ScopedPropertyMap`; panggil scope_executor; hapus hardcoded metadata styling reads |
| `model_ai/docx/generator.py` | Modify | Thread `ScopedPropertyMap` melalui pipeline |
| `tests/docx/test_style_mapping_pipeline.py` | Modify | Update tests ke `ScopedPropertyMap` |
| `tests/docx/test_scope_executor.py` | Create | Unit tests untuk setiap scope dispatcher |
| `tests/docx/test_docx_generator.py` | Modify | Update fixture dan integration test |
| `tests/docx/test_style_translator_llm.py` | Delete | Superseded |

---

## Task 1: Definisikan `ScopedPropertyMap` dan tulis tesnya

**Files:**
- Modify: `experiments/pymupdf4llm/model_ai/docx/style_mapping_pipeline.py`
- Modify: `experiments/pymupdf4llm/tests/docx/test_style_mapping_pipeline.py`

- [ ] **Step 1: Tulis failing test**

Tambahkan ke `tests/docx/test_style_mapping_pipeline.py`:

```python
from model_ai.docx.style_mapping_pipeline import ScopedPropertyMap


def test_scoped_property_map_defaults_are_empty():
    spm = ScopedPropertyMap()
    assert spm.normal_style == {}
    assert spm.heading_1_style == {}
    assert spm.heading_2_style == {}
    assert spm.page_layout == {}
    assert spm.page_number_prelim == {}
    assert spm.page_number_content == {}
    assert spm.caption_figure == {}
    assert spm.caption_table == {}


def test_scoped_property_map_accepts_arbitrary_style_props():
    spm = ScopedPropertyMap(
        normal_style={
            "font.name": "Arial",
            "font.size_pt": 11,
            "paragraph_format.line_spacing": 1.5,
            "paragraph_format.first_line_indent_cm": 1.25,
        },
        heading_1_style={
            "font.bold": True,
            "font.all_caps": True,
            "paragraph_format.space_after_pt": 6.0,
        },
    )
    assert spm.normal_style["font.name"] == "Arial"
    assert spm.normal_style["paragraph_format.first_line_indent_cm"] == 1.25
    assert spm.heading_1_style["font.all_caps"] is True


def test_scoped_property_map_accepts_page_layout():
    spm = ScopedPropertyMap(
        page_layout={
            "orientation": "PORTRAIT",
            "margin_top_cm": 4.0,
            "margin_left_cm": 4.0,
            "margin_right_cm": 3.0,
            "margin_bottom_cm": 3.0,
        }
    )
    assert spm.page_layout["margin_left_cm"] == 4.0
```

- [ ] **Step 2: Jalankan test untuk verifikasi gagal**

```
cd experiments/pymupdf4llm
python -m pytest tests/docx/test_style_mapping_pipeline.py::test_scoped_property_map_defaults_are_empty -v
```

Expected: `FAILED` — `ImportError: cannot import name 'ScopedPropertyMap'`

- [ ] **Step 3: Tambahkan `ScopedPropertyMap` ke `style_mapping_pipeline.py`**

Tambahkan setelah blok konstanta `EMBEDDING_DIMENSION` (sekitar line 50), sebelum `DocxStyleConfig`:

```python
class ScopedPropertyMap(BaseModel):
    """
    Model utama output pipeline LLM→python-docx.

    Setiap scope adalah dict bebas: LLM menentukan property apa yang diset
    berdasarkan python-docx dictionary. Renderer tahu cara mengeksekusi
    property-property tersebut per scope.

    Scope = fixed (developer). Property dalam scope = dynamic (LLM).
    """
    normal_style: dict[str, Any] = Field(default_factory=dict)
    heading_1_style: dict[str, Any] = Field(default_factory=dict)
    heading_2_style: dict[str, Any] = Field(default_factory=dict)
    page_layout: dict[str, Any] = Field(default_factory=dict)
    page_number_prelim: dict[str, Any] = Field(default_factory=dict)
    page_number_content: dict[str, Any] = Field(default_factory=dict)
    caption_figure: dict[str, Any] = Field(default_factory=dict)
    caption_table: dict[str, Any] = Field(default_factory=dict)
```

Hapus `DocxStyleConfig` lama setelah ini (atau biarkan dulu sampai Task 6 cleanup).

- [ ] **Step 4: Jalankan semua test baru**

```
cd experiments/pymupdf4llm
python -m pytest tests/docx/test_style_mapping_pipeline.py::test_scoped_property_map_defaults_are_empty tests/docx/test_style_mapping_pipeline.py::test_scoped_property_map_accepts_arbitrary_style_props tests/docx/test_style_mapping_pipeline.py::test_scoped_property_map_accepts_page_layout -v
```

Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add experiments/pymupdf4llm/model_ai/docx/style_mapping_pipeline.py \
        experiments/pymupdf4llm/tests/docx/test_style_mapping_pipeline.py
git commit -m "feat: define ScopedPropertyMap — fixed scopes, dynamic properties per scope"
```

---

## Task 2: Implementasikan `build_base_scoped_map()` dari `DocumentMetadata`

Fungsi ini membaca `DocumentMetadata` dan menghasilkan `ScopedPropertyMap` sebagai baseline fallback. Ini memastikan pipeline tetap berjalan tanpa LLM.

**Files:**
- Modify: `experiments/pymupdf4llm/model_ai/docx/style_mapping_pipeline.py`
- Modify: `experiments/pymupdf4llm/tests/docx/test_style_mapping_pipeline.py`

- [ ] **Step 1: Tulis failing test**

```python
from model_ai.docx.style_mapping_pipeline import ScopedPropertyMap, build_base_scoped_map
from model_ai.extractor.models import (
    DocumentMetadata, TypographyExtracted, SpacingExtracted,
    PageLayoutExtracted, NumberingExtracted, NumberingConfig,
    FiguresTablesExtracted, DocumentStructureProposal,
)


def _make_metadata() -> DocumentMetadata:
    return DocumentMetadata(
        typography=TypographyExtracted(
            font_family="Times New Roman",
            font_size_body_pt=12,
            font_size_heading_pt=14,
            heading_bold=True,
            heading_all_caps=True,
        ),
        spacing=SpacingExtracted(
            line_spacing_body=1.5,
            paragraph_alignment="Justify",
        ),
        page_layout=PageLayoutExtracted(
            margin_top_cm=4.0,
            margin_bottom_cm=3.0,
            margin_left_cm=4.0,
            margin_right_cm=3.0,
            orientation="PORTRAIT",
        ),
        numbering=NumberingExtracted(
            preliminary=NumberingConfig(location="footer", alignment="right"),
            content=NumberingConfig(location="header", alignment="right"),
        ),
        figures_and_tables=FiguresTablesExtracted(
            caption_format_figure="Gambar {n}. {title}",
            caption_format_table="Tabel {bab}.{n} {title}",
            table_caption_position="ABOVE",
            figure_caption_position="BELOW",
        ),
        document_structure_proposal=DocumentStructureProposal(sections=[]),
    )


def test_build_base_scoped_map_normal_style():
    meta = _make_metadata()
    spm = build_base_scoped_map(meta)
    assert spm.normal_style["font.name"] == "Times New Roman"
    assert spm.normal_style["font.size_pt"] == 12.0
    assert spm.normal_style["paragraph_format.line_spacing"] == 1.5
    assert spm.normal_style["paragraph_format.alignment"] == "JUSTIFY"


def test_build_base_scoped_map_heading_style():
    meta = _make_metadata()
    spm = build_base_scoped_map(meta)
    assert spm.heading_1_style["font.size_pt"] == 14.0
    assert spm.heading_1_style["font.bold"] is True
    assert spm.heading_1_style["font.all_caps"] is True


def test_build_base_scoped_map_page_layout():
    meta = _make_metadata()
    spm = build_base_scoped_map(meta)
    assert spm.page_layout["margin_top_cm"] == 4.0
    assert spm.page_layout["margin_left_cm"] == 4.0
    assert spm.page_layout["orientation"] == "PORTRAIT"


def test_build_base_scoped_map_page_numbering():
    meta = _make_metadata()
    spm = build_base_scoped_map(meta)
    assert spm.page_number_prelim["position"] == "footer_right"
    assert spm.page_number_prelim["format"] == "lowerRoman"
    assert spm.page_number_content["position"] == "header_right"
    assert spm.page_number_content["format"] == "decimal"


def test_build_base_scoped_map_captions():
    meta = _make_metadata()
    spm = build_base_scoped_map(meta)
    assert spm.caption_figure["template"] == "Gambar {n}. {title}"
    assert spm.caption_figure["position"] == "BELOW"
    assert spm.caption_table["position"] == "ABOVE"
```

- [ ] **Step 2: Jalankan test untuk verifikasi gagal**

```
cd experiments/pymupdf4llm
python -m pytest tests/docx/test_style_mapping_pipeline.py::test_build_base_scoped_map_normal_style -v
```

Expected: `FAILED` — `ImportError: cannot import name 'build_base_scoped_map'`

- [ ] **Step 3: Implementasikan `build_base_scoped_map()` di `style_mapping_pipeline.py`**

```python
def build_base_scoped_map(metadata: DocumentMetadata) -> ScopedPropertyMap:
    """
    Membangun ScopedPropertyMap baseline dari DocumentMetadata.
    Dipakai sebagai fallback jika LLM gagal, dan sebagai starting point
    sebelum LLM overrides diterapkan.
    """
    typ = metadata.typography
    spacing = metadata.spacing
    layout = metadata.page_layout
    num = metadata.numbering
    fig = metadata.figures_and_tables

    body_font = typ.font_family or "Times New Roman"
    body_size = float(typ.font_size_body_pt or 12)
    heading_size = float(typ.font_size_heading_pt or body_size)

    normal_style: dict[str, Any] = {
        "font.name": body_font,
        "font.size_pt": body_size,
        "paragraph_format.line_spacing": float(spacing.line_spacing_body or 1.5),
        "paragraph_format.alignment": _coerce_alignment(spacing.paragraph_alignment),
    }

    heading_base: dict[str, Any] = {
        "font.name": body_font,
        "font.size_pt": heading_size,
        "font.bold": bool(typ.heading_bold),
        "font.all_caps": bool(typ.heading_all_caps),
        "paragraph_format.alignment": "CENTER",
    }

    page_layout: dict[str, Any] = {
        "orientation": _coerce_orientation(layout.orientation),
        "margin_top_cm": float(layout.margin_top_cm or 3.0),
        "margin_bottom_cm": float(layout.margin_bottom_cm or 3.0),
        "margin_left_cm": float(layout.margin_left_cm or 4.0),
        "margin_right_cm": float(layout.margin_right_cm or 3.0),
    }

    prelim_pos = _build_position(
        num.preliminary.location if num.preliminary else None,
        num.preliminary.alignment if num.preliminary else None,
        default="footer_right",
    )
    content_pos = _build_position(
        num.content.location if num.content else None,
        num.content.alignment if num.content else None,
        default="header_right",
    )

    return ScopedPropertyMap(
        normal_style=normal_style,
        heading_1_style=dict(heading_base),
        heading_2_style=dict(heading_base),
        page_layout=page_layout,
        page_number_prelim={
            "position": prelim_pos,
            "format": "lowerRoman",
            "start": 1,
        },
        page_number_content={
            "position": content_pos,
            "format": "decimal",
            "start": 1,
        },
        caption_figure={
            "template": fig.caption_format_figure or "Gambar {n}. {title} ({source})",
            "position": _coerce_caption_position(fig.figure_caption_position, "BELOW"),
        },
        caption_table={
            "template": fig.caption_format_table or "Tabel {bab}.{n} {title}",
            "position": _coerce_caption_position(fig.table_caption_position, "ABOVE"),
        },
    )


def _coerce_orientation(raw: str | None) -> str:
    val = (raw or "PORTRAIT").strip().upper()
    return "LANDSCAPE" if val == "LANDSCAPE" else "PORTRAIT"


def _coerce_caption_position(raw: str | None, default: str) -> str:
    val = (raw or default).strip().upper()
    return "ABOVE" if val == "ABOVE" else "BELOW"
```

- [ ] **Step 4: Jalankan semua test baru**

```
cd experiments/pymupdf4llm
python -m pytest tests/docx/test_style_mapping_pipeline.py -k "base_scoped_map" -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add experiments/pymupdf4llm/model_ai/docx/style_mapping_pipeline.py \
        experiments/pymupdf4llm/tests/docx/test_style_mapping_pipeline.py
git commit -m "feat: add build_base_scoped_map() — DocumentMetadata → ScopedPropertyMap baseline"
```

---

## Task 3: Implementasikan `scope_executor.py` — dispatcher per scope

File baru yang tahu cara mengeksekusi property path bebas ke python-docx API per scope.

**Files:**
- Create: `experiments/pymupdf4llm/model_ai/docx/scope_executor.py`
- Create: `experiments/pymupdf4llm/tests/docx/test_scope_executor.py`

- [ ] **Step 1: Tulis failing tests**

Buat `tests/docx/test_scope_executor.py`:

```python
"""
Test unit untuk scope_executor — dispatcher yang mengeksekusi ScopedPropertyMap ke python-docx.
"""
import pytest
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

from model_ai.docx.scope_executor import apply_word_style, apply_page_layout


def test_apply_word_style_font_name():
    doc = Document()
    style = doc.styles["Normal"]
    apply_word_style(style, {"font.name": "Arial"})
    assert style.font.name == "Arial"


def test_apply_word_style_font_size():
    doc = Document()
    style = doc.styles["Normal"]
    apply_word_style(style, {"font.size_pt": 11.0})
    assert style.font.size == Pt(11.0)


def test_apply_word_style_font_bold():
    doc = Document()
    style = doc.styles["Normal"]
    apply_word_style(style, {"font.bold": True})
    assert style.font.bold is True


def test_apply_word_style_font_all_caps():
    doc = Document()
    style = doc.styles["Normal"]
    apply_word_style(style, {"font.all_caps": True})
    assert style.font.all_caps is True


def test_apply_word_style_line_spacing():
    doc = Document()
    style = doc.styles["Normal"]
    apply_word_style(style, {"paragraph_format.line_spacing": 1.5})
    assert style.paragraph_format.line_spacing == 1.5


def test_apply_word_style_alignment_justify():
    doc = Document()
    style = doc.styles["Normal"]
    apply_word_style(style, {"paragraph_format.alignment": "JUSTIFY"})
    assert style.paragraph_format.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY


def test_apply_word_style_space_after():
    doc = Document()
    style = doc.styles["Heading 1"]
    apply_word_style(style, {"paragraph_format.space_after_pt": 6.0})
    assert style.paragraph_format.space_after == Pt(6.0)


def test_apply_word_style_first_line_indent():
    doc = Document()
    style = doc.styles["Normal"]
    apply_word_style(style, {"paragraph_format.first_line_indent_cm": 1.25})
    assert abs(style.paragraph_format.first_line_indent - Cm(1.25)) < 100


def test_apply_word_style_unknown_prop_is_ignored():
    doc = Document()
    style = doc.styles["Normal"]
    # Should not raise
    apply_word_style(style, {"font.unknown_future_prop": "value"})


def test_apply_page_layout_margins():
    doc = Document()
    section = doc.sections[0]
    apply_page_layout(section, {
        "margin_top_cm": 4.0,
        "margin_bottom_cm": 3.0,
        "margin_left_cm": 4.0,
        "margin_right_cm": 3.0,
    })
    assert abs(section.top_margin - Cm(4.0)) < 100
    assert abs(section.left_margin - Cm(4.0)) < 100


def test_apply_page_layout_portrait():
    doc = Document()
    section = doc.sections[0]
    apply_page_layout(section, {"orientation": "PORTRAIT"})
    from docx.enum.section import WD_ORIENT
    assert section.orientation == WD_ORIENT.PORTRAIT
```

- [ ] **Step 2: Jalankan test untuk verifikasi gagal**

```
cd experiments/pymupdf4llm
python -m pytest tests/docx/test_scope_executor.py -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'model_ai.docx.scope_executor'`

- [ ] **Step 3: Buat `model_ai/docx/scope_executor.py`**

```python
"""
Fungsi: Dispatcher yang mengeksekusi ScopedPropertyMap ke python-docx API.

Digunakan oleh: model_ai/docx/docx_renderer.py

Tujuan: Memisahkan logika "cara mengeksekusi property" dari renderer,
sehingga property baru bisa ditambahkan di sini tanpa menyentuh renderer.

Setiap fungsi `apply_*` menerima object python-docx + dict property,
lalu iterasi dan eksekusi setiap path yang dikenali. Path yang tidak
dikenali di-skip (tidak raise) agar pipeline tetap forward-compatible.
"""
from typing import Any

from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt


_ALIGNMENT_MAP = {
    "LEFT": WD_ALIGN_PARAGRAPH.LEFT,
    "CENTER": WD_ALIGN_PARAGRAPH.CENTER,
    "RIGHT": WD_ALIGN_PARAGRAPH.RIGHT,
    "JUSTIFY": WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def _apply_font_prop(font, prop: str, value: Any) -> None:
    """Eksekusi satu property pada font object python-docx."""
    if prop == "name":
        font.name = str(value)
    elif prop == "size_pt":
        font.size = Pt(float(value))
    elif prop == "bold":
        font.bold = bool(value)
    elif prop == "italic":
        font.italic = bool(value)
    elif prop == "all_caps":
        font.all_caps = bool(value)
    elif prop == "underline":
        font.underline = bool(value)
    elif prop == "strike":
        font.strike = bool(value)
    # prop yang tidak dikenali di-skip — forward-compatible


def _apply_paragraph_format_prop(pf, prop: str, value: Any) -> None:
    """Eksekusi satu property pada paragraph_format object python-docx."""
    if prop == "line_spacing":
        pf.line_spacing = float(value)
    elif prop == "alignment":
        pf.alignment = _ALIGNMENT_MAP.get(str(value).upper(), WD_ALIGN_PARAGRAPH.JUSTIFY)
    elif prop == "space_before_pt":
        pf.space_before = Pt(float(value))
    elif prop == "space_after_pt":
        pf.space_after = Pt(float(value))
    elif prop == "first_line_indent_cm":
        pf.first_line_indent = Cm(float(value))
    elif prop == "left_indent_cm":
        pf.left_indent = Cm(float(value))
    elif prop == "right_indent_cm":
        pf.right_indent = Cm(float(value))
    # prop yang tidak dikenali di-skip


def apply_word_style(style, props: dict[str, Any]) -> None:
    """
    Eksekusi semua property dalam dict ke sebuah Word style object.

    Format key: "<sub_object>.<property>"
    Contoh: "font.name", "font.size_pt", "paragraph_format.line_spacing"

    Property yang tidak dikenali di-skip (tidak raise).
    """
    for path, value in props.items():
        parts = path.split(".", 1)
        if len(parts) != 2:
            continue
        sub_obj, prop = parts[0], parts[1]
        if sub_obj == "font":
            _apply_font_prop(style.font, prop, value)
        elif sub_obj == "paragraph_format":
            _apply_paragraph_format_prop(style.paragraph_format, prop, value)
        # sub_obj lain di-skip — forward-compatible


def apply_page_layout(section, props: dict[str, Any]) -> None:
    """
    Eksekusi property page layout ke section object python-docx.

    Keys yang dikenali: orientation, margin_top_cm, margin_bottom_cm,
    margin_left_cm, margin_right_cm.
    """
    orientation = props.get("orientation", "").upper()
    if orientation == "LANDSCAPE":
        from docx.shared import Mm
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width = Mm(297)
        section.page_height = Mm(210)
    elif orientation == "PORTRAIT":
        from docx.shared import Mm
        section.orientation = WD_ORIENT.PORTRAIT
        section.page_width = Mm(210)
        section.page_height = Mm(297)

    if "margin_top_cm" in props:
        section.top_margin = Cm(float(props["margin_top_cm"]))
    if "margin_bottom_cm" in props:
        section.bottom_margin = Cm(float(props["margin_bottom_cm"]))
    if "margin_left_cm" in props:
        section.left_margin = Cm(float(props["margin_left_cm"]))
    if "margin_right_cm" in props:
        section.right_margin = Cm(float(props["margin_right_cm"]))
```

- [ ] **Step 4: Jalankan semua tests**

```
cd experiments/pymupdf4llm
python -m pytest tests/docx/test_scope_executor.py -v
```

Expected: semua PASSED

- [ ] **Step 5: Commit**

```bash
git add experiments/pymupdf4llm/model_ai/docx/scope_executor.py \
        experiments/pymupdf4llm/tests/docx/test_scope_executor.py
git commit -m "feat: add scope_executor.py — apply_word_style and apply_page_layout dispatchers"
```

---

## Task 4: Tambahkan `validate_scoped_map()`, `propose_scoped_map_with_llm()`, dan `build_docx_scoped_map()`

Dua lapis penjagaan agar LLM tidak menggunakan property di luar catalog:
- **Lapis 1 (prompt):** instruksi eksplisit yang melarang improvisasi di luar catalog
- **Lapis 2 (post-validation):** `validate_scoped_map()` membuang property yang tidak ada di catalog setelah LLM output

**Files:**
- Modify: `experiments/pymupdf4llm/model_ai/docx/style_mapping_pipeline.py`
- Modify: `experiments/pymupdf4llm/tests/docx/test_style_mapping_pipeline.py`

- [ ] **Step 1: Tulis failing tests**

```python
from unittest.mock import patch, MagicMock
from model_ai.docx.style_mapping_pipeline import (
    ScopedPropertyMap,
    DocxCatalogEntry,
    validate_scoped_map,
    propose_scoped_map_with_llm,
    build_docx_scoped_map,
)


# --- validate_scoped_map tests ---

def _make_entries() -> list[DocxCatalogEntry]:
    return [
        DocxCatalogEntry(
            id="property::font.name", section="font", kind="property",
            path="font.name", description="Font name", chunk_text="",
        ),
        DocxCatalogEntry(
            id="property::font.bold", section="font", kind="property",
            path="font.bold", description="Bold", chunk_text="",
        ),
        DocxCatalogEntry(
            id="property::paragraph_format.line_spacing", section="paragraph_format",
            kind="property", path="paragraph_format.line_spacing",
            description="Line spacing", chunk_text="",
        ),
    ]


def test_validate_scoped_map_removes_unknown_style_properties():
    entries = _make_entries()
    spm = ScopedPropertyMap(
        normal_style={
            "font.name": "Arial",           # ada di catalog — keep
            "font.bold": True,              # ada di catalog — keep
            "font.invented_prop": "bad",    # tidak ada — reject
        },
    )
    cleaned, rejected = validate_scoped_map(spm, entries)
    assert "font.name" in cleaned.normal_style
    assert "font.bold" in cleaned.normal_style
    assert "font.invented_prop" not in cleaned.normal_style
    assert "normal_style.font.invented_prop" in rejected


def test_validate_scoped_map_semantic_scopes_not_validated():
    """page_layout, page_number_*, caption_* tidak divalidasi terhadap catalog."""
    entries = _make_entries()
    spm = ScopedPropertyMap(
        page_layout={"margin_top_cm": 4.0, "any_semantic_key": "value"},
        page_number_prelim={"position": "footer_right", "format": "lowerRoman"},
        caption_figure={"template": "Gambar {n}", "position": "BELOW"},
    )
    cleaned, rejected = validate_scoped_map(spm, entries)
    assert cleaned.page_layout["margin_top_cm"] == 4.0
    assert cleaned.page_layout["any_semantic_key"] == "value"
    assert cleaned.page_number_prelim["position"] == "footer_right"
    assert cleaned.caption_figure["template"] == "Gambar {n}"
    assert rejected == []


def test_validate_scoped_map_empty_returns_empty():
    cleaned, rejected = validate_scoped_map(ScopedPropertyMap(), [])
    assert rejected == []
    assert cleaned.normal_style == {}


def test_validate_scoped_map_all_valid_passes_through():
    entries = _make_entries()
    spm = ScopedPropertyMap(
        normal_style={"font.name": "Times New Roman", "font.bold": False},
        heading_1_style={"font.bold": True},
    )
    cleaned, rejected = validate_scoped_map(spm, entries)
    assert rejected == []
    assert cleaned.normal_style["font.name"] == "Times New Roman"
    assert cleaned.heading_1_style["font.bold"] is True


# --- propose_scoped_map_with_llm tests ---

def test_propose_scoped_map_with_llm_returns_scoped_map():
    flattened = {
        "typography.font_family": "Times New Roman",
        "typography.font_size_body_pt": 12,
        "spacing.paragraph_alignment": "Justify",
    }
    retrieved_chunks = [
        {"chunk_id": "section::font", "text": "section=font\npath=font.name\ndescription=Font name"},
    ]
    expected = ScopedPropertyMap(
        normal_style={"font.name": "Times New Roman", "font.size_pt": 12.0},
        heading_1_style={"font.bold": True},
    )

    with patch("model_ai.docx.style_mapping_pipeline.ChatGroq") as MockGroq:
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = expected
        MockGroq.return_value.with_structured_output.return_value = mock_chain

        result = propose_scoped_map_with_llm(flattened, retrieved_chunks)

    assert isinstance(result, ScopedPropertyMap)
    assert result.normal_style["font.name"] == "Times New Roman"
    assert result.heading_1_style["font.bold"] is True


# --- build_docx_scoped_map tests ---

def test_build_docx_scoped_map_merges_base_and_llm(tmp_path):
    import json
    extracted = {
        "typography": {"font_family": "Arial", "font_size_body_pt": 11},
        "spacing": {"paragraph_alignment": "Justify", "line_spacing_body": 1.5},
        "page_layout": {"margin_top_cm": 3.0, "margin_bottom_cm": 3.0,
                        "margin_left_cm": 4.0, "margin_right_cm": 3.0},
        "numbering": {},
        "figures_and_tables": {},
    }
    extracted_path = tmp_path / "output.json"
    extracted_path.write_text(json.dumps(extracted), encoding="utf-8")

    meta = _make_metadata()  # helper dari Task 2
    llm_map = ScopedPropertyMap(
        normal_style={"font.name": "Arial", "font.size_pt": 11.0},
        heading_1_style={"font.bold": True, "font.italic": True},
    )

    with patch("model_ai.docx.style_mapping_pipeline.propose_scoped_map_with_llm",
               return_value=llm_map), \
         patch("model_ai.docx.style_mapping_pipeline.validate_scoped_map",
               side_effect=lambda spm, entries: (spm, [])), \
         patch("model_ai.docx.style_mapping_pipeline.build_chunk_index", return_value=[]), \
         patch("model_ai.docx.style_mapping_pipeline._build_embedder"):

        result = build_docx_scoped_map(
            metadata=meta,
            extracted_path=extracted_path,
            use_llm_mapper=True,
            with_embeddings=False,
        )

    assert result.normal_style["font.name"] == "Arial"
    assert result.heading_1_style["font.italic"] is True
    assert "margin_top_cm" in result.page_layout
```

- [ ] **Step 2: Jalankan test untuk verifikasi gagal**

```
cd experiments/pymupdf4llm
python -m pytest tests/docx/test_style_mapping_pipeline.py::test_validate_scoped_map_removes_unknown_style_properties -v
```

Expected: `FAILED` — `ImportError: cannot import name 'validate_scoped_map'`

- [ ] **Step 3: Implementasikan `validate_scoped_map()` di `style_mapping_pipeline.py`**

```python
# Scope semantik: key-nya bukan python-docx path — tidak perlu divalidasi terhadap catalog
_SEMANTIC_SCOPES: frozenset[str] = frozenset({
    "page_layout",
    "page_number_prelim",
    "page_number_content",
    "caption_figure",
    "caption_table",
})
# Scope style: key-nya adalah python-docx path — wajib divalidasi terhadap catalog
_STYLE_SCOPES: frozenset[str] = frozenset({
    "normal_style",
    "heading_1_style",
    "heading_2_style",
})


def validate_scoped_map(
    spm: ScopedPropertyMap,
    entries: list[DocxCatalogEntry],
) -> tuple[ScopedPropertyMap, list[str]]:
    """
    Lapis 2 penjagaan: buang property yang tidak ada di catalog setelah LLM output.

    - Scope style (normal_style, heading_*): setiap key divalidasi terhadap catalog path.
      Property yang tidak ditemukan di catalog di-drop dan dilaporkan.
    - Scope semantik (page_layout, page_number_*, caption_*): tidak divalidasi —
      key-nya adalah field semantik (margin_top_cm, position, dll), bukan python-docx path.

    Returns: (cleaned_map, list_of_rejected_keys)
    """
    known_paths: set[str] = {entry.path for entry in entries}
    cleaned: dict[str, dict[str, Any]] = {}
    rejected: list[str] = []

    for scope_name, props in spm.model_dump().items():
        if scope_name in _SEMANTIC_SCOPES:
            cleaned[scope_name] = props
            continue

        if scope_name in _STYLE_SCOPES:
            valid_props: dict[str, Any] = {}
            for key, value in props.items():
                if key in known_paths:
                    valid_props[key] = value
                else:
                    rejected.append(f"{scope_name}.{key}")
            cleaned[scope_name] = valid_props
            continue

        # Scope tidak dikenali — pass through aman
        cleaned[scope_name] = props

    return ScopedPropertyMap.model_validate(cleaned), rejected
```

- [ ] **Step 4: Jalankan tests `validate_scoped_map` untuk verifikasi pass**

```
cd experiments/pymupdf4llm
python -m pytest tests/docx/test_style_mapping_pipeline.py -k "validate_scoped_map" -v
```

Expected: 4 PASSED

- [ ] **Step 5: Implementasikan `_build_scoped_map_prompt()` dengan constraint ketat**

Dua perbedaan kunci vs versi lama: (1) bagian `ATURAN KETAT` yang eksplisit, (2) catalog ditampilkan sebelum scope description agar LLM membaca referensi dulu.

```python
def _build_scoped_map_prompt(
    flattened_payload: dict[str, Any],
    retrieved_chunks: list[dict[str, Any]],
) -> str:
    source_lines = [
        f"- {key}: {json.dumps(value, ensure_ascii=False)}"
        for key, value in flattened_payload.items()
    ]
    catalog_lines = [
        "\n".join([f"[{chunk.get('chunk_id')}]", str(chunk.get("text", ""))])
        for chunk in retrieved_chunks
    ]
    return (
        "Kamu bertugas menerjemahkan hasil ekstraksi format dokumen ke konfigurasi python-docx.\n\n"
        "ATURAN KETAT — WAJIB DIPATUHI TANPA PENGECUALIAN:\n"
        "1. Kamu HANYA boleh menggunakan property path yang BENAR-BENAR TERCANTUM "
        "   di bagian '## Referensi Catalog python-docx' di bawah.\n"
        "2. Jika tidak ada catalog entry yang cocok untuk suatu field, "
        "   JANGAN isi property tersebut — biarkan scope kosong atau skip key tersebut.\n"
        "3. DILARANG KERAS menggunakan pengetahuan python-docx dari training data "
        "   atau sumber lain di luar catalog yang disediakan.\n"
        "4. Nilai enum (mis. alignment) harus PERSIS SAMA dengan members di catalog "
        "   (contoh: 'JUSTIFY' bukan 'Justify' atau 'justified').\n"
        "5. Tipe nilai harus sesuai type yang tercantum di catalog "
        "   (bool → true/false, float → angka desimal, string → teks).\n\n"
        "FORMAT KEY dalam scope style (normal_style, heading_*): "
        "'<sub_object>.<property>' sesuai catalog path "
        "(contoh: 'font.name', 'paragraph_format.line_spacing').\n\n"
        "SCOPE yang tersedia:\n"
        "- normal_style: properti untuk Word style 'Normal' (body text). "
        "  Gunakan path dari catalog, contoh: font.name, font.size_pt, font.bold, "
        "  font.italic, font.all_caps, paragraph_format.line_spacing, "
        "  paragraph_format.alignment, paragraph_format.space_before, "
        "  paragraph_format.space_after, paragraph_format.first_line_indent.\n"
        "- heading_1_style: sama, untuk Word style 'Heading 1'.\n"
        "- heading_2_style: sama, untuk Word style 'Heading 2'.\n"
        "- page_layout: orientation (PORTRAIT/LANDSCAPE), margin_top_cm, margin_bottom_cm, "
        "  margin_left_cm, margin_right_cm. (Key semantik, bukan catalog path.)\n"
        "- page_number_prelim: position (header_left/center/right atau footer_left/center/right), "
        "  format (decimal/lowerRoman/upperRoman), start (int).\n"
        "- page_number_content: idem.\n"
        "- caption_figure: template (string dengan {n}, {title}, {source}), position (ABOVE/BELOW).\n"
        "- caption_table: idem.\n\n"
        "PENTING: Hanya isi scope yang memang ada datanya di hasil ekstraksi. "
        "Jika tidak ada data relevan, biarkan scope kosong ({}).\n\n"
        "## Referensi Catalog python-docx\n"
        + "\n\n---\n\n".join(catalog_lines)
        + "\n\n## Hasil Ekstraksi Dokumen\n"
        + "\n".join(source_lines)
    )
```

- [ ] **Step 6: Implementasikan `propose_scoped_map_with_llm()`**

```python
def propose_scoped_map_with_llm(
    flattened_payload: dict[str, Any],
    retrieved_chunks: list[dict[str, Any]],
) -> ScopedPropertyMap:
    prompt = _build_scoped_map_prompt(flattened_payload, retrieved_chunks)
    config = get_config()
    config.disable_blackhole_proxies()
    llm = ChatGroq(
        model=config.model_name,
        temperature=config.temperature,
        api_key=config.groq_api_key.get_secret_value(),
    )
    chain = llm.with_structured_output(ScopedPropertyMap)
    return chain.invoke(prompt)
```

- [ ] **Step 7: Implementasikan `build_docx_scoped_map()` dengan validasi setelah LLM**

```python
def build_docx_scoped_map(
    metadata: DocumentMetadata,
    extracted_path: Path,
    dictionary_path: Path = DEFAULT_DICTIONARY_PATH,
    use_llm_mapper: bool = True,
    with_embeddings: bool = True,
) -> ScopedPropertyMap:
    """
    Orchestrator utama: bangun ScopedPropertyMap dari metadata + LLM.

    Alur:
    1. Build base map dari DocumentMetadata (fallback baseline)
    2. Run RAG: catalog chunks + embedding index + retrieval
    3. LLM mengisi ScopedPropertyMap berdasarkan output.json + catalog context
    4. validate_scoped_map(): buang property di luar catalog (lapis 2 penjagaan)
    5. Merge: LLM overrides base per scope (dict.update per scope)
    6. Return merged ScopedPropertyMap
    """
    base = build_base_scoped_map(metadata)

    try:
        entries = build_docx_property_catalog(dictionary_path)
        chunks = build_catalog_chunks(entries)
        save_catalog_artifacts(
            entries, chunks,
            catalog_path=DEFAULT_CATALOG_PATH,
            chunks_path=DEFAULT_CHUNKS_PATH,
        )
        chunk_index = build_chunk_index(
            chunks,
            index_path=DEFAULT_INDEX_PATH,
            with_embeddings=with_embeddings,
        )
        extracted_payload = load_extracted_payload(extracted_path)
        flattened = _flatten_json(extracted_payload)
        query_text = "\n".join(f"{k}: {v}" for k, v in flattened.items())
        retrieved = retrieve_relevant_chunks(query_text, chunk_index=chunk_index, top_k=15)

        if use_llm_mapper:
            llm_map = propose_scoped_map_with_llm(flattened, retrieved)
            # Lapis 2: buang property yang tidak ada di catalog
            llm_map, rejected = validate_scoped_map(llm_map, entries)
            if rejected:
                print(
                    f"[docx-scoped-map] {len(rejected)} property di luar catalog di-drop: "
                    + ", ".join(rejected)
                )
        else:
            llm_map = _rule_based_scoped_map(flattened, base)

    except Exception as exc:
        if not use_llm_mapper:
            raise
        print(f"[docx-scoped-map] Warning: LLM mapping gagal, pakai base map. Detail: {exc}")
        return base

    # Merge per scope: LLM props di-update ke atas base props
    merged_data = base.model_dump()
    for scope_name, llm_props in llm_map.model_dump().items():
        if llm_props:
            merged_data[scope_name].update(llm_props)

    return ScopedPropertyMap.model_validate(merged_data)


def _rule_based_scoped_map(
    flattened: dict[str, Any],
    base: ScopedPropertyMap,
) -> ScopedPropertyMap:
    """Fallback deterministik: update base dengan field yang langsung terbaca dari flattened."""
    overrides: dict[str, dict[str, Any]] = {
        "normal_style": {},
        "heading_1_style": {},
        "heading_2_style": {},
        "page_layout": {},
    }
    for key, value in flattened.items():
        k = key.lower()
        if "font_family" in k and isinstance(value, str):
            overrides["normal_style"]["font.name"] = value.strip()
            overrides["heading_1_style"]["font.name"] = value.strip()
            overrides["heading_2_style"]["font.name"] = value.strip()
        elif "font_size_body" in k and isinstance(value, (int, float)):
            overrides["normal_style"]["font.size_pt"] = float(value)
        elif "font_size_heading" in k and isinstance(value, (int, float)):
            overrides["heading_1_style"]["font.size_pt"] = float(value)
            overrides["heading_2_style"]["font.size_pt"] = float(value)
        elif "heading_bold" in k and isinstance(value, bool):
            overrides["heading_1_style"]["font.bold"] = value
            overrides["heading_2_style"]["font.bold"] = value
        elif "heading_all_caps" in k and isinstance(value, bool):
            overrides["heading_1_style"]["font.all_caps"] = value
        elif "paragraph_alignment" in k and isinstance(value, str):
            overrides["normal_style"]["paragraph_format.alignment"] = _coerce_alignment(value)
        elif "line_spacing" in k and isinstance(value, (int, float)):
            overrides["normal_style"]["paragraph_format.line_spacing"] = float(value)
        elif "margin_top" in k and isinstance(value, (int, float)):
            overrides["page_layout"]["margin_top_cm"] = float(value)
        elif "margin_bottom" in k and isinstance(value, (int, float)):
            overrides["page_layout"]["margin_bottom_cm"] = float(value)
        elif "margin_left" in k and isinstance(value, (int, float)):
            overrides["page_layout"]["margin_left_cm"] = float(value)
        elif "margin_right" in k and isinstance(value, (int, float)):
            overrides["page_layout"]["margin_right_cm"] = float(value)

    merged = base.model_dump()
    for scope, props in overrides.items():
        merged[scope].update(props)
    return ScopedPropertyMap.model_validate(merged)
```

- [ ] **Step 8: Jalankan semua tests Task 4**

```
cd experiments/pymupdf4llm
python -m pytest tests/docx/test_style_mapping_pipeline.py -k "scoped_map or validate_scoped" -v
```

Expected: semua PASSED

- [ ] **Step 9: Commit**

```bash
git add experiments/pymupdf4llm/model_ai/docx/style_mapping_pipeline.py \
        experiments/pymupdf4llm/tests/docx/test_style_mapping_pipeline.py
git commit -m "feat: add validate_scoped_map() + strict prompt + build_docx_scoped_map() orchestrator"
```

---

## Task 5: Update `docx_renderer.py` untuk konsumsi `ScopedPropertyMap`

Renderer sekarang memanggil scope_executor per scope. Semua hardcoded metadata styling reads dihapus.

**Files:**
- Modify: `experiments/pymupdf4llm/model_ai/docx/docx_renderer.py`
- Modify: `experiments/pymupdf4llm/tests/docx/test_docx_generator.py`

- [ ] **Step 1: Tulis failing tests**

Tambahkan ke `tests/docx/test_docx_generator.py`:

```python
from model_ai.docx.style_mapping_pipeline import ScopedPropertyMap
from model_ai.docx.docx_renderer import render_proposal_docx
from model_ai.extractor.models import (
    DocumentMetadata, TypographyExtracted, SpacingExtracted,
    PageLayoutExtracted, NumberingExtracted, FiguresTablesExtracted,
    DocumentStructureProposal,
)
from docx import Document
from docx.shared import Cm


def _minimal_metadata() -> DocumentMetadata:
    return DocumentMetadata(
        typography=TypographyExtracted(),
        spacing=SpacingExtracted(),
        page_layout=PageLayoutExtracted(),
        numbering=NumberingExtracted(),
        figures_and_tables=FiguresTablesExtracted(),
        document_structure_proposal=DocumentStructureProposal(sections=[]),
    )


def test_renderer_uses_scoped_map_font(tmp_path):
    spm = ScopedPropertyMap(
        normal_style={"font.name": "Courier New", "font.size_pt": 10.0},
        page_number_content={"position": "header_right", "format": "decimal", "start": 1},
    )
    output = tmp_path / "out.docx"
    render_proposal_docx(_minimal_metadata(), [], spm, output)
    doc = Document(str(output))
    assert doc.styles["Normal"].font.name == "Courier New"


def test_renderer_uses_scoped_map_margins(tmp_path):
    spm = ScopedPropertyMap(
        page_layout={"margin_top_cm": 5.0, "margin_left_cm": 6.0,
                     "margin_bottom_cm": 3.0, "margin_right_cm": 3.0},
        page_number_content={"position": "header_right", "format": "decimal", "start": 1},
    )
    output = tmp_path / "out.docx"
    render_proposal_docx(_minimal_metadata(), [], spm, output)
    doc = Document(str(output))
    assert abs(doc.sections[0].top_margin - Cm(5.0)) < 100
    assert abs(doc.sections[0].left_margin - Cm(6.0)) < 100


def test_renderer_uses_scoped_map_heading_style(tmp_path):
    spm = ScopedPropertyMap(
        heading_1_style={"font.bold": True, "font.all_caps": True, "font.size_pt": 14.0},
        page_number_content={"position": "header_right", "format": "decimal", "start": 1},
    )
    output = tmp_path / "out.docx"
    render_proposal_docx(_minimal_metadata(), [], spm, output)
    doc = Document(str(output))
    h1 = doc.styles["Heading 1"]
    assert h1.font.bold is True
    assert h1.font.all_caps is True
```

- [ ] **Step 2: Jalankan test untuk verifikasi gagal**

```
cd experiments/pymupdf4llm
python -m pytest tests/docx/test_docx_generator.py::test_renderer_uses_scoped_map_font -v
```

Expected: `FAILED` — renderer masih pakai `DocxStyleConfig`

- [ ] **Step 3: Update `render_proposal_docx()` di `docx_renderer.py`**

Ganti import:
```python
from model_ai.docx.style_mapping_pipeline import ScopedPropertyMap
from model_ai.docx.scope_executor import apply_page_layout, apply_word_style
```

Hapus import `DocxStyleConfig`.

Update `render_proposal_docx()`:

```python
def render_proposal_docx(
    metadata: DocumentMetadata,
    chunks: list[ChunkSource],
    style_config: ScopedPropertyMap,
    output_path: Path,
) -> Path:
    document = Document()
    first_section = document.sections[0]

    apply_page_layout(first_section, style_config.page_layout)
    apply_word_style(document.styles["Normal"], style_config.normal_style)
    apply_word_style(document.styles["Heading 1"], style_config.heading_1_style)
    apply_word_style(document.styles["Heading 2"], style_config.heading_2_style)

    has_preliminary = _has_preliminary_pages(metadata)
    if has_preliminary:
        _render_preliminary_pages(document, metadata)
        _apply_page_numbering(first_section, style_config.page_number_prelim)

        content_section = document.add_section(WD_SECTION_START.NEW_PAGE)
        apply_page_layout(content_section, style_config.page_layout)
        _apply_page_numbering(content_section, style_config.page_number_content)
    else:
        _apply_page_numbering(first_section, style_config.page_number_content)

    _render_proposal_body(document, metadata, chunks, style_config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
    return output_path
```

- [ ] **Step 4: Update `_apply_page_numbering()` untuk terima dict**

```python
def _apply_page_numbering(section, page_num_props: dict[str, Any]) -> None:
    if not page_num_props:
        return
    position = page_num_props.get("position", "footer_right")
    fmt = page_num_props.get("format", "decimal")
    start = int(page_num_props.get("start", 1))

    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False

    target = section.header if position.startswith("header_") else section.footer
    alignment = _position_alignment(position)
    paragraph = target.paragraphs[0] if target.paragraphs else target.add_paragraph()
    paragraph.alignment = alignment
    _clear_paragraph(paragraph)
    _append_field(paragraph, " PAGE ")
    _set_page_number_type(section, fmt=fmt, start=start)
```

- [ ] **Step 5: Update `_render_caption_examples()` untuk terima `ScopedPropertyMap`**

```python
def _render_caption_examples(document: Document, style_config: ScopedPropertyMap) -> None:
    fig = style_config.caption_figure
    tbl = style_config.caption_table

    fig_template = fig.get("template", "Gambar {n}. {title} ({source})")
    tbl_template = tbl.get("template", "Tabel {bab}.{n} {title}")
    fig_pos = fig.get("position", "BELOW").upper()
    tbl_pos = tbl.get("position", "ABOVE").upper()

    if tbl_pos == "ABOVE":
        _add_seq_caption(document, "Table", tbl_template)
        _force_paragraph_runs_black(document.add_paragraph("[PLACEHOLDER_TABEL]"))
    else:
        _force_paragraph_runs_black(document.add_paragraph("[PLACEHOLDER_TABEL]"))
        _add_seq_caption(document, "Table", tbl_template)

    if fig_pos == "BELOW":
        _force_paragraph_runs_black(document.add_paragraph("[PLACEHOLDER_GAMBAR]"))
        _add_seq_caption(document, "Figure", fig_template)
    else:
        _add_seq_caption(document, "Figure", fig_template)
        _force_paragraph_runs_black(document.add_paragraph("[PLACEHOLDER_GAMBAR]"))
```

- [ ] **Step 6: Update `_configure_page_layout()` dan `_apply_base_styles()` — hapus keduanya**

Kedua fungsi ini tidak lagi diperlukan (digantikan oleh `apply_page_layout` dan `apply_word_style` dari `scope_executor`). Hapus dari `docx_renderer.py`.

- [ ] **Step 7: Hapus import `_map_alignment` dari `docx_renderer.py` jika tidak dipakai lagi**

Cek apakah `_map_alignment` masih dipakai. Jika tidak, hapus.

- [ ] **Step 8: Jalankan semua tests baru**

```
cd experiments/pymupdf4llm
python -m pytest tests/docx/test_docx_generator.py -k "scoped_map" -v
```

Expected: 3 PASSED

- [ ] **Step 9: Jalankan full suite**

```
cd experiments/pymupdf4llm
python -m pytest tests/ -v 2>&1 | tail -30
```

- [ ] **Step 10: Commit**

```bash
git add experiments/pymupdf4llm/model_ai/docx/docx_renderer.py \
        experiments/pymupdf4llm/tests/docx/test_docx_generator.py
git commit -m "feat: renderer konsumsi ScopedPropertyMap via scope_executor, hapus hardcoded metadata styling"
```

---

## Task 6: Update `generator.py` dan cleanup simbol lama

**Files:**
- Modify: `experiments/pymupdf4llm/model_ai/docx/generator.py`
- Modify: `experiments/pymupdf4llm/model_ai/docx/style_mapping_pipeline.py`
- Delete: `experiments/pymupdf4llm/tests/docx/test_style_translator_llm.py`

- [ ] **Step 1: Update `generator.py`**

```python
"""
Fungsi: Orkestrator utama pembuatan DOCX proposal dari metadata, chunk, dan scoped property map.
"""
from pathlib import Path

from model_ai.docx.chunk_loader import load_chunk_sources
from model_ai.docx.docx_renderer import render_proposal_docx
from model_ai.docx.metadata_loader import load_document_metadata
from model_ai.docx.style_mapping_pipeline import build_docx_scoped_map


def generate_proposal_docx(
    metadata_path: Path,
    chunks_path: Path,
    output_path: Path,
    use_llm_normalization: bool = True,
) -> Path:
    metadata = load_document_metadata(metadata_path)
    chunks = load_chunk_sources(chunks_path)
    scoped_map = build_docx_scoped_map(
        metadata=metadata,
        extracted_path=metadata_path,
        use_llm_mapper=use_llm_normalization,
        with_embeddings=use_llm_normalization,
    )
    return render_proposal_docx(
        metadata=metadata,
        chunks=chunks,
        style_config=scoped_map,
        output_path=output_path,
    )
```

- [ ] **Step 2: Hapus simbol lama dari `style_mapping_pipeline.py`**

Hapus:
- `DocxStyleConfig` (lama)
- `LLMStyleConfigCandidate`
- `MappingCandidate`, `ProposedMapping`, `ValidatedMapping`, `ValidationReport`, `ApplyPlan`
- `propose_mappings_with_llm()`, `propose_mappings_rule_based()`
- `validate_candidate_mappings()`, `build_apply_plan()`
- `_build_candidate_prompt()`, `save_pipeline_outputs()`
- `run_docx_style_mapping_pipeline()` (lama)
- `translate_docx_style_config()` (lama)
- `build_base_style_config()` (lama)

Pastikan semua yang di-keep masih di-export dan tidak ada import yang rusak.

- [ ] **Step 3: Hapus file test lama**

```bash
git rm experiments/pymupdf4llm/tests/docx/test_style_translator_llm.py
```

- [ ] **Step 4: Jalankan full test suite**

```
cd experiments/pymupdf4llm
python -m pytest tests/ -v
```

Expected: semua PASSED, zero warnings.

- [ ] **Step 5: Commit**

```bash
git add experiments/pymupdf4llm/model_ai/docx/generator.py \
        experiments/pymupdf4llm/model_ai/docx/style_mapping_pipeline.py
git rm experiments/pymupdf4llm/tests/docx/test_style_translator_llm.py
git commit -m "refactor: generator pakai build_docx_scoped_map, hapus simbol pipeline lama"
```

---

## Task 7: Integration smoke test dan CLI verification

- [ ] **Step 1: Jalankan CLI dalam mode deterministik (tanpa LLM/embedding)**

```bash
cd experiments/pymupdf4llm
python manage.py docx \
  --metadata data/output.json \
  --chunks data/output_chunks.json \
  --output data/test_output.docx \
  --no-llm
```

Expected: file terbuat tanpa exception.

- [ ] **Step 2: Verifikasi output DOCX**

```python
from docx import Document
doc = Document("experiments/pymupdf4llm/data/test_output.docx")
print(doc.styles["Normal"].font.name)     # Times New Roman
print(doc.styles["Normal"].font.size.pt)  # 12.0
print(doc.styles["Heading 1"].font.bold)  # True
```

- [ ] **Step 3: Final full test suite**

```
cd experiments/pymupdf4llm
python -m pytest tests/ -v
```

Expected: semua PASSED.

- [ ] **Step 4: Final commit**

```bash
git commit -m "test: integration smoke test passes — full ScopedPropertyMap pipeline end-to-end"
```

---

## Self-Review

### Spec Coverage

| Requirement | Dicovered oleh |
|-------------|---------------|
| Semua output.json field dibaca LLM | Task 4 — `propose_scoped_map_with_llm()` terima seluruh flattened payload |
| LLM pakai RAG catalog python-docx | Task 4 — retrieved chunks dari embedding index diinjek ke prompt |
| Fleksibilitas: LLM tentukan property apa dalam scope | Task 1 — scope adalah `dict[str, Any]`, bukan field hardcoded |
| Validasi scope tersedia | Task 1 — `ScopedPropertyMap` validasi Pydantic di level scope |
| Lapis 1: prompt melarang improvisasi di luar catalog | Task 4 — `ATURAN KETAT` eksplisit di `_build_scoped_map_prompt()` |
| Lapis 2: post-validation buang property asing | Task 4 — `validate_scoped_map()` dibandingkan `known_paths` dari catalog |
| Renderer tidak hardcode metadata styling | Task 5 — semua styling via `scope_executor` |
| Fallback deterministik jika LLM gagal | Task 4 — `_rule_based_scoped_map()` + exception handler |
| Property baru bisa ditambah tanpa ubah model | Task 3 — cukup tambah `elif` di `scope_executor.py` |
| CLI `manage.py` tetap berfungsi | Task 7 |

### Placeholder Scan

Tidak ada TBD, TODO, atau placeholder.

### Type Consistency

- `ScopedPropertyMap` didefinisikan Task 1, dipakai Tasks 2–7 ✓
- `build_base_scoped_map(metadata) -> ScopedPropertyMap` — Task 2 ✓
- `propose_scoped_map_with_llm(flattened, chunks) -> ScopedPropertyMap` — Task 4 ✓
- `build_docx_scoped_map(metadata, extracted_path, ...) -> ScopedPropertyMap` — Task 4 ✓
- `apply_word_style(style, props: dict)` — Task 3 ✓
- `apply_page_layout(section, props: dict)` — Task 3 ✓
- `render_proposal_docx(..., style_config: ScopedPropertyMap)` — Task 5 ✓
- `generate_proposal_docx(...)` calls `build_docx_scoped_map()` — Task 6 ✓
