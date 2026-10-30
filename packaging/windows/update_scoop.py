"""Verify official Desktop release archives before updating both Scoop manifests.

Online mode uses gh release metadata and assets. --archive-dir is explicitly local
mode: --tag is mandatory and no claim about published release metadata is made.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = {
    "monatendard": ("Desktop", "font-monatendard", "Monatendard"),
    "monatendard-nerd": ("Desktop-Nerd", "font-monatendard-nerd-font", "Monatendard-Nerd"),
}


def stable_version(tag):
    if not isinstance(tag, str) or not re.fullmatch(
        r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag
    ):
        raise ValueError(f"Expected a stable version tag: {tag!r}")
    return tag[1:]


def validate_repository(repository):
    if not isinstance(repository, str) or not re.fullmatch(
        r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]+", repository
    ) or repository.split("/")[1] in {".", ".."}:
        raise ValueError(f"Expected repository owner/name: {repository!r}")


def release_version(release):
    if release.get("draft") or release.get("prerelease"):
        raise ValueError("Draft and prerelease releases are not supported")
    return stable_version(release.get("tag_name"))


def verify_archive(archive, expected_fonts, scripts):
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate ZIP entries: {archive.name}")
        for name in names:
            if "\\" in name or PurePosixPath(name).is_absolute() or ".." in name.split("/"):
                raise ValueError(f"Unsafe ZIP path: {name}")
        fonts = sorted(name for name in names if name.lower().endswith(".ttf"))
        if len(expected_fonts) != 14 or len(set(expected_fonts)) != 14 or fonts != expected_fonts:
            raise ValueError(f"Expected exactly 14 Cask font paths: {archive.name}")
        for script in scripts:
            if script not in names or zipped.getinfo(script).file_size == 0:
                raise ValueError(f"Missing or empty bundled script: {script}")
        bad = zipped.testzip()
        if bad:
            raise ValueError(f"Corrupt ZIP entry: {bad}")


def prepare_updates(root, repository, release, archive_dir):
    """Return (version, {path: JSON text}); validate both packages without writes."""
    validate_repository(repository)
    version = release_version(release)
    root, archive_dir = Path(root), Path(archive_dir)
    checksums = (archive_dir / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    updates = {}
    for token, (kind, cask, script_name) in PACKAGES.items():
        path = root / "bucket" / f"{token}.json"
        original = path.read_text(encoding="utf-8")
        manifest = json.loads(original)
        if not isinstance(manifest, dict) or any(
            not isinstance(manifest.get(field), str) for field in ("version", "url", "hash")
        ):
            raise ValueError(f"Expected string version, url and hash fields: {path}")
        previous = stable_version("v" + manifest["version"])
        if tuple(map(int, version.split("."))) < tuple(map(int, previous.split("."))):
            raise ValueError(f"Version rollback: {previous} -> {version}")
        filename = f"Monatendard-v{version}-{kind}.zip"
        # Count filename occurrences before validating syntax, so even a malformed
        # duplicate checksum cannot hide beside a valid entry.
        entries = [line.split() for line in checksums if line.split()]
        matches = [parts for parts in entries if parts[-1].lstrip("*") == filename]
        if len(matches) != 1 or len(matches[0]) != 2 or not re.fullmatch(
            r"[0-9a-fA-F]{64}", matches[0][0]
        ) or matches[0][1] not in {filename, "*" + filename}:
            raise ValueError(f"Expected one valid checksum entry: {filename}")
        archive = archive_dir / filename
        with archive.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if matches[0][0].lower() != actual:
            raise ValueError(f"Checksum mismatch: {filename}")
        cask_text = (root / "Casks" / f"{cask}.rb").read_text(encoding="utf-8")
        expected = sorted(re.findall(r'^  font "([^"]+)"$', cask_text, re.MULTILINE))
        verify_archive(
            archive, expected, (f"Install-{script_name}.ps1", f"Uninstall-{script_name}.ps1")
        )
        fields = {
            "version": version,
            "url": f"https://github.com/{repository}/releases/download/v{version}/{filename}",
            "hash": actual,
        }
        unchanged = all(manifest[key] == value for key, value in fields.items())
        manifest.update(fields)
        updates[path] = original if unchanged else json.dumps(manifest, indent=4) + "\n"
    return version, updates


def write_updates(updates):
    """Stage all changed manifests before replacing any destination file."""
    staged = {}
    try:
        for path, content in updates.items():
            if path.read_text(encoding="utf-8") == content:
                continue
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
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


def main(argv=None):
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
        # Explicit local mode: these flags describe local input, not a GitHub release.
        release = {"tag_name": args.tag, "draft": False, "prerelease": False}
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
        with tempfile.TemporaryDirectory(prefix="monatendard-scoop-") as directory:
            subprocess.run(
                [
                    "gh", "release", "download", release["tag_name"],
                    "--repo", args.repository, "--dir", directory,
                    "--pattern", f"Monatendard-v{version}-Desktop.zip",
                    "--pattern", f"Monatendard-v{version}-Desktop-Nerd.zip",
                    "--pattern", "SHA256SUMS.txt",
                ],
                check=True,
            )
            version, updates = prepare_updates(ROOT, args.repository, release, Path(directory))
    changed = write_updates(updates)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"version={version}\nchanged={str(changed).lower()}\n")
    print(f"Verified {args.repository} v{version}; Scoop changed: {str(changed).lower()}")


if __name__ == "__main__":
    main()
