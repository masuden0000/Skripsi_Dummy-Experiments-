# ai/model/tests/test_body_content_check.py
"""Test untuk _is_heading_para, _check_body_content, caption_alignment dinamis di
_check_caption_format / _check_figures_tables."""
from pathlib import Path
from unittest.mock import MagicMock

from model_ai.validation.validocx_runner import (
    _is_heading_para,
    _check_body_content,
    _check_caption_format,
    _check_figures_tables,
)

_DOCX = Path(__file__).parent / "file_target.docx"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_para(style_name: str, base_style_name: str | None = None):
    para = MagicMock()
    style = MagicMock()
    style.name = style_name
    if base_style_name:
        base = MagicMock()
        base.name = base_style_name
        base.base_style = None
        style.base_style = base
    else:
        style.base_style = None
    para.style = style
    return para


def _make_body_metadata(font="Times New Roman", size=12, spacing=1.15):
    meta = MagicMock()
    meta.typography.font_family = font
    meta.typography.font_size_body_pt = size
    meta.spacing.line_spacing = spacing
    meta.spacing.line_spacing_rule = None
    return meta


def _make_caption_metadata(
    font="Times New Roman",
    size=12,
    fig_align: str | None = "CENTER",
    tbl_align: str | None = "CENTER",
    lamp_align: str | None = "CENTER",
    fig_fmt: str | None = None,
    tbl_fmt: str | None = None,
    lamp_fmt: str | None = None,
    fig_pos: str | None = None,
    tbl_pos: str | None = None,
):
    meta = MagicMock()
    meta.typography.font_family = font
    meta.typography.font_size_body_pt = size
    meta.figures_and_tables.caption_alignment_figure   = fig_align
    meta.figures_and_tables.caption_alignment_table    = tbl_align
    meta.figures_and_tables.caption_alignment_lampiran = lamp_align
    meta.figures_and_tables.caption_format_figure      = fig_fmt
    meta.figures_and_tables.caption_format_table       = tbl_fmt
    meta.figures_and_tables.caption_format_lampiran    = lamp_fmt
    meta.figures_and_tables.figure_caption_position    = fig_pos
    meta.figures_and_tables.table_caption_position     = tbl_pos
    return meta


# ── _is_heading_para() ────────────────────────────────────────────────────────

def test_is_heading_para_heading1():
    assert _is_heading_para(_mock_para("Heading 1")) is True

def test_is_heading_para_heading2():
    assert _is_heading_para(_mock_para("Heading 2")) is True

def test_is_heading_para_judul1():
    assert _is_heading_para(_mock_para("Judul1")) is True

def test_is_heading_para_judul_spasi():
    assert _is_heading_para(_mock_para("Judul 3")) is True

def test_is_heading_para_normal_is_not_heading():
    assert _is_heading_para(_mock_para("Normal")) is False

def test_is_heading_para_list_paragraph_is_not_heading():
    assert _is_heading_para(_mock_para("List Paragraph")) is False

def test_is_heading_para_toc_is_not_heading():
    assert _is_heading_para(_mock_para("toc 1")) is False

def test_is_heading_para_via_inheritance():
    para = _mock_para("CustomBab", base_style_name="Heading 1")
    assert _is_heading_para(para) is True


# ── _check_body_content() ─────────────────────────────────────────────────────

def test_check_body_content_returns_checks():
    _, checks = _check_body_content(_DOCX, _make_body_metadata())
    assert len(checks) > 0

def test_check_body_content_has_alignment_field():
    _, checks = _check_body_content(_DOCX, _make_body_metadata())
    fields = [c.field for c in checks]
    assert "body_alignment" in fields, f"body_alignment tidak ada. Fields: {fields}"

def test_check_body_content_has_font_family_field():
    _, checks = _check_body_content(_DOCX, _make_body_metadata())
    fields = [c.field for c in checks]
    assert "body_font_family" in fields, f"body_font_family tidak ada. Fields: {fields}"

def test_check_body_content_excludes_headings():
    _, checks = _check_body_content(_DOCX, _make_body_metadata())
    for chk in [c for c in checks if c.field == "body_alignment"]:
        for occ in (chk.occurrences or []):
            assert "Heading" not in (occ.get("style") or ""), (
                f"Heading ditemukan di body check: style='{occ.get('style')}'"
            )

def test_check_body_content_includes_list_paragraph():
    _, checks = _check_body_content(_DOCX, _make_body_metadata())
    all_occs = [o for c in checks for o in (c.occurrences or [])]
    assert any((o.get("style") or "") == "List Paragraph" for o in all_occs), (
        "List Paragraph tidak ditemukan di body content check"
    )

