from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_windows_scripts_are_ascii_only() -> None:
    scripts = (ROOT / "packaging" / "windows").glob("*.ps1")
    for script in scripts:
        assert script.read_text(encoding="utf-8").isascii()


def test_project_surfaces_link_to_official_website() -> None:
    official_url = "https://monatendard.github.io/"
    paths = [
        ROOT / "README.ko.md",
        ROOT / "pyproject.toml",
        ROOT / "packaging" / "windows" / "설치방법.txt",
        ROOT / "packaging" / "windows" / "Nerd-설치방법.txt",
    ]
    for path in paths:
        assert official_url in path.read_text(encoding="utf-8")


def test_windows_scripts_support_dry_run_and_user_install() -> None:
    installer = (ROOT / "packaging" / "windows" / "Install-Monatendard.ps1").read_text(
        encoding="utf-8"
    )
    uninstaller = (ROOT / "packaging" / "windows" / "Uninstall-Monatendard.ps1").read_text(
        encoding="utf-8"
    )
    for script in (installer, uninstaller):
        assert "SupportsShouldProcess" in script
        assert "HKCU:" in script
        assert "WM_FONTCHANGE" not in script or "0x001D" in script
    assert "LOCALAPPDATA" in installer
    assert "-Value $destination" in installer
    assert "-Value $font.Name" not in installer
    assert "GetFileName([string]$property.Value)" in uninstaller
    assert "Monatendard-*.ttf" in uninstaller


def test_nerd_windows_scripts_are_isolated_from_standard_family() -> None:
    installer = (
        ROOT / "packaging" / "windows" / "Install-Monatendard-Nerd.ps1"
    ).read_text(encoding="utf-8")
    uninstaller = (
        ROOT / "packaging" / "windows" / "Uninstall-Monatendard-Nerd.ps1"
    ).read_text(encoding="utf-8")
    for script in (installer, uninstaller):
        assert "SupportsShouldProcess" in script
        assert "HKCU:" in script
        assert "MonatendardNFM-*.ttf" in script
        assert "Monatendard Nerd Font Mono" in script
    assert "-Value $destination" in installer
    assert "RemoveFontResourceEx" in installer
    assert "GetFileName([string]$property.Value)" in uninstaller


def test_windows_installers_preserve_existing_font_registry_entries() -> None:
    installers = [
        ROOT / "packaging" / "windows" / "Install-Monatendard.ps1",
        ROOT / "packaging" / "windows" / "Install-Monatendard-Nerd.ps1",
    ]
    for path in installers:
        installer = path.read_text(encoding="utf-8")
        assert "New-Item -Force -Path $fontRegistry" not in installer
        assert "if (-not (Test-Path -LiteralPath $fontRegistry))" in installer


@pytest.mark.parametrize(
    "suffix,api", [("", "MonatendardFontApiV2"), ("-Nerd", "MonatendardNerdFontApiV2")]
)
def test_windows_font_lifecycle_is_safe(suffix: str, api: str) -> None:
    scripts = [
        (ROOT / "packaging" / "windows" / f"{action}-Monatendard{suffix}.ps1")
        .read_text(encoding="utf-8")
        for action in ("Install", "Uninstall")
    ]
    definitions = []
    for script in scripts:
        match = re.search(r"Add-Type -TypeDefinition @'\n(.*?)\n'@", script, re.S)
        assert match is not None
        definitions.append(match[1])
    assert definitions[0] == definitions[1]
    for script in scripts:
        assert f"-not ('{api}' -as [type])" in script
        assert "extern int AddFontResourceEx" in script
        assert "extern bool RemoveFontResourceEx" in script
        assert "[System.IO.File]::Open(" in script
        assert "[System.IO.FileMode]::Open" in script
        assert "[System.IO.FileAccess]::ReadWrite" in script
        assert "[System.IO.FileShare]::None" in script
        assert "$stream.Dispose()" in script
        assert "Rename-Item" not in script
        assert "Close applications using the fonts and retry." in script
        assert script.index("]::RemoveFontResourceEx(") < script.index("[System.IO.File]::Open(")
        assert "$released[$destination]++" in script
        assert "$i -lt $released[$path]" in script

        assert "if (-not $WhatIfPreference)" in script
    installer, uninstaller = scripts
    assert installer.index("[System.IO.File]::Open(") < installer.index(
        "New-Item -ItemType Directory"
    )
    assert installer.index("]::RemoveFontResourceEx(") < installer.index("Copy-Item")
    assert uninstaller.index("[System.IO.File]::Open(") < uninstaller.index(
        "Remove-Item -LiteralPath"
    )
    assert uninstaller.index("Remove-Item -LiteralPath") < uninstaller.index("Remove-ItemProperty")
    assert "[string]$property.Value -ne $fileName" in uninstaller
    assert "[string]$property.Value -ne $destination" in uninstaller
    assert "-not (Test-Path -LiteralPath $destination)" in uninstaller


@pytest.mark.parametrize("actions", [("Install", "Uninstall"), ("Uninstall", "Install")])
def test_windows_font_api_reuse_in_powershell(actions: tuple[str, str]) -> None:
    powershell = shutil.which("pwsh") or shutil.which("powershell.exe")
    if powershell is None:
        pytest.skip("PowerShell is not installed; Windows native font lifecycle needs Windows")
    assert powershell is not None
    # Parse complete scripts, then run only their guarded Add-Type blocks. This
    # exercises both lifecycle orders without touching real fonts or registry.
    blocks = []
    for suffix in ("", "-Nerd"):
        family_blocks = []
        for action in actions:
            path = ROOT / "packaging" / "windows" / f"{action}-Monatendard{suffix}.ps1"
            source = path.read_text(encoding="utf-8")
            escaped = str(path).replace("'", "''")
            blocks.append(
                "$tokens = $null; $errors = $null; "
                f"[void][System.Management.Automation.Language.Parser]::ParseFile('{escaped}', "
                "[ref]$tokens, [ref]$errors); if ($errors.Count) { throw ($errors | Out-String) }"
            )
            match = re.search(
                r"if \(-not \$WhatIfPreference -and -not \('[^']+' -as \[type\]\)\) "
                r"\{\n    Add-Type -TypeDefinition @'\n.*?\n'@\n\}",
                source,
                re.S,
            )
            assert match is not None
            family_blocks.append(match[0])
        # Repeat both guarded definitions within the same PowerShell process.
        blocks.extend(family_blocks + family_blocks[::-1] + family_blocks)
    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference = 'Stop'; $WhatIfPreference = $false;\n" + "\n".join(blocks),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
