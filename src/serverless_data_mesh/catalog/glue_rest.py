"""Zero-config AWS Glue Iceberg REST catalog adapter for serverless 2PC commits."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import boto3
from pyiceberg.catalog import load_catalog
from pyiceberg.table import Table

from serverless_data_mesh.exceptions import CatalogCommitError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GlueRestCatalogAdapter:
    """Native Python catalog commit adapter using Glue's Iceberg REST endpoint.

    Replaces heavy PySpark JVM catalog operations with lightweight HTTPS REST
    calls authenticated via AWS SigV4. IceGuard performs physical file writes;
    this adapter executes the final metadata commit in the two-phase commit (2PC)
    sequence purely over REST.
    """

    catalog_name: str
    namespace: str
    table_name: str
    region: str
    warehouse: str | None = None
    catalog: Any = field(default=None, repr=False)
    _prepared_files: list[str] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def from_environment(
        cls,
        *,
        namespace: str,
        table_name: str,
        catalog_name: str = "glue_rest",
        aws_account_id: str | None = None,
        warehouse: str | None = None,
    ) -> GlueRestCatalogAdapter:
        """Construct adapter from standard Lambda environment variables."""
        region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
        account_id = aws_account_id or os.environ.get("AWS_ACCOUNT_ID")
        if not account_id:
            account_id = boto3.client("sts").get_caller_identity()["Account"]
        resolved_warehouse = warehouse or os.environ.get(
            "ICEBERG_WAREHOUSE",
            f"{account_id}:s3tablescatalog/{os.environ.get('ICEBERG_TABLE_BUCKET', 'default')}",
        )
        return cls(
            catalog_name=catalog_name,
            namespace=namespace,
            table_name=table_name,
            region=region,
            warehouse=resolved_warehouse,
        )

    def _rest_properties(self) -> dict[str, str]:
        """Build pyiceberg REST catalog properties with SigV4 signing."""
        if not self.warehouse:
            raise ValueError("warehouse is required for Glue REST catalog access")
        return {
            "type": "rest",
            "uri": f"https://glue.{self.region}.amazonaws.com/iceberg",
            "warehouse": self.warehouse,
            "rest.sigv4-enabled": "true",
            "rest.signing-name": "glue",
            "rest.signing-region": self.region,
        }

    def connect(self) -> Table:
        """Authenticate via SigV4 and load the target Iceberg table handle."""
        if self.catalog is None:
            self.catalog = load_catalog(self.catalog_name, **self._rest_properties())
        identifier = f"{self.namespace}.{self.table_name}"
        table = self.catalog.load_table(identifier)
        logger.info("Connected to Iceberg table %s via Glue REST", identifier)
        return table

    def prepare_commit(self, parquet_paths: list[str]) -> None:
        """Phase-1 prepare: stage file paths for the pending metadata transaction."""
        if not parquet_paths:
            raise ValueError("prepare_commit requires at least one parquet path")
        self._prepared_files = list(dict.fromkeys(parquet_paths))
        logger.info("Prepared %d data files for REST metadata commit", len(self._prepared_files))

    def commit(self, *, snapshot_properties: dict[str, str] | None = None) -> int:
        """Phase-2 commit: publish a new Iceberg snapshot via HTTPS REST."""
        if not self._prepared_files:
            raise CatalogCommitError("commit called before prepare_commit")

        table = self.connect()
        props = snapshot_properties or {
            "write.format.default": "parquet",
            "app-id": "serverless-data-mesh",
        }
        try:
            with table.transaction() as tx:
                tx.add_files(self._prepared_files, snapshot_properties=props)
        except Exception as exc:
            raise CatalogCommitError(f"Glue REST commit failed: {exc}") from exc

        snapshot_id = table.metadata.current_snapshot_id()
        logger.info(
            "Committed snapshot %s with %d files to %s.%s",
            snapshot_id,
            len(self._prepared_files),
            self.namespace,
            self.table_name,
        )
        self._prepared_files.clear()
        return int(snapshot_id or 0)

    def abort(self) -> None:
        """Abort the in-flight metadata transaction without catalog side effects."""
        self._prepared_files.clear()
        logger.info("Aborted pending REST catalog commit for %s.%s", self.namespace, self.table_name)

    def rollback_to_snapshot(self, snapshot_id: int) -> None:
        """Rollback table metadata to a prior snapshot (IceGuard timeout recovery)."""
        table = self.connect()
        table.manage_snapshots().rollback_to_snapshot(snapshot_id).commit()
        logger.warning(
            "Rolled back %s.%s to snapshot %s",
            self.namespace,
            self.table_name,
            snapshot_id,
        )
