"""Tests for consumer SLA enforcement."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from serverless_data_mesh.governance.consumer_sla import enforce_consumer_sla, grant_read_if_sla_met
from serverless_data_mesh.types.workload import ConsumerSLAContract
from serverless_data_mesh.verification.backend import create_proof_generator
from serverless_data_mesh.types.workload import DataWriteWorkload, DomainTransactionBoundary


def _passing_proof() -> dict:
    gen, _ = create_proof_generator()
    boundary = DomainTransactionBoundary(
        domain_id="orders",
        source_namespace="raw_orders",
        target_table="orders_curated",
        partition_spec={"dt": "2026-06-14"},
    )
    workload = DataWriteWorkload(
        workload_id="sla-test",
        boundary=boundary,
        source_uri="file:///source",
        target_uri="file:///sink",
        total_records=10,
        checkpoint_bucket="/ckpt",
        proof_bucket="/proofs",
    )
    source = [{"id": str(i), "payload_hash": f"h{i}"} for i in range(10)]
    return gen.build_proof(
        source_records=source,
        sink_records=source,
        workload=workload,
        chunk_start=0,
        chunk_end=10,
    )


def test_consumer_sla_grants_on_passing_proof() -> None:
    contract = ConsumerSLAContract(
        consumer_id="analytics",
        target_table="orders_curated",
        max_freshness_minutes=60,
        min_completeness_pct=99.0,
        required_columns=("id", "payload_hash"),
    )
    proof = _passing_proof()
    decision = enforce_consumer_sla(
        contract,
        proof=proof,
        snapshot_committed_at=datetime.now(timezone.utc),
    )
    assert decision.granted is True
    assert decision.checks["vrp_pass"] is True
    assert decision.checks["completeness"] is True


def test_consumer_sla_denies_stale_snapshot() -> None:
    contract = ConsumerSLAContract(
        consumer_id="analytics",
        target_table="orders_curated",
        max_freshness_minutes=30,
    )
    proof = _passing_proof()
    stale = datetime.now(timezone.utc) - timedelta(hours=2)
    decision = enforce_consumer_sla(contract, proof=proof, snapshot_committed_at=stale)
    assert decision.granted is False
    assert decision.checks["freshness"] is False


def test_lf_grant_payload() -> None:
    contract = ConsumerSLAContract(consumer_id="bi", target_table="orders_curated")
    payload = grant_read_if_sla_met(
        contract,
        proof=_passing_proof(),
        snapshot_committed_at=datetime.now(timezone.utc),
    )
    assert payload["grant_read"] is True
    assert payload["lf_action"] == "GrantPermissions"