def test_check_body_content_excludes_lampiran_captions():
    _, checks = _check_body_content(_DOCX, _make_body_metadata())
    all_occs = [o for c in checks for o in (c.occurrences or [])]
    lamp_in_body = [o for o in all_occs if (o.get("text") or "").startswith("Lampiran ")]
    assert len(lamp_in_body) == 0, f"Lampiran captions ditemukan di body check: {lamp_in_body[:3]}"

def test_check_body_content_results_in_doc_order():
    _, checks = _check_body_content(_DOCX, _make_body_metadata())
    all_idxs = [
        o.get("para_idx") for c in checks for o in (c.occurrences or [])
        if o.get("para_idx") is not None
    ]
    assert all_idxs == sorted(all_idxs), f"para_idx tidak berurutan: {all_idxs[:10]}..."


# ── caption_alignment dinamis di _check_caption_format() ─────────────────────

def test_caption_format_emits_figure_alignment_field():
    meta = _make_caption_metadata(fig_align="CENTER", tbl_align="CENTER")
    _, checks = _check_caption_format(_DOCX, meta)
    fields = [c.field for c in checks]
    assert "caption_alignment_figure" in fields, f"Fields: {fields}"

def test_caption_format_emits_table_alignment_field():
    meta = _make_caption_metadata(fig_align="CENTER", tbl_align="CENTER")
    _, checks = _check_caption_format(_DOCX, meta)
    fields = [c.field for c in checks]
    assert "caption_alignment_table" in fields, f"Fields: {fields}"

def test_caption_format_figure_alignment_uses_metadata():
    meta = _make_caption_metadata(fig_align="CENTER")
    _, checks = _check_caption_format(_DOCX, meta)
    fig_align_checks = [c for c in checks if c.field == "caption_alignment_figure"]
    assert any(c.status == "passed" for c in fig_align_checks), (
        f"Tidak ada passed untuk caption_alignment_figure: {[(c.status, c.message) for c in fig_align_checks]}"
    )

def test_caption_format_figure_alignment_fails_on_wrong_value():
    meta = _make_caption_metadata(fig_align="LEFT")
    _, checks = _check_caption_format(_DOCX, meta)
    fig_align_checks = [c for c in checks if c.field == "caption_alignment_figure"]
    if fig_align_checks:
        statuses = [c.status for c in fig_align_checks]
        assert any(s in ("warning", "failed") for s in statuses), (
            f"Diharapkan warning/failed jika expected=LEFT, dapat: {statuses}"
        )

def test_caption_format_uses_metadata_not_hardcoded():
    meta_center = _make_caption_metadata(fig_align="CENTER")
    meta_left   = _make_caption_metadata(fig_align="LEFT")
    _, checks_center = _check_caption_format(_DOCX, meta_center)
    _, checks_left   = _check_caption_format(_DOCX, meta_left)
    expected_center = next(
        (c.expected for c in checks_center if c.field == "caption_alignment_figure"), None
    )
    expected_left = next(
        (c.expected for c in checks_left if c.field == "caption_alignment_figure"), None
    )
    assert expected_center != expected_left, (
        "expected value identik padahal metadata berbeda — alignment masih hardcode"
    )


# ── caption_format_lampiran + caption_alignment_lampiran ─────────────────────

def test_figures_tables_lampiran_format_field_emitted():
    meta = _make_caption_metadata(lamp_fmt="Lampiran {n}. {title}")
    _, checks = _check_figures_tables(_DOCX, meta)
    fields = [c.field for c in checks]
    assert "lampiran_caption_format" in fields, f"Fields: {fields}"

def test_figures_tables_lampiran_format_skipped_when_none():
    meta = _make_caption_metadata(lamp_fmt=None, lamp_align=None)
    _, checks = _check_figures_tables(_DOCX, meta)
    fields = [c.field for c in checks]
    assert "lampiran_caption_format" not in fields, f"Muncul padahal None: {fields}"

def test_figures_tables_lampiran_alignment_field_emitted():
    meta = _make_caption_metadata(lamp_align="CENTER", lamp_fmt=None)
    _, checks = _check_figures_tables(_DOCX, meta)
    fields = [c.field for c in checks]
    assert "lampiran_caption_alignment" in fields, f"Fields: {fields}"

def test_figures_tables_lampiran_alignment_skipped_when_none():
    meta = _make_caption_metadata(lamp_align=None, lamp_fmt=None)
    _, checks = _check_figures_tables(_DOCX, meta)
    fields = [c.field for c in checks]
    assert "lampiran_caption_alignment" not in fields, f"Muncul padahal None: {fields}"
