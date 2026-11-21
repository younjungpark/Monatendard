from __future__ import annotations

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from monatendard.builder import (
    _fit_cjk_transform,
    _fit_cjk_transform_xy,
    _fit_latin_metrics,
    _ribbi_names,
    cjk_cell_span,
    is_cell_connecting,
    is_cjk,
    update_metadata,
)
from monatendard.sources import VARIANTS, make_variant
from monatendard.verify import _check_ribbi_metadata


@pytest.mark.parametrize(
    "codepoint",
    [0x1100, 0x3042, 0x30A2, 0x3131, 0x321C, 0x339E, 0xAC00, 0xD7A3, 0x4E00, 0xFF01, 0xFFE6],
)
def test_wide_cjk_ranges_have_two_cell_span(codepoint: int) -> None:
    assert is_cjk(codepoint)
    assert cjk_cell_span(codepoint) == 2


@pytest.mark.parametrize("codepoint", [0x203B, 0xFF61, 0xFFA1, 0xFFDC, 0xFFE8])
def test_halfwidth_cjk_and_reference_mark_have_single_cell_span(codepoint: int) -> None:
    assert is_cjk(codepoint)
    assert cjk_cell_span(codepoint) == 1


@pytest.mark.parametrize("codepoint", [0x20, 0x41, 0x391, 0xFF00, 0xFFDF, 0x1F600])
def test_non_cjk_ranges_are_not_selected(codepoint: int) -> None:
    assert not is_cjk(codepoint)
    assert cjk_cell_span(codepoint) is None


def test_cjk_transform_centers_outline_in_two_cell_advance() -> None:
    scale, shift = _fit_cjk_transform(
        (100, -200, 900, 800),
        normalized_scale=2.0,
        target_advance=2220,
        safe_ymin=-500,
        safe_ymax=1600,
    )
    transformed_center = ((100 + 900) / 2) * scale + shift
    assert transformed_center == pytest.approx(1110)
    assert 0 < scale <= 2.0


def test_cjk_transform_supports_independent_horizontal_and_vertical_scale() -> None:
    scale_x, scale_y, shift = _fit_cjk_transform_xy(
        (100, -200, 900, 800),
        normalized_scale_x=2.24,
        normalized_scale_y=2.16,
        target_advance=2220,
        safe_ymin=-1000,
        safe_ymax=2000,
    )
    transformed_center = ((100 + 900) / 2) * scale_x + shift
    assert transformed_center == pytest.approx(1110)
    assert scale_x == pytest.approx(2.24)
    assert scale_y == pytest.approx(2.16)


def test_latin_outline_is_centered_in_wider_advance() -> None:
    advance, left_side_bearing, shift = _fit_latin_metrics(
        1240,
        100,
        outline_scale=0.925,
        advance_scale=1180 / 1240,
    )
    assert advance == 1180
    assert shift == pytest.approx(16.5)
    assert left_side_bearing == 109


@pytest.mark.parametrize(
    "codepoint",
    [0x2500, 0x257F, 0x2580, 0x259F, 0xE0B0, 0xE0D4],
)
def test_cell_connecting_ranges_are_selected(codepoint: int) -> None:
    assert is_cell_connecting(codepoint)


@pytest.mark.parametrize("codepoint", [0x249F, 0x25A0, 0xE0A3, 0xE0D5])
def test_non_connecting_ranges_are_not_selected(codepoint: int) -> None:
    assert not is_cell_connecting(codepoint)


def test_connecting_outline_keeps_source_overlap_at_target_cell_edges() -> None:
    advance_scale = 1200 / 1240
    target_advance, _, shift = _fit_latin_metrics(
        1240,
        -10,
        outline_scale=advance_scale,
        advance_scale=advance_scale,
    )
    transformed_xmin = -10 * advance_scale + shift
    transformed_xmax = 1250 * advance_scale + shift

    assert target_advance == 1200
    assert transformed_xmin < 0
    assert transformed_xmax > target_advance


def _minimal_ttf() -> TTFont:
    builder = FontBuilder(2000, isTTF=True)
    builder.setupGlyphOrder([".notdef"])
    builder.setupCharacterMap({})
    pen = TTGlyphPen(None)
    builder.setupGlyf({".notdef": pen.glyph()})
    builder.setupHorizontalMetrics({".notdef": (1240, 0)})
    builder.setupHorizontalHeader(ascent=1990, descent=-500)
    builder.setupNameTable({"familyName": "Monaspace Neon Frozen", "styleName": "Regular"})
    builder.font["name"].setName("Monaspace Neon Frozen Regular", 18, 3, 1, 0x409)
    builder.font["name"].setName('printf("Hello, Monaspace Neon Frozen!")', 19, 3, 1, 0x409)
    builder.setupOS2()
    builder.setupPost()
    return builder.font


def test_update_metadata_normalizes_ribbi_names_and_style_flags() -> None:
    for variant in VARIANTS:
        font = _minimal_ttf()
        update_metadata(font, variant, "0.3.1")
        assert _check_ribbi_metadata(font, enforce_gdi_length=True) == []
        id1 = font["name"].getName(1, 3, 1, 0x409).toUnicode()
        id2 = font["name"].getName(2, 3, 1, 0x409).toUnicode()
        id16 = font["name"].getName(16, 3, 1, 0x409).toUnicode()
        id17 = font["name"].getName(17, 3, 1, 0x409).toUnicode()
        assert (id1, id2) == _ribbi_names("Monatendard", variant)
        assert id16 == "Monatendard"
        assert id17 == variant.subfamily_name
        assert font["OS/2"].usWeightClass == variant.css_weight

    extrabold = _minimal_ttf()
    update_metadata(extrabold, make_variant("ExtraBold", "normal"), "0.3.1")
    assert extrabold["head"].macStyle == 0
    assert extrabold["OS/2"].fsSelection == (1 << 6) | (1 << 7)

    bold_italic = _minimal_ttf()
    update_metadata(bold_italic, make_variant("Bold", "italic"), "0.3.1")
    assert bold_italic["head"].macStyle == (1 << 0) | (1 << 1)
    assert bold_italic["OS/2"].fsSelection == (1 << 0) | (1 << 5) | (1 << 7)

