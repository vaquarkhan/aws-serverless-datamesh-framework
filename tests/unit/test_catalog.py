"""Unit tests for Glue REST catalog adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from serverless_data_mesh.catalog.glue_rest import GlueRestCatalogAdapter
from serverless_data_mesh.exceptions import CatalogCommitError


def test_glue_catalog_connector_is_adapter_alias() -> None:
    from serverless_data_mesh.catalog import GlueCatalogConnector, GlueRestCatalogAdapter

    assert GlueCatalogConnector is GlueRestCatalogAdapter


    adapter = GlueRestCatalogAdapter(
        catalog_name="glue_rest",
        namespace="raw_orders",
        table_name="orders_curated",
        region="us-east-1",
        warehouse="123456789012:s3tablescatalog/lakehouse",
    )
    props = adapter._rest_properties()
    assert props["type"] == "rest"
    assert props["rest.sigv4-enabled"] == "true"
    assert props["rest.signing-name"] == "glue"
    assert "glue.us-east-1.amazonaws.com" in props["uri"]


def test_prepare_commit_deduplicates_paths() -> None:
    adapter = GlueRestCatalogAdapter(
        catalog_name="glue_rest",
        namespace="ns",
        table_name="tbl",
        region="us-east-1",
        warehouse="1:s3tablescatalog/b",
    )
    adapter.prepare_commit(["s3://b/a.parquet", "s3://b/a.parquet", "s3://b/b.parquet"])
    assert len(adapter._prepared_files) == 2


def test_commit_without_prepare_raises() -> None:
    adapter = GlueRestCatalogAdapter(
        catalog_name="glue_rest",
        namespace="ns",
        table_name="tbl",
        region="us-east-1",
        warehouse="1:s3tablescatalog/b",
    )
    with pytest.raises(CatalogCommitError):
        adapter.commit()


@patch("serverless_data_mesh.catalog.glue_rest.load_catalog")
def test_connect_loads_table(mock_load_catalog: MagicMock) -> None:
    mock_catalog = MagicMock()
    mock_table = MagicMock()
    mock_load_catalog.return_value = mock_catalog
    mock_catalog.load_table.return_value = mock_table

    adapter = GlueRestCatalogAdapter(
        catalog_name="glue_rest",
        namespace="raw_orders",
        table_name="orders_curated",
        region="us-east-1",
        warehouse="1:s3tablescatalog/b",
    )
    table = adapter.connect()
    assert table is mock_table
    mock_catalog.load_table.assert_called_once_with("raw_orders.orders_curated")
