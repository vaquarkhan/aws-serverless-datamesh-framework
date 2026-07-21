"""Serverless Data Mesh: cross-domain lakehouse write coordination on AWS Lambda."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from serverless_data_mesh.config import MeshSettings
from serverless_data_mesh.exceptions import (
    CatalogCommitError,
    RuleEvaluationError,
    ServerlessDataMeshError,
    VerificationRejectedError,
    WorkloadConfigurationError,
)
from serverless_data_mesh.types import (
    ChunkWriteResult,
    DataProductContract,
    DataWriteWorkload,
    DomainTransactionBoundary,
    WriteOutcome,
)

def _read_version() -> str:
    try:
        from importlib.metadata import version

        return version("serverless-data-mesh")
    except Exception:
        pass

    pkg = Path(__file__).resolve().parent
    for candidate in (
        pkg / "VERSION",
        pkg.parent / "VERSION",
        Path(__file__).resolve().parents[2] / "VERSION",
    ):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    return "0.0.0"


__version__ = _read_version()

__all__ = [
    "CatalogCommitError",
    "ChunkWriteResult",
    "DataProductContract",
    "DataWriteWorkload",
    "DecisionAttestation",
    "DomainTransactionBoundary",
    "GlueCatalogConnector",
    "GlueRestCatalogAdapter",
    "IceGuardDurableCoordinator",
    "MeshSettings",
    "OrchestrationState",
    "RuleEvaluationError",
    "RuleFireSummary",
    "SparkRulesConnector",
    "ServerlessDataMeshError",
    "VRPProofGenerator",
    "VerificationRejectedError",
    "WorkloadConfigurationError",
    "WriteOutcome",
    "attach_kms_signature",
    "create_attestation",
    "validate_then_commit",
    "verify_attestation",
    "verify_kms_signature",
    "__version__",
]


def __getattr__(name: str) -> Any:
    """Lazy-load heavy integrations (IceGuard, veridata-recon, PyIceberg)."""
    if name in ("GlueCatalogConnector", "GlueRestCatalogAdapter"):
        from serverless_data_mesh.catalog import GlueCatalogConnector, GlueRestCatalogAdapter

        return {
            "GlueCatalogConnector": GlueCatalogConnector,
            "GlueRestCatalogAdapter": GlueRestCatalogAdapter,
        }[name]
    if name in ("SparkRulesConnector", "RuleFireSummary"):
        from serverless_data_mesh.rules import RuleFireSummary, SparkRulesConnector

        return {
            "SparkRulesConnector": SparkRulesConnector,
            "RuleFireSummary": RuleFireSummary,
        }[name]
    if name in ("IceGuardDurableCoordinator", "OrchestrationState"):
        from serverless_data_mesh.orchestration import (
            IceGuardDurableCoordinator,
            OrchestrationState,
        )

        return {
            "IceGuardDurableCoordinator": IceGuardDurableCoordinator,
            "OrchestrationState": OrchestrationState,
        }[name]
    if name in ("VRPProofGenerator", "validate_then_commit"):
        from serverless_data_mesh.verification import VRPProofGenerator, validate_then_commit

        return {
            "VRPProofGenerator": VRPProofGenerator,
            "validate_then_commit": validate_then_commit,
        }[name]
    if name in ("attach_kms_signature", "verify_kms_signature"):
        from serverless_data_mesh.verification.kms_sign import (
            attach_kms_signature,
            verify_kms_signature,
        )

        return {
            "attach_kms_signature": attach_kms_signature,
            "verify_kms_signature": verify_kms_signature,
        }[name]
    if name in ("DecisionAttestation", "create_attestation", "verify_attestation"):
        from serverless_data_mesh.attestation import (
            DecisionAttestation,
            create_attestation,
            verify_attestation,
        )

        return {
            "DecisionAttestation": DecisionAttestation,
            "create_attestation": create_attestation,
            "verify_attestation": verify_attestation,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
