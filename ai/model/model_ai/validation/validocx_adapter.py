"""Adapter: konversi DocumentMetadata Project 1 AI → requirements dict yang dikenali validocx.

Posisi pipeline: jembatan antara metadata Pydantic dan engine validocx (validate()).
"""
from typing import Any

from model_ai.extractor.models import DocumentMetadata


_ALIGNMENT_MAP: dict[str, int] = {
    "LEFT": 0,
    "CENTER": 1,
    "RIGHT": 2,
    "JUSTIFY": 3,
}

_ORIENTATION_MAP: dict[str, int] = {
    "PORTRAIT": 0,
    "portrait": 0,
    "LANDSCAPE": 1,
    "landscape": 1,
}

_GRUP_A_LINE_SPACING: dict[str, float] = {
    "SINGLE": 1.0,
    "ONE_POINT_FIVE": 1.15,
    "DOUBLE": 2.0,
}

_PAPER_SIZE_DIMS: dict[str, tuple[float, float]] = {
    "A4":     (21.0, 29.7),
    "F4":     (21.0, 33.0),
    "A5":     (14.85, 21.0),
    "A3":     (29.7, 42.0),
    "LETTER": (21.59, 27.94),
}


def _resolve_alignment(name: str | None, default: str = "JUSTIFY") -> int:
    if not name:
        return _ALIGNMENT_MAP[default]
    return _ALIGNMENT_MAP.get(name.upper().strip(), _ALIGNMENT_MAP[default])


def _resolve_line_spacing(metadata: DocumentMetadata) -> float:
    s = metadata.spacing
    if s is None:
        return 1.15
    rule = (s.line_spacing_rule or "").upper()
    if rule in _GRUP_A_LINE_SPACING:
        return _GRUP_A_LINE_SPACING[rule]
    return s.line_spacing if s.line_spacing is not None else 1.15


def _build_heading_font_attrs(metadata: DocumentMetadata, level: int) -> list[Any]:
    """Font attributes untuk Heading 1–2 (mengikuti setting admin).

    Bold hanya dicek jika admin mengaktifkan heading_bold.
    Heading 3–5 tidak menggunakan fungsi ini — mereka pakai normal font.
    """
    t = metadata.typography
    attrs: list[Any] = []
    if t is None:
        return attrs
    size = t.font_size_heading_pt
    if size is not None:
        attrs.append(int(size))
    if t.font_family:
        attrs.append(t.font_family)
    # Bold hanya ditambahkan untuk H1–H2 jika admin mengaktifkannya.
    # H3–H5 tidak pernah mewajibkan bold (normal_style tidak menyertakannya).
    if level <= 2 and t.heading_bold:
        attrs.append("bold")
    return attrs


def _build_normal_font_attrs(metadata: DocumentMetadata) -> list[Any]:
    """Font attributes untuk style Normal dan H3–H5 (TNR 12pt tanpa bold)."""
    t = metadata.typography
    attrs: list[Any] = []
    if t is None:
        return attrs
    if t.font_size_body_pt is not None:
        attrs.append(int(t.font_size_body_pt))
    if t.font_family:
        attrs.append(t.font_family)
    # Tidak ada bold — normal paragraf tidak pernah diwajibkan bold.
    return attrs


