"""OpenLineage emitter tests."""

from __future__ import annotations

from serverless_data_mesh.lineage.openlineage import emit_from_commit_result, emit_openlineage_event


def test_emit_openlineage_event_shape() -> None:
    event = emit_openlineage_event(
        job_name="orders.orders_curated",
        inputs=["raw_orders"],
        outputs=["orders_curated"],
        facets={"vrp_proof_id": "abc123"},
    )
    assert event["eventType"] == "COMPLETE"
    assert event["job"]["name"] == "orders.orders_curated"
    assert event["inputs"][0]["name"] == "raw_orders"
    assert event["facets"]["vrp_proof_id"] == "abc123"


def test_emit_from_commit_skips_non_committed() -> None:
    assert emit_from_commit_result(
        domain_id="orders",
        target_table="orders_curated",
        source_namespace="raw_orders",
        commit_result={"outcome": "verification_failed"},
    ) == {}


def test_emit_from_commit_on_success() -> None:
    event = emit_from_commit_result(
        domain_id="orders",
        target_table="orders_curated",
        source_namespace="raw_orders",
        commit_result={
            "outcome": "committed",
            "workload_id": "wl-1",
            "records_written": 1000,
            "snapshot_id": "snap-1",
            "proof_chain_tail": "proof-tail",
        },
    )
    assert event["job"]["name"] == "orders.orders_curated"
    assert event["facets"]["snapshot_id"] == "snap-1"
