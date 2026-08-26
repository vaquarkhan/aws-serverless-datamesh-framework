"""Cryptographic verification and reconciliation proofs."""

from serverless_data_mesh.verification.backend import create_proof_generator, veridata_available
from serverless_data_mesh.verification.commit_gate import (
    CommitGateResult,
    attach_file_digests,
    bind_file_digests,
    digest_bytes,
    digest_uri,
    metadata_commit_gate,
    source_as_sink_allowed,
)
from serverless_data_mesh.verification.fallback import FallbackProofGenerator, reconcile_multiset
from serverless_data_mesh.verification.kms_sign import (
    attach_kms_signature,
    kms_key_id_from_env,
    verify_kms_signature,
)
from serverless_data_mesh.verification.pvdm_primitives import (
    PvdmBinding,
    build_pvdm_binding,
    multiset_hash,
    require_steward_keys,
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
    "CommitGateResult",
    "PvdmBinding",
    "validate_then_commit",
    "metadata_commit_gate",
    "bind_file_digests",
    "attach_file_digests",
    "digest_bytes",
    "digest_uri",
    "source_as_sink_allowed",
    "multiset_hash",
    "build_pvdm_binding",
    "require_steward_keys",
    "create_proof_generator",
    "veridata_available",
    "reconcile_multiset",
    "attach_kms_signature",
    "verify_kms_signature",
    "kms_key_id_from_env",
]