def metadata_to_requirements(metadata: DocumentMetadata) -> dict:
    """Bangun dict requirements (styles + sections) sesuai schema validocx.

    Dua template digunakan:
    ─ heading_style  : Heading 1–2, mengikuti setting admin (font, alignment,
                       bold opsional). Tidak dicek line_spacing.
    ─ normal_style   : Normal + Heading 3–5 + semua style paragraf lain.
                       Font TNR 12pt, alignment JUSTIFY, line_spacing 1.15.
    """
    s = metadata.spacing
    l = metadata.page_layout

    body_alignment = _resolve_alignment(
        s.paragraph_alignment if s else None, default="JUSTIFY"
    )
    heading_alignment = _resolve_alignment(
        s.heading_alignment if s else None, default="CENTER"
    )
    line_spacing = _resolve_line_spacing(metadata)

    # ── Template Normal ───────────────────────────────────────────────────────
    # Dipakai oleh: Normal, Heading 3–5, dan semua alias style paragraf.
    normal_font_attrs = _build_normal_font_attrs(metadata)
    normal_style: dict = {
        "exclude": {"text_regex": r"^\s*(\d{1,3})?\s*$"},
        "font": {
            "unit": "pt",
            "attributes": normal_font_attrs,
        },
        "paragraph": {
            "unit": "cm",
            "attributes": {
                "alignment": body_alignment,
                "line_spacing": line_spacing,
            },
        },
    }

    # ── Template Heading (H1–H2) ──────────────────────────────────────────────
    # Alignment dari admin; tidak dicek line_spacing; bold hanya jika admin set.
    def _make_heading_style(level: int) -> dict:
        return {
            "font": {
                "unit": "pt",
                "attributes": _build_heading_font_attrs(metadata, level),
            },
            "paragraph": {
                "unit": "cm",
                "attributes": {
                    # H1 dan H2 sama-sama mengikuti alignment dari admin.
                    "alignment": heading_alignment,
                },
            },
        }

    styles: dict[str, dict] = {
        "Normal": normal_style,
    }

    # H1–H2: template heading (ikut admin)
    for level in (1, 2):
        styles[f"Heading {level}"] = _make_heading_style(level)

    # H3–H5: template normal (TNR 12pt 1.15 justify, tanpa bold)
    for level in (3, 4, 5):
        styles[f"Heading {level}"] = {
            k: v for k, v in normal_style.items() if k != "exclude"
        }

    # ── Alias style template Word Indonesia (Judul1–5) ────────────────────────
    # Dokumen PKM sering menggunakan style "JudulN" alih-alih "Heading N".
    for level in (1, 2):
        styles[f"Judul{level}"] = _make_heading_style(level)
        styles[f"Judul {level}"] = _make_heading_style(level)
    for level in (3, 4, 5):
        no_exclude = {k: v for k, v in normal_style.items() if k != "exclude"}
        styles[f"Judul{level}"] = no_exclude
        styles[f"Judul {level}"] = no_exclude

    # ── Caption tabel dan gambar — default CENTER ─────────────────────────────
    # Caption biasanya berada di bawah/atas objek dan rata tengah.
    # Tidak mewajibkan line_spacing karena caption umumnya satu baris.
    caption_style: dict = {
        "font": {
            "unit": "pt",
            "attributes": normal_font_attrs,
        },
        "paragraph": {
            "unit": "cm",
            "attributes": {
                "alignment": _ALIGNMENT_MAP["CENTER"],
            },
        },
    }
    for name in ("Tabel", "Gambar", "TabelGambar", "Caption", "Figure", "Table"):
        styles[name] = caption_style

    section_attrs: dict[str, Any] = {}
    if l is not None:
        if l.margin_left_cm is not None:
            section_attrs["left_margin"] = float(l.margin_left_cm)
        if l.margin_right_cm is not None:
            section_attrs["right_margin"] = float(l.margin_right_cm)
        if l.margin_top_cm is not None:
            section_attrs["top_margin"] = float(l.margin_top_cm)
        if l.margin_bottom_cm is not None:
            section_attrs["bottom_margin"] = float(l.margin_bottom_cm)
        if l.paper_size and l.paper_size.upper() in _PAPER_SIZE_DIMS:
            w, h = _PAPER_SIZE_DIMS[l.paper_size.upper()]
            section_attrs["page_width"] = w
            section_attrs["page_height"] = h
        if l.orientation:
            section_attrs["orientation"] = _ORIENTATION_MAP.get(l.orientation, 0)

    sections = [{"unit": "cm", "attributes": section_attrs}] if section_attrs else []

    requirements: dict = {"styles": styles}
    if sections:
        requirements["sections"] = sections
    else:
        requirements["sections"] = [{"unit": "cm", "attributes": {}}]

    return requirements
