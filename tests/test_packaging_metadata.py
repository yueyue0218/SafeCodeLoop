from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_mit_license_identifies_author() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert license_text.startswith("MIT License")
    assert "Copyright (c) 2026 曹潇月" in license_text
    assert "Permission is hereby granted, free of charge" in license_text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in license_text


def test_project_metadata_declares_license_author_and_links() -> None:
    pyproject = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    metadata = pyproject["project"]

    assert pyproject["build-system"]["requires"] == ["setuptools>=77.0.3"]
    assert metadata["readme"] == "README.md"
    assert metadata["license"] == "MIT"
    assert metadata["license-files"] == ["LICENSE"]
    assert metadata["authors"] == [{"name": "曹潇月"}]
    assert "Programming Language :: Python :: 3.11" in metadata["classifiers"]
    assert "Operating System :: OS Independent" in metadata["classifiers"]
    assert metadata["urls"] == {
        "Homepage": "https://github.com/yueyue0218/SafeCodeLoop",
        "Repository": "https://github.com/yueyue0218/SafeCodeLoop",
        "Issues": "https://github.com/yueyue0218/SafeCodeLoop/issues",
        "Releases": "https://github.com/yueyue0218/SafeCodeLoop/releases",
    }


def test_third_party_notices_cover_runtime_build_and_test_dependencies() -> None:
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    expected_entries = {
        "keyring": "https://pypi.org/project/keyring/",
        "setuptools": "https://github.com/pypa/setuptools/blob/main/LICENSE",
        "build": "https://pypi.org/project/build/",
        "pytest": "https://github.com/pytest-dev/pytest/blob/main/LICENSE",
    }
    for dependency, source in expected_entries.items():
        assert dependency in notices
        assert source in notices
    assert notices.count("MIT") >= len(expected_entries)


def test_source_distribution_manifest_includes_legal_and_project_files() -> None:
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()

    assert "include LICENSE" in manifest
    assert "include README.md" in manifest
    assert "include THIRD_PARTY_NOTICES.md" in manifest
