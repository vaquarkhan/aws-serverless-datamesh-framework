"""Tests for reference reader modules."""

from __future__ import annotations

import os

import pytest


def test_s3_bronze_synthetic_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRONZE_LANDING_BUCKET", "test-landing")
    monkeypatch.setenv("BRONZE_LANDING_KEY", "empty/")
    monkeypatch.setenv("ICEBERG_TABLE_BUCKET", "test-lake")

    from serverless_data_mesh.readers.s3_bronze import source_reader_s3_landing

    # No real S3 — list returns empty, synthetic demo rows
    rows = source_reader_s3_landing(0, 5)
    assert len(rows) == 5
    assert "id" in rows[0]


def test_upstream_synthetic_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ICEBERG_TABLE_BUCKET", "test-lake")
    monkeypatch.setenv("UPSTREAM_TABLE", "orders_bronze")
    monkeypatch.setenv("TARGET_PARTITION", "dt=2026-01-01")

    from serverless_data_mesh.readers.upstream_parquet import source_reader_upstream

    rows = source_reader_upstream(0, 3)
    assert len(rows) == 3


def test_portable_adapters() -> None:
    from serverless_data_mesh.portable.cloud import GCPAdapter, get_adapter

    assert get_adapter("aws").provider == "aws"
    with pytest.raises(NotImplementedError):
        GCPAdapter().list_prefix("gs://bucket/prefix/")
