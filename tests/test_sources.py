from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from monatendard import __version__
from monatendard.sources import (
    VARIANTS,
    VARIANTS_BY_SUFFIX,
    load_lock,
    make_variant,
    verify_archive,
)


def test_variant_matrix_has_seven_weights_and_two_styles() -> None:
    assert len(VARIANTS) == 14
    assert "Regular" in VARIANTS_BY_SUFFIX
    assert "Italic" in VARIANTS_BY_SUFFIX
    assert "ExtraBoldItalic" in VARIANTS_BY_SUFFIX


def test_regular_italic_source_name_matches_upstream() -> None:
    variant = make_variant("Regular", "italic")
    assert variant.latin_filename == "MonaspaceNeonFrozen-Italic.ttf"
    assert variant.output_suffix == "Italic"
    assert variant.subfamily_name == "Italic"


def test_unknown_variant_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="weight"):
        make_variant("Thin", "normal")
    with pytest.raises(ValueError, match="style"):
        make_variant("Regular", "oblique")


def test_lock_pins_required_versions_scale_and_sha256() -> None:
    lock = load_lock()
    assert lock["project"]["version"] == __version__ == "0.3.0"
    assert lock["project"]["latin_horizontal_scale"] == 1.0
    assert lock["project"]["latin_advance_em"] == 0.620
    assert lock["project"]["cjk_horizontal_scale"] == 1.15
    assert lock["project"]["cjk_vertical_scale"] == 1.15
    assert lock["sources"]["monaspace"]["version"] == "1.400"
    assert lock["sources"]["pretendard"]["version"] == "1.3.9"
    assert lock["sources"]["nerd_fonts"]["version"] == "3.4.0"
    for source in lock["sources"].values():
        assert len(source["sha256"]) == 64
        int(source["sha256"], 16)


def test_archive_verification_detects_mismatch(tmp_path: Path) -> None:
    archive = tmp_path / "source.zip"
    archive.write_bytes(b"locked source")
    expected = hashlib.sha256(b"locked source").hexdigest()
    verify_archive(archive, expected)
    with pytest.raises(ValueError, match="SHA256"):
        verify_archive(archive, "0" * 64)
