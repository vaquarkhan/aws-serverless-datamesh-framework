"""Framework-specific exceptions for transaction boundary enforcement."""

from __future__ import annotations


class ServerlessDataMeshError(Exception):
    """Base error for all serverless-data-mesh failures."""


class VerificationRejectedError(ServerlessDataMeshError):
    """Raised when VRP validation blocks a chunk from committing."""


class CatalogCommitError(ServerlessDataMeshError):
    """Raised when the Glue REST metadata commit fails."""


class WorkloadConfigurationError(ServerlessDataMeshError):
    """Raised when a domain workload or boundary contract is invalid."""


class RuleEvaluationError(ServerlessDataMeshError):
    """Raised when SparkRules quality gate or policy evaluation fails."""
