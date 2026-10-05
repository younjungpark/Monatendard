from __future__ import annotations

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import ttProgram

from monatendard.builder import (
    _fit_cjk_transform,
    load_profile,
    profile_names,
    scale_latin_horizontally,
)
from monatendard.verify import _check_latin_hinting

UNITS_PER_EM = 2000
ADVANCE = 1240
SAMPLE = " A0Hinmwao"


def test_default_profile_matches_released_family() -> None:
    profile = load_profile()
    assert profile.family == "Monatendard"
    assert profile.file_prefix == "Monatendard"
    assert profile.nerd_family == "Monatendard Nerd Font Mono"
    assert profile.nerd_file_prefix == "MonatendardNFM"
    assert not profile.keeps_latin_outlines


@pytest.mark.parametrize(
    ("name", "family", "file_prefix", "cjk_scale"),
    [
        ("proto-a", "Monatendard Proto A", "MonatendardProtoA", 1.15),
        ("proto-b", "Monatendard Proto B", "MonatendardProtoB", 1.07),
    ],
)
def test_prototype_profiles_keep_latin_and_scale_hangul_uniformly(
    name: str, family: str, file_prefix: str, cjk_scale: float
) -> None:
    profile = load_profile(name)
    assert profile.family == family
    assert profile.file_prefix == file_prefix
    assert profile.nerd_family == f"{family} Nerd Font Mono"
    assert profile.nerd_file_prefix == f"{file_prefix}NFM"
    assert profile.keeps_latin_outlines
    assert profile.latin_advance_em == 0.620
    assert profile.cjk_horizontal_scale == profile.cjk_vertical_scale == cjk_scale
    assert name in profile_names()


def test_proto_c_keeps_released_latin_and_scales_hangul_uniformly() -> None:
    profile = load_profile("proto-c")
    released = load_profile()
    assert profile.family == "Monatendard Proto C"
    assert not profile.keeps_latin_outlines
    assert profile.latin_horizontal_scale == released.latin_horizontal_scale
    assert profile.latin_advance_em == released.latin_advance_em
    assert profile.cjk_horizontal_scale == profile.cjk_vertical_scale == 1.15


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="profile"):
        load_profile("proto-z")


def test_uniform_cjk_transform_shrinks_tall_glyph_on_both_axes_together() -> None:
    scale, shift = _fit_cjk_transform(
        (100, -100, 1900, 1900),
        normalized_scale=2000 / 2048 * 1.19,
        target_advance=2 * ADVANCE,
        safe_ymin=-400,
        safe_ymax=1890,
    )
    assert scale == pytest.approx(1890 / 1900)
    assert ((100 + 1900) / 2) * scale + shift == pytest.approx(ADVANCE)


def _hinted_font() -> TTFont:
    glyph_order = [".notdef", *(f"g{index}" for index in range(len(SAMPLE)))]
    builder = FontBuilder(UNITS_PER_EM, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap({ord(char): f"g{index}" for index, char in enumerate(SAMPLE)})
    glyphs = {}
    for name in glyph_order:
        pen = TTGlyphPen(None)
        pen.moveTo((100, 0))
        pen.lineTo((100, 1000))
        pen.lineTo((1100, 1000))
        pen.closePath()
        glyph = pen.glyph()
        program = ttProgram.Program()
        program.fromBytecode(b"\xb0\x00")  # PUSHB[0] 0
        glyph.program = program
        glyphs[name] = glyph
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (ADVANCE, 100) for name in glyph_order})
    builder.setupHorizontalHeader(ascent=1890, descent=-400)
    builder.setupOS2()
    builder.setupPost()
    for tag in ("fpgm", "prep"):
        table = newTable(tag)
        table.program = ttProgram.Program()
        table.program.fromBytecode(b"\xb0\x00")
        builder.font[tag] = table
    cvt = newTable("cvt ")
    cvt.values = [0]
    builder.font["cvt "] = cvt
    return builder.font


def test_unscaled_latin_keeps_outlines_and_hinting() -> None:
    font = _hinted_font()
    pristine = _hinted_font()
    before = font["glyf"]["g1"].compile(font["glyf"])

    advance = scale_latin_horizontally(font, pristine, 1.0, ADVANCE / UNITS_PER_EM)

    assert advance == ADVANCE
    assert font["glyf"]["g1"].compile(font["glyf"]) == before
    assert _check_latin_hinting(font, font.getBestCmap()) == []


def test_compressed_latin_drops_hinting() -> None:
    font = _hinted_font()
    pristine = _hinted_font()

    advance = scale_latin_horizontally(font, pristine, 0.925, 0.600)

    assert advance == 1200
    errors = _check_latin_hinting(font, font.getBestCmap())
    assert any("fpgm" in error for error in errors)
    assert any("'A'" in error for error in errors)
