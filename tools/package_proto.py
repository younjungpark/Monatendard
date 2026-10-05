"""시제품 Nerd 글꼴을 다른 PC에 설치할 수 있는 ZIP으로 묶는다.

    uv run python tools/package_proto.py proto-a proto-c
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from monatendard.builder import load_profile
from monatendard.packaging import _file_sha256, _zip_directory

ROOT = Path(__file__).resolve().parents[1]
PROTO_ROOT = ROOT / "build" / "proto"
PACKAGING_DIR = ROOT / "packaging" / "windows" / "proto"
DIST_DIR = ROOT / "dist"
EXPECTED_STYLES = 14

NOTES = {
    "proto-a": (
        "영문은 Monaspace Neon 원본 그대로(힌팅 포함), 셀 폭 0.620em,\n"
        "한글은 Pretendard 원래 비율(균등 1.15배)인 시험판입니다.\n"
        "터미널 프로필에 cellWidth가 있으면 지워야 원래 셀 폭(0.620em)으로 보입니다."
    ),
    "proto-c": (
        "v0.2.3과 영문·셀 폭(0.600em)은 같고,\n"
        "한글만 Pretendard 원래 비율(균등 1.15배)로 바꾼 시험판입니다."
    ),
}


def _terminal_profile(profile_name: str) -> dict:
    profiles = json.loads(
        (PACKAGING_DIR / "windows-terminal-profiles.json").read_text(encoding="utf-8")
    )
    family = load_profile(profile_name).nerd_family
    profile = next(item for item in profiles if item["font"]["face"] == family)
    profile = dict(profile)
    profile.pop("startingDirectory", None)
    return profile


def _install_notes(profile_name: str, terminal: dict) -> str:
    profile = load_profile(profile_name)
    font_settings = ", ".join(
        f'"{key}": {json.dumps(value)}' for key, value in terminal["font"].items()
    )
    return f"""{profile.family} (시험판, {profile.version})
{"=" * 40}

{NOTES.get(profile_name, "")}
기존 Monatendard, Jetendard, 다른 시험판과 이름이 달라 함께 설치해 둘 수 있습니다.

설치
  install.cmd를 더블클릭합니다. 관리자 권한은 필요 없습니다(현재 사용자에게만 설치).
  설치 후 터미널과 편집기를 다시 시작합니다.

글꼴 이름
  {profile.nerd_family}
  (14개 스타일: ExtraLight ~ ExtraBold, 각 이탤릭 포함)

Windows Terminal
  settings.json의 profiles.list에 windows-terminal-profile.json 내용을 넣거나,
  기존 프로필의 font를 아래처럼 바꿉니다.
    {font_settings}
  pwsh가 없는 PC라면 commandline을 "powershell.exe"로 바꿉니다.

VS Code
  "editor.fontFamily": "'{profile.nerd_family}'"

제거
  uninstall.cmd를 더블클릭합니다.

라이선스
  글꼴: SIL Open Font License 1.1 (LICENSES/OFL.txt)
  Nerd Fonts 아이콘: MIT (LICENSES/NERD_FONTS_LICENSE.txt)
"""


def _write_crlf(path: Path, lines: list[str]) -> None:
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("ascii"))


def package(profile_name: str) -> Path:
    profile = load_profile(profile_name)
    fonts = sorted(
        (PROTO_ROOT / profile_name / "nerd-ttf").glob(f"{profile.nerd_file_prefix}-*.ttf")
    )
    if len(fonts) != EXPECTED_STYLES:
        raise FileNotFoundError(
            f"{profile.nerd_family} TTF가 {len(fonts)}개입니다. 먼저 --all로 빌드하세요."
        )

    staging = PROTO_ROOT / "package" / profile_name
    shutil.rmtree(staging, ignore_errors=True)
    package_dir = staging / profile.family.replace(" ", "-")
    (package_dir / "fonts").mkdir(parents=True)
    (package_dir / "LICENSES").mkdir()
    for font in fonts:
        shutil.copy2(font, package_dir / "fonts" / font.name)
    for script in ("Install-MonatendardProto.ps1", "Uninstall-MonatendardProto.ps1"):
        shutil.copy2(PACKAGING_DIR / script, package_dir / script)
    shutil.copy2(ROOT / "LICENSE", package_dir / "LICENSES" / "OFL.txt")
    for path in sorted((ROOT / "licenses").glob("*")):
        if path.is_file():
            shutil.copy2(path, package_dir / "LICENSES" / path.name)

    prefix = profile.nerd_file_prefix
    powershell = "powershell -NoProfile -ExecutionPolicy Bypass -File"
    _write_crlf(
        package_dir / "install.cmd",
        [
            "@echo off",
            f'{powershell} "%~dp0Install-MonatendardProto.ps1" -FontDirectory "%~dp0fonts"'
            f' -FilePrefix {prefix} -FamilyName "{profile.nerd_family}"',
            "pause",
        ],
    )
    _write_crlf(
        package_dir / "uninstall.cmd",
        [
            "@echo off",
            f'{powershell} "%~dp0Uninstall-MonatendardProto.ps1" -FilePrefix {prefix}',
            "pause",
        ],
    )
    terminal = _terminal_profile(profile_name)
    (package_dir / "windows-terminal-profile.json").write_text(
        json.dumps(terminal, indent=4, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (package_dir / "설치방법.txt").write_text(
        _install_notes(profile_name, terminal), encoding="utf-8"
    )

    output = DIST_DIR / f"{profile.family.replace(' ', '-')}-{profile.version}-Nerd.zip"
    _zip_directory(staging, output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("profiles", nargs="+", help="예: proto-a proto-c")
    args = parser.parse_args()
    for profile_name in args.profiles:
        output = package(profile_name)
        print(f"{output} ({output.stat().st_size // 1024} KB) sha256={_file_sha256(output)}")


if __name__ == "__main__":
    main()
