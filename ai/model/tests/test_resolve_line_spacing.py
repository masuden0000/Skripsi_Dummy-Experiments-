# ai/model/tests/test_resolve_line_spacing.py
"""Unit test untuk _resolve_line_spacing di validocx_adapter.

Kasus yang dicakup:
  - Grup A (SINGLE / ONE_POINT_FIVE / DOUBLE) → multiplier tetap, line_spacing diabaikan
  - MULTIPLE → pakai line_spacing langsung sebagai multiplier
  - AT_LEAST / EXACTLY → line_spacing (pt) dikonversi ke cm agar setara dengan
    nilai yang dibaca python-docx via paragraph_format.line_spacing.cm
  - Fallback → None / spacing=None → default 1.15
"""
import pytest
from unittest.mock import MagicMock

from model_ai.validation.validocx_adapter import _resolve_line_spacing

PT_TO_CM = 2.54 / 72  # 1 pt = 0.03528 cm


def _make_meta(rule: str | None, value: float | None) -> MagicMock:
    spacing = MagicMock()
    spacing.line_spacing_rule = rule
    spacing.line_spacing = value
    meta = MagicMock()
    meta.spacing = spacing
    return meta


# ── Grup A ────────────────────────────────────────────────────────────────────

def test_single_returns_1():
    assert _resolve_line_spacing(_make_meta("SINGLE", None)) == pytest.approx(1.0)


def test_one_point_five_returns_1_5():
    assert _resolve_line_spacing(_make_meta("ONE_POINT_FIVE", None)) == pytest.approx(1.5)


def test_double_returns_2():
    assert _resolve_line_spacing(_make_meta("DOUBLE", None)) == pytest.approx(2.0)


def test_grup_a_ignores_line_spacing_value():
    """Nilai line_spacing tidak berpengaruh saat rule Grup A."""
    assert _resolve_line_spacing(_make_meta("SINGLE", 99.0)) == pytest.approx(1.0)


# ── MULTIPLE ──────────────────────────────────────────────────────────────────

def test_multiple_returns_raw_multiplier():
    assert _resolve_line_spacing(_make_meta("MULTIPLE", 1.15)) == pytest.approx(1.15)


def test_multiple_none_falls_back_to_1_15():
    assert _resolve_line_spacing(_make_meta("MULTIPLE", None)) == pytest.approx(1.15)


# ── AT_LEAST / EXACTLY — unit conversion pt → cm ─────────────────────────────

def test_at_least_14pt_converts_to_cm():
    """14pt → 14 * 2.54/72 cm ≈ 0.4939 cm."""
    expected = 14.0 * PT_TO_CM
    assert _resolve_line_spacing(_make_meta("AT_LEAST", 14.0)) == pytest.approx(expected, rel=1e-4)


def test_exactly_12pt_converts_to_cm():
    """12pt → 12 * 2.54/72 cm ≈ 0.4233 cm."""
    expected = 12.0 * PT_TO_CM
    assert _resolve_line_spacing(_make_meta("EXACTLY", 12.0)) == pytest.approx(expected, rel=1e-4)


def test_exactly_none_falls_back_to_1_15():
    """Jika line_spacing tidak diisi untuk EXACTLY, fallback ke 1.15."""
    assert _resolve_line_spacing(_make_meta("EXACTLY", None)) == pytest.approx(1.15)


def test_at_least_none_falls_back_to_1_15():
    assert _resolve_line_spacing(_make_meta("AT_LEAST", None)) == pytest.approx(1.15)


# ── Case insensitive ──────────────────────────────────────────────────────────

def test_rule_lowercase_single():
    assert _resolve_line_spacing(_make_meta("single", None)) == pytest.approx(1.0)


def test_rule_lowercase_at_least():
    expected = 14.0 * PT_TO_CM
    assert _resolve_line_spacing(_make_meta("at_least", 14.0)) == pytest.approx(expected, rel=1e-4)


# ── Fallback / edge cases ─────────────────────────────────────────────────────

def test_spacing_none_returns_default():
    meta = MagicMock()
    meta.spacing = None
    assert _resolve_line_spacing(meta) == pytest.approx(1.15)


def test_unknown_rule_returns_line_spacing():
    assert _resolve_line_spacing(_make_meta("CUSTOM", 1.5)) == pytest.approx(1.5)


def test_unknown_rule_none_returns_1_15():
    assert _resolve_line_spacing(_make_meta("CUSTOM", None)) == pytest.approx(1.15)
