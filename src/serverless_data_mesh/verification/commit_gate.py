"""Metadata-phase commit gate (PVDM Theorems 1–3 / N4 / N5 / N10).

Fail-closed catalog commit requires:
  - Steward signature over the binding body
  - verdict PASS
  - target matches expected commit target
  - nonce not previously consumed
  - per-file digests still match published bytes (TOCTOU)
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from serverless_data_mesh.verification.nonce_ledger import NonceReplayError, claim_nonce
from serverless_data_mesh.verification.pvdm_primitives import (
    PvdmBinding,
    steward_sign_key_from_env,
    unsigned_proofs_allowed,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CommitGateResult:
    """Outcome of the proof-gated Metadata check."""

    outcome: str
    reason: str | None = None


def _parse_s3(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Not an s3 URI: {uri}")
    key = parsed.path.lstrip("/")
    return parsed.netloc, key


def digest_bytes(data: bytes) -> str:
    """SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def digest_uri(uri: str, *, s3_client: Any | None = None) -> str:
    """Hash local path or ``s3://`` object bytes (streaming)."""
    if uri.startswith("s3://"):
        import boto3

        client = s3_client or boto3.client("s3")
        bucket, key = _parse_s3(uri)
        hasher = hashlib.sha256()
        response = client.get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        while True:
            chunk = body.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
        return hasher.hexdigest()

    path = uri.removeprefix("file://")
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def bind_file_digests(
    paths: list[str],
    *,
    s3_client: Any | None = None,
    allow_unreadable: bool | None = None,
) -> list[dict[str, str]]:
    """Compute per-file digests for staged objects (Verify-time binding)."""
    if allow_unreadable is None:
        allow_unreadable = os.environ.get("SDM_ALLOW_UNREADABLE_STAGING", "").lower() in (
            "1",
            "true",
            "yes",
        )
    digests: list[dict[str, str]] = []
    for path in paths:
        try:
            digests.append({"path": path, "sha256": digest_uri(path, s3_client=s3_client)})
        except Exception as exc:
            if not allow_unreadable:
                raise RuntimeError(
                    f"Cannot bind file digest for staged path {path!r}: {exc}. "
                    "Write real staging objects before Verify, or set "
                    "SDM_ALLOW_UNREADABLE_STAGING=1 only for local stubs."
                ) from exc
            logger.warning("Unreadable staging path %s (%s); digest unbound", path, exc)
            digests.append({"path": path, "sha256": ""})
    return digests


def attach_file_digests(proof: dict[str, Any], digests: list[dict[str, str]]) -> dict[str, Any]:
    """Attach physical file digests to a VRP proof envelope (mutates and returns)."""
    proof["physical_file_digests"] = digests
    return proof


def source_as_sink_allowed() -> bool:
    """Demo escape hatch: compare source to itself (disables real content gate)."""
    return os.environ.get("SDM_ALLOW_SOURCE_AS_SINK", "").lower() in ("1", "true", "yes")


def file_digest_gate_enabled() -> bool:
    """TOCTOU re-hash at Metadata; default on unless explicitly disabled."""
    raw = os.environ.get("SDM_FILE_DIGEST_GATE")
    if raw is None:
        return True
    return raw.lower() in ("1", "true", "yes")


def _binding_from_proof(proof: dict[str, Any]) -> PvdmBinding | None:
    raw = proof.get("pvdm_binding")
    if not raw:
        return None
    return PvdmBinding.from_dict(raw)


