"""Tests for local auto-repair demo."""

from __future__ import annotations

from serverless_data_mesh.local.runtime import LocalPVDMRuntime


def test_run_write_with_auto_repair_commits() -> None:
    runtime = LocalPVDMRuntime()
    result = runtime.run_write_with_auto_repair(record_count=50, drop_count=3)
    assert result["outcome"] == "repaired_and_committed"
    assert result["consumer_row_count"] == 50
