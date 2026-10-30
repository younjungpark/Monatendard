"""Static contract checks complement the real Windows Scoop workflow."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("package", "prefix", "script"),
    [
        ("monatendard", "Monatendard-", "Monatendard"),
        ("monatendard-nerd", "MonatendardNFM-", "Monatendard-Nerd"),
    ],
)
def test_manifest_lifecycle_contract(package, prefix, script):
    manifest = json.loads((ROOT / "bucket" / f"{package}.json").read_text())
    pre_install = "\n".join(manifest["pre_install"])
    assert "$global" in pre_install
    assert "17763" in pre_install
    assert "Existing manual font installation detected" in pre_install
    assert f"fonts\\{prefix}*.ttf" in pre_install
    assert "HKLM:" not in json.dumps(manifest)
    for operation, filename in [("installer", "Install"), ("uninstaller", "Uninstall")]:
        commands = "\n".join(manifest[operation]["script"])
        assert "powershell.exe" in commands
        assert "-NoProfile -NonInteractive" in commands
        assert f"{filename}-{script}.ps1" in commands
        assert "$LASTEXITCODE -ne 0" in commands
    pre_uninstall = "\n".join(manifest["pre_uninstall"])
    assert f"fonts\\{prefix}*.ttf" in pre_uninstall
    assert "[IO.FileShare]::None" in pre_uninstall
    assert "finally" in pre_uninstall
    assert "$handle.Dispose()" in pre_uninstall
    assert "Remove-ItemProperty" not in pre_uninstall
    assert "Copy-Item" not in pre_install


def test_windows_ci_uses_windows_powershell_and_runs_verification():
    for name in ["scoop.yml", "update-font-scoop.yml"]:
        workflow = (ROOT / ".github" / "workflows" / name).read_text()
        assert "runs-on: windows-latest" in workflow
        assert "shell: powershell" in workflow
        assert "verify_scoop.ps1" in workflow
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    assert "uses: ./.github/workflows/update-font-scoop.yml" in release
