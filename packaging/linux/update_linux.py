"""Verify official Desktop release archives before updating the Linux installer.

Online mode uses gh release metadata and assets. --archive-dir is explicitly local
mode: --tag is mandatory and no claim about published release metadata is made.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = {
    "standard": ("Desktop", "font-monatendard", "STANDARD"),
    "nerd": ("Desktop-Nerd", "font-monatendard-nerd-font", "NERD"),
}


def stable_version(tag: object) -> str:
    if not isinstance(tag, str) or not re.fullmatch(
        r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag
    ):
        raise ValueError(f"Expected a stable version tag: {tag!r}")
    return tag[1:]


def validate_repository(repository: object) -> None:
    if (
        not isinstance(repository, str)
        or not re.fullmatch(
            r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]+",
            repository,
        )
        or repository.split("/")[1] in {".", ".."}
    ):
        raise ValueError(f"Expected repository owner/name: {repository!r}")


def release_version(release: dict[str, object]) -> str:
    if release.get("draft") or release.get("prerelease"):
        raise ValueError("Draft and prerelease releases are not supported")
    return stable_version(release.get("tag_name"))


def _extract_array_fonts(script_text: str, array_name: str) -> list[str]:
    match = re.search(rf"^{array_name}=\(\n(.*?)\n\)$", script_text, flags=re.M | re.S)
    if match is None:
        raise ValueError(f"Missing {array_name} array in Linux installer")
    fonts = sorted(re.findall(r'"([^"]+)"', match[1]))
    if len(fonts) != 14 or len(set(fonts)) != 14:
        raise ValueError(f"Expected 14 unique font entries in {array_name}")
    return fonts


def verify_archive(archive: Path, expected_fonts: list[str]) -> None:
    with zipfile.ZipFile(archive) as zipped:
        infos = zipped.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate ZIP entries: {archive.name}")
        for info in infos:
            name = info.filename
            if "\\" in name or PurePosixPath(name).is_absolute() or ".." in name.split("/"):
                raise ValueError(f"Unsafe ZIP path: {name}")
            mode = (info.external_attr >> 16) & 0o170000
            if stat.S_ISLNK(mode):
                raise ValueError(f"Symlink ZIP entry: {name}")
        fonts = sorted(name for name in names if name.lower().endswith(".ttf"))
        if len(expected_fonts) != 14 or len(set(expected_fonts)) != 14 or fonts != expected_fonts:
            raise ValueError(f"Expected exactly 14 Cask font paths: {archive.name}")
        bad = zipped.testzip()
        if bad:
            raise ValueError(f"Corrupt ZIP entry: {bad}")


def _substitute_constant(text: str, key: str, value: str) -> str:
    updated, count = re.subn(
        rf'^{key}="[^"]+"$',
        lambda _: f'{key}="{value}"',
        text,
        flags=re.M,
    )
    if count != 1:
        raise ValueError(f"Expected single constant definition for {key}")
    return updated


def prepare_updates(
    root: Path,
    repository: str,
    release: dict[str, object],
    archive_dir: Path,
) -> tuple[str, dict[Path, str]]:
    """Return (version, {install.sh: text}); validate both archives without writes."""
    validate_repository(repository)
    version = release_version(release)
    root_path, archive_root = Path(root), Path(archive_dir)

    installer_path = root_path / "packaging" / "linux" / "install.sh"
    raw_bytes = installer_path.read_bytes()
    if b"\r" in raw_bytes:
        raise ValueError("Linux installer must use LF line endings")
    original = raw_bytes.decode("utf-8")
    if not original.isascii():
        raise ValueError("Linux installer must be ASCII-only with LF line endings")

    current_matches = re.findall(r'^RELEASE_VERSION="([^"]+)"$', original, flags=re.M)
    if len(current_matches) != 1:
        raise ValueError(f"Expected single RELEASE_VERSION in {installer_path}")
    previous = stable_version("v" + current_matches[0])
    if tuple(map(int, version.split("."))) < tuple(map(int, previous.split("."))):
        raise ValueError(f"Version rollback: {previous} -> {version}")

    checksums = (archive_root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    entries = [line.split() for line in checksums if line.split()]

    replacements: list[tuple[str, str]] = [("RELEASE_VERSION", version)]
    for _, (kind, cask, prefix) in PACKAGES.items():
        filename = f"Monatendard-v{version}-{kind}.zip"
        matches = [parts for parts in entries if parts[-1].lstrip("*") == filename]
        if (
            len(matches) != 1
            or len(matches[0]) != 2
            or not re.fullmatch(r"[0-9a-fA-F]{64}", matches[0][0])
            or matches[0][1] not in {filename, "*" + filename}
        ):
            raise ValueError(f"Expected one valid checksum entry: {filename}")

        archive = archive_root / filename
        with archive.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if matches[0][0].lower() != actual:
            raise ValueError(f"Checksum mismatch: {filename}")

        cask_text = (root_path / "Casks" / f"{cask}.rb").read_text(encoding="utf-8")
        expected = sorted(re.findall(r'^  font "([^"]+)"$', cask_text, flags=re.M))
        installer_fonts = _extract_array_fonts(original, f"{prefix}_FONTS")
        if installer_fonts != expected:
            raise ValueError(f"Installer font list does not match Cask: {cask}")

        verify_archive(archive, expected)
        url = f"https://github.com/{repository}/releases/download/v{version}/{filename}"
        replacements.append((f"{prefix}_URL", url))
        replacements.append((f"{prefix}_SHA256", actual))

    updated = original
    for key, value in replacements:
        updated = _substitute_constant(updated, key, value)
    return version, {installer_path: updated}


def write_updates(updates: dict[Path, str]) -> bool:
    """Stage all changed files before replacing destinations atomically."""
    staged: dict[Path, Path] = {}
    try:
        for path, content in updates.items():
            if path.read_bytes() == content.encode("utf-8"):
                continue
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=path.parent,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                staged[path] = temporary
                stream.write(content)
            temporary.chmod(path.stat().st_mode & 0o777)
        for path, temporary in staged.items():
            os.replace(temporary, path)
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
    return bool(staged)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", default="")
    parser.add_argument("--archive-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        validate_repository(args.repository)
        if args.tag:
            stable_version(args.tag)
        if args.archive_dir and not args.tag:
            raise ValueError("--archive-dir requires an explicit stable --tag")
    except ValueError as error:
        parser.error(str(error))

    if args.archive_dir:
        release: dict[str, object] = {"tag_name": args.tag, "draft": False, "prerelease": False}
        version, updates = prepare_updates(ROOT, args.repository, release, args.archive_dir)
    else:
        endpoint = f"repos/{args.repository}/releases/" + (
            f"tags/{args.tag}" if args.tag else "latest"
        )
        release = json.loads(
            subprocess.check_output(["gh", "api", endpoint], text=True, encoding="utf-8")
        )
        version = release_version(release)
        if args.tag and release["tag_name"] != args.tag:
            raise ValueError("Release metadata does not match requested tag")
        with tempfile.TemporaryDirectory(prefix="monatendard-linux-") as directory:
            subprocess.run(
                [
                    "gh",
                    "release",
                    "download",
                    str(release["tag_name"]),
                    "--repo",
                    args.repository,
                    "--dir",
                    directory,
                    "--pattern",
                    f"Monatendard-v{version}-Desktop.zip",
                    "--pattern",
                    f"Monatendard-v{version}-Desktop-Nerd.zip",
                    "--pattern",
                    "SHA256SUMS.txt",
                ],
                check=True,
            )
            version, updates = prepare_updates(ROOT, args.repository, release, Path(directory))

    changed = write_updates(updates)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"version={version}\nchanged={str(changed).lower()}\n")
    print(f"Verified {args.repository} v{version}; Linux installer changed: {str(changed).lower()}")


if __name__ == "__main__":
    main()
