#!/usr/bin/env python3
"""Keep VERSION, pyproject.toml, and __init__.py in sync."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
PYPROJECT = ROOT / "pyproject.toml"
INIT_PY = ROOT / "src" / "serverless_data_mesh" / "__init__.py"


def read_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def pyproject_version(text: str) -> str | None:
    if 'path = "VERSION"' in text:
        return read_version()
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def init_version(text: str) -> str | None:
    match = re.search(r'__version__\s*=\s*(_read_version\(\)|"([^"]+)")', text)
    if not match:
        return None
    if match.group(2):
        return match.group(2)
    return read_version()


def write_pyproject(version: str) -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    if 'dynamic = ["version"]' not in text:
        text = re.sub(
            r'^version\s*=\s*"[^"]+"\s*\n',
            'dynamic = ["version"]\n',
            text,
            count=1,
            flags=re.MULTILINE,
        )
    if "[tool.hatch.version]" not in text:
        text += '\n[tool.hatch.version]\npath = "VERSION"\n'
    PYPROJECT.write_text(text, encoding="utf-8")


def write_init(version: str) -> None:
    text = INIT_PY.read_text(encoding="utf-8")
    if "_read_version" not in text:
        text = text.replace(
            '__version__ = "0.1.0"',
            """def _read_version() -> str:
    return (Path(__file__).resolve().parents[3] / "VERSION").read_text(encoding="utf-8").strip()


__version__ = _read_version()""",
        )
        if "from pathlib import Path" not in text:
            text = text.replace(
                "from typing import Any",
                "from pathlib import Path\nfrom typing import Any",
            )
    INIT_PY.write_text(text, encoding="utf-8")


def check() -> list[str]:
    version = read_version()
    errors: list[str] = []
    pp = PYPROJECT.read_text(encoding="utf-8")
    init = INIT_PY.read_text(encoding="utf-8")
    if f'path = "VERSION"' not in pp:
        errors.append("pyproject.toml missing [tool.hatch.version] path = VERSION")
    pv = pyproject_version(pp)
    if pv != version:
        errors.append(f"pyproject version mismatch: expected {version}, got {pv}")
    iv = init_version(init)
    if iv != version:
        errors.append(f"__init__.py version mismatch: expected {version}, got {iv}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify sync only")
    parser.add_argument("--write", action="store_true", help="Apply sync to tracked files")
    args = parser.parse_args()

    version = read_version()
    if args.check:
        errors = check()
        if errors:
            for err in errors:
                print(f"ERROR: {err}", file=sys.stderr)
            return 1
        print(f"OK: version {version} synced across VERSION, pyproject.toml, __init__.py")
        return 0

    if args.write or not args.check:
        write_pyproject(version)
        write_init(version)
        print(f"Synced version {version}")
    errors = check()
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
