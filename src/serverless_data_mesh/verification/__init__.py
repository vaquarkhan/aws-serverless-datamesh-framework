"""Cryptographic verification and reconciliation proofs."""

from serverless_data_mesh.verification.backend import create_proof_generator, veridata_available
from serverless_data_mesh.verification.fallback import FallbackProofGenerator, reconcile_multiset
from serverless_data_mesh.verification.kms_sign import (
    attach_kms_signature,
    kms_key_id_from_env,
    verify_kms_signature,
)
from serverless_data_mesh.verification.vrp import (
    ValidateResult,
    VerifyResult,
    VRPProofGenerator,
    validate_then_commit,
)

__all__ = [
    "VRPProofGenerator",
    "FallbackProofGenerator",
    "ValidateResult",
    "VerifyResult",
    "validate_then_commit",
    "create_proof_generator",
    "veridata_available",
    "reconcile_multiset",
    "attach_kms_signature",
    "verify_kms_signature",
    "kms_key_id_from_env",
]
