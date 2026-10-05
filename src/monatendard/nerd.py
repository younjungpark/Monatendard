"""완성된 Monatendard에 Nerd Fonts Symbols Only 글리프를 병합한다."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from fontTools.ttLib import TTFont

from monatendard.builder import (
    DEFAULT_OUTPUT_DIR,
    BuildProfile,
    _fit_cjk_transform,
    _glyph_bounds,
    _redraw_scaled_glyph,
    _safe_vertical_bounds,
    _set_name,
    derive_monospace_advance,
    load_profile,
)
from monatendard.sources import (
    NERD_FONTS_DIR,
    NERD_SYMBOLS_FILENAME,
    Variant,
)

logger = logging.getLogger(__name__)

NERD_FAMILY_NAME = "Monatendard Nerd Font Mono"
NERD_FILE_PREFIX = "MonatendardNFM"
DEFAULT_NERD_OUTPUT_DIR = DEFAULT_OUTPUT_DIR / "nerd-ttf"
DEFAULT_STANDARD_INPUT_DIR = DEFAULT_OUTPUT_DIR / "ttf"
NERD_ICON_VERTICAL_OFFSET_EM = 0.025
REQUIRED_NERD_CODEPOINTS = (
    0xE0A0,
    0xE0B0,
    0xF00C,
    0xF07C,
    0xF126,
    0xF489,
    0xF0001,
)
CENTERED_NERD_CODEPOINTS = (0xF00C, 0xF07C, 0xF126, 0xF489, 0xF0001)


@dataclass(frozen=True)
class NerdBuildStats:
    """한 Nerd 변형의 변환 결과."""

    output_path: Path
    mapped_symbol_count: int
    latin_advance: int
    hangul_advance: int


def is_private_use(codepoint: int) -> bool:
    """Unicode 사적 사용 영역인지 판단한다."""
    return (
        0xE000 <= codepoint <= 0xF8FF
        or 0xF0000 <= codepoint <= 0xFFFFD
        or 0x100000 <= codepoint <= 0x10FFFD
    )


def _update_unicode_cmaps(font: TTFont, codepoint: int, glyph_name: str) -> None:
    for subtable in font["cmap"].tables:
        if subtable.format == 14 or not subtable.isUnicode():
            continue
        if codepoint <= 0xFFFF or subtable.format in (12, 13):
            subtable.cmap[codepoint] = glyph_name


def _vertical_center_shift(
    bounds: tuple[float, float, float, float] | None,
    *,
    scale: float,
    target_center: float,
) -> float:
    """축소된 아이콘의 세로 중심을 기준 글리프 중심에 맞춘다."""
    if bounds is None:
        return 0
    source_center = (bounds[1] + bounds[3]) / 2
    return target_center - source_center * scale


def merge_nerd_symbols(font: TTFont, symbols_font: TTFont, latin_advance: int) -> int:
    """기존 글리프는 보존하고 비어 있는 Nerd PUA 글리프를 한 칸 폭으로 복사한다."""
    source_cmap = symbols_font.getBestCmap()
    target_cmap = font.getBestCmap()
    if not source_cmap:
        raise ValueError("Nerd Fonts Symbols Only cmap을 읽을 수 없습니다.")
    if not target_cmap:
        raise ValueError("Monatendard cmap을 읽을 수 없습니다.")

    source_glyph_set = symbols_font.getGlyphSet()
    target_glyf = font["glyf"]
    target_hmtx = font["hmtx"]
    reference_name = target_cmap.get(ord("x"))
    reference_bounds = (
        _glyph_bounds(font.getGlyphSet(), reference_name) if reference_name is not None else None
    )
    if reference_bounds is None:
        raise ValueError("Nerd 아이콘 세로 중심 기준인 소문자 x를 읽을 수 없습니다.")
    units_per_em = cast("Any", font["head"]).unitsPerEm
    target_center_y = (
        (reference_bounds[1] + reference_bounds[3]) / 2
        + units_per_em * NERD_ICON_VERTICAL_OFFSET_EM
    )
    safe_ymin, safe_ymax = _safe_vertical_bounds(font)
    normalized_scale = (
        units_per_em / cast("Any", symbols_font["head"]).unitsPerEm
    )

    mapped = 0
    copied_names: dict[str, str] = {}
    for codepoint, source_name in sorted(source_cmap.items()):
        if not is_private_use(codepoint) or codepoint in target_cmap:
            continue
        if source_name not in source_glyph_set:
            continue

        target_name = copied_names.get(source_name)
        if target_name is None:
            target_name = f"mdnfuni{codepoint:06X}"
            source_bounds = _glyph_bounds(source_glyph_set, source_name)
            scale, shift_x = _fit_cjk_transform(
                source_bounds,
                normalized_scale=normalized_scale,
                target_advance=latin_advance,
                safe_ymin=safe_ymin,
                safe_ymax=safe_ymax,
            )
            shift_y = _vertical_center_shift(
                source_bounds,
                scale=scale,
                target_center=target_center_y,
            )
            target_glyf[target_name] = _redraw_scaled_glyph(
                source_glyph_set,
                source_name,
                scale,
                scale,
                shift_x,
                shift_y,
            )
            left_side_bearing = (
                round(source_bounds[0] * scale + shift_x)
                if source_bounds is not None
                else 0
            )
            target_hmtx.metrics[target_name] = (latin_advance, left_side_bearing)
            copied_names[source_name] = target_name

        _update_unicode_cmaps(font, codepoint, target_name)
        target_cmap[codepoint] = target_name
        mapped += 1

    font.setGlyphOrder(list(target_glyf.glyphOrder))
    return mapped


def update_nerd_metadata(
    font: TTFont,
    variant: Variant,
    project_version: str,
    *,
    family_name: str = NERD_FAMILY_NAME,
    file_prefix: str = NERD_FILE_PREFIX,
) -> None:
    """일반판과 충돌하지 않는 Nerd 전용 패밀리 이름을 설정한다."""
    postscript_subfamily = variant.subfamily_name.replace(" ", "")
    postscript_name = f"{file_prefix}-{postscript_subfamily}"
    values = {
        1: family_name,
        2: variant.subfamily_name,
        3: f"{postscript_name};{project_version}",
        4: f"{family_name} {variant.subfamily_name}",
        5: f"Version {project_version}",
        6: postscript_name,
        13: (
            "Monatendard is distributed under the SIL Open Font License, Version 1.1. "
            "Nerd Fonts Symbols Only glyphs are distributed under the MIT License."
        ),
        14: "https://github.com/younjungpark/Monatendard",
        16: family_name,
        17: variant.subfamily_name,
    }
    for name_id, value in values.items():
        _set_name(font, name_id, value)


def build_nerd_font(
    variant: Variant,
    *,
    input_dir: Path = DEFAULT_STANDARD_INPUT_DIR,
    output_dir: Path = DEFAULT_NERD_OUTPUT_DIR,
    symbols_path: Path = NERD_FONTS_DIR / NERD_SYMBOLS_FILENAME,
    project_version: str | None = None,
    profile: BuildProfile | None = None,
) -> NerdBuildStats:
    """기존 Monatendard 한 변형에 Nerd 아이콘을 병합한다."""
    profile = profile or load_profile()
    version = project_version or profile.version
    base_path = input_dir / f"{profile.file_prefix}-{variant.output_suffix}.ttf"
    for path in (base_path, symbols_path):
        if not path.exists():
            raise FileNotFoundError(
                "Nerd 변형 입력이 없습니다. 먼저 `monatendard fetch`와 "
                f"`monatendard build`를 실행하세요: {path}"
            )

    target = TTFont(base_path, recalcTimestamp=False)
    symbols = TTFont(symbols_path, recalcTimestamp=False)
    try:
        latin_advance = derive_monospace_advance(target)
        mapped = merge_nerd_symbols(target, symbols, latin_advance)
        update_nerd_metadata(
            target,
            variant,
            version,
            family_name=profile.nerd_family,
            file_prefix=profile.nerd_file_prefix,
        )
        target.recalcTimestamp = False
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{profile.nerd_file_prefix}-{variant.output_suffix}.ttf"
        target.save(output_path, reorderTables=False)
    finally:
        target.close()
        symbols.close()

    logger.info(
        "%s Nerd 변형 생성: 아이콘=%d, 영문 advance=%d, 한글 advance=%d",
        variant.output_suffix,
        mapped,
        latin_advance,
        latin_advance * 2,
    )
    return NerdBuildStats(output_path, mapped, latin_advance, latin_advance * 2)


def build_nerd_variants(
    variants: list[Variant],
    *,
    input_dir: Path = DEFAULT_STANDARD_INPUT_DIR,
    output_dir: Path = DEFAULT_NERD_OUTPUT_DIR,
    profile: BuildProfile | None = None,
) -> list[NerdBuildStats]:
    """선택한 모든 변형의 Nerd 전용 TTF를 생성한다."""
    profile = profile or load_profile()
    return [
        build_nerd_font(variant, input_dir=input_dir, output_dir=output_dir, profile=profile)
        for variant in variants
    ]
