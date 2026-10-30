"""Scoop publication uses synthetic archives; no network or real release hashes."""

import hashlib
import importlib.util
import json
import re
import shutil
import struct
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "update_scoop", ROOT / "packaging/windows/update_scoop.py"
)
assert SPEC is not None and SPEC.loader is not None
UPDATER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATER)
REPOSITORY = "younjungpark/Monatendard"


def checksums(archives):
    (archives / "SHA256SUMS.txt").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
            for path in sorted(archives.glob("*.zip"))
        ),
        encoding="utf-8",
    )


@pytest.fixture
def release_files(tmp_path):
    (tmp_path / "bucket").mkdir()
    shutil.copytree(ROOT / "Casks", tmp_path / "Casks")
    archives = tmp_path / "downloads"
    archives.mkdir()
    for token, (kind, cask, script_name) in UPDATER.PACKAGES.items():
        manifest = {
            "version": "0.2.2", "url": "https://example.invalid/old.zip", "hash": "0" * 64,
            "homepage": "https://monatendard.github.io/",
            "installer": {"script": ["keep existing lifecycle"]},
        }
        (tmp_path / "bucket" / f"{token}.json").write_text(json.dumps(manifest))
        cask_text = (tmp_path / "Casks" / f"{cask}.rb").read_text()
        with zipfile.ZipFile(archives / f"Monatendard-v0.2.3-{kind}.zip", "w") as zipped:
            for font in re.findall(r'^  font "([^"]+)"$', cask_text, re.M):
                zipped.writestr(font, b"synthetic font fixture")
            for action in ("Install", "Uninstall"):
                zipped.writestr(f"{action}-{script_name}.ps1", b"# synthetic legacy script\n")
    checksums(archives)
    return tmp_path, {"tag_name": "v0.2.3", "draft": False, "prerelease": False}, archives


def prepare(files):
    return UPDATER.prepare_updates(files[0], REPOSITORY, files[1], files[2])


def snapshot(files):
    return {path: path.read_bytes() for path in (files[0] / "bucket").glob("*.json")}


def rewrite_archive(files, change):
    archive = files[2] / "Monatendard-v0.2.3-Desktop-Nerd.zip"
    with zipfile.ZipFile(archive) as zipped:
        entries = {name: zipped.read(name) for name in zipped.namelist()}
    change(entries)
    with zipfile.ZipFile(archive, "w") as zipped:
        for name, content in entries.items():
            zipped.writestr(name, content)
    checksums(files[2])


def test_prepare_updates_and_idempotence(release_files):
    before = snapshot(release_files)
    version, updates = prepare(release_files)
    assert version == "0.2.3"
    assert len(updates) == 2
    assert snapshot(release_files) == before
    for path, text in updates.items():
        manifest = json.loads(text)
        kind = UPDATER.PACKAGES[path.stem][0]
        filename = f"Monatendard-v0.2.3-{kind}.zip"
        assert manifest["version"] == version
        assert manifest["url"] == (
            f"https://github.com/{REPOSITORY}/releases/download/v0.2.3/{filename}"
        )
        assert manifest["hash"] == hashlib.sha256(
            (release_files[2] / filename).read_bytes()
        ).hexdigest()
        assert manifest["installer"] == {"script": ["keep existing lifecycle"]}
    assert UPDATER.write_updates(updates) is True
    assert prepare(release_files)[1] == updates
    mtimes = {path: path.stat().st_mtime_ns for path in updates}
    assert UPDATER.write_updates(prepare(release_files)[1]) is False
    assert {path: path.stat().st_mtime_ns for path in updates} == mtimes


@pytest.mark.parametrize("field", ["draft", "prerelease"])
def test_unstable_release(release_files, field):
    release_files[1][field] = True
    with pytest.raises(ValueError, match="Draft and prerelease"):
        prepare(release_files)


@pytest.mark.parametrize("tag", ["v0.2.3-beta", "0.2.3", "v01.2.3", "--help", "v0.2.3\n",
                                  "v١.2.3", None, "v0.2"])
def test_invalid_tag(tag):
    with pytest.raises(ValueError, match="stable version"):
        UPDATER.stable_version(tag)


@pytest.mark.parametrize("repository", ["owner", "owner/name/extra", "--owner/name", "owner/..",
                                         "owner/.", "owner/name\n", "https://github.com/o/r", None])
def test_invalid_repository(release_files, repository):
    with pytest.raises(ValueError, match="owner/name"):
        UPDATER.prepare_updates(release_files[0], repository, release_files[1], release_files[2])


