"""Glue Catalog Connector — metadata-only integration for Lambda domain writers.

AWS Glue **ETL jobs** (managed Spark runners) do not run inside Lambda containers.
Domain writers execute **physical** transforms on Lambda (PySpark-on-Lambda, Polars,
PyArrow, DuckDB, etc.) and use this connector for **metadata** commits against the
Glue Data Catalog Iceberg REST endpoint.

The connector is a thin SigV4 HTTPS client via PyIceberg — no Glue job runtime, no JVM
Spark catalog session, no Glue Studio dependency.
"""

from serverless_data_mesh.catalog.glue_rest import GlueRestCatalogAdapter

# Public alias — "Glue connector" in docs maps to this class.
GlueCatalogConnector = GlueRestCatalogAdapter

__all__ = ["GlueCatalogConnector", "GlueRestCatalogAdapter"]
