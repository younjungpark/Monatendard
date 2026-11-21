"""Linux installer updater contract tests using synthetic archives (no network)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import stat
import struct
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UPDATER_PATH = ROOT / "packaging" / "linux" / "update_linux.py"
REPOSITORY = "younjungpark/Monatendard"


def _load_updater():
    assert UPDATER_PATH.exists(), f"Missing updater module: {UPDATER_PATH}"
    spec = importlib.util.spec_from_file_location("update_linux", UPDATER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_checksums(archives: Path) -> None:
    (archives / "SHA256SUMS.txt").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
            for path in sorted(archives.glob("*.zip"))
        ),
        encoding="utf-8",
    )


@pytest.fixture
def updater():
    return _load_updater()


@pytest.fixture
def release_files(tmp_path: Path, updater):
    shutil.copytree(ROOT / "Casks", tmp_path / "Casks")
    linux_dir = tmp_path / "packaging" / "linux"
    linux_dir.mkdir(parents=True)
    install_text = (ROOT / "packaging" / "linux" / "install.sh").read_text(encoding="utf-8")
    # Rewind fixture installer version to 0.2.2 so 0.2.3 is a forward release.
    install_text = re.sub(
        r'^RELEASE_VERSION="[^"]+"$', 'RELEASE_VERSION="0.2.2"', install_text, flags=re.M
    )
    install_text = re.sub(
        r'^STANDARD_SHA256="[^"]+"$', f'STANDARD_SHA256="{"0" * 64}"', install_text, flags=re.M
    )
    install_text = re.sub(
        r'^NERD_SHA256="[^"]+"$', f'NERD_SHA256="{"0" * 64}"', install_text, flags=re.M
    )
    installer = linux_dir / "install.sh"
    with installer.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(install_text)

    archives = tmp_path / "downloads"
    archives.mkdir()
    for _, (kind, cask, _) in updater.PACKAGES.items():
        cask_text = (tmp_path / "Casks" / f"{cask}.rb").read_text(encoding="utf-8")
        with zipfile.ZipFile(archives / f"Monatendard-v0.2.3-{kind}.zip", "w") as zipped:
            for font in re.findall(r'^  font "([^"]+)"$', cask_text, re.M):
                zipped.writestr(font, b"synthetic font fixture")
            zipped.writestr("LICENSES/LICENSE", b"OFL")
    _write_checksums(archives)
    return tmp_path, {"tag_name": "v0.2.3", "draft": False, "prerelease": False}, archives


def _rewrite_nerd_archive(files, change) -> None:
    archive = files[2] / "Monatendard-v0.2.3-Desktop-Nerd.zip"
    with zipfile.ZipFile(archive) as zipped:
        entries = {name: zipped.read(name) for name in zipped.namelist()}
    change(entries)
    with zipfile.ZipFile(archive, "w") as zipped:
        for name, content in entries.items():
            zipped.writestr(name, content)
    _write_checksums(files[2])


def test_prepare_updates_and_idempotence(updater, release_files) -> None:
    root, release, archives = release_files
    installer = root / "packaging" / "linux" / "install.sh"
    before = installer.read_bytes()

    version, updates = updater.prepare_updates(root, REPOSITORY, release, archives)
    assert version == "0.2.3"
    assert list(updates.keys()) == [installer]
    assert installer.read_bytes() == before

    updated_text = updates[installer]
    assert "\r" not in updated_text
    assert updated_text.isascii()
    std_sha = hashlib.sha256((archives / "Monatendard-v0.2.3-Desktop.zip").read_bytes()).hexdigest()
    nerd_sha = hashlib.sha256(
        (archives / "Monatendard-v0.2.3-Desktop-Nerd.zip").read_bytes()
    ).hexdigest()
    assert 'RELEASE_VERSION="0.2.3"' in updated_text
    assert (
        f'STANDARD_URL="https://github.com/{REPOSITORY}/releases/download/'
        'v0.2.3/Monatendard-v0.2.3-Desktop.zip"'
    ) in updated_text
    assert f'STANDARD_SHA256="{std_sha}"' in updated_text
    assert (
        f'NERD_URL="https://github.com/{REPOSITORY}/releases/download/'
        'v0.2.3/Monatendard-v0.2.3-Desktop-Nerd.zip"'
    ) in updated_text
    assert f'NERD_SHA256="{nerd_sha}"' in updated_text

    assert updater.write_updates(updates) is True
    mtime = installer.stat().st_mtime_ns
    repeat_updates = updater.prepare_updates(root, REPOSITORY, release, archives)[1]
    assert updater.write_updates(repeat_updates) is False
    assert installer.stat().st_mtime_ns == mtime


@pytest.mark.parametrize("field", ["draft", "prerelease"])
def test_rejects_draft_and_prerelease(updater, release_files, field: str) -> None:
    root, release, archives = release_files
    release[field] = True
    with pytest.raises(ValueError, match="Draft and prerelease"):
        updater.prepare_updates(root, REPOSITORY, release, archives)


@pytest.mark.parametrize(
    "tag", ["v0.2.3-beta.1", "0.2.3", "v01.2.3", "--help", "v0.2.3\n", None, "v0.2"]
)
def test_rejects_invalid_tags(updater, tag) -> None:
    with pytest.raises(ValueError, match="stable version"):
        updater.stable_version(tag)


def test_rejects_version_rollback(updater, release_files) -> None:
    root, release, archives = release_files
    installer = root / "packaging" / "linux" / "install.sh"
    text = installer.read_text(encoding="utf-8")
    updated = re.sub(r'^RELEASE_VERSION="[^"]+"$', 'RELEASE_VERSION="0.3.0"', text, flags=re.M)
    with installer.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)
    with pytest.raises(ValueError, match="Version rollback"):
        updater.prepare_updates(root, REPOSITORY, release, archives)


def test_rejects_checksum_mismatch_without_writing(updater, release_files) -> None:
    root, release, archives = release_files
    installer = root / "packaging" / "linux" / "install.sh"
    before = installer.read_bytes()
    with (archives / "Monatendard-v0.2.3-Desktop-Nerd.zip").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="Checksum mismatch"):
        updater.prepare_updates(root, REPOSITORY, release, archives)
    assert installer.read_bytes() == before


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "malformed", "malformed_duplicate"])
def test_rejects_bad_checksum_entries(updater, release_files, mutation: str) -> None:
    root, release, archives = release_files
    checksum_file = archives / "SHA256SUMS.txt"
    lines = checksum_file.read_text(encoding="utf-8").splitlines()
    if mutation == "missing":
        lines.pop()
    elif mutation == "duplicate":
        lines.append(lines[-1])
    elif mutation == "malformed":
        lines[-1] = "not-a-hash  " + lines[-1].split()[-1]
    else:
        lines.append("not-a-hash  " + lines[-1].split()[-1])
    checksum_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="one valid checksum"):
        updater.prepare_updates(root, REPOSITORY, release, archives)


@pytest.mark.parametrize("mutation", ["missing_font", "extra_font", "unsafe_path", "wrong_path"])
def test_rejects_invalid_archive_contents(updater, release_files, mutation: str) -> None:
    root, release, archives = release_files

    def change(entries: dict[str, bytes]) -> None:
        if mutation == "missing_font":
            entries.pop("fonts/MonatendardNFM-Regular.ttf")
        elif mutation == "extra_font":
            entries["fonts/unexpected.ttf"] = b"font"
        elif mutation == "unsafe_path":
            entries["../escape.txt"] = b"bad"
        else:
            entries["other/MonatendardNFM-Regular.ttf"] = entries.pop(
                "fonts/MonatendardNFM-Regular.ttf"
            )

    _rewrite_nerd_archive(release_files, change)
    with pytest.raises(ValueError, match="font paths|Unsafe ZIP"):
        updater.prepare_updates(root, REPOSITORY, release, archives)


def test_rejects_symlink_duplicate_and_corrupt_zip_entries(updater, release_files) -> None:
    root, release, archives = release_files
    archive = archives / "Monatendard-v0.2.3-Desktop-Nerd.zip"

    # Symlink entry rejected.
    with zipfile.ZipFile(archive, "a") as zipped:
        info = zipfile.ZipInfo("fonts/link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zipped.writestr(info, "/etc/passwd")
    _write_checksums(archives)
    with pytest.raises(ValueError, match="Symlink ZIP entry"):
        updater.prepare_updates(root, REPOSITORY, release, archives)

    # Restore clean archive and test duplicate entry.
    _rewrite_nerd_archive(release_files, lambda entries: entries.pop("fonts/link"))
    with pytest.warns(UserWarning, match="Duplicate name"), zipfile.ZipFile(archive, "a") as zipped:
        zipped.writestr("LICENSES/LICENSE", b"dup")
    _write_checksums(archives)
    with pytest.raises(ValueError, match="Duplicate ZIP"):
        updater.prepare_updates(root, REPOSITORY, release, archives)

    # Restore clean archive and corrupt stored payload while recomputing outer SHA256.
    _rewrite_nerd_archive(release_files, lambda _entries: None)
    data = bytearray(archive.read_bytes())
    name_length, extra_length = struct.unpack_from("<HH", data, 26)
    data[30 + name_length + extra_length] ^= 1
    archive.write_bytes(bytes(data))
    _write_checksums(archives)
    with pytest.raises(ValueError, match="Corrupt ZIP"):
        updater.prepare_updates(root, REPOSITORY, release, archives)


def test_local_and_online_cli_modes_and_github_output(
    updater, release_files, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root, release, archives = release_files
    monkeypatch.setattr(updater, "ROOT", root)
    output_file = tmp_path / "github_output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

    # Local mode requires --tag.
    with pytest.raises(SystemExit):
        updater.main(["--repository", REPOSITORY, "--archive-dir", str(archives)])

    # Local mode succeeds and emits GITHUB_OUTPUT.
    updater.main(["--repository", REPOSITORY, "--tag", "v0.2.3", "--archive-dir", str(archives)])
    lines = output_file.read_text(encoding="utf-8").splitlines()
    assert "version=0.2.3" in lines
    assert "changed=true" in lines

    # Online mode calls gh api + gh release download and reports changed=false on repeat.
    output_file.unlink()
    calls: list[list[str]] = []

    def fake_check_output(cmd, **kwargs):
        calls.append(cmd)
        return json.dumps(release)

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        dir_index = cmd.index("--dir") + 1
        target = Path(cmd[dir_index])
        for item in archives.iterdir():
            shutil.copy2(item, target / item.name)
        return None

    monkeypatch.setattr(updater.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.main(["--repository", REPOSITORY])
    assert calls[0][:3] == ["gh", "api", f"repos/{REPOSITORY}/releases/latest"]
    assert calls[1][:4] == ["gh", "release", "download", "v0.2.3"]
    lines2 = output_file.read_text(encoding="utf-8").splitlines()
    assert "version=0.2.3" in lines2
    assert "changed=false" in lines2
