"""Tests for mesh init scaffold and trust dashboard."""

from __future__ import annotations

from pathlib import Path

from serverless_data_mesh.dashboard.trust import render_trust_dashboard
from serverless_data_mesh.scaffold.init_domain import scaffold_domain


def test_scaffold_domain_creates_files(tmp_path: Path) -> None:
    root = scaffold_domain(
        domain="payments",
        table="fact_payments",
        account_id="123456789012",
        output_dir=str(tmp_path),
    )
    assert (root / "handler.py").exists()
    assert (root / "contract.yaml").exists()
    assert (root / "consumer_sla.yaml").exists()
    assert (root / "step_function.asl.json").exists()
    assert (root / "terraform" / "main.tf").exists()
    assert (root / "tests" / "test_payments.py").exists()


def test_trust_dashboard_demo(tmp_path: Path) -> None:
    out = tmp_path / "dash.html"
    path = render_trust_dashboard(output=str(out), demo=True)
    html = path.read_text(encoding="utf-8")
    assert "Mesh Trust Dashboard" in html
    assert "inventory" in html
