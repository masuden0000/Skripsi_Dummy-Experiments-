"""
Bandingkan properti DOCX dengan rules dari DocumentMetadata.

Digunakan oleh: validator.py

Tujuan: Mendeteksi deviasi format antara dokumen dengan rules yang diharapkan.
"""
from typing import Any

from model_ai.extractor.models import DocumentMetadata
from model_ai.validation.models import DocxProperties, ValidationIssue


# ---------------------------------------------------------------------------
# Digunakan oleh: Dipakai internal di file ini atau dipanggil dari entrypoint runtime.
# Blok konstanta `TOLERANCE` untuk menyimpan konfigurasi/registry yang dipakai berulang.
# ---------------------------------------------------------------------------
# Tolerance untuk perbandingan float (dalam satuan masing-masing)
MARGIN_TOLERANCE_CM = 0.1  # 0.1 cm tolerance untuk margin
LINE_SPACING_TOLERANCE = 0.01  # 0.01 tolerance untuk line spacing (misal 1.15 vs 1.5)


# ---------------------------------------------------------------------------
# Digunakan oleh: Dipakai internal di file ini atau dipanggil dari entrypoint runtime.
# Mendefinisikan fungsi `_compare_values` untuk kebutuhan modul `rule_validator`.
# ---------------------------------------------------------------------------
def _compare_values(
    expected: Any,
    actual: Any,
    tolerance: float | None = None,
) -> tuple[bool, str]:
    """Compare two values with optional tolerance.

    Args:
        expected: Expected value from rules
        actual: Actual value from document
        tolerance: Tolerance for float comparison (e.g., 0.1 for 10% or 0.1cm)

    Returns:
        Tuple of (is_match, comparison_description)
    """
    # Both None = match
    if expected is None and actual is None:
        return True, "both None"

    # One is None = no match
    if expected is None or actual is None:
        return False, f"expected={expected}, actual={actual}"

    # String comparison (case-insensitive for fonts)
    if isinstance(expected, str) and isinstance(actual, str):
        match = expected.lower().strip() == actual.lower().strip()
        return match, f"expected='{expected}', actual='{actual}'"

    # Boolean comparison
    if isinstance(expected, bool) or isinstance(actual, bool):
        match = bool(expected) == bool(actual)
        return match, f"expected={expected}, actual={actual}"

    # Numeric comparison with tolerance
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if tolerance is not None:
            match = abs(float(expected) - float(actual)) <= tolerance
        else:
            match = expected == actual
        return match, f"expected={expected}, actual={actual}"

    # Default comparison
    match = expected == actual
    return match, f"expected={expected}, actual={actual}"


# ---------------------------------------------------------------------------
# Digunakan oleh: Dipakai internal di file ini atau dipanggil dari entrypoint runtime.
# Mendefinisikan fungsi `_add_issue` untuk kebutuhan modul `rule_validator`.
# ---------------------------------------------------------------------------
def _add_issue(
    issues: list[ValidationIssue],
    category: str,
    field: str,
    expected: Any,
    actual: Any,
    severity: str = "error",
    message: str = "",
) -> None:
    """Add a validation issue to the list."""
    if severity not in ("error", "warning", "info"):
        severity = "error"

    issues.append(
        ValidationIssue(
            category=category,
            field=field,
            expected=expected,
            actual=actual,
            severity=severity,
            message=message or f"{field} tidak sesuai: diharapkan {expected}, ditemukan {actual}",
        )
    )


