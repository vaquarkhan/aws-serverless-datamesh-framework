"""Medallion (bronze / silver / gold) mesh contract model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from serverless_data_mesh.compile.contract import (
    ConsumerSlaSpec,
    MeshPipelineContract,
    PipelineAccounts,
    PipelineBoundary,
    PipelineGovernance,
    PipelineRuntime,
    PipelineTrigger,
    PipelineWorkload,
)

MEDALLION_LAYERS = ("bronze", "silver", "gold")


@dataclass(frozen=True, slots=True)
class MedallionLayerSpec:
    """One medallion layer within a domain data product."""

    layer: str
    target_table: str
    source_namespace: str
    upstream_layer: str | None = None
    description: str = ""
    identity_fields: tuple[str, ...] = ("id",)
    content_fields: tuple[str, ...] = ("id", "payload_hash")
    runtime_engine: str = "pyarrow"
    package_extras: str = ""
    lambda_memory_mb: int = 3008
    spark_rules_enabled: bool = False
    max_chunk_records: int = 5000
    auto_repair: bool = True
    transforms: tuple[str, ...] = ()
    consumer_slas: tuple[ConsumerSlaSpec, ...] = ()


@dataclass(frozen=True, slots=True)
class MedallionDomainSpec:
    """Bronze → silver → gold layers for one mesh domain."""

    domain_id: str
    owner_team: str
    description: str
    layers: tuple[MedallionLayerSpec, ...]
    schedule_cron: str | None = None
    mesh_transaction_group: str | None = None


@dataclass(frozen=True, slots=True)
class MedallionMeshContract:
    """Full federated mesh defined as medallion layers per domain."""

    api_version: str
    kind: str
    organization: str
    description: str
    accounts: PipelineAccounts
    domains: tuple[MedallionDomainSpec, ...]
    aws_region: str = "us-east-2"
    name_prefix: str = "sdm-mesh"
    mesh_transactions: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": self.api_version,
            "kind": self.kind,
            "metadata": {
                "organization": self.organization,
                "description": self.description,
            },
            "spec": {
                "accounts": {
                    "producer": self.accounts.producer,
                    "steward": self.accounts.steward,
                    "publisher": self.accounts.publisher,
                },
                "aws_region": self.aws_region,
                "name_prefix": self.name_prefix,
                "domains": [
                    {
                        "domain_id": d.domain_id,
                        "owner_team": d.owner_team,
                        "description": d.description,
                        "schedule_cron": d.schedule_cron,
                        "mesh_transaction_group": d.mesh_transaction_group,
                        "layers": {
                            layer.layer: {
                                "target_table": layer.target_table,
                                "source_namespace": layer.source_namespace,
                                "upstream_layer": layer.upstream_layer,
                                "description": layer.description,
                                "identity_fields": list(layer.identity_fields),
                                "content_fields": list(layer.content_fields),
                                "runtime": {
                                    "engine": layer.runtime_engine,
                                    "package_extras": layer.package_extras,
                                    "lambda_memory_mb": layer.lambda_memory_mb,
                                    "spark_rules_enabled": layer.spark_rules_enabled,
                                },
                                "max_chunk_records": layer.max_chunk_records,
                                "auto_repair": layer.auto_repair,
                                "transforms": list(layer.transforms),
                                "consumer_slas": [
                                    {
                                        "consumer_id": c.consumer_id,
                                        "target_table": c.target_table,
                                        "max_freshness_minutes": c.max_freshness_minutes,
                                        "min_completeness_pct": c.min_completeness_pct,
                                        "required_columns": list(c.required_columns),
                                        "enforcement": c.enforcement,
                                    }
                                    for c in layer.consumer_slas
                                ],
                            }
                            for layer in d.layers
                        },
                    }
                    for d in self.domains
                ],
                "mesh_transactions": list(self.mesh_transactions),
            },
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> MedallionMeshContract:
        meta = raw.get("metadata") or {}
        spec = raw.get("spec") or {}
        accounts_raw = spec.get("accounts") or {}

        domains: list[MedallionDomainSpec] = []
        for d in spec.get("domains") or []:
            layers_raw = d.get("layers") or {}
            layer_specs: list[MedallionLayerSpec] = []
            for layer_name in MEDALLION_LAYERS:
                if layer_name not in layers_raw:
                    continue
                lr = layers_raw[layer_name]
                rt = lr.get("runtime") or {}
                slas = tuple(
                    ConsumerSlaSpec(
                        consumer_id=str(c["consumer_id"]),
                        target_table=str(c.get("target_table") or lr.get("target_table", "")),
                        max_freshness_minutes=int(c.get("max_freshness_minutes", 60)),
                        min_completeness_pct=float(c.get("min_completeness_pct", 99.9)),
                        required_columns=tuple(c.get("required_columns") or ()),
                        enforcement=str(c.get("enforcement", "vrp_backed")),
                    )
                    for c in (lr.get("consumer_slas") or [])
                )
                layer_specs.append(
                    MedallionLayerSpec(
                        layer=layer_name,
                        target_table=str(lr["target_table"]),
                        source_namespace=str(
                            lr.get("source_namespace") or f"{layer_name}_{d['domain_id']}"
                        ),
                        upstream_layer=lr.get("upstream_layer"),
                        description=str(lr.get("description") or ""),
                        identity_fields=tuple(lr.get("identity_fields") or ("id",)),
                        content_fields=tuple(
                            lr.get("content_fields") or lr.get("identity_fields") or ("id",)
                        ),
                        runtime_engine=str(rt.get("engine") or "pyarrow"),
                        package_extras=str(rt.get("package_extras") or ""),
                        lambda_memory_mb=int(rt.get("lambda_memory_mb") or 3008),
                        spark_rules_enabled=bool(rt.get("spark_rules_enabled", False)),
                        max_chunk_records=int(lr.get("max_chunk_records") or 5000),
                        auto_repair=bool(lr.get("auto_repair", True)),
                        transforms=tuple(lr.get("transforms") or ()),
                        consumer_slas=slas,
                    )
                )
            domains.append(
                MedallionDomainSpec(
                    domain_id=str(d["domain_id"]),
                    owner_team=str(d.get("owner_team") or f"{d['domain_id']}-platform"),
                    description=str(d.get("description") or ""),
                    layers=tuple(layer_specs),
                    schedule_cron=d.get("schedule_cron"),
                    mesh_transaction_group=d.get("mesh_transaction_group"),
                )
            )

        return cls(
            api_version=str(raw.get("apiVersion", "")),
            kind=str(raw.get("kind", "")),
            organization=str(meta.get("organization") or "mesh"),
            description=str(meta.get("description") or ""),
            accounts=PipelineAccounts(
                producer=str(accounts_raw.get("producer") or ""),
                steward=accounts_raw.get("steward"),
                publisher=accounts_raw.get("publisher"),
            ),
            domains=tuple(domains),
            aws_region=str(spec.get("aws_region") or "us-east-2"),
            name_prefix=str(spec.get("name_prefix") or "sdm-mesh"),
            mesh_transactions=tuple(spec.get("mesh_transactions") or ()),
        )

    def layer_pipeline_contract(
        self,
        domain: MedallionDomainSpec,
        layer: MedallionLayerSpec,
    ) -> MeshPipelineContract:
        """Convert one medallion layer into a compilable DataProductPipeline contract."""
        product_id = f"{domain.domain_id}-{layer.layer}-{layer.target_table}"
        triggers: list[PipelineTrigger] = []
        if layer.layer == "bronze" and domain.schedule_cron:
            triggers.append(
                PipelineTrigger(
                    type="schedule",
                    cron=domain.schedule_cron,
                    description=f"Bronze ingest for {domain.domain_id}",
                )
            )
        elif layer.upstream_layer:
            triggers.append(
                PipelineTrigger(
                    type="chain",
                    description=f"Run after {layer.upstream_layer} VRP PASS",
                )
            )
        else:
            triggers.append(PipelineTrigger(type="manual"))

        extras = layer.package_extras
        if not extras:
            if layer.runtime_engine == "pyspark":
                extras = "spark"
            elif layer.spark_rules_enabled:
                extras = "rules"

        return MeshPipelineContract(
            api_version="sdm/v1",
            kind="DataProductPipeline",
            domain_id=domain.domain_id,
            product_id=product_id,
            owner_team=domain.owner_team,
            description=layer.description or f"{layer.layer} layer for {domain.domain_id}",
            accounts=self.accounts,
            boundary=PipelineBoundary(
                source_namespace=layer.source_namespace,
                target_table=layer.target_table,
                partition_key="dt",
                max_chunk_records=layer.max_chunk_records,
            ),
            workload=PipelineWorkload(
                identity_fields=layer.identity_fields,
                content_fields=layer.content_fields,
            ),
            governance=PipelineGovernance(
                auto_repair=layer.auto_repair,
            ),
            runtime=PipelineRuntime(
                engine=layer.runtime_engine,
                package_extras=extras,
                lambda_memory_mb=layer.lambda_memory_mb,
                spark_rules_enabled=layer.spark_rules_enabled,
            ),
            triggers=tuple(triggers),
            consumer_slas=layer.consumer_slas,
            aws_region=self.aws_region,
            name_prefix=f"{self.name_prefix}-{domain.domain_id}-{layer.layer}",
        )
