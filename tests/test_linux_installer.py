"""Linux installer CLI contract tests at the bash process boundary."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "packaging" / "linux" / "install.sh"
STANDARD_CASK = ROOT / "Casks" / "font-monatendard.rb"
NERD_CASK = ROOT / "Casks" / "font-monatendard-nerd-font.rb"


def _cask_metadata(path: Path) -> tuple[str, str, list[str]]:
    text = path.read_text(encoding="utf-8")
    version = re.search(r'^  version "([^"]+)"$', text, re.M)
    sha256 = re.search(r'^  sha256 "([^"]+)"$', text, re.M)
    fonts = sorted(re.findall(r'^  font "([^"]+)"$', text, re.M))
    assert version is not None and sha256 is not None
    return version[1], sha256[1], fonts


def _to_wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix().split(":", 1)[1]
    return f"/mnt/{drive}{rest}"


def _linux_runner() -> list[str] | None:
    if sys.platform == "linux":
        bash = shutil.which("bash")
        return [bash] if bash else None
    if sys.platform == "win32" and shutil.which("wsl"):
        probe = subprocess.run(
            ["wsl", "-e", "bash", "-c", "uname -s"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if probe.returncode == 0 and probe.stdout.strip() == "Linux":
            return ["wsl", "-e", "bash"]
    return None


LINUX_BASH = _linux_runner()
requires_linux_bash = pytest.mark.skipif(
    LINUX_BASH is None,
    reason="Linux bash (native or WSL) is required to run installer process tests",
)


def _path_for_bash(path: Path) -> str:
    if sys.platform == "linux":
        return str(path.resolve())
    return _to_wsl_path(path)


def _write_lf(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    if executable and sys.platform == "linux":
        path.chmod(0o755)


def _make_archive(destination: Path, fonts: list[str], payload: bytes = b"synthetic-ttf") -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for font in fonts:
            zipped.writestr(font, payload)
        zipped.writestr("LICENSES/LICENSE", b"OFL")
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def _prepare_patched_installer(
    tmp_path: Path,
    *,
    version: str = "0.3.1",
    standard_sha: str,
    nerd_sha: str,
    standard_url: str | None = None,
    nerd_url: str | None = None,
) -> Path:
    text = INSTALLER.read_text(encoding="utf-8")
    standard_url = standard_url or (
        f"https://github.com/younjungpark/Monatendard/releases/download/v{version}/"
        f"Monatendard-v{version}-Desktop.zip"
    )
    nerd_url = nerd_url or (
        f"https://github.com/younjungpark/Monatendard/releases/download/v{version}/"
        f"Monatendard-v{version}-Desktop-Nerd.zip"
    )
    replacements = [
        (r'^RELEASE_VERSION="[^"]+"$', f'RELEASE_VERSION="{version}"'),
        (r'^STANDARD_URL="[^"]+"$', f'STANDARD_URL="{standard_url}"'),
        (r'^STANDARD_SHA256="[^"]+"$', f'STANDARD_SHA256="{standard_sha}"'),
        (r'^NERD_URL="[^"]+"$', f'NERD_URL="{nerd_url}"'),
        (r'^NERD_SHA256="[^"]+"$', f'NERD_SHA256="{nerd_sha}"'),
    ]
    for pattern, value in replacements:
        text, count = re.subn(pattern, lambda _, v=value: v, text, flags=re.M)
        assert count == 1, f"Missing constant for pattern: {pattern}"
    patched = tmp_path / "install.sh"
    _write_lf(patched, text, executable=True)
    return patched


def _run_installer(
    tmp_path: Path,
    script: Path,
    args: list[str],
    *,
    archives: dict[str, Path] | None = None,
    extra_stubs: dict[str, str] | None = None,
    omit_tools: set[str] | None = None,
    pipe_stdin: bool = False,
    xdg_data_home: Path | None = None,
    xdg_data_home_raw: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    assert LINUX_BASH is not None
    home_dir = tmp_path / "home"
    home_dir.mkdir(exist_ok=True)
    stub_dir = tmp_path / "stubs"
    if stub_dir.exists():
        shutil.rmtree(stub_dir)
    stub_dir.mkdir()
    fc_cache_log = tmp_path / "fc-cache.log"
    curl_log = tmp_path / "curl.log"
    omit = omit_tools or set()

    # Use a controlled PATH directory so tests can stub or omit specific tools cleanly.
    bin_dir = tmp_path / "bin"
    if bin_dir.exists():
        shutil.rmtree(bin_dir)
    bin_dir.mkdir()

    # Copy/wrap standard commands from the Linux environment except omitted ones.
    tool_links = [
        "bash", "cat", "chmod", "comm", "cp", "dirname", "find", "grep", "head",
        "id", "mkdir", "mktemp", "mv", "printf", "rm", "sed", "sha256sum",
        "sort", "tr", "uname", "unzip", "wc",
    ]
    base_stubs: dict[str, str] = {}

    if "curl" not in omit:
        cases = []
        for url, archive_path in (archives or {}).items():
            cases.append(f'    "{url}") cp "{_path_for_bash(archive_path)}" "$out" ;;')
        case_body = "\n".join(cases)
        base_stubs["curl"] = (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f'printf "%s\\n" "$*" >> "{_path_for_bash(curl_log)}"\n'
            'out=""\n'
            'url=""\n'
            'while [[ $# -gt 0 ]]; do\n'
            '  case "$1" in\n'
            '    -o) out="$2"; shift 2 ;;\n'
            '    --proto|--tlsv1.2|--connect-timeout|--max-time)\n'
            '      if [[ "$1" == "--tlsv1.2" ]]; then shift; else shift 2; fi ;;\n'
            '    -*) shift ;;\n'
            '    *) url="$1"; shift ;;\n'
            '  esac\n'
            'done\n'
            'case "$url" in\n'
            f"{case_body}\n"
            '  *) echo "unexpected URL: $url" >&2; exit 22 ;;\n'
            "esac\n"
        )

    if "fc-cache" not in omit:
        base_stubs["fc-cache"] = (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f'printf "%s\\n" "$*" >> "{_path_for_bash(fc_cache_log)}"\n'
        )

    if extra_stubs:
        base_stubs.update(extra_stubs)

    for name, body in base_stubs.items():
        if name in omit:
            continue
        _write_lf(stub_dir / name, body, executable=True)

    # Build a small launcher script run inside Linux bash that sets up isolated PATH.
    setup_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f'BIN_DIR="{_path_for_bash(bin_dir)}"',
        f'STUB_DIR="{_path_for_bash(stub_dir)}"',
        'chmod +x "$STUB_DIR"/* 2>/dev/null || true',
    ]
    for tool in tool_links:
        if tool in omit:
            continue
        setup_lines.append(
            f'if p="$(command -v {tool} 2>/dev/null)"; then ln -sf "$p" "$BIN_DIR/{tool}"; fi'
        )

    setup_lines.append('export PATH="$STUB_DIR:$BIN_DIR"')
    setup_lines.append(f'export HOME="{_path_for_bash(home_dir)}"')
    if xdg_data_home_raw is not None:
        setup_lines.append(f'export XDG_DATA_HOME="{xdg_data_home_raw}"')
    elif xdg_data_home is not None:
        setup_lines.append(f'export XDG_DATA_HOME="{_path_for_bash(xdg_data_home)}"')
    else:
        setup_lines.append("unset XDG_DATA_HOME")

    quoted_args = " ".join(f'"{a}"' for a in args)
    script_linux = _path_for_bash(script)
    if pipe_stdin:
        if quoted_args:
            setup_lines.append(f'cat "{script_linux}" | bash -s -- {quoted_args}')
        else:
            setup_lines.append(f'cat "{script_linux}" | bash')
    else:
        if quoted_args:
            setup_lines.append(f'bash "{script_linux}" {quoted_args}')
        else:
            setup_lines.append(f'bash "{script_linux}"')

    runner_script = tmp_path / "run_test.sh"
    _write_lf(runner_script, "\n".join(setup_lines) + "\n", executable=True)
    result = subprocess.run(
        [*LINUX_BASH, _path_for_bash(runner_script)],
        capture_output=True,
        text=True,
        timeout=30,
        env={k: v for k, v in os.environ.items() if k != "XDG_DATA_HOME"},
    )
    return result, home_dir, fc_cache_log


def test_installer_is_ascii_lf_and_matches_official_casks() -> None:
    for script in (INSTALLER, ROOT / "packaging" / "linux" / "verify_linux.sh"):
        raw = script.read_bytes()
        assert b"\r" not in raw, f"{script.name} must use LF line endings"
        assert raw.decode("utf-8").isascii(), f"{script.name} must be ASCII-only"

    text = INSTALLER.read_text(encoding="utf-8")

    std_ver, std_sha, std_fonts = _cask_metadata(STANDARD_CASK)
    nerd_ver, nerd_sha, nerd_fonts = _cask_metadata(NERD_CASK)
    assert std_ver == nerd_ver

    assert f'RELEASE_VERSION="{std_ver}"' in text
    assert (
        f'STANDARD_URL="https://github.com/younjungpark/Monatendard/releases/download/'
        f'v{std_ver}/Monatendard-v{std_ver}-Desktop.zip"'
    ) in text
    assert f'STANDARD_SHA256="{std_sha}"' in text
    assert (
        f'NERD_URL="https://github.com/younjungpark/Monatendard/releases/download/'
        f'v{nerd_ver}/Monatendard-v{nerd_ver}-Desktop-Nerd.zip"'
    ) in text
    assert f'NERD_SHA256="{nerd_sha}"' in text
    for font in std_fonts + nerd_fonts:
        assert f'"{font}"' in text


@requires_linux_bash
def test_help_version_and_invalid_options(tmp_path: Path) -> None:
    help_res, _, _ = _run_installer(tmp_path, INSTALLER, ["--help"])
    assert help_res.returncode == 0
    assert "--nerd" in help_res.stdout
    assert "--all" in help_res.stdout
    assert "--uninstall" in help_res.stdout
    assert "--status" in help_res.stdout
    assert "--dry-run" in help_res.stdout

    expected_version, _, _ = _cask_metadata(STANDARD_CASK)
    ver_res, _, _ = _run_installer(tmp_path, INSTALLER, ["--version"])
    assert ver_res.returncode == 0
    assert expected_version in ver_res.stdout

    for bad_args in [
        ["--unknown"],
        ["--nerd", "--all"],
        ["--version", "0.3.0"],
        ["--version", "--nerd"],
        ["--help", "--version"],
        ["--help", "--uninstall"],
        ["extra-positional"],
    ]:
        res, _, _ = _run_installer(tmp_path, INSTALLER, bad_args)
        assert res.returncode != 0, f"Expected failure for {bad_args}"


@requires_linux_bash
def test_rejects_non_linux_root_and_missing_tools(tmp_path: Path) -> None:
    non_linux, _, _ = _run_installer(
        tmp_path,
        INSTALLER,
        [],
        extra_stubs={"uname": "#!/usr/bin/env bash\necho Darwin\n"},
    )
    assert non_linux.returncode != 0
    assert "Linux" in non_linux.stderr

    as_root, _, _ = _run_installer(
        tmp_path,
        INSTALLER,
        [],
        extra_stubs={"id": "#!/usr/bin/env bash\necho 0\n"},
    )
    assert as_root.returncode != 0
    assert "root" in as_root.stderr.lower()

    for missing in ({"curl"}, {"unzip"}, {"sha256sum"}, {"fc-cache"}):
        res, _, _ = _run_installer(tmp_path, INSTALLER, [], omit_tools=missing)
        assert res.returncode != 0, f"Expected failure when omitting {missing}"


@requires_linux_bash
def test_default_install_via_pipe_and_idempotent_update(tmp_path: Path) -> None:
    _, _, std_fonts = _cask_metadata(STANDARD_CASK)
    _, _, nerd_fonts = _cask_metadata(NERD_CASK)
    zip_v1 = tmp_path / "std-v1.zip"
    sha_v1 = _make_archive(zip_v1, std_fonts, b"font-v1")
    url_v1 = (
        "https://github.com/younjungpark/Monatendard/releases/download/"
        "v0.3.1/Monatendard-v0.3.1-Desktop.zip"
    )
    script_v1 = _prepare_patched_installer(
        tmp_path / "v1", version="0.3.1", standard_sha=sha_v1, nerd_sha="0" * 64
    )

    res, home_dir, fc_log = _run_installer(
        tmp_path,
        script_v1,
        [],
        archives={url_v1: zip_v1},
        pipe_stdin=True,
    )
    assert res.returncode == 0, res.stderr
    target_dir = home_dir / ".local" / "share" / "fonts" / "monatendard"
    assert sorted(p.name for p in target_dir.glob("*.ttf")) == sorted(
        Path(f).name for f in std_fonts
    )
    assert (target_dir / "Monatendard-Regular.ttf").read_bytes() == b"font-v1"
    marker = (target_dir / ".monatendard-managed").read_text(encoding="utf-8")
    assert "family=monatendard" in marker
    assert "version=0.3.1" in marker
    assert fc_log.exists() and "-f" in fc_log.read_text(encoding="utf-8")

    # Idempotent upgrade to a newer version replaces managed files cleanly.
    zip_v2 = tmp_path / "std-v2.zip"
    sha_v2 = _make_archive(zip_v2, std_fonts, b"font-v2")
    url_v2 = (
        "https://github.com/younjungpark/Monatendard/releases/download/"
        "v0.3.2/Monatendard-v0.3.2-Desktop.zip"
    )
    script_v2 = _prepare_patched_installer(
        tmp_path / "v2", version="0.3.2", standard_sha=sha_v2, nerd_sha="0" * 64
    )
    res2, _, _ = _run_installer(
        tmp_path,
        script_v2,
        [],
        archives={url_v2: zip_v2},
    )
    assert res2.returncode == 0, res2.stderr
    assert (target_dir / "Monatendard-Regular.ttf").read_bytes() == b"font-v2"
    assert "version=0.3.2" in (target_dir / ".monatendard-managed").read_text(encoding="utf-8")
    assert not (home_dir / ".local" / "share" / "fonts" / "monatendard-nerd").exists()
    assert len(nerd_fonts) == 14


@requires_linux_bash
def test_nerd_coexistence_all_and_uninstall_lifecycle(tmp_path: Path) -> None:
    _, _, std_fonts = _cask_metadata(STANDARD_CASK)
    _, _, nerd_fonts = _cask_metadata(NERD_CASK)
    std_zip = tmp_path / "std.zip"
    nerd_zip = tmp_path / "nerd.zip"
    std_sha = _make_archive(std_zip, std_fonts, b"std-bytes")
    nerd_sha = _make_archive(nerd_zip, nerd_fonts, b"nerd-bytes")
    std_url = (
        "https://github.com/younjungpark/Monatendard/releases/download/"
        "v0.3.1/Monatendard-v0.3.1-Desktop.zip"
    )
    nerd_url = (
        "https://github.com/younjungpark/Monatendard/releases/download/"
        "v0.3.1/Monatendard-v0.3.1-Desktop-Nerd.zip"
    )
    script = _prepare_patched_installer(
        tmp_path / "script", version="0.3.1", standard_sha=std_sha, nerd_sha=nerd_sha
    )
    archives = {std_url: std_zip, nerd_url: nerd_zip}

    # Install Nerd only.
    res, home_dir, _ = _run_installer(tmp_path, script, ["--nerd"], archives=archives)
    assert res.returncode == 0, res.stderr
    fonts_root = home_dir / ".local" / "share" / "fonts"
    assert not (fonts_root / "monatendard").exists()
    assert (fonts_root / "monatendard-nerd" / "MonatendardNFM-Regular.ttf").exists()

    # Install both (--all): Standard installed alongside existing Nerd.
    res_all, _, _ = _run_installer(tmp_path, script, ["--all"], archives=archives)
    assert res_all.returncode == 0, res_all.stderr
    assert (fonts_root / "monatendard" / "Monatendard-Regular.ttf").exists()
    assert (fonts_root / "monatendard-nerd" / "MonatendardNFM-Regular.ttf").exists()

    # Uninstall Standard only: Nerd remains intact.
    res_unstd, _, _ = _run_installer(tmp_path, script, ["--uninstall"])
    assert res_unstd.returncode == 0, res_unstd.stderr
    assert not (fonts_root / "monatendard").exists()
    assert (fonts_root / "monatendard-nerd" / "MonatendardNFM-Regular.ttf").exists()

    # Uninstalling already-absent Standard exits 0 cleanly.
    res_again, _, _ = _run_installer(tmp_path, script, ["--uninstall"])
    assert res_again.returncode == 0, res_again.stderr
    assert "not installed" in res_again.stdout.lower()

    # Uninstall --all cleans up remaining Nerd cleanly (exit 0 even when Standard absent).
    res_unall, _, _ = _run_installer(tmp_path, script, ["--all", "--uninstall"])
    assert res_unall.returncode == 0, res_unall.stderr
    assert not (fonts_root / "monatendard-nerd").exists()


@requires_linux_bash
def test_dry_run_makes_no_changes_and_custom_xdg_works(tmp_path: Path) -> None:
    _, _, std_fonts = _cask_metadata(STANDARD_CASK)
    std_zip = tmp_path / "std.zip"
    std_sha = _make_archive(std_zip, std_fonts, b"std-bytes")
    std_url = (
        "https://github.com/younjungpark/Monatendard/releases/download/"
        "v0.3.1/Monatendard-v0.3.1-Desktop.zip"
    )
    script = _prepare_patched_installer(
        tmp_path / "script", version="0.3.1", standard_sha=std_sha, nerd_sha="0" * 64
    )
    custom_xdg = tmp_path / "custom-data"

    # Relative XDG_DATA_HOME is rejected.
    rel_res, _, _ = _run_installer(
        tmp_path, script, ["--dry-run"], xdg_data_home_raw="relative/xdg"
    )
    assert rel_res.returncode != 0

    # Dry-run install leaves disk and fc-cache untouched.
    dry_res, _, fc_log = _run_installer(
        tmp_path, script, ["--dry-run"], archives={std_url: std_zip}, xdg_data_home=custom_xdg
    )
    assert dry_res.returncode == 0, dry_res.stderr
    assert "[dry-run]" in dry_res.stdout
    assert not (custom_xdg / "fonts" / "monatendard").exists()
    assert not fc_log.exists()

    # Actual install into custom XDG_DATA_HOME, then dry-run uninstall keeps files.
    inst_res, _, _ = _run_installer(
        tmp_path, script, [], archives={std_url: std_zip}, xdg_data_home=custom_xdg
    )
    assert inst_res.returncode == 0, inst_res.stderr
    assert (custom_xdg / "fonts" / "monatendard" / "Monatendard-Regular.ttf").exists()

    fc_log.unlink()
    dry_un, _, _ = _run_installer(
        tmp_path, script, ["--uninstall", "--dry-run"], xdg_data_home=custom_xdg
    )
    assert dry_un.returncode == 0, dry_un.stderr
    assert (custom_xdg / "fonts" / "monatendard" / "Monatendard-Regular.ttf").exists()
    assert not fc_log.exists()


@requires_linux_bash
def test_manual_install_conflicts_block_install_all_and_uninstall(tmp_path: Path) -> None:
    _, _, std_fonts = _cask_metadata(STANDARD_CASK)
    _, _, nerd_fonts = _cask_metadata(NERD_CASK)
    std_zip = tmp_path / "std.zip"
    nerd_zip = tmp_path / "nerd.zip"
    std_sha = _make_archive(std_zip, std_fonts, b"std-bytes")
    nerd_sha = _make_archive(nerd_zip, nerd_fonts, b"nerd-bytes")
    std_url = (
        "https://github.com/younjungpark/Monatendard/releases/download/"
        "v0.3.1/Monatendard-v0.3.1-Desktop.zip"
    )
    nerd_url = (
        "https://github.com/younjungpark/Monatendard/releases/download/"
        "v0.3.1/Monatendard-v0.3.1-Desktop-Nerd.zip"
    )
    script = _prepare_patched_installer(
        tmp_path / "script", version="0.3.1", standard_sha=std_sha, nerd_sha=nerd_sha
    )
    archives = {std_url: std_zip, nerd_url: nerd_zip}
    home_dir = tmp_path / "home"
    fonts_root = home_dir / ".local" / "share" / "fonts"

    # 1. External manual font in XDG root blocks --all before installing either family.
    manual_nerd = fonts_root / "custom" / "MonatendardNFM-Regular.ttf"
    manual_nerd.parent.mkdir(parents=True, exist_ok=True)
    manual_nerd.write_bytes(b"manual-nerd")
    res_all, _, _ = _run_installer(tmp_path, script, ["--all"], archives=archives)
    assert res_all.returncode != 0
    assert not (fonts_root / "monatendard").exists()
    assert not (fonts_root / "monatendard-nerd").exists()

    # Standard alone is unaffected by a manual Nerd file (coexistence).
    res_std, _, _ = _run_installer(tmp_path, script, [], archives=archives)
    assert res_std.returncode == 0, res_std.stderr
    assert (fonts_root / "monatendard" / "Monatendard-Regular.ttf").exists()

    # Uninstalling Nerd fails (exit 1) when only manual Nerd exists, without deleting it.
    res_un_manual, _, _ = _run_installer(tmp_path, script, ["--nerd", "--uninstall"])
    assert res_un_manual.returncode != 0
    assert manual_nerd.exists()
    manual_nerd.unlink()

    # 2. Legacy ~/.fonts conflict also blocks installation.
    legacy_file = home_dir / ".fonts" / "MonatendardNFM-Bold.ttf"
    legacy_file.parent.mkdir(parents=True, exist_ok=True)
    legacy_file.write_bytes(b"legacy")
    res_legacy, _, _ = _run_installer(tmp_path, script, ["--nerd"], archives=archives)
    assert res_legacy.returncode != 0
    assert "Manual installation conflict" in res_legacy.stderr
    legacy_file.unlink()

    # 3. Unmarked target directory blocks install and uninstall.
    unmarked = fonts_root / "monatendard-nerd"
    unmarked.mkdir(parents=True)
    (unmarked / "MonatendardNFM-Regular.ttf").write_bytes(b"unmarked")
    res_unmarked, _, _ = _run_installer(tmp_path, script, ["--nerd"], archives=archives)
    assert res_unmarked.returncode != 0
    res_unmarked_rm, _, _ = _run_installer(tmp_path, script, ["--nerd", "--uninstall"])
    assert res_unmarked_rm.returncode != 0
    assert (unmarked / "MonatendardNFM-Regular.ttf").exists()


@requires_linux_bash
def test_archive_integrity_security_and_wget_fallback(tmp_path: Path) -> None:
    _, _, std_fonts = _cask_metadata(STANDARD_CASK)
    std_url = (
        "https://github.com/younjungpark/Monatendard/releases/download/"
        "v0.3.1/Monatendard-v0.3.1-Desktop.zip"
    )

    # 1. SHA256 mismatch is rejected.
    good_zip = tmp_path / "good.zip"
    _make_archive(good_zip, std_fonts, b"good")
    bad_sha_script = _prepare_patched_installer(
        tmp_path / "bad-sha", version="0.3.1", standard_sha="f" * 64, nerd_sha="0" * 64
    )
    res_sha, home_dir, _ = _run_installer(
        tmp_path, bad_sha_script, [], archives={std_url: good_zip}
    )
    assert res_sha.returncode != 0
    assert "SHA256 mismatch" in res_sha.stderr
    assert not (home_dir / ".local" / "share" / "fonts" / "monatendard").exists()

    # 2. Path traversal entry is rejected even when SHA256 matches.
    traversal_zip = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal_zip, "w") as zipped:
        for font in std_fonts:
            zipped.writestr(font, b"ok")
        zipped.writestr("../escape.txt", b"evil")
    trav_sha = hashlib.sha256(traversal_zip.read_bytes()).hexdigest()
    trav_script = _prepare_patched_installer(
        tmp_path / "trav", version="0.3.1", standard_sha=trav_sha, nerd_sha="0" * 64
    )
    res_trav, _, _ = _run_installer(tmp_path, trav_script, [], archives={std_url: traversal_zip})
    assert res_trav.returncode != 0
    assert "Unsafe path" in res_trav.stderr

    # 3. Symlink entry in ZIP is rejected even when SHA256 matches.
    symlink_zip = tmp_path / "symlink.zip"
    with zipfile.ZipFile(symlink_zip, "w") as zipped:
        for font in std_fonts:
            zipped.writestr(font, b"ok")
        info = zipfile.ZipInfo("fonts/link")
        info.create_system = 3
        info.external_attr = (0o120777 << 16)
        zipped.writestr(info, "/etc/passwd")
    sym_sha = hashlib.sha256(symlink_zip.read_bytes()).hexdigest()
    sym_script = _prepare_patched_installer(
        tmp_path / "sym", version="0.3.1", standard_sha=sym_sha, nerd_sha="0" * 64
    )
    res_sym, _, _ = _run_installer(tmp_path, sym_script, [], archives={std_url: symlink_zip})
    assert res_sym.returncode != 0
    assert "Symlink" in res_sym.stderr

    # 4. Missing TTF entry is rejected even when SHA256 matches.
    short_zip = tmp_path / "short.zip"
    short_sha = _make_archive(short_zip, std_fonts[:-1], b"short")
    short_script = _prepare_patched_installer(
        tmp_path / "short", version="0.3.1", standard_sha=short_sha, nerd_sha="0" * 64
    )
    res_short, _, _ = _run_installer(tmp_path, short_script, [], archives={std_url: short_zip})
    assert res_short.returncode != 0
    assert "14 TTF" in res_short.stderr

    # 5. wget fallback works when curl is absent.
    good_sha = hashlib.sha256(good_zip.read_bytes()).hexdigest()
    good_script = _prepare_patched_installer(
        tmp_path / "wget-test", version="0.3.1", standard_sha=good_sha, nerd_sha="0" * 64
    )
    wget_stub = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'out=""\n'
        'url=""\n'
        'while [[ $# -gt 0 ]]; do\n'
        '  case "$1" in\n'
        '    -qO) out="$2"; shift 2 ;;\n'
        '    --*) shift ;;\n'
        '    *) url="$1"; shift ;;\n'
        '  esac\n'
        'done\n'
        f'if [[ "$url" == "{std_url}" ]]; then\n'
        f'  cp "{_path_for_bash(good_zip)}" "$out"\n'
        "else\n"
        "  exit 1\n"
        "fi\n"
    )
    res_wget, _, _ = _run_installer(
        tmp_path,
        good_script,
        [],
        omit_tools={"curl"},
        extra_stubs={"wget": wget_stub},
    )
    assert res_wget.returncode == 0, res_wget.stderr
    installed_regular = (
        home_dir / ".local" / "share" / "fonts" / "monatendard" / "Monatendard-Regular.ttf"
    )
    assert installed_regular.exists()


@requires_linux_bash
def test_atomic_swap_failure_rolls_back_previous_managed_installation(tmp_path: Path) -> None:
    _, _, std_fonts = _cask_metadata(STANDARD_CASK)
    zip_v1 = tmp_path / "v1.zip"
    zip_v2 = tmp_path / "v2.zip"
    sha_v1 = _make_archive(zip_v1, std_fonts, b"version-1")
    sha_v2 = _make_archive(zip_v2, std_fonts, b"version-2")
    url_v1 = (
        "https://github.com/younjungpark/Monatendard/releases/download/"
        "v0.3.1/Monatendard-v0.3.1-Desktop.zip"
    )
    url_v2 = (
        "https://github.com/younjungpark/Monatendard/releases/download/"
        "v0.3.2/Monatendard-v0.3.2-Desktop.zip"
    )
    script_v1 = _prepare_patched_installer(
        tmp_path / "s1", version="0.3.1", standard_sha=sha_v1, nerd_sha="0" * 64
    )
    script_v2 = _prepare_patched_installer(
        tmp_path / "s2", version="0.3.2", standard_sha=sha_v2, nerd_sha="0" * 64
    )

    res1, home_dir, _ = _run_installer(tmp_path, script_v1, [], archives={url_v1: zip_v1})
    assert res1.returncode == 0, res1.stderr

    # Inject a failing mv only for the staging -> target swap; backup and rollback mv succeed.
    mv_stub = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'if [[ "$1" == *".monatendard-staging-"* && "$2" == *"/monatendard" ]]; then\n'
        "  exit 1\n"
        "fi\n"
        'exec /bin/mv "$@"\n'
    )
    res2, _, _ = _run_installer(
        tmp_path,
        script_v2,
        [],
        archives={url_v2: zip_v2},
        extra_stubs={"mv": mv_stub},
    )
    assert res2.returncode != 0
    target_dir = home_dir / ".local" / "share" / "fonts" / "monatendard"
    assert (target_dir / "Monatendard-Regular.ttf").read_bytes() == b"version-1"
    assert "version=0.3.1" in (target_dir / ".monatendard-managed").read_text(encoding="utf-8")


@requires_linux_bash
def test_managed_dir_tolerates_fontconfig_uuid_but_blocks_unknown_files(tmp_path: Path) -> None:
    _, _, std_fonts = _cask_metadata(STANDARD_CASK)
    std_zip = tmp_path / "std.zip"
    std_sha = _make_archive(std_zip, std_fonts, b"std-v1")
    std_url = (
        "https://github.com/younjungpark/Monatendard/releases/download/"
        "v0.3.1/Monatendard-v0.3.1-Desktop.zip"
    )
    script = _prepare_patched_installer(
        tmp_path / "script", version="0.3.1", standard_sha=std_sha, nerd_sha="0" * 64
    )

    res1, home_dir, _ = _run_installer(tmp_path, script, [], archives={std_url: std_zip})
    assert res1.returncode == 0, res1.stderr
    target_dir = home_dir / ".local" / "share" / "fonts" / "monatendard"

    # fontconfig on Ubuntu 20.04 creates .uuid inside font directories; update must succeed.
    (target_dir / ".uuid").write_text("11111111-2222-3333-4444-555555555555\n", encoding="utf-8")
    res_update, _, _ = _run_installer(tmp_path, script, [], archives={std_url: std_zip})
    assert res_update.returncode == 0, res_update.stderr

    # An arbitrary unmanaged file inside the managed directory must block uninstall.
    unmanaged = target_dir / "UserCustom.ttf"
    unmanaged.write_bytes(b"custom")
    res_unmanaged, _, _ = _run_installer(tmp_path, script, ["--uninstall"])
    assert res_unmanaged.returncode != 0
    assert unmanaged.exists()


@requires_linux_bash
def test_status_reports_not_installed_managed_outdated_manual_and_conflict(tmp_path: Path) -> None:
    _, _, std_fonts = _cask_metadata(STANDARD_CASK)
    _, _, nerd_fonts = _cask_metadata(NERD_CASK)
    std_zip = tmp_path / "std.zip"
    nerd_zip = tmp_path / "nerd.zip"
    std_sha = _make_archive(std_zip, std_fonts, b"std-v1")
    nerd_sha = _make_archive(nerd_zip, nerd_fonts, b"nerd-v1")
    std_url = (
        "https://github.com/younjungpark/Monatendard/releases/download/"
        "v0.3.1/Monatendard-v0.3.1-Desktop.zip"
    )
    nerd_url = (
        "https://github.com/younjungpark/Monatendard/releases/download/"
        "v0.3.1/Monatendard-v0.3.1-Desktop-Nerd.zip"
    )
    script = _prepare_patched_installer(
        tmp_path / "script", version="0.3.1", standard_sha=std_sha, nerd_sha=nerd_sha
    )
    archives = {std_url: std_zip, nerd_url: nerd_zip}

    # Conflicting flag combinations with --status are rejected.
    for bad_args in (
        ["--status", "--uninstall"],
        ["--uninstall", "--status"],
        ["--status", "--dry-run"],
        ["--status", "--help"],
        ["--status", "--version"],
    ):
        res_bad, _, _ = _run_installer(tmp_path, script, bad_args)
        assert res_bad.returncode != 0

    # Works even without fc-cache, curl, unzip, or sha256sum when not installed.
    res_empty, home_dir, _ = _run_installer(
        tmp_path,
        script,
        ["--status"],
        omit_tools={"fc-cache", "curl", "unzip", "sha256sum"},
    )
    assert res_empty.returncode == 0, res_empty.stderr
    assert "Monatendard: not installed" in res_empty.stdout
    assert "Monatendard Nerd Font Mono: not installed" in res_empty.stdout

    # Managed standard install reports up-to-date; nerd remains not installed.
    res_install, _, _ = _run_installer(tmp_path, script, [], archives=archives)
    assert res_install.returncode == 0, res_install.stderr
    res_up, _, _ = _run_installer(tmp_path, script, ["--status"])
    assert res_up.returncode == 0, res_up.stderr
    assert "Monatendard: installed (managed, v0.3.1, up-to-date)" in res_up.stdout
    assert "Monatendard Nerd Font Mono: not installed" in res_up.stdout

    # Older marker version reports update available.
    marker = home_dir / ".local" / "share" / "fonts" / "monatendard" / ".monatendard-managed"
    marker.write_text(
        marker.read_text(encoding="utf-8").replace("version=0.3.1", "version=0.3.0"),
        encoding="utf-8",
        newline="\n",
    )
    res_outdated, _, _ = _run_installer(tmp_path, script, ["--status"])
    assert res_outdated.returncode == 0, res_outdated.stderr
    assert (
        "Monatendard: installed (managed, v0.3.0, update available: v0.3.1)"
        in res_outdated.stdout
    )

    # External manual files alongside managed dir report conflict; manual-only reports manual.
    fonts_root = home_dir / ".local" / "share" / "fonts"
    conflict_file = fonts_root / "custom" / "Monatendard-Regular.ttf"
    conflict_file.parent.mkdir(parents=True, exist_ok=True)
    conflict_file.write_bytes(b"manual-std")
    manual_nerd = fonts_root / "custom" / "MonatendardNFM-Regular.ttf"
    manual_nerd.write_bytes(b"manual-nerd")

    res_conflict, _, _ = _run_installer(tmp_path, script, ["--all", "--status"])
    assert res_conflict.returncode == 0, res_conflict.stderr
    assert "Monatendard: conflict (managed v0.3.0" in res_conflict.stdout
    assert "Monatendard Nerd Font Mono: manual installation detected" in res_conflict.stdout

    res_nerd_only, _, _ = _run_installer(tmp_path, script, ["--nerd", "--status"])
    assert res_nerd_only.returncode == 0, res_nerd_only.stderr
    assert "Monatendard Nerd Font Mono: manual installation detected" in res_nerd_only.stdout
    assert "Monatendard: conflict" not in res_nerd_only.stdout

