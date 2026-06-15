"""Evaluation and benchmark tests (require veridata-recon)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("veridata_recon")

ROOT = Path(__file__).resolve().parents[2]


def test_consumer_safety_benchmark_exits_zero() -> None:
    """Corrupt data scenarios must never PASS: quantitative trust boundary."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "eval" / "validate_then_commit_benchmark.py"), "--json"],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "corrupt_data_never_passes" in proc.stdout
    assert '"all_scenarios_passed": true' in proc.stdout.replace(" ", "")
