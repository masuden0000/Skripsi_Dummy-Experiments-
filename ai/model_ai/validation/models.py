"""
Schema untuk validasi dokumen.

Digunakan oleh: validator.py, rule_validator.py, docx_property_extractor.py

Tujuan: Mendefinisikan struktur data untuk hasil validasi dan properti DOCX.
"""
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Digunakan oleh: Dipakai oleh fungsi-fungsi di modul ini dan modul terkait saat import runtime.
# Blok konstanta `VALIDATION_CATEGORIES` untuk menyimpan konfigurasi/registry yang dipakai berulang.
# ---------------------------------------------------------------------------
VALIDATION_CATEGORIES = (
    "typography",
    "page_layout",
    "spacing",
    "document_structure",
    "numbering",
    "figures_tables",
)


# ---------------------------------------------------------------------------
# Digunakan oleh: Dipakai internal di file ini atau dipanggil dari entrypoint runtime.
# Mendefinisikan class `ValidationIssue` untuk kebutuhan modul `validation`.
# ---------------------------------------------------------------------------
class ValidationIssue(BaseModel):
    """Represents a single validation issue found in the document."""

    category: Literal[
        "typography",
        "page_layout",
        "spacing",
        "document_structure",
        "numbering",
        "figures_tables",
    ] = Field(
        description="Category of the validation issue"
    )
    field: str = Field(
        description="Field name that has the issue (e.g., 'font_family', 'margin_top_cm')"
    )
    expected: str | int | float | bool | None = Field(
        default=None,
        description="Expected value from the rules (DocumentMetadata)"
    )
    actual: str | int | float | bool | None = Field(
        default=None,
        description="Actual value found in the document"
    )
    severity: Literal["error", "warning", "info"] = Field(
        default="error",
        description="Severity level of the issue"
    )
    message: str = Field(
        default="",
        description="Human-readable description of the issue"
    )

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.category}.{self.field}: {self.message}"


# ---------------------------------------------------------------------------
# Digunakan oleh: Dipakai internal di file ini atau dipanggil dari entrypoint runtime.
# Mendefinisikan class `ValidationResult` untuk kebutuhan modul `validation`.
# ---------------------------------------------------------------------------
class ValidationResult(BaseModel):
    """Represents the result of a document validation."""

    status: Literal["pass", "fail", "warning"] = Field(
        default="pass",
        description="Overall validation status"
    )
    issues: list[ValidationIssue] = Field(
        default_factory=list,
        description="List of validation issues found"
    )
    validated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp when validation was performed"
    )
    document_path: str | None = Field(
        default=None,
        description="Path to the validated document"
    )
    document_name: str | None = Field(
        default=None,
        description="Name of the validated document"
    )
    summary: str = Field(
        default="",
        description="Human-readable summary of the validation result"
    )

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "info")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status,
            "issues": [issue.model_dump() for issue in self.issues],
            "validated_at": self.validated_at,
            "document_path": self.document_path,
            "document_name": self.document_name,
            "summary": self.summary,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
        }


# ---------------------------------------------------------------------------
# Digunakan oleh: Dipakai internal di file ini atau dipanggil dari entrypoint runtime.
# Mendefinisikan class `DocxProperties` untuk kebutuhan modul `validation`.
# ---------------------------------------------------------------------------
class DocxProperties(BaseModel):
    """Represents extracted properties from a DOCX file.

    This mirrors the structure of DocumentMetadata for easy comparison.
    """

    # Typography
    font_family: str | None = Field(default=None, description="Primary font family")
    font_size_body_pt: int | None = Field(default=None, description="Body font size in points")
    font_size_heading_pt: int | None = Field(default=None, description="Heading font size in points")
    heading_bold: bool | None = Field(default=None, description="Whether headings are bold")
    heading_all_caps: bool | None = Field(default=None, description="Whether headings are ALL CAPS")

    # Page Layout
    margin_top_cm: float | None = Field(default=None, description="Top margin in cm")
    margin_bottom_cm: float | None = Field(default=None, description="Bottom margin in cm")
    margin_left_cm: float | None = Field(default=None, description="Left margin in cm")
    margin_right_cm: float | None = Field(default=None, description="Right margin in cm")
    paper_size: str | None = Field(default=None, description="Paper size (A4, F4, etc.)")
    orientation: str | None = Field(default=None, description="Portrait or Landscape")

    # Spacing
    line_spacing: float | None = Field(default=None, description="Line spacing value")
    line_spacing_rule: str | None = Field(default=None, description="Line spacing rule (MULTIPLE, EXACT, AT_LEAST)")
    paragraph_alignment: str | None = Field(default=None, description="Default paragraph alignment")
    first_line_indent_cm: float | None = Field(default=None, description="First line indent in cm")
    references_hanging_indent: bool | None = Field(default=None, description="Whether references use hanging indent")

    # Document Structure
    heading_count: int = Field(default=0, description="Number of headings in document")
    section_count: int = Field(default=0, description="Number of sections in document")
    has_halaman_sampul: bool = Field(default=False, description="Whether document has cover page")
    has_halaman_pengesahan: bool = Field(default=False, description="Whether document has approval page")
    has_ringkasan: bool = Field(default=False, description="Whether document has summary/abstract")

    # Numbering
    chapter_format: str | None = Field(default=None, description="Chapter number format")
    preliminary_page_format: str | None = Field(default=None, description="Preliminary pages numbering format")
    content_page_format: str | None = Field(default=None, description="Content pages numbering format")

    # Figures & Tables
    table_caption_position: str | None = Field(default=None, description="Table caption position (above/below)")
    figure_caption_position: str | None = Field(default=None, description="Figure caption position (above/below)")
    table_count: int = Field(default=0, description="Number of tables in document")
    figure_count: int = Field(default=0, description="Number of figures in document")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump()