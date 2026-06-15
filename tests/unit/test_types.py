"""Unit tests for domain workload types."""

from serverless_data_mesh.types.workload import WriteOutcome


def test_write_outcome_values() -> None:
    assert WriteOutcome.COMMITTED.value == "committed"
    assert WriteOutcome.ROLLED_BACK.value == "rolled_back"
    assert WriteOutcome.VERIFICATION_FAILED.value == "verification_failed"


def test_sample_workload_fixture(sample_workload) -> None:
    assert sample_workload.workload_id == "test-workload-001"
    assert sample_workload.boundary.domain_id == "orders-domain"
    assert sample_workload.total_records == 100


def test_data_product_contract_registry_entry() -> None:
    from serverless_data_mesh.types import DataProductContract, DomainTransactionBoundary

    boundary = DomainTransactionBoundary(
        domain_id="orders-domain",
        source_namespace="raw_orders",
        target_table="orders_curated",
        partition_spec={"dt": "2026-06-14"},
    )
    contract = DataProductContract(
        product_id="orders-curated-daily",
        owner_team="orders-platform",
        boundary=boundary,
        sla_freshness_hours=2,
        schema_version="1.0.0",
    )
    entry = contract.to_registry_entry()
    assert entry["product_id"] == "orders-curated-daily"
    assert entry["owner_team"] == "orders-platform"
    assert entry["domain_id"] == "orders-domain"
    assert entry["sla_freshness_hours"] == 2
