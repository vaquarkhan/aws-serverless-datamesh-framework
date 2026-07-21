"""Unit tests for SNS ops notifications."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from serverless_data_mesh.observability.sns_notify import (
    notify_ops,
    notify_rollback,
    notify_vrp_failure,
    sns_enabled,
    sns_topic_arn_from_env,
)


def test_sns_disabled_without_topic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SDM_SNS_TOPIC_ARN", raising=False)
    monkeypatch.delenv("VRP_ALERT_SNS_TOPIC_ARN", raising=False)
    monkeypatch.delenv("ALARM_SNS_TOPIC_ARN", raising=False)
    monkeypatch.setenv("SDM_SNS_ENABLED", "true")
    assert sns_topic_arn_from_env() is None
    assert sns_enabled() is False


def test_sns_opt_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDM_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:1:t")
    monkeypatch.setenv("SDM_SNS_ENABLED", "false")
    assert sns_enabled() is False
    assert notify_ops(subject="x", event="y") is False


def test_notify_ops_publishes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDM_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:1:ops")
    monkeypatch.setenv("SDM_SNS_ENABLED", "true")
    client = MagicMock()
    assert (
        notify_ops(
            subject="alert",
            event="test_event",
            domain_id="orders",
            workload_id="w1",
            sns_client=client,
        )
        is True
    )
    client.publish.assert_called_once()
    kwargs = client.publish.call_args.kwargs
    assert kwargs["TopicArn"].endswith(":ops")
    assert "test_event" in kwargs["Message"]


def test_notify_vrp_and_rollback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDM_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:1:ops")
    client = MagicMock()
    assert (
        notify_vrp_failure(
            domain_id="orders",
            workload_id="w",
            verdict="FAIL",
            reason="drop",
            proof_id="p1",
            sns_client=client,
        )
        is True
    )
    assert (
        notify_rollback(
            domain_id="orders",
            workload_id="w",
            detail="near timeout",
            sns_client=client,
        )
        is True
    )
    assert client.publish.call_count == 2


def test_notify_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDM_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:1:ops")
    client = MagicMock()
    client.publish.side_effect = RuntimeError("AccessDenied")
    assert notify_ops(subject="x", event="y", sns_client=client) is False


def test_notify_without_boto3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDM_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:1:ops")
    monkeypatch.setenv("SDM_SNS_ENABLED", "true")
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "boto3":
            raise ImportError("no boto3")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    assert notify_ops(subject="x", event="y") is False
