# Coverage gate for new high-value modules (must be 100%).
# Usage: PYTHONPATH=src python scripts/coverage_gate.py

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    "serverless_data_mesh/attestation",
    "serverless_data_mesh/verification/kms_sign.py",
    "serverless_data_mesh/rules/gate.py",
    "serverless_data_mesh/ui/data.py",
]


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/unit/test_attestation_kms.py",
        "tests/unit/test_coverage_new_modules.py",
        "tests/unit/test_ui_server.py",
        "tests/unit/test_observability.py",
        "--cov=serverless_data_mesh.attestation",
        "--cov=serverless_data_mesh.verification.kms_sign",
        "--cov=serverless_data_mesh.rules.gate",
        "--cov=serverless_data_mesh.ui.data",
        "--cov-branch",
        "--cov-report=term-missing",
        "--cov-fail-under=100",
        "-q",
    ]
    print("Running:", " ".join(cmd))
    env = {
        **dict(**{k: v for k, v in __import__("os").environ.items()}),
        "PYTHONPATH": str(ROOT / "src"),
    }
    return subprocess.call(cmd, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