# ---------------------------------------------------------------------------
# Digunakan oleh: Dipakai internal di file ini atau dipanggil dari entrypoint runtime.
# Mendefinisikan fungsi `_validate_typography" untuk kebutuhan modul `rule_validator`.
# ---------------------------------------------------------------------------
def _validate_typography(
    props: DocxProperties,
    metadata: DocumentMetadata,
    issues: list[ValidationIssue],
) -> None:
    """Validate typography properties."""
    if metadata.typography is None:
        return

    typo = metadata.typography

    # Font family
    if typo.font_family and props.font_family:
        match, desc = _compare_values(typo.font_family, props.font_family)
        if not match:
            _add_issue(
                issues,
                category="typography",
                field="font_family",
                expected=typo.font_family,
                actual=props.font_family,
                message=f"Font keluarga tidak sesuai: diharapkan '{typo.font_family}', ditemukan '{props.font_family}'",
            )

    # Font size body
    if typo.font_size_body_pt and props.font_size_body_pt:
        match, desc = _compare_values(typo.font_size_body_pt, props.font_size_body_pt)
        if not match:
            _add_issue(
                issues,
                category="typography",
                field="font_size_body_pt",
                expected=typo.font_size_body_pt,
                actual=props.font_size_body_pt,
                message=f"Ukuran font body tidak sesuai: diharapkan {typo.font_size_body_pt}pt, ditemukan {props.font_size_body_pt}pt",
            )

    # Font size heading
    if typo.font_size_heading_pt and props.font_size_heading_pt:
        match, desc = _compare_values(typo.font_size_heading_pt, props.font_size_heading_pt)
        if not match:
            _add_issue(
                issues,
                category="typography",
                field="font_size_heading_pt",
                expected=typo.font_size_heading_pt,
                actual=props.font_size_heading_pt,
                message=f"Ukuran font heading tidak sesuai: diharapkan {typo.font_size_heading_pt}pt, ditemukan {props.font_size_heading_pt}pt",
            )

    # Heading bold
    if typo.heading_bold is not None and props.heading_bold is not None:
        match, desc = _compare_values(typo.heading_bold, props.heading_bold)
        if not match:
            expected_val = "Ya" if typo.heading_bold else "Tidak"
            actual_val = "Ya" if props.heading_bold else "Tidak"
            _add_issue(
                issues,
                category="typography",
                field="heading_bold",
                expected=typo.heading_bold,
                actual=props.heading_bold,
                severity="warning",
                message=f"Heading bold: diharapkan {expected_val}, ditemukan {actual_val}",
            )

    # Heading all caps
    if typo.heading_all_caps is not None and props.heading_all_caps is not None:
        match, desc = _compare_values(typo.heading_all_caps, props.heading_all_caps)
        if not match:
            expected_val = "Ya" if typo.heading_all_caps else "Tidak"
            actual_val = "Ya" if props.heading_all_caps else "Tidak"
            _add_issue(
                issues,
                category="typography",
                field="heading_all_caps",
                expected=typo.heading_all_caps,
                actual=props.heading_all_caps,
                severity="warning",
                message=f"Heading ALL CAPS: diharapkan {expected_val}, ditemukan {actual_val}",
            )


# ---------------------------------------------------------------------------
# Digunakan oleh: Dipakai internal di file ini atau dipanggil dari entrypoint runtime.
# Mendefinisikan fungsi `_validate_page_layout" untuk kebutuhan modul `rule_validator`.
# ---------------------------------------------------------------------------
def _validate_page_layout(
    props: DocxProperties,
    metadata: DocumentMetadata,
    issues: list[ValidationIssue],
) -> None:
    """Validate page layout properties."""
    if metadata.page_layout is None:
        return

    layout = metadata.page_layout

    # Margins
    margin_fields = [
        ("margin_top_cm", layout.margin_top_cm, props.margin_top_cm, "Margin atas"),
        ("margin_bottom_cm", layout.margin_bottom_cm, props.margin_bottom_cm, "Margin bawah"),
        ("margin_left_cm", layout.margin_left_cm, props.margin_left_cm, "Margin kiri"),
        ("margin_right_cm", layout.margin_right_cm, props.margin_right_cm, "Margin kanan"),
    ]

    for field, expected, actual, label in margin_fields:
        if expected is not None and actual is not None:
            match, desc = _compare_values(expected, actual, tolerance=MARGIN_TOLERANCE_CM)
            if not match:
                _add_issue(
                    issues,
                    category="page_layout",
                    field=field,
                    expected=expected,
                    actual=actual,
                    message=f"{label} tidak sesuai: diharapkan {expected}cm, ditemukan {actual}cm",
                )

    # Paper size
    if layout.paper_size and props.paper_size:
        match, desc = _compare_values(layout.paper_size, props.paper_size)
        if not match:
            _add_issue(
                issues,
                category="page_layout",
                field="paper_size",
                expected=layout.paper_size,
                actual=props.paper_size,
                message=f"Ukuran kertas tidak sesuai: diharapkan {layout.paper_size}, ditemukan {props.paper_size}",
            )

    # Orientation
    if layout.orientation and props.orientation:
        match, desc = _compare_values(layout.orientation, props.orientation)
        if not match:
            _add_issue(
                issues,
                category="page_layout",
                field="orientation",
                expected=layout.orientation,
                actual=props.orientation,
                message=f"Orientasi halaman tidak sesuai: diharapkan {layout.orientation}, ditemukan {props.orientation}",
            )


