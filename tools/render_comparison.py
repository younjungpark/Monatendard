"""시제품 판정용 래스터 비교 이미지를 만든다.

Windows의 Edge(Chromium)는 글꼴을 DirectWrite로 그리므로 Windows Terminal과 같은
래스터라이저를 거친다. 모든 글꼴을 같은 px 크기로 한 장에 놓는다.

    uv run python tools/render_comparison.py
"""

from __future__ import annotations

import argparse
import html
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USER_FONTS = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Fonts"
OUTPUT_DIR = ROOT / "build" / "proto" / "compare"
EDGE_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
)
WEIGHTS = ("Light", "Regular")

SAMPLE = """\
fn main() -> Result<(), Error> { let x = 0x1F; }
if (count >= 10 && name != "") return { ok: true };
The quick brown fox jumps over the lazy dog. 0O 1lI|
// 설정 파일을 읽는 중입니다. 잠시만 기다려 주세요.
console.log("안녕하세요, 세계!"); // 다람쥐 헌 쳇바퀴
한글과 English가 섞인 문장: 빌드 성공 build ok 12건
가나다라마바사 아자차카타파하 ㄱㄴㄷ ㅏㅑㅓㅕ 읽힘
┌──────┬──────┐ █▓▒░ ▁▂▃▄▅▆▇█ ╰─╯"""
NERD_LINE = "\ue0b0\ue0b2  \uf126 main  \uf07c src  \uf00c done  \uf489 \U000f0001"


@dataclass(frozen=True)
class Specimen:
    label: str
    family: str
    files: dict[str, Path]
    latin_only: bool = False
    nerd: bool = True


def _specimens() -> list[Specimen]:
    proto = ROOT / "build" / "proto"
    release = ROOT / "build" / "release-0.2.3" / "fonts" / "nerd-ttf"
    upstream = ROOT / "upstream" / "monaspace"
    return [
        Specimen(
            "Monatendard v0.2.3",
            "cmp-v023",
            {weight: release / f"MonatendardNFM-{weight}.ttf" for weight in WEIGHTS},
        ),
        Specimen(
            "Proto A (한글 균등 1.15)",
            "cmp-proto-a",
            {
                weight: proto / "proto-a" / "nerd-ttf" / f"MonatendardProtoANFM-{weight}.ttf"
                for weight in WEIGHTS
            },
        ),
        Specimen(
            "Proto B (한글 균등 1.07)",
            "cmp-proto-b",
            {
                weight: proto / "proto-b" / "nerd-ttf" / f"MonatendardProtoBNFM-{weight}.ttf"
                for weight in WEIGHTS
            },
        ),
        Specimen(
            "Jetendard",
            "cmp-jetendard",
            {weight: USER_FONTS / f"Jetendard-{weight}.ttf" for weight in WEIGHTS},
            nerd=False,
        ),
        Specimen(
            "Monaspace Neon 원본 (영문만)",
            "cmp-monaspace",
            {weight: upstream / f"MonaspaceNeonFrozen-{weight}.ttf" for weight in WEIGHTS},
            latin_only=True,
            nerd=False,
        ),
    ]


def _font_faces(specimens: list[Specimen]) -> str:
    rules = []
    for specimen in specimens:
        for weight, path in specimen.files.items():
            css_weight = 300 if weight == "Light" else 400
            rules.append(
                f"@font-face {{ font-family: '{specimen.family}'; "
                f"src: url('{path.resolve().as_uri()}'); font-weight: {css_weight}; }}"
            )
    return "\n".join(rules)


def _sample_for(specimen: Specimen) -> str:
    lines = SAMPLE.splitlines()
    if specimen.latin_only:
        lines = [line for line in lines if line.isascii()]
    if specimen.nerd:
        lines.append(NERD_LINE)
    return "\n".join(lines)


def build_html(specimens: list[Specimen], size_px: float, line_height: float) -> str:
    blocks = []
    for specimen in specimens:
        cells = []
        for weight in WEIGHTS:
            css_weight = 300 if weight == "Light" else 400
            cells.append(
                f'<div class="cell"><div class="weight">{weight}</div>'
                f'<pre style="font-family: \'{specimen.family}\'; font-weight: {css_weight}">'
                f"{html.escape(_sample_for(specimen))}</pre></div>"
            )
        blocks.append(
            f'<section><h2>{html.escape(specimen.label)}</h2>'
            f'<div class="row">{"".join(cells)}</div></section>'
        )
    return f"""<!doctype html>
<meta charset="utf-8">
<style>
{_font_faces(specimens)}
html, body {{ margin: 0; background: #0c0c0c; color: #cccccc; }}
body {{ padding: 16px 24px; font-family: 'Segoe UI', sans-serif; }}
h1 {{ font-size: 15px; font-weight: 600; margin: 0 0 4px; color: #f2f2f2; }}
p.note {{ font-size: 12px; margin: 0 0 12px; color: #8a8a8a; }}
h2 {{ font-size: 13px; font-weight: 600; margin: 14px 0 4px; color: #61d6d6; }}
.row {{ display: flex; gap: 48px; }}
.weight {{ font-size: 11px; color: #767676; }}
pre {{ margin: 2px 0 0; font-size: {size_px}px; line-height: {line_height};
       font-variant-ligatures: normal; font-feature-settings: "calt" 1, "liga" 1; }}
</style>
<h1>Monatendard 시제품 래스터 비교</h1>
<p class="note">{size_px:g}px · 96 DPI · line-height {line_height:g} · DirectWrite (Chromium) ·
배경 Campbell #0C0C0C</p>
{"".join(blocks)}
"""


def _find_browser() -> Path:
    for candidate in EDGE_CANDIDATES:
        if candidate.exists():
            return candidate
    found = shutil.which("msedge") or shutil.which("chrome")
    if found:
        return Path(found)
    raise FileNotFoundError("Edge 또는 Chrome을 찾을 수 없습니다.")


def render(size_px: float, line_height: float, output_dir: Path) -> Path:
    specimens = _specimens()
    missing = [path for item in specimens for path in item.files.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "비교 대상 글꼴이 없습니다: " + ", ".join(str(path) for path in missing)
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{size_px:g}px".replace(".", "_")
    html_path = output_dir / f"compare-{tag}.html"
    png_path = output_dir / f"compare-{tag}.png"
    html_path.write_text(build_html(specimens, size_px, line_height), encoding="utf-8")
    lines = len(SAMPLE.splitlines()) + 1
    height = 80 + len(specimens) * (40 + round(lines * size_px * line_height))
    subprocess.run(
        [
            str(_find_browser()),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            "--allow-file-access-from-files",
            f"--window-size={round(size_px * 0.62 * 54 * 2 + 120)},{height}",
            f"--screenshot={png_path}",
            html_path.resolve().as_uri(),
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )
    return png_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--size", type=float, default=20, help="글자 크기(px), 15pt = 20px")
    parser.add_argument("--line-height", type=float, default=1.5)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    print(render(args.size, args.line_height, args.output_dir))


if __name__ == "__main__":
    main()
