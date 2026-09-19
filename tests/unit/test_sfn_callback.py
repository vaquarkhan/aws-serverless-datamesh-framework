"""Unit tests for Step Functions task-token callback helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from serverless_data_mesh.orchestration.sfn_callback import (
    complete_task_token,
    extract_task_token,
    unwrap_workload_event,
)


def test_extract_task_token_variants() -> None:
    assert extract_task_token({"task_token": "abc"}) == "abc"
    assert extract_task_token({"TaskToken": "xyz"}) == "xyz"
    assert extract_task_token({"workload_id": "w1"}) is None


def test_unwrap_sync_event_passthrough() -> None:
    event = {"workload_id": "w1", "total_records": 10}
    assert unwrap_workload_event(event) is event or unwrap_workload_event(event) == event


def test_unwrap_async_callback_payload() -> None:
    event = {
        "task_token": "tok",
        "resume_attempt": 2,
        "workload": {"workload_id": "w1", "total_records": 10},
    }
    out = unwrap_workload_event(event)
    assert out["workload_id"] == "w1"
    assert out["resume_attempt"] == 2


def test_complete_task_token_noop_without_token() -> None:
    client = MagicMock()
    complete_task_token(task_token=None, result={"outcome": "committed"}, sfn_client=client)
    client.send_task_success.assert_not_called()
    client.send_task_failure.assert_not_called()


def test_complete_task_token_success() -> None:
    client = MagicMock()
    complete_task_token(
        task_token="tok",
        result={"outcome": "committed"},
        sfn_client=client,
    )
    client.send_task_success.assert_called_once()
    assert client.send_task_success.call_args.kwargs["taskToken"] == "tok"


def test_complete_task_token_failure() -> None:
    client = MagicMock()
    complete_task_token(
        task_token="tok",
        result={"outcome": "unknown_failure"},
        error="Boom",
        cause="detail",
        sfn_client=client,
    )
    client.send_task_failure.assert_called_once()
    assert client.send_task_failure.call_args.kwargs["error"] == "Boom"