# ---------------------------------------------------------------------------
# Digunakan oleh: Dipakai internal di file ini atau dipanggil dari entrypoint runtime.
# Mendefinisikan fungsi `_validate_spacing" untuk kebutuhan modul `rule_validator`.
# ---------------------------------------------------------------------------
def _validate_spacing(
    props: DocxProperties,
    metadata: DocumentMetadata,
    issues: list[ValidationIssue],
) -> None:
    """Validate spacing properties."""
    if metadata.spacing is None:
        return

    spacing = metadata.spacing

    # Line spacing
    if spacing.line_spacing and props.line_spacing:
        match, desc = _compare_values(
            spacing.line_spacing,
            props.line_spacing,
            tolerance=LINE_SPACING_TOLERANCE,
        )
        if not match:
            _add_issue(
                issues,
                category="spacing",
                field="line_spacing",
                expected=spacing.line_spacing,
                actual=props.line_spacing,
                message=f"Line spacing tidak sesuai: diharapkan {spacing.line_spacing}, ditemukan {props.line_spacing}",
            )

    # Paragraph alignment
    if spacing.paragraph_alignment and props.paragraph_alignment:
        match, desc = _compare_values(spacing.paragraph_alignment, props.paragraph_alignment)
        if not match:
            _add_issue(
                issues,
                category="spacing",
                field="paragraph_alignment",
                expected=spacing.paragraph_alignment,
                actual=props.paragraph_alignment,
                message=f"Paragraf alignment tidak sesuai: diharapkan {spacing.paragraph_alignment}, ditemukan {props.paragraph_alignment}",
            )

    # First line indent
    if spacing.first_line_indent_cm and props.first_line_indent_cm:
        match, desc = _compare_values(
            spacing.first_line_indent_cm,
            props.first_line_indent_cm,
            tolerance=MARGIN_TOLERANCE_CM,
        )
        if not match:
            _add_issue(
                issues,
                category="spacing",
                field="first_line_indent_cm",
                expected=spacing.first_line_indent_cm,
                actual=props.first_line_indent_cm,
                message=f"First line indent tidak sesuai: diharapkan {spacing.first_line_indent_cm}cm, ditemukan {props.first_line_indent_cm}cm",
            )


# ---------------------------------------------------------------------------
# Digunakan oleh: Dipakai internal di file ini atau dipanggil dari entrypoint runtime.
# Mendefinisikan fungsi `_validate_document_structure" untuk kebutuhan modul `rule_validator`.
# ---------------------------------------------------------------------------
def _validate_document_structure(
    props: DocxProperties,
    metadata: DocumentMetadata,
    issues: list[ValidationIssue],
) -> None:
    """Validate document structure."""
    if metadata.document_structure_proposal is None:
        return

    doc_struct = metadata.document_structure_proposal

    # Check required sections
    if doc_struct.halaman_sampul and not props.has_halaman_sampul:
        _add_issue(
            issues,
            category="document_structure",
            field="halaman_sampul",
            expected=True,
            actual=False,
            severity="warning",
            message="Halaman sampul tidak ditemukan dalam dokumen",
        )

    if doc_struct.halaman_pengesahan and not props.has_halaman_pengesahan:
        _add_issue(
            issues,
            category="document_structure",
            field="halaman_pengesahan",
            expected=True,
            actual=False,
            severity="warning",
            message="Halaman pengesahan tidak ditemukan dalam dokumen",
        )

    # Check section count
    if props.section_count < 1:
        _add_issue(
            issues,
            category="document_structure",
            field="section_count",
            expected=">= 1",
            actual=props.section_count,
            severity="error",
            message=f"Dokumen tidak memiliki section yang valid (ditemukan {props.section_count})",
        )


# ---------------------------------------------------------------------------
# Digunakan oleh: Dipakai internal di file ini atau dipanggil dari entrypoint runtime.
# Mendefinisikan fungsi `compare_properties` untuk kebutuhan modul `rule_validator`.
# ---------------------------------------------------------------------------
def compare_properties(
    props: DocxProperties,
    metadata: DocumentMetadata,
) -> list[ValidationIssue]:
    """Compare DOCX properties against DocumentMetadata rules.

    Args:
        props: Extracted properties from the DOCX file.
        metadata: DocumentMetadata containing the rules to validate against.

    Returns:
        List of ValidationIssue objects found during comparison.
    """
    issues: list[ValidationIssue] = []

    # Validate each category
    _validate_typography(props, metadata, issues)
    _validate_page_layout(props, metadata, issues)
    _validate_spacing(props, metadata, issues)
    _validate_document_structure(props, metadata, issues)

    return issues