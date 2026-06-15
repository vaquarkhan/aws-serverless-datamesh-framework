"""CloudWatch metrics opt-out and non-fatal publish."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from serverless_data_mesh.metrics.mesh_trust import metrics_enabled, publish_vrp_metric


def test_metrics_disabled_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDM_METRICS_ENABLED", "false")
    assert metrics_enabled() is False
    monkeypatch.delenv("SDM_METRICS_ENABLED", raising=False)
    monkeypatch.setenv("SDM_DISABLE_METRICS", "true")
    assert metrics_enabled() is False


def test_publish_swallows_cloudwatch_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDM_METRICS_ENABLED", "true")
    client = MagicMock()
    client.put_metric_data.side_effect = Exception("AccessDenied")
    publish_vrp_metric(
        domain_id="orders",
        verdict="PASS",
        row_count=10,
        cloudwatch_client=client,
    )
    client.put_metric_data.assert_called_once()


def test_publish_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDM_METRICS_ENABLED", "off")
    client = MagicMock()
    publish_vrp_metric(domain_id="orders", verdict="PASS", cloudwatch_client=client)
    client.put_metric_data.assert_not_called()