def test_second_archive_hash_failure_prevents_all_writes(release_files):
    before = snapshot(release_files)
    with (release_files[2] / "Monatendard-v0.2.3-Desktop-Nerd.zip").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(ValueError, match="Checksum mismatch"):
        prepare(release_files)
    assert snapshot(release_files) == before


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "malformed", "malformed_duplicate"])
def test_checksum_entries(release_files, mutation):
    path = release_files[2] / "SHA256SUMS.txt"
    lines = path.read_text().splitlines()
    if mutation == "missing":
        lines.pop()
    elif mutation == "duplicate":
        lines.append(lines[-1])
    elif mutation == "malformed":
        lines[-1] = "not-a-hash  " + lines[-1].split()[-1]
    else:
        lines.append("not-a-hash  " + lines[-1].split()[-1])
    path.write_text("\n".join(lines))
    with pytest.raises(ValueError, match="one valid checksum"):
        prepare(release_files)


def test_binary_checksum_format(release_files):
    path = release_files[2] / "SHA256SUMS.txt"
    path.write_text("".join(
        f"{digest.upper()} *{filename}\n"
        for digest, filename in (line.split() for line in path.read_text().splitlines())
    ))
    assert prepare(release_files)[0] == "0.2.3"


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_font",
        "extra_font",
        "missing_script",
        "empty_script",
        "unsafe_path",
        "wrong_font_path",
    ],
)
def test_archive_contents(release_files, mutation):
    def change(entries):
        if mutation == "missing_font":
            entries.pop("fonts/MonatendardNFM-Regular.ttf")
        elif mutation == "extra_font":
            entries["fonts/unexpected.ttf"] = b"font"
        elif mutation == "missing_script":
            entries.pop("Uninstall-Monatendard-Nerd.ps1")
        elif mutation == "empty_script":
            entries["Install-Monatendard-Nerd.ps1"] = b""
        elif mutation == "unsafe_path":
            entries["../outside"] = b"bad"
        else:
            entries["other/MonatendardNFM-Regular.ttf"] = entries.pop(
                "fonts/MonatendardNFM-Regular.ttf"
            )
    before = snapshot(release_files)
    rewrite_archive(release_files, change)
    with pytest.raises(ValueError, match="font paths|bundled script|Unsafe ZIP"):
        prepare(release_files)
    assert snapshot(release_files) == before


def test_duplicate_zip_entry(release_files):
    archive = release_files[2] / "Monatendard-v0.2.3-Desktop-Nerd.zip"
    with pytest.warns(UserWarning, match="Duplicate name"), zipfile.ZipFile(archive, "a") as zipped:
        zipped.writestr("Install-Monatendard-Nerd.ps1", b"duplicate")
    checksums(release_files[2])
    with pytest.raises(ValueError, match="Duplicate ZIP"):
        prepare(release_files)


def test_corrupt_zip_crc_even_when_checksum_matches(release_files):
    archive = release_files[2] / "Monatendard-v0.2.3-Desktop-Nerd.zip"
    data = bytearray(archive.read_bytes())
    # Mutate the first stored payload without updating ZIP's CRC, but rehash SHA256SUMS.
    name_length, extra_length = struct.unpack_from("<HH", data, 26)
    data[30 + name_length + extra_length] ^= 1
    archive.write_bytes(data)
    checksums(release_files[2])
    with pytest.raises(ValueError, match="Corrupt ZIP"):
        prepare(release_files)


def test_invalid_zip(release_files):
    (release_files[2] / "Monatendard-v0.2.3-Desktop-Nerd.zip").write_bytes(b"not a ZIP")
    checksums(release_files[2])
    with pytest.raises(zipfile.BadZipFile):
        prepare(release_files)


def test_rollback_in_second_manifest(release_files):
    path = release_files[0] / "bucket/monatendard-nerd.json"
    path.write_text(path.read_text().replace("0.2.2", "0.2.4"))
    before = snapshot(release_files)
    with pytest.raises(ValueError, match="rollback"):
        prepare(release_files)
    assert snapshot(release_files) == before


@pytest.mark.parametrize("field", ["version", "url", "hash"])
def test_missing_manifest_field(release_files, field):
    path = release_files[0] / "bucket/monatendard-nerd.json"
    manifest = json.loads(path.read_text())
    del manifest[field]
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Expected string"):
        prepare(release_files)


