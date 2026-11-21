from __future__ import annotations

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from monatendard.builder import update_metadata
from monatendard.nerd import (
    NERD_FAMILY_NAME,
    NERD_FILE_PREFIX,
    NERD_ICON_VERTICAL_OFFSET_EM,
    REQUIRED_NERD_CODEPOINTS,
    REQUIRED_NERD_NON_PUA_CODEPOINTS,
    _vertical_center_shift,
    is_nerd_symbol,
    is_private_use,
    update_nerd_metadata,
)
from monatendard.sources import VARIANTS
from monatendard.verify import _check_ribbi_metadata


def test_nerd_family_and_files_are_separate_from_standard_family() -> None:
    assert NERD_FAMILY_NAME == "Monatendard Nerd Font Mono"
    assert NERD_FILE_PREFIX == "MonatendardNFM"


def test_required_prompt_icons_are_private_use_codepoints() -> None:
    assert {0xE0A0, 0xE0B0, 0xF00C, 0xF07C, 0xF126, 0xF489, 0xF0001}.issubset(
        REQUIRED_NERD_CODEPOINTS
    )
    assert all(is_private_use(codepoint) for codepoint in REQUIRED_NERD_CODEPOINTS)
    assert all(is_nerd_symbol(codepoint) for codepoint in REQUIRED_NERD_CODEPOINTS)
    assert all(is_nerd_symbol(codepoint) for codepoint in REQUIRED_NERD_NON_PUA_CODEPOINTS)
    assert not is_private_use(ord("A"))
    assert not is_private_use(0xAC00)
    assert not is_nerd_symbol(ord("A"))
    assert not is_nerd_symbol(0xAC00)


def test_nerd_icon_vertical_center_uses_optical_offset_above_x_height() -> None:
    bounds = (1, -182, 2049, 1410)
    scale = 1101 / 2048
    target_center = 513.5 + 2000 * NERD_ICON_VERTICAL_OFFSET_EM
    shift = _vertical_center_shift(bounds, scale=scale, target_center=target_center)
    transformed_center = ((bounds[1] + bounds[3]) / 2) * scale + shift
    assert transformed_center == target_center


def _minimal_ttf() -> TTFont:
    builder = FontBuilder(2000, isTTF=True)
    builder.setupGlyphOrder([".notdef"])
    builder.setupCharacterMap({})
    pen = TTGlyphPen(None)
    builder.setupGlyf({".notdef": pen.glyph()})
    builder.setupHorizontalMetrics({".notdef": (1240, 0)})
    builder.setupHorizontalHeader(ascent=1990, descent=-500)
    builder.setupNameTable({"familyName": "Monaspace Neon Frozen", "styleName": "Regular"})
    builder.setupOS2()
    builder.setupPost()
    return builder.font


def test_update_nerd_metadata_follows_ribbi_and_gdi_length_limit() -> None:
    for variant in VARIANTS:
        font = _minimal_ttf()
        update_metadata(font, variant, "0.3.1")
        update_nerd_metadata(font, variant, "0.3.1")
        assert _check_ribbi_metadata(font, enforce_gdi_length=True) == []
        id1 = font["name"].getName(1, 3, 1, 0x409).toUnicode()
        id16 = font["name"].getName(16, 3, 1, 0x409).toUnicode()
        assert len(id1) <= 31
        assert id16 == NERD_FAMILY_NAME
        if variant.weight_name in ("Regular", "Bold"):
            assert id1 == NERD_FAMILY_NAME
        else:
            assert id1 == f"Monatendard NFM {variant.weight_name}"