def metadata_commit_gate(
    *,
    verification_passed: bool,
    parquet_paths: list[str],
    bound_digests: list[dict[str, str]] | None = None,
    proofs: list[dict[str, Any]] | None = None,
    expected_target: str | None = None,
    proof_bucket: str | None = None,
    s3_client: Any | None = None,
    burn_nonces: bool = True,
) -> CommitGateResult:
    """Fail-closed Metadata gate matching the paper reference ``validate_then_commit``."""
    if not verification_passed:
        return CommitGateResult("FAIL", "verification_passed is false")

    if not parquet_paths and not proofs:
        return CommitGateResult("PASS")

    bindings: list[PvdmBinding] = []
    if proofs:
        for idx, proof in enumerate(proofs):
            verdict = (proof.get("reconciliation") or {}).get("verdict")
            binding = _binding_from_proof(proof)
            if binding is None:
                if unsigned_proofs_allowed():
                    logger.warning("Proof[%s] missing pvdm_binding (unsigned escape hatch)", idx)
                    if verdict != "PASS":
                        return CommitGateResult(
                            "FAIL",
                            f"proof[{idx}] verdict={verdict!r}; Metadata requires PASS",
                        )
                    continue
                return CommitGateResult(
                    "FAIL",
                    f"proof[{idx}] missing pvdm_binding (N5 Steward-signed binding required)",
                )
            if binding.verdict != "PASS" or verdict != "PASS":
                return CommitGateResult(
                    "FAIL",
                    f"proof[{idx}] verdict={verdict!r} binding={binding.verdict!r}",
                )
            sign_key = steward_sign_key_from_env()
            if sign_key is None and not unsigned_proofs_allowed():
                return CommitGateResult("FAIL", "Steward sign key not configured (N5)")
            if sign_key is not None and not binding.verify_signature(sign_key):
                return CommitGateResult("FAIL", f"proof[{idx}] Steward signature invalid")
            if expected_target and binding.target != expected_target:
                return CommitGateResult(
                    "FAIL",
                    f"proof[{idx}] target mismatch (misdirection): "
                    f"proof={binding.target!r} expected={expected_target!r}",
                )
            bindings.append(binding)

    if not file_digest_gate_enabled():
        if burn_nonces:
            for binding in bindings:
                try:
                    claim_nonce(binding.nonce, proof_bucket=proof_bucket, s3_client=s3_client)
                except NonceReplayError as exc:
                    return CommitGateResult("FAIL", str(exc))
        return CommitGateResult("PASS")

    expected = list(bound_digests or [])
    if proofs and not expected:
        for proof in proofs:
            expected.extend(proof.get("physical_file_digests") or [])
            binding = _binding_from_proof(proof)
            if binding:
                expected.extend({"path": p, "sha256": d} for p, d in binding.file_digests.items())

    if not parquet_paths:
        if burn_nonces:
            for binding in bindings:
                try:
                    claim_nonce(binding.nonce, proof_bucket=proof_bucket, s3_client=s3_client)
                except NonceReplayError as exc:
                    return CommitGateResult("FAIL", str(exc))
        return CommitGateResult("PASS")

    if not expected:
        if os.environ.get("SDM_ALLOW_UNREADABLE_STAGING", "").lower() in (
            "1",
            "true",
            "yes",
        ):
            logger.warning("Metadata commit without bound file digests (escape hatch)")
            return CommitGateResult("PASS")
        return CommitGateResult(
            "FAIL",
            "no physical_file_digests bound at Verify; refusing Metadata commit",
        )

    by_path = {item["path"]: item.get("sha256", "") for item in expected}
    for path in parquet_paths:
        bound = by_path.get(path)
        if bound is None:
            return CommitGateResult("FAIL", f"path not in Verify digests: {path}")
        if not bound:
            return CommitGateResult("FAIL", f"empty Verify digest for path: {path}")
        try:
            actual = digest_uri(path, s3_client=s3_client)
        except Exception as exc:
            return CommitGateResult("FAIL", f"cannot re-hash published bytes for {path}: {exc}")
        if actual != bound:
            return CommitGateResult(
                "FAIL",
                f"TOCTOU digest mismatch for {path}: verify={bound[:16]}… commit={actual[:16]}…",
            )

    for path, bound in by_path.items():
        if path not in parquet_paths and bound:
            return CommitGateResult(
                "FAIL",
                f"Verify-bound path missing from Metadata commit set: {path}",
            )

    if burn_nonces:
        for binding in bindings:
            try:
                claim_nonce(binding.nonce, proof_bucket=proof_bucket, s3_client=s3_client)
            except NonceReplayError as exc:
                return CommitGateResult("FAIL", str(exc))

    return CommitGateResult("PASS")
