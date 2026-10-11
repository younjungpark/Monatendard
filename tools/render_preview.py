"""README용 Claude Code 작업 화면 이미지를 만든다.

Windows의 Edge(Chromium)는 글꼴을 DirectWrite로 그리므로 Windows Terminal과 같은
래스터라이저를 거친다. 빌드한 Nerd 글꼴을 직접 불러와 터미널 화면처럼 그린다.

    uv run monatendard build-nerd --variants Regular
    uv run python tools/render_preview.py
"""

from __future__ import annotations

import argparse
import html
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path

from fontTools.ttLib import TTFont

from monatendard import __version__

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "fonts" / "nerd-ttf" / "MonatendardNFM-Regular.ttf"
OUTPUT = ROOT / "assets" / "claude-code-preview.png"
EDGE_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
)
FONT_PX = 20
COLUMNS = 74
PADDING_PX = 24

Segment = tuple[str, str]
Line = list[Segment]


def width(text: str) -> int:
    """터미널 칸 수. 한글처럼 넓은 문자는 두 칸이다."""
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def pad(text: str, cells: int) -> str:
    if width(text) > cells:
        raise ValueError(f"{cells}칸을 넘습니다: {text!r}")
    return text + " " * (cells - width(text))


def plain(text: str = "", style: str = "") -> Line:
    return [(text, style)] if text else []


def boxed(rows: list[Line], inner: int, style: str, indent: str = "") -> list[Line]:
    """둥근 테두리 상자. 행 안의 색은 그대로 둔다."""
    lines = [[(indent, ""), ("╭" + "─" * inner + "╮", style)]]
    for row in rows:
        used = sum(width(text) for text, _ in row)
        lines.append(
            [(indent, ""), ("│", style), *row, (" " * (inner - used), ""), ("│", style)]
        )
    lines.append([(indent, ""), ("╰" + "─" * inner + "╯", style)])
    return lines


def workspace(indent: str) -> list[Line]:
    """Monatendard 격자를 보여 주는 표. 기존 README 화면과 같은 구성이다."""
    left, right = 21, 48
    full = left + right + 1
    files = [
        "PROJECT FILES",
        "src/",
        "└─ monatendard/",
        "   ├─ builder.py",
        "   └─ verify.py",
        "tests/",
        "└─ test_profiles.py",
    ]
    code = [
        "CODE VERIFICATION",
        '01 │ latin = measure("AA")',
        '02 │ hangul = measure("가")',
        "03 │ assert latin == hangul",
        "04 │ # 한글 한 글자 = 영문 두 글자",
        '05 │ assert measure("CODE") == measure("한글")',
        "",
    ]
    table = [
        ("영문 샘플", "영문 폭", "한글 샘플", "한글 폭", "결과"),
        ("AA", "2 cells", "가", "2 cells", "PASS"),
        ("CODE", "4 cells", "한글", "4 cells", "PASS"),
        ("GRID2026", "8 cells", "정렬완료", "8 cells", "PASS"),
        ("ABCDEFGHIJ", "10 cells", "가나다라마", "10 cells", "PASS"),
    ]
    widths = (13, 10, 13, 10, 4)

    def row(text: str) -> str:
        return " " + pad(text, full - 1)

    out: list[str] = []
    out.append("┌" + "─" * full + "┐")
    out.append("│" + row(f"MONATENDARD v{__version__} / CLAUDE CODE WORKSPACE") + "│")
    out.append("├" + "─" * left + "┬" + "─" * right + "┤")
    for name, line in zip(files, code, strict=True):
        out.append("│ " + pad(name, left - 1) + "│ " + pad(line, right - 1) + "│")
    out.append("├" + "─" * left + "┴" + "─" * right + "┤")
    out.append("│" + row("WIDTH CHECK") + "│")
    for cells in table:
        text = " ".join(pad(cell, size) for cell, size in zip(cells, widths, strict=True))
        out.append("│" + row(" " + text) + "│")
    out.append("├" + "─" * full + "┤")
    out.append("│" + row("LIGATURES") + "│")
    out.append("│" + row("!=  ===  =>  ->  -->  ==>  ===>  <=  >=  ::") + "│")
    out.append("│" + row("Monaspace ligatures preserved") + "│")
    out.append("├" + "─" * full + "┤")
    out.append(
        "│" + row(f"\uf126 main \ue0b1 tests: 44 passed \ue0b1 v{__version__}") + "│"
    )
    out.append("└" + "─" * full + "┘")
    return [[(indent, ""), (line, "")] for line in out]


