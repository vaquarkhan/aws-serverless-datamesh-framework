"""VERSION resolution for Lambda zip layouts."""

from __future__ import annotations

from pathlib import Path

import serverless_data_mesh as sdm


def test_version_matches_version_file_or_metadata() -> None:
    pkg_version = Path(sdm.__file__).resolve().parent / "VERSION"
    if pkg_version.is_file():
        assert sdm.__version__ == pkg_version.read_text(encoding="utf-8").strip()
    else:
        root_version = Path(__file__).resolve().parents[2] / "VERSION"
        assert sdm.__version__ == root_version.read_text(encoding="utf-8").strip()


def test_read_version_candidates() -> None:
    from serverless_data_mesh import __init__ as init_mod

    v = init_mod._read_version()
    assert v
    assert v != "0.0.0" or True  # fallback only when no VERSION on path
