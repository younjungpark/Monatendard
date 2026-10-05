"""Monaspace Neon을 설정한 배율로 조정하고 Pretendard 한글을 병합한다."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from monatendard.sources import (
    LOCK_PATH,
    MONASPACE_DIR,
    PRETENDARD_DIR,
    VARIANTS,
    Variant,
    load_lock,
)

logger = logging.getLogger(__name__)

FAMILY_NAME = "Monatendard"
DEFAULT_OUTPUT_DIR = Path("fonts")
REPRODUCIBLE_TIMESTAMP = 2_082_844_800  # 1970-01-01, OpenType의 1904 epoch 기준
ASCII_SAMPLE = tuple(ord(char) for char in " A0Hinmw")
REQUIRED_HANGUL = (0x1100, 0x1161, 0x3131, 0x314F, 0xAC00, 0xD55C, 0xAE00, 0xD7A3)
CELL_CONNECTING_RANGES = (
    (0x2500, 0x259F),  # Box Drawing, Block Elements
    (0xE0B0, 0xE0D4),  # Powerline separators and extra symbols
)
CHOSEONG_MAP = {
    0x1100: 0x3131,
    0x1101: 0x3132,
    0x1102: 0x3134,
    0x1103: 0x3137,
    0x1104: 0x3138,
    0x1105: 0x3139,
    0x1106: 0x3141,
    0x1107: 0x3142,
    0x1108: 0x3143,
    0x1109: 0x3145,
    0x110A: 0x3146,
    0x110B: 0x3147,
    0x110C: 0x3148,
    0x110D: 0x3149,
    0x110E: 0x314A,
    0x110F: 0x314B,
    0x1110: 0x314C,
    0x1111: 0x314D,
    0x1112: 0x314E,
}
JUNGSEONG_MAP = {code: 0x314F + (code - 0x1161) for code in range(0x1161, 0x1176)}
JONGSEONG_MAP = {
    0x11A8: 0x3131,
    0x11A9: 0x3132,
    0x11AA: 0x3133,
    0x11AB: 0x3134,
    0x11AC: 0x3135,
    0x11AD: 0x3136,
    0x11AE: 0x3137,
    0x11AF: 0x3139,
    0x11B0: 0x313A,
    0x11B1: 0x313B,
    0x11B2: 0x313C,
    0x11B3: 0x313D,
    0x11B4: 0x313E,
    0x11B5: 0x313F,
    0x11B6: 0x3140,
    0x11B7: 0x3141,
    0x11B8: 0x3142,
    0x11B9: 0x3144,
    0x11BA: 0x3145,
    0x11BB: 0x3146,
    0x11BC: 0x3147,
    0x11BD: 0x3148,
    0x11BE: 0x314A,
    0x11BF: 0x314B,
    0x11C0: 0x314C,
    0x11C1: 0x314D,
    0x11C2: 0x314E,
}
JAMO_COMPATIBILITY_MAP = CHOSEONG_MAP | JUNGSEONG_MAP | JONGSEONG_MAP


DEFAULT_PROFILE = "default"


@dataclass(frozen=True)
class BuildProfile:
    """패밀리 이름과 영문·한글 배율 묶음. 기본값은 lock의 `[project]`다."""

    name: str
    family: str
    version: str
    latin_horizontal_scale: float
    latin_advance_em: float
    cjk_horizontal_scale: float
    cjk_vertical_scale: float

    @property
    def file_prefix(self) -> str:
        return self.family.replace(" ", "")

    @property
    def nerd_family(self) -> str:
        return f"{self.family} Nerd Font Mono"

    @property
    def nerd_file_prefix(self) -> str:
        return f"{self.file_prefix}NFM"

    @property
    def keeps_latin_outlines(self) -> bool:
        """영문 윤곽을 누르지 않는 설정인지 판단한다. 셀 폭은 빌드 시 원본과 대조한다."""
        return self.latin_horizontal_scale == 1.0


def load_profile(name: str = DEFAULT_PROFILE, lock: dict | None = None) -> BuildProfile:
    """lock 파일에서 이름으로 빌드 설정을 읽는다."""
    lock = lock or load_lock(LOCK_PATH)
    if name == DEFAULT_PROFILE:
        values = lock["project"]
    else:
        prototypes = lock.get("prototypes", {})
        if name not in prototypes:
            raise ValueError(
                f"지원하지 않는 profile: {name}. "
                f"지원 목록: {', '.join([DEFAULT_PROFILE, *prototypes])}"
            )
        values = prototypes[name]
    return BuildProfile(
        name=name,
        family=str(values["family"]),
        version=str(values["version"]),
        latin_horizontal_scale=float(values["latin_horizontal_scale"]),
        latin_advance_em=float(values["latin_advance_em"]),
        cjk_horizontal_scale=float(values["cjk_horizontal_scale"]),
        cjk_vertical_scale=float(values["cjk_vertical_scale"]),
    )


def profile_names(lock: dict | None = None) -> list[str]:
    lock = lock or load_lock(LOCK_PATH)
    return [DEFAULT_PROFILE, *lock.get("prototypes", {})]


@dataclass(frozen=True)
class BuildStats:
    """한 파일의 변환 결과."""

    output_path: Path
    copied_cjk_count: int
    latin_advance: int
    hangul_advance: int


def is_cjk(codepoint: int) -> bool:
    """Pretendard에서 가져올 한글 및 CJK 관련 범위인지 판단한다."""
    return (
        0x1100 <= codepoint <= 0x11FF
        or 0x3130 <= codepoint <= 0x318F
        or 0xA960 <= codepoint <= 0xA97F
        or 0xAC00 <= codepoint <= 0xD7A3
        or 0xD7B0 <= codepoint <= 0xD7FF
        or 0x3000 <= codepoint <= 0x303F
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xFF00 <= codepoint <= 0xFFEF
    )


def is_cell_connecting(codepoint: int) -> bool:
    """인접 셀의 윤곽과 끊김 없이 맞닿아야 하는 문자인지 판단한다."""
    return any(start <= codepoint <= end for start, end in CELL_CONNECTING_RANGES)


def derive_monospace_advance(font: TTFont) -> int:
    """대표 ASCII가 공유하는 advance를 구한다."""
    cmap = font.getBestCmap()
    if not cmap:
        raise ValueError("Monaspace cmap을 읽을 수 없습니다.")
    hmtx = font["hmtx"].metrics
    widths = {
        hmtx[cmap[codepoint]][0]
        for codepoint in ASCII_SAMPLE
        if codepoint in cmap and cmap[codepoint] in hmtx
    }
    if len(widths) != 1:
        raise ValueError(f"Monaspace ASCII advance가 단일 값이 아닙니다: {sorted(widths)}")
    return widths.pop()


def _redraw_scaled_glyph(
    source_glyph_set: Any,
    glyph_name: str,
    scale_x: float,
    scale_y: float,
    shift_x: float = 0,
    shift_y: float = 0,
) -> Any:
    recording = DecomposingRecordingPen(source_glyph_set)
    source_glyph_set[glyph_name].draw(recording)
    target_pen = TTGlyphPen(None)
    transform_pen = TransformPen(
        target_pen,
        (scale_x, 0, 0, scale_y, shift_x, shift_y),
    )
    recording.replay(transform_pen)
    return target_pen.glyph()


def _fit_latin_metrics(
    advance: int,
    left_side_bearing: int,
    *,
    outline_scale: float,
    advance_scale: float,
) -> tuple[int, int, float]:
    target_advance = round(advance * advance_scale)
    shift_x = (target_advance - round(advance * outline_scale)) / 2
    return target_advance, round(left_side_bearing * outline_scale + shift_x), shift_x


def scale_latin_horizontally(
    font: TTFont,
    pristine_font: TTFont,
    outline_scale: float,
    advance_em: float,
    *,
    connecting_font: TTFont | None = None,
) -> int:
    """Monaspace 윤곽을 축소하고 지정한 advance 안에 중앙 정렬한다.

    배율이 1이고 advance가 원본과 같으면 윤곽과 힌팅을 그대로 둔다. 이때도 이탤릭의
    셀 접합 글리프는 정체에서 가져와 다시 그린다.
    """
    if not 0 < outline_scale <= 1:
        raise ValueError(f"가로 배율은 0보다 크고 1 이하여야 합니다: {outline_scale}")
    if not 0 < advance_em <= 1:
        raise ValueError(f"영문 advance는 0em보다 크고 1em 이하여야 합니다: {advance_em}")

    source_glyph_set = pristine_font.getGlyphSet()
    source_hmtx = pristine_font["hmtx"]
    connecting_source = connecting_font or pristine_font
    connecting_glyph_set = connecting_source.getGlyphSet()
    connecting_hmtx = connecting_source["hmtx"]
    glyf = font["glyf"]
    hmtx = font["hmtx"]
    source_advance = derive_monospace_advance(pristine_font)
    target_advance = round(cast("Any", font["head"]).unitsPerEm * advance_em)
    advance_scale = target_advance / source_advance
    keeps_outlines = outline_scale == 1 and target_advance == source_advance
    target_cmap = pristine_font.getBestCmap() or {}
    connecting_cmap = connecting_source.getBestCmap() or {}
    connecting_glyphs = {
        target_name: connecting_cmap[codepoint]
        for codepoint, target_name in target_cmap.items()
        if is_cell_connecting(codepoint) and codepoint in connecting_cmap
    }
    for glyph_name in pristine_font.getGlyphOrder():
        connecting_name = connecting_glyphs.get(glyph_name)
        if keeps_outlines and (connecting_name is None or connecting_source is pristine_font):
            continue
        if connecting_name is None:
            glyph_source_set = source_glyph_set
            source_name = glyph_name
            advance, left_side_bearing = source_hmtx.metrics[source_name]
            glyph_outline_scale = outline_scale
        else:
            glyph_source_set = connecting_glyph_set
            source_name = connecting_name
            advance, left_side_bearing = connecting_hmtx.metrics[source_name]
            glyph_outline_scale = advance_scale
        scaled_advance, scaled_lsb, shift_x = _fit_latin_metrics(
            advance,
            left_side_bearing,
            outline_scale=glyph_outline_scale,
            advance_scale=advance_scale,
        )
        glyf[glyph_name] = _redraw_scaled_glyph(
            glyph_source_set, source_name, glyph_outline_scale, 1.0, shift_x
        )
        hmtx.metrics[glyph_name] = (scaled_advance, scaled_lsb)

    if not keeps_outlines:
        for hint_table in ("fpgm", "prep", "cvt "):
            if hint_table in font:
                del font[hint_table]

    latin_advance = derive_monospace_advance(font)
    cast("Any", font["hhea"]).advanceWidthMax = max(width for width, _ in hmtx.metrics.values())
    cast("Any", font["OS/2"]).xAvgCharWidth = latin_advance
    return latin_advance


def _glyph_bounds(glyph_set: Any, glyph_name: str) -> tuple[float, float, float, float] | None:
    pen = BoundsPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    return pen.bounds


def _safe_vertical_bounds(font: TTFont) -> tuple[int, int]:
    hhea = cast("Any", font["hhea"])
    os2 = cast("Any", font["OS/2"])
    minimum = max(int(hhea.descent), int(os2.sTypoDescender))
    maximum = min(int(hhea.ascent), int(os2.sTypoAscender))
    if minimum >= maximum:
        return int(hhea.descent), int(hhea.ascent)
    return minimum, maximum


def _fit_cjk_transform(
    bounds: tuple[float, float, float, float] | None,
    *,
    normalized_scale: float,
    target_advance: int,
    safe_ymin: int,
    safe_ymax: int,
) -> tuple[float, float]:
    """원본 비율을 유지하면서 두 영문 칸 안에 중앙 정렬한다."""
    if bounds is None:
        return normalized_scale, 0

    xmin, ymin, xmax, ymax = bounds
    guard = max(8, round(target_advance * 0.02))
    scale = normalized_scale
    source_width = xmax - xmin
    if source_width > 0:
        scale = min(scale, (target_advance - guard * 2) / source_width)
    if ymax > 0:
        scale = min(scale, safe_ymax / ymax)
    if ymin < 0 and safe_ymin < 0:
        scale = min(scale, safe_ymin / ymin)
    if scale <= 0:
        raise ValueError(f"CJK 글리프를 셀에 맞출 수 없습니다: {bounds}")

    center = ((xmin + xmax) / 2) * scale
    shift_x = (target_advance / 2) - center
    return scale, shift_x


def _fit_cjk_transform_xy(
    bounds: tuple[float, float, float, float] | None,
    *,
    normalized_scale_x: float,
    normalized_scale_y: float,
    target_advance: int,
    safe_ymin: int,
    safe_ymax: int,
) -> tuple[float, float, float]:
    """두 영문 칸 안에서 CJK 윤곽의 가로·세로 배율을 따로 맞춘다."""
    if bounds is None:
        return normalized_scale_x, normalized_scale_y, 0

    xmin, ymin, xmax, ymax = bounds
    guard = max(8, round(target_advance * 0.02))
    scale_x = normalized_scale_x
    source_width = xmax - xmin
    if source_width > 0:
        scale_x = min(scale_x, (target_advance - guard * 2) / source_width)

    scale_y = normalized_scale_y
    if ymax > 0:
        scale_y = min(scale_y, safe_ymax / ymax)
    if ymin < 0 and safe_ymin < 0:
        scale_y = min(scale_y, safe_ymin / ymin)
    if scale_x <= 0 or scale_y <= 0:
        raise ValueError(f"CJK 글리프를 셀에 맞출 수 없습니다: {bounds}")

    center = ((xmin + xmax) / 2) * scale_x
    shift_x = (target_advance / 2) - center
    return scale_x, scale_y, shift_x


def _update_unicode_cmaps(font: TTFont, codepoint: int, glyph_name: str) -> None:
    for subtable in font["cmap"].tables:
        if subtable.format == 14 or not subtable.isUnicode():
            continue
        if codepoint <= 0xFFFF or subtable.format in (12, 13):
            subtable.cmap[codepoint] = glyph_name


def merge_cjk(
    font: TTFont,
    cjk_font: TTFont,
    latin_advance: int,
    horizontal_scale: float,
    vertical_scale: float,
) -> int:
    """Pretendard의 한글/CJK 글리프를 정확히 두 영문 칸 advance로 복사한다."""
    if horizontal_scale <= 0 or vertical_scale <= 0:
        raise ValueError(
            f"CJK 시각 배율은 0보다 커야 합니다: {horizontal_scale}, {vertical_scale}"
        )

    cmap = cjk_font.getBestCmap()
    if not cmap:
        raise ValueError("Pretendard cmap을 읽을 수 없습니다.")

    cjk_glyph_set = cjk_font.getGlyphSet()
    target_glyf = font["glyf"]
    target_hmtx = font["hmtx"]
    target_advance = latin_advance * 2
    safe_ymin, safe_ymax = _safe_vertical_bounds(font)
    normalized_scale = (
        cast("Any", font["head"]).unitsPerEm / cast("Any", cjk_font["head"]).unitsPerEm
    )

    uniform = horizontal_scale == vertical_scale
    copied = 0
    codepoints = {code for code in cmap if is_cjk(code)}
    codepoints.update(JAMO_COMPATIBILITY_MAP)
    for codepoint in sorted(codepoints):
        source_codepoint = JAMO_COMPATIBILITY_MAP.get(codepoint, codepoint)
        source_name = cmap.get(source_codepoint)
        if source_name is None:
            continue
        if source_name not in cjk_glyph_set:
            continue
        target_name = f"mduni{codepoint:04X}"
        source_bounds = _glyph_bounds(cjk_glyph_set, source_name)
        if uniform:
            # 셀을 넘는 글자는 가로·세로를 함께 줄여 원래 비율을 지킨다.
            scale_x, shift_x = _fit_cjk_transform(
                source_bounds,
                normalized_scale=normalized_scale * horizontal_scale,
                target_advance=target_advance,
                safe_ymin=safe_ymin,
                safe_ymax=safe_ymax,
            )
            scale_y = scale_x
        else:
            scale_x, scale_y, shift_x = _fit_cjk_transform_xy(
                source_bounds,
                normalized_scale_x=normalized_scale * horizontal_scale,
                normalized_scale_y=normalized_scale * vertical_scale,
                target_advance=target_advance,
                safe_ymin=safe_ymin,
                safe_ymax=safe_ymax,
            )
        glyph = _redraw_scaled_glyph(
            cjk_glyph_set, source_name, scale_x, scale_y, shift_x
        )
        target_glyf[target_name] = glyph

        left_side_bearing = (
            round(source_bounds[0] * scale_x + shift_x) if source_bounds is not None else 0
        )
        target_hmtx.metrics[target_name] = (target_advance, left_side_bearing)
        _update_unicode_cmaps(font, codepoint, target_name)
        copied += 1

    font.setGlyphOrder(list(target_glyf.glyphOrder))

    target_os2 = cast("Any", font["OS/2"])
    source_os2 = cast("Any", cjk_font["OS/2"])
    for field in (
        "ulUnicodeRange1",
        "ulUnicodeRange2",
        "ulUnicodeRange3",
        "ulUnicodeRange4",
        "ulCodePageRange1",
        "ulCodePageRange2",
    ):
        target_value = int(getattr(target_os2, field, 0))
        source_value = int(getattr(source_os2, field, 0))
        setattr(target_os2, field, target_value | source_value)

    return copied


def _set_name(font: TTFont, name_id: int, value: str) -> None:
    name_table = font["name"]
    name_table.setName(value, name_id, 3, 1, 0x409)
    name_table.setName(value, name_id, 1, 0, 0)


def update_metadata(
    font: TTFont,
    variant: Variant,
    project_version: str,
    family_name: str = FAMILY_NAME,
) -> None:
    """패밀리·스타일·버전·라이선스 메타데이터를 Monatendard로 고정한다."""
    postscript_family = family_name.replace(" ", "")
    postscript_subfamily = variant.subfamily_name.replace(" ", "")
    full_name = f"{family_name} {variant.subfamily_name}"
    postscript_name = f"{postscript_family}-{postscript_subfamily}"

    values = {
        1: family_name,
        2: variant.subfamily_name,
        3: f"{postscript_name};{project_version}",
        4: full_name,
        5: f"Version {project_version}",
        6: postscript_name,
        13: (
            "Monatendard is based on Monaspace Neon and Pretendard and is distributed "
            "under the SIL Open Font License, Version 1.1."
        ),
        14: "https://openfontlicense.org",
        16: family_name,
        17: variant.subfamily_name,
    }
    for name_id, value in values.items():
        _set_name(font, name_id, value)

    head = cast("Any", font["head"])
    os2 = cast("Any", font["OS/2"])
    post = cast("Any", font["post"])
    head.fontRevision = float(".".join(project_version.split(".")[:2]))
    head.created = REPRODUCIBLE_TIMESTAMP
    head.modified = REPRODUCIBLE_TIMESTAMP

    mac_bold = 1 << 0
    mac_italic = 1 << 1
    fs_italic = 1 << 0
    fs_bold = 1 << 5
    fs_regular = 1 << 6
    head.macStyle &= ~(mac_bold | mac_italic)
    os2.fsSelection &= ~(fs_italic | fs_bold | fs_regular)
    if variant.is_italic:
        head.macStyle |= mac_italic
        os2.fsSelection |= fs_italic
    if variant.css_weight >= 700:
        head.macStyle |= mac_bold
        os2.fsSelection |= fs_bold
    if variant.weight_name == "Regular" and not variant.is_italic:
        os2.fsSelection |= fs_regular

    os2.usWeightClass = variant.css_weight
    os2.panose.bProportion = 9
    post.isFixedPitch = 1
    if "DSIG" in font:
        del font["DSIG"]


def build_font(
    variant: Variant,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    horizontal_scale: float | None = None,
    project_version: str | None = None,
    profile: BuildProfile | None = None,
) -> BuildStats:
    """한 variant를 TTF와 WOFF2로 생성한다."""
    profile = profile or load_profile()
    scale = horizontal_scale or profile.latin_horizontal_scale
    version = project_version or profile.version
    latin_path = MONASPACE_DIR / variant.latin_filename
    connecting_path = (
        MONASPACE_DIR / f"MonaspaceNeonFrozen-{variant.weight_name}.ttf"
        if variant.is_italic
        else latin_path
    )
    cjk_path = PRETENDARD_DIR / variant.cjk_filename
    for path in (latin_path, connecting_path, cjk_path):
        if not path.exists():
            raise FileNotFoundError(
                f"원본 파일이 없습니다. 먼저 `monatendard fetch`를 실행하세요: {path}"
            )

    target = TTFont(latin_path, recalcTimestamp=False)
    pristine = TTFont(latin_path, recalcTimestamp=False)
    connecting = TTFont(connecting_path, recalcTimestamp=False)
    cjk = TTFont(cjk_path, recalcTimestamp=False)
    try:
        latin_advance = scale_latin_horizontally(
            target,
            pristine,
            scale,
            profile.latin_advance_em,
            connecting_font=connecting if variant.is_italic else None,
        )
        copied = merge_cjk(
            target,
            cjk,
            latin_advance,
            profile.cjk_horizontal_scale,
            profile.cjk_vertical_scale,
        )
        update_metadata(target, variant, version, profile.family)
        target.recalcTimestamp = False

        ttf_dir = output_dir / "ttf"
        web_dir = output_dir / "webfont"
        ttf_dir.mkdir(parents=True, exist_ok=True)
        web_dir.mkdir(parents=True, exist_ok=True)
        ttf_path = ttf_dir / f"{profile.file_prefix}-{variant.output_suffix}.ttf"
        woff2_path = web_dir / f"{profile.file_prefix}-{variant.output_suffix}.woff2"
        target.save(ttf_path, reorderTables=False)

        web_font = TTFont(ttf_path, recalcTimestamp=False)
        try:
            web_font.flavor = "woff2"
            web_font.save(woff2_path, reorderTables=False)
        finally:
            web_font.close()
    finally:
        target.close()
        pristine.close()
        connecting.close()
        cjk.close()

    logger.info(
        "%s 생성: CJK=%d, 영문 advance=%d, 한글 advance=%d",
        variant.output_suffix,
        copied,
        latin_advance,
        latin_advance * 2,
    )
    return BuildStats(ttf_path, copied, latin_advance, latin_advance * 2)


def write_web_css(
    output_dir: Path,
    variants: list[Variant],
    profile: BuildProfile | None = None,
) -> Path:
    """빌드된 WOFF2를 위한 @font-face CSS를 만든다."""
    profile = profile or load_profile()
    blocks = []
    for variant in variants:
        blocks.append(
            "\n".join(
                [
                    "@font-face {",
                    f"  font-family: '{profile.family}';",
                    f"  src: url('./{profile.file_prefix}-{variant.output_suffix}.woff2') "
                    "format('woff2');",
                    f"  font-weight: {variant.css_weight};",
                    f"  font-style: {variant.style};",
                    "  font-display: swap;",
                    "}",
                ]
            )
        )
    path = output_dir / "webfont" / f"{profile.file_prefix.lower()}.css"
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return path


def build_variants(
    variants: list[Variant],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    profile: BuildProfile | None = None,
) -> list[BuildStats]:
    """선택한 variant를 순서대로 빌드한다."""
    profile = profile or load_profile()
    stats = [
        build_font(variant, output_dir=output_dir, profile=profile) for variant in variants
    ]
    write_web_css(output_dir, variants, profile)
    return stats


def all_variants() -> list[Variant]:
    return list(VARIANTS)
