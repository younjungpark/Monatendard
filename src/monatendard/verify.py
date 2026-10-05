"""생성 글꼴의 이름, 폭, 글리프, 리게이처와 재현성을 검증한다."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fontTools.ttLib import TTFont

from monatendard.builder import (
    ASCII_SAMPLE,
    REQUIRED_HANGUL,
    BuildProfile,
    _glyph_bounds,
    build_font,
    load_profile,
)
from monatendard.nerd import (
    CENTERED_NERD_CODEPOINTS,
    NERD_ICON_VERTICAL_OFFSET_EM,
    REQUIRED_NERD_CODEPOINTS,
    build_nerd_font,
)
from monatendard.sources import VARIANTS_BY_SUFFIX

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HINTING_TABLES = ("fpgm", "prep", "cvt ")
HINTED_SAMPLE = "Aao"
REQUIRED_TABLES = {"cmap", "glyf", "head", "hhea", "hmtx", "maxp", "name", "OS/2", "post"}
LIGATURE_FEATURES = {"liga", "calt", *(f"ss{number:02d}" for number in range(1, 11))}
EDGE_JOIN_REQUIREMENTS = {
    0x2500: (True, True),  # BOX DRAWINGS LIGHT HORIZONTAL
    0x2588: (True, True),  # FULL BLOCK
    0xE0B0: (True, False),  # POWERLINE SYMBOL RIGHT
    0xE0B2: (False, True),  # POWERLINE SYMBOL LEFT
}


def _name_values(font: TTFont, name_id: int) -> set[str]:
    values: set[str] = set()
    for record in font["name"].names:
        if record.nameID == name_id:
            values.add(record.toUnicode())
    return values


def _check_latin_hinting(font: TTFont, cmap: dict[int, str]) -> list[str]:
    """원본 영문 힌팅 테이블과 글리프 명령어가 남아 있는지 확인한다."""
    errors: list[str] = []
    missing = [tag.strip() for tag in HINTING_TABLES if tag not in font]
    if missing:
        errors.append(f"영문 힌팅 테이블 누락: {', '.join(missing)}")
    glyf = font["glyf"]
    for char in HINTED_SAMPLE:
        glyph_name = cmap.get(ord(char))
        glyph = glyf[glyph_name] if glyph_name is not None else None
        program = getattr(glyph, "program", None)
        if program is None or not program.getBytecode():
            errors.append(f"영문 '{char}' 글리프에 힌팅 명령어가 없습니다.")
    return errors


def verify_font(path: Path, profile: BuildProfile | None = None) -> list[str]:
    """한 글꼴을 검사하고 실패 사유를 반환한다."""
    profile = profile or load_profile()
    errors: list[str] = []
    try:
        font = TTFont(path)
        font.ensureDecompiled()
    except Exception as exc:
        return [f"글꼴을 열 수 없습니다: {exc}"]

    try:
        missing_tables = REQUIRED_TABLES - set(font.keys())
        if missing_tables:
            errors.append(f"필수 테이블 누락: {', '.join(sorted(missing_tables))}")

        for name_id, label, expected in (
            (1, "Family", profile.family),
            (4, "Full", profile.family),
            (6, "PostScript", profile.file_prefix),
        ):
            values = _name_values(font, name_id)
            if not values or any(expected not in value for value in values):
                errors.append(f"{label} name이 {expected} 규칙과 다릅니다: {sorted(values)}")

        licenses = _name_values(font, 13)
        if not licenses or not any("SIL Open Font License" in value for value in licenses):
            errors.append("name ID 13에 SIL OFL 고지가 없습니다.")

        cmap = font.getBestCmap() or {}
        hmtx = font["hmtx"].metrics
        ascii_widths = {
            hmtx[cmap[codepoint]][0]
            for codepoint in ASCII_SAMPLE
            if codepoint in cmap and cmap[codepoint] in hmtx
        }
        if len(ascii_widths) != 1:
            errors.append(f"대표 영문 advance가 단일 값이 아닙니다: {sorted(ascii_widths)}")
        else:
            latin_advance = next(iter(ascii_widths))
            expected_advance = round(font["head"].unitsPerEm * profile.latin_advance_em)
            if latin_advance != expected_advance:
                errors.append(
                    f"영문 advance={latin_advance}, expected={expected_advance} "
                    f"({profile.latin_advance_em:.3f}em)"
                )
            for codepoint in REQUIRED_HANGUL:
                glyph_name = cmap.get(codepoint)
                if glyph_name is None:
                    errors.append(f"필수 한글 글리프 누락: U+{codepoint:04X}")
                elif hmtx[glyph_name][0] != latin_advance * 2:
                    errors.append(
                        f"U+{codepoint:04X} advance={hmtx[glyph_name][0]}, "
                        f"expected={latin_advance * 2}"
                    )

            glyph_set = font.getGlyphSet()
            for codepoint, (joins_left, joins_right) in EDGE_JOIN_REQUIREMENTS.items():
                glyph_name = cmap.get(codepoint)
                bounds = (
                    _glyph_bounds(glyph_set, glyph_name) if glyph_name is not None else None
                )
                if bounds is None:
                    errors.append(f"셀 접합 글리프 누락: U+{codepoint:04X}")
                    continue
                xmin, _, xmax, _ = bounds
                if joins_left and xmin > 0:
                    errors.append(
                        f"U+{codepoint:04X} 왼쪽 셀 경계 미접합: xmin={xmin:g}"
                    )
                if joins_right and xmax < latin_advance:
                    errors.append(
                        f"U+{codepoint:04X} 오른쪽 셀 경계 미접합: "
                        f"xmax={xmax:g}, expected>={latin_advance}"
                    )

        if "GSUB" not in font:
            errors.append("Monaspace 리게이처를 위한 GSUB 테이블이 없습니다.")
        else:
            feature_list = font["GSUB"].table.FeatureList
            tags = (
                {record.FeatureTag for record in feature_list.FeatureRecord}
                if feature_list is not None
                else set()
            )
            if not tags & LIGATURE_FEATURES:
                errors.append(f"리게이처 feature가 없습니다: {sorted(tags)}")

        if profile.keeps_latin_outlines:
            errors.extend(_check_latin_hinting(font, cmap))

        if not cast_fixed_pitch(font):
            errors.append("고정폭 메타데이터가 설정되지 않았습니다.")
    finally:
        font.close()
    return errors


def verify_nerd_font(path: Path, profile: BuildProfile | None = None) -> list[str]:
    """일반 글꼴 규칙과 Nerd 전용 패밀리·아이콘·폭을 함께 검사한다."""
    profile = profile or load_profile()
    errors = verify_font(path, profile)
    try:
        font = TTFont(path)
        font.ensureDecompiled()
    except Exception as exc:
        return errors or [f"글꼴을 열 수 없습니다: {exc}"]

    try:
        families = _name_values(font, 16) or _name_values(font, 1)
        if families != {profile.nerd_family}:
            errors.append(f"Nerd 패밀리 이름이 다릅니다: {sorted(families)}")

        cmap = font.getBestCmap() or {}
        hmtx = font["hmtx"].metrics
        ascii_glyph = cmap.get(ord("A"))
        latin_advance = hmtx[ascii_glyph][0] if ascii_glyph in hmtx else None
        for codepoint in REQUIRED_NERD_CODEPOINTS:
            glyph_name = cmap.get(codepoint)
            if glyph_name is None:
                errors.append(f"필수 Nerd 아이콘 누락: U+{codepoint:04X}")
            elif latin_advance is not None and hmtx[glyph_name][0] != latin_advance:
                errors.append(
                    f"U+{codepoint:04X} advance={hmtx[glyph_name][0]}, "
                    f"expected={latin_advance}"
                )

        glyph_set = font.getGlyphSet()
        reference_name = cmap.get(ord("x"))
        reference_bounds = (
            _glyph_bounds(glyph_set, reference_name) if reference_name is not None else None
        )
        if reference_bounds is None:
            errors.append("Nerd 아이콘 세로 중심 기준인 소문자 x를 읽을 수 없습니다.")
        else:
            reference_center = (
                (reference_bounds[1] + reference_bounds[3]) / 2
                + font["head"].unitsPerEm * NERD_ICON_VERTICAL_OFFSET_EM
            )
            for codepoint in CENTERED_NERD_CODEPOINTS:
                glyph_name = cmap.get(codepoint)
                bounds = (
                    _glyph_bounds(glyph_set, glyph_name) if glyph_name is not None else None
                )
                if bounds is None:
                    continue
                center = (bounds[1] + bounds[3]) / 2
                if abs(center - reference_center) > 2:
                    errors.append(
                        f"U+{codepoint:04X} 세로 중심={center:g}, "
                        f"expected={reference_center:g}"
                    )

        licenses = _name_values(font, 13)
        if not any("MIT License" in value for value in licenses):
            errors.append("name ID 13에 Nerd Fonts MIT 고지가 없습니다.")
    finally:
        font.close()
    return errors


def cast_fixed_pitch(font: TTFont) -> bool:
    """일반적인 두 고정폭 플래그가 모두 설정됐는지 확인한다."""
    return bool(font["post"].isFixedPitch) and font["OS/2"].panose.bProportion == 9


def verify_directory(
    font_dir: Path,
    *,
    nerd: bool = False,
    profile: BuildProfile | None = None,
) -> dict[Path, list[str]]:
    """디렉터리의 모든 TTF를 검사한다."""
    profile = profile or load_profile()
    prefix = profile.nerd_file_prefix if nerd else profile.file_prefix
    verifier = verify_nerd_font if nerd else verify_font
    paths = sorted(font_dir.glob(f"{prefix}-*.ttf"))
    if not paths:
        label = profile.nerd_family if nerd else profile.family
        return {font_dir: [f"검사할 {label} TTF가 없습니다."]}
    return {path: errors for path in paths if (errors := verifier(path, profile))}


def verify_reproducible(
    variant_name: str = "Regular",
    profile: BuildProfile | None = None,
) -> tuple[bool, str, str]:
    """같은 입력을 두 번 빌드해 TTF SHA256이 같은지 확인한다."""
    from monatendard.sources import sha256

    variant = VARIANTS_BY_SUFFIX[variant_name]
    temporary_root = PROJECT_ROOT / "build"
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="monatendard-repro-",
        dir=temporary_root,
    ) as temporary:
        root = Path(temporary)
        first = build_font(variant, output_dir=root / "first", profile=profile).output_path
        second = build_font(variant, output_dir=root / "second", profile=profile).output_path
        first_hash = sha256(first)
        second_hash = sha256(second)
    return first_hash == second_hash, first_hash, second_hash


def verify_nerd_reproducible(
    variant_name: str = "Regular",
    profile: BuildProfile | None = None,
    input_dir: Path | None = None,
) -> tuple[bool, str, str]:
    """같은 일반판 입력에서 Nerd TTF를 두 번 만들어 SHA256을 비교한다."""
    from monatendard.sources import sha256

    variant = VARIANTS_BY_SUFFIX[variant_name]
    temporary_root = PROJECT_ROOT / "build"
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="monatendard-nerd-repro-",
        dir=temporary_root,
    ) as temporary:
        root = Path(temporary)
        options = {"profile": profile}
        if input_dir is not None:
            options["input_dir"] = input_dir
        first = build_nerd_font(variant, output_dir=root / "first", **options).output_path
        second = build_nerd_font(variant, output_dir=root / "second", **options).output_path
        first_hash = sha256(first)
        second_hash = sha256(second)
    return first_hash == second_hash, first_hash, second_hash
