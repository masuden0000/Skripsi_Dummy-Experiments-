"""
Fungsi: Test unit untuk pipeline mapping style DOCX berbasis dictionary python-docx.

Digunakan oleh: Dijalankan oleh pytest saat suite test dijalankan.

Tujuan: Menjaga agar chunking, validasi mapping, dan apply plan tetap stabil.
"""
import json
from pathlib import Path
from uuid import uuid4

from model_ai.docx.style_mapping_pipeline import (
    MappingCandidate,
    ProposedMapping,
    ScopedPropertyMap,
    build_apply_plan,
    build_catalog_chunks,
    build_docx_property_catalog,
    run_docx_style_mapping_pipeline,
    validate_candidate_mappings,
)


def _write_sample_dictionary(path: Path) -> None:
    path.write_text(
        (
            "paragraph:\n"
            "  properties:\n"
            "    alignment:\n"
            "      type: enum\n"
            "      description: \"Paragraph alignment WD_PARAGRAPH_ALIGNMENT\"\n"
            "paragraph_format:\n"
            "  properties:\n"
            "    line_spacing:\n"
            "      type: Length | float | None\n"
            "      description: \"Spacing antar baris\"\n"
            "font:\n"
            "  properties:\n"
            "    bold:\n"
            "      type: boolean | None\n"
            "      description: \"Bold text\"\n"
            "enumerations:\n"
            "  WD_PARAGRAPH_ALIGNMENT:\n"
            "    members:\n"
            "      - LEFT\n"
            "      - CENTER\n"
            "      - RIGHT\n"
            "      - JUSTIFY\n"
        ),
        encoding="utf-8",
    )


def test_build_catalog_and_section_chunking():
    data_dir = Path(__file__).resolve().parents[2] / "data"
    run_id = uuid4().hex
    dictionary_path = data_dir / f"test_dictionary_{run_id}.yaml"

    try:
        _write_sample_dictionary(dictionary_path)
        entries = build_docx_property_catalog(dictionary_path)
        chunks = build_catalog_chunks(entries)

        paths = {entry.path for entry in entries}
        assert "paragraph.alignment" in paths
        assert "paragraph_format.line_spacing" in paths
        assert "font.bold" in paths
        assert "enumerations.WD_PARAGRAPH_ALIGNMENT" in paths

        section_chunk_ids = {chunk.chunk_id for chunk in chunks if chunk.chunk_type == "section"}
        assert "section::paragraph" in section_chunk_ids
        assert "section::font" in section_chunk_ids
    finally:
        if dictionary_path.exists():
            dictionary_path.unlink()


def test_validate_candidate_and_build_apply_plan():
    data_dir = Path(__file__).resolve().parents[2] / "data"
    run_id = uuid4().hex
    dictionary_path = data_dir / f"test_dictionary_{run_id}.yaml"

    try:
        _write_sample_dictionary(dictionary_path)
        entries = build_docx_property_catalog(dictionary_path)

        candidate = MappingCandidate(
            mappings=[
                ProposedMapping(
                    source_field="spacing.paragraph_alignment",
                    target_path="paragraph.alignment",
                    normalized_value="center",
                    confidence=0.9,
                    reason="alignment mapping",
                ),
                ProposedMapping(
                    source_field="typography.heading_bold",
                    target_path="font.bold",
                    normalized_value=True,
                    confidence=0.9,
                    reason="bold mapping",
                ),
                ProposedMapping(
                    source_field="broken.value",
                    target_path="font.bold",
                    normalized_value="yes",
                    confidence=0.9,
                    reason="invalid bool",
                ),
                ProposedMapping(
                    source_field="unknown.path",
                    target_path="font.unknown",
                    normalized_value="x",
                    confidence=0.5,
                    reason="unknown target",
                ),
            ],
            new_found=[{"source_field": "new.style.token", "value": "abc"}],
        )

        report = validate_candidate_mappings(candidate, entries)
        assert len(report.accepted) == 2
        assert len(report.rejected) == 2
        assert any(item.target_path == "paragraph.alignment" for item in report.accepted)

        plan = build_apply_plan(report)
        assert plan.style_config_overrides["paragraph_alignment"] == "CENTER"
        assert plan.style_config_overrides["heading_bold"] is True
        assert "paragraph.alignment" in plan.docx_property_overrides
    finally:
        if dictionary_path.exists():
            dictionary_path.unlink()


def test_run_pipeline_without_embeddings_and_llm():
    data_dir = Path(__file__).resolve().parents[2] / "data"
    run_id = uuid4().hex
    dictionary_path = data_dir / f"test_dictionary_{run_id}.yaml"
    extracted_path = data_dir / f"test_output_{run_id}.json"
    catalog_path = data_dir / f"test_catalog_{run_id}.json"
    chunks_path = data_dir / f"test_chunks_{run_id}.json"
    index_path = data_dir / f"test_index_{run_id}.json"
    candidate_path = data_dir / f"test_candidate_{run_id}.json"
    report_path = data_dir / f"test_report_{run_id}.json"
    apply_plan_path = data_dir / f"test_apply_plan_{run_id}.json"

    try:
        _write_sample_dictionary(dictionary_path)
        extracted_path.write_text(
            json.dumps(
                {
                    "spacing": {"paragraph_alignment": "justify", "line_spacing": 1.5},
                    "typography": {"heading_bold": True},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        run_docx_style_mapping_pipeline(
            dictionary_path=dictionary_path,
            extracted_path=extracted_path,
            with_embeddings=False,
            use_llm_mapper=False,
            catalog_path=catalog_path,
            chunks_path=chunks_path,
            index_path=index_path,
            candidate_path=candidate_path,
            report_path=report_path,
            apply_plan_path=apply_plan_path,
        )

        assert catalog_path.exists()
        assert chunks_path.exists()
        assert index_path.exists()
        assert candidate_path.exists()
        assert report_path.exists()
        assert apply_plan_path.exists()
    finally:
        for path in (
            dictionary_path,
            extracted_path,
            catalog_path,
            chunks_path,
            index_path,
            candidate_path,
            report_path,
            apply_plan_path,
        ):
            if path.exists():
                path.unlink()


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