def test_local_cli_and_github_output(release_files, monkeypatch, tmp_path):
    monkeypatch.setattr(UPDATER, "ROOT", release_files[0])
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    def no_network(*args, **kwargs):
        pytest.fail("local mode must not use gh")
    monkeypatch.setattr(UPDATER.subprocess, "check_output", no_network)
    monkeypatch.setattr(UPDATER.subprocess, "run", no_network)
    argv = ["--repository", REPOSITORY, "--tag", "v0.2.3",
            "--archive-dir", str(release_files[2])]
    UPDATER.main(argv)
    UPDATER.main(argv)
    assert output.read_text() == "version=0.2.3\nchanged=true\nversion=0.2.3\nchanged=false\n"
    assert all(
        json.loads(path.read_text())["version"] == "0.2.3" for path in snapshot(release_files)
    )


def test_local_cli_requires_tag(release_files):
    with pytest.raises(SystemExit, match="2"):
        UPDATER.main(["--repository", REPOSITORY, "--archive-dir", str(release_files[2])])


def test_local_cli_failure_does_not_publish_or_emit_output(release_files, monkeypatch, tmp_path):
    monkeypatch.setattr(UPDATER, "ROOT", release_files[0])
    output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    before = snapshot(release_files)
    rewrite_archive(release_files, lambda entries: entries.pop("Uninstall-Monatendard-Nerd.ps1"))
    with pytest.raises(ValueError, match="bundled script"):
        UPDATER.main([
            "--repository", REPOSITORY, "--tag", "v0.2.3",
            "--archive-dir", str(release_files[2]),
        ])
    assert snapshot(release_files) == before
    assert not output.exists()


def test_staging_failure_preserves_both_manifests(release_files, monkeypatch):
    _, updates = prepare(release_files)
    before = snapshot(release_files)
    original = UPDATER.tempfile.NamedTemporaryFile
    calls = []

    def fail_second_stage(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            raise OSError("synthetic staging failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(UPDATER.tempfile, "NamedTemporaryFile", fail_second_stage)
    with pytest.raises(OSError, match="staging failure"):
        UPDATER.write_updates(updates)
    assert snapshot(release_files) == before
    assert sorted(path.name for path in (release_files[0] / "bucket").iterdir()) == [
        "monatendard-nerd.json", "monatendard.json",
    ]


@pytest.mark.parametrize("tag", ["", "v0.2.3"])
def test_online_cli_fetches_metadata_and_exact_assets(release_files, monkeypatch, tag):
    monkeypatch.setattr(UPDATER, "ROOT", release_files[0])
    calls = []
    def metadata(command, **kwargs):
        endpoint = "tags/v0.2.3" if tag else "latest"
        assert command == ["gh", "api", f"repos/{REPOSITORY}/releases/{endpoint}"]
        return json.dumps(release_files[1])
    def download(command, **kwargs):
        calls.append(command)
        assert kwargs == {"check": True}
        destination = Path(command[command.index("--dir") + 1])
        for source in release_files[2].iterdir():
            shutil.copyfile(source, destination / source.name)
    monkeypatch.setattr(UPDATER.subprocess, "check_output", metadata)
    monkeypatch.setattr(UPDATER.subprocess, "run", download)
    UPDATER.main(["--repository", REPOSITORY] + (["--tag", tag] if tag else []))
    assert calls[0][:6] == ["gh", "release", "download", "v0.2.3", "--repo", REPOSITORY]
    assert calls[0][-6:] == ["--pattern", "Monatendard-v0.2.3-Desktop.zip", "--pattern",
                            "Monatendard-v0.2.3-Desktop-Nerd.zip", "--pattern", "SHA256SUMS.txt"]
    assert all(
        json.loads(path.read_text())["version"] == "0.2.3" for path in snapshot(release_files)
    )


@pytest.mark.parametrize("mutation", ["draft", "prerelease", "tag_mismatch"])
def test_online_rejects_metadata_before_download(release_files, monkeypatch, mutation):
    monkeypatch.setattr(UPDATER, "ROOT", release_files[0])
    release = dict(release_files[1])
    if mutation == "tag_mismatch":
        release["tag_name"] = "v0.2.4"
    else:
        release[mutation] = True
    monkeypatch.setattr(UPDATER.subprocess, "check_output", lambda *a, **k: json.dumps(release))
    def no_download(*args, **kwargs):
        pytest.fail("invalid metadata must not trigger download")
    monkeypatch.setattr(UPDATER.subprocess, "run", no_download)
    before = snapshot(release_files)
    with pytest.raises(ValueError):
        UPDATER.main(["--repository", REPOSITORY, "--tag", "v0.2.3"])
    assert snapshot(release_files) == before