def screen() -> list[Line]:
    welcome = boxed(
        [
            [(" ", ""), ("✱", "accent"), (" Welcome to ", ""), ("Claude Code", "bold"), ("!", "")],
            [],
            [("   /help for help, /status for your current setup", "dim")],
            [],
            [("   cwd: C:\\work\\Monatendard", "dim")],
        ],
        inner=54,
        style="accent",
    )
    prompt = boxed(
        [[(" > ", ""), ("Try \"review my current changes\"", "dim")]],
        inner=COLUMNS - 2,
        style="dim",
    )
    return [
        *welcome,
        [],
        [("> ", "dim"), ("한글과 영문이 같은 격자에 맞는지 보여 주는 화면을 그려줘", "dim")],
        [],
        [("●", "ok"), (" ", ""), ("Bash", "bold"), ("(uv run monatendard verify --nerd)", "")],
        [("  └ ", "dim"), ("검증 완료: fonts\\nerd-ttf", "")],
        [],
        [("●", ""), (" Monatendard 고정폭 검증 화면입니다.", "")],
        [],
        *workspace("  "),
        [],
        *prompt,
        [("  ? for shortcuts", "dim"), (" " * (COLUMNS - 28), ""), ("✓ Opus 5.5", "dim")],
    ]


def line_height(font: Path) -> float:
    """Windows Terminal 기본값처럼 글꼴의 줄 높이를 쓴다. 이래야 세로 박스 선이 이어진다."""
    with TTFont(font) as ttf:
        os2 = ttf["OS/2"]
        return (os2.usWinAscent + os2.usWinDescent) / ttf["head"].unitsPerEm


def render_html(font: Path) -> str:
    lines = []
    for line in screen():
        spans = "".join(
            f'<span class="{style}">{html.escape(text)}</span>' if style else html.escape(text)
            for text, style in line
        )
        lines.append(spans)
    body = "\n".join(lines)
    return f"""<!doctype html>
<meta charset="utf-8">
<style>
@font-face {{ font-family: "Preview"; src: url("{font.as_uri()}"); }}
html, body {{ margin: 0; background: #0c0c0c; }}
pre {{
  margin: 0; padding: {PADDING_PX}px; color: #cccccc;
  font: {FONT_PX}px/{FONT_PX * line_height(font)}px "Preview"; font-variant-ligatures: contextual;
}}
.accent {{ color: #d77757; }}
.dim {{ color: #8a8a8a; }}
.bold {{ font-weight: 700; color: #ffffff; }}
.ok {{ color: #4eba65; }}
</style>
<pre>{body}</pre>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--font", type=Path, default=FONT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    if not args.font.exists():
        parser.error(f"글꼴이 없습니다: {args.font}. 먼저 build-nerd를 실행하세요.")
    browser = next((path for path in EDGE_CANDIDATES if path.exists()), None)
    if browser is None:
        parser.error("Edge 또는 Chrome을 찾지 못했습니다.")

    char_px = FONT_PX * 0.620
    page_width = round(COLUMNS * char_px + 2 * PADDING_PX + 2 * char_px)
    page_height = round(len(screen()) * FONT_PX * line_height(args.font) + 2 * PADDING_PX)
    with tempfile.TemporaryDirectory() as work:
        page = Path(work) / "preview.html"
        page.write_text(render_html(args.font.resolve()), encoding="utf-8")
        shot = Path(work) / "preview.png"
        subprocess.run(
            [
                str(browser),
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                f"--user-data-dir={Path(work) / 'profile'}",
                f"--window-size={page_width},{page_height}",
                f"--screenshot={shot}",
                page.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(shot, args.output)
    print(f"생성 완료: {args.output} ({page_width}x{page_height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
