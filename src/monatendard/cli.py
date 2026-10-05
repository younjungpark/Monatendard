"""Monatendard 개발자용 명령행 인터페이스."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from monatendard.builder import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PROFILE,
    BuildProfile,
    build_variants,
    load_profile,
    profile_names,
)
from monatendard.nerd import (
    DEFAULT_NERD_OUTPUT_DIR,
    DEFAULT_STANDARD_INPUT_DIR,
    build_nerd_variants,
)
from monatendard.packaging import create_release_assets
from monatendard.sources import VARIANTS, VARIANTS_BY_SUFFIX, fetch_sources
from monatendard.verify import (
    verify_directory,
    verify_nerd_reproducible,
    verify_reproducible,
)


def _add_variant_selection(parser: argparse.ArgumentParser) -> None:
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--all", action="store_true", help="전체 14개 variant 빌드")
    selection.add_argument(
        "--variants",
        nargs="+",
        metavar="NAME",
        help="예: Regular Italic BoldItalic",
    )


PROTOTYPE_OUTPUT_ROOT = Path("build") / "proto"


def _add_profile(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        choices=profile_names(),
        help="sources.lock.toml의 빌드 설정 (기본: default)",
    )


def _profile_root(profile: BuildProfile) -> Path:
    """시제품은 정식 fonts/와 섞이지 않도록 build/proto/<이름> 아래에 둔다."""
    if profile.name == DEFAULT_PROFILE:
        return DEFAULT_OUTPUT_DIR
    return PROTOTYPE_OUTPUT_ROOT / profile.name


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monatendard 재현 가능 글꼴 빌드")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("fetch", help="고정 원본 다운로드, SHA256 검증 및 추출")

    build = subparsers.add_parser("build", help="Monaspace와 Pretendard 병합")
    _add_variant_selection(build)
    _add_profile(build)
    build.add_argument("--output-dir", type=Path)

    build_nerd = subparsers.add_parser(
        "build-nerd",
        help="일반 Monatendard에 Nerd Fonts 아이콘 병합",
    )
    _add_variant_selection(build_nerd)
    _add_profile(build_nerd)
    build_nerd.add_argument("--input-dir", type=Path)
    build_nerd.add_argument("--output-dir", type=Path)

    verify = subparsers.add_parser("verify", help="생성 글꼴 자동 검증")
    _add_profile(verify)
    verify.add_argument("--font-dir", type=Path)
    verify.add_argument("--nerd", action="store_true", help="Nerd 전용 TTF 검사")
    verify.add_argument("--reproducible", action="store_true", help="Regular 두 번 빌드 비교")

    package = subparsers.add_parser("package", help="GitHub Release 자산 생성")
    package.add_argument("--version", required=True)
    package.add_argument("--fonts-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    package.add_argument("--dist-dir", type=Path, default=Path("dist"))
    return parser


def _selected_variants(names: list[str] | None, all_variants: bool) -> list:
    if all_variants or not names:
        return list(VARIANTS)
    unknown = [name for name in names if name not in VARIANTS_BY_SUFFIX]
    if unknown:
        raise ValueError(
            f"지원하지 않는 variant: {', '.join(unknown)}. "
            f"지원 목록: {', '.join(VARIANTS_BY_SUFFIX)}"
        )
    return list(dict.fromkeys(VARIANTS_BY_SUFFIX[name] for name in names))


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        if args.command == "fetch":
            archives = fetch_sources()
            for path in archives:
                print(f"검증 완료: {path}")
            return 0

        profile = load_profile(getattr(args, "profile", DEFAULT_PROFILE))
        root = _profile_root(profile)

        if args.command == "build":
            variants = _selected_variants(args.variants, args.all)
            stats = build_variants(variants, args.output_dir or root, profile)
            for result in stats:
                print(
                    f"생성 완료: {result.output_path} "
                    f"(영문={result.latin_advance}, 한글={result.hangul_advance})"
                )
            return 0

        if args.command == "build-nerd":
            variants = _selected_variants(args.variants, args.all)
            stats = build_nerd_variants(
                variants,
                input_dir=args.input_dir or root / DEFAULT_STANDARD_INPUT_DIR.name,
                output_dir=args.output_dir or root / DEFAULT_NERD_OUTPUT_DIR.name,
                profile=profile,
            )
            for result in stats:
                print(
                    f"Nerd 생성 완료: {result.output_path} "
                    f"(아이콘={result.mapped_symbol_count}, "
                    f"영문={result.latin_advance}, 한글={result.hangul_advance})"
                )
            return 0

        if args.command == "verify":
            font_dir = args.font_dir or root / (
                DEFAULT_NERD_OUTPUT_DIR.name if args.nerd else DEFAULT_STANDARD_INPUT_DIR.name
            )
            failures = verify_directory(font_dir, nerd=args.nerd, profile=profile)
            for path, errors in failures.items():
                for error in errors:
                    print(f"실패: {path}: {error}")
            if failures:
                return 1
            print(f"검증 완료: {font_dir}")
            if args.reproducible:
                if args.nerd:
                    same, first, second = verify_nerd_reproducible(
                        profile=profile,
                        input_dir=root / DEFAULT_STANDARD_INPUT_DIR.name,
                    )
                else:
                    same, first, second = verify_reproducible(profile=profile)
                print(f"재현성 SHA256: {first}")
                if not same:
                    print(f"재현성 실패: second={second}")
                    return 1
            return 0

        if args.command == "package":
            assets = create_release_assets(
                version=args.version,
                fonts_dir=args.fonts_dir,
                dist_dir=args.dist_dir,
            )
            for path in assets:
                print(f"Release 자산: {path}")
            return 0
    except (FileNotFoundError, KeyError, OSError, ValueError) as exc:
        parser.exit(1, f"오류: {exc}\n")

    parser.error(f"알 수 없는 명령: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
