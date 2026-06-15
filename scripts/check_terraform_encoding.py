#!/usr/bin/env python3
"""Fail CI if Terraform files contain UTF-8 BOM (breaks terraform validate on Linux)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TF_ROOT = ROOT / "infrastructure" / "terraform"
BOM = b"\xef\xbb\xbf"


def main() -> int:
    bad: list[Path] = []
    for path in sorted(TF_ROOT.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in {".tf", ".tfvars", ".tfvars.example"}:
            continue
        if path.name.endswith(".tfstate") or ".terraform" in path.parts:
            continue
        head = path.read_bytes()[:3]
        if head == BOM:
            bad.append(path)

    if bad:
        print("UTF-8 BOM detected (re-save as UTF-8 without BOM):", file=sys.stderr)
        for p in bad:
            print(f"  {p.relative_to(ROOT)}", file=sys.stderr)
        return 1

    print(f"OK: {len(list(TF_ROOT.rglob('*.tf')))} .tf files — no BOM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
