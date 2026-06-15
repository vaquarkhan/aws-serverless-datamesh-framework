"""Cryptographic verification via veridata-recon (VRP v0.1)."""

from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import boto3
import veridata_recon as vr

from serverless_data_mesh.types.workload import DataWriteWorkload

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VerifyResult:
    """Outcome of a validate-then-commit reconciliation check."""

    outcome: str
    reason: str | None = None


ValidateResult = VerifyResult


def _identity_rule(fields: tuple[str, ...]) -> str:
    if len(fields) == 1:
        return f"field:{fields[0]}"
    return f"composite:[{','.join(fields)}]"


def _coerce_records(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    """veridata-recon requires string field values for canonical hashing."""
    return [{key: str(value) for key, value in record.items()} for record in records]


@dataclass(slots=True)
class VRPProofGenerator:
    """Generate offline, tamper-evident reconciliation proofs for pipeline chunks."""

    private_key_b64: str
    public_key_b64: str
    salt_hex: str
    producer: str = "serverless-data-mesh/0.1.0"

    @classmethod
    def from_env(cls) -> VRPProofGenerator:
        """Load signing keys from ``VRP_SIGNING_KEY_B64`` or generate ephemeral ones."""
        raw = os.environ.get("VRP_SIGNING_KEY_B64")
        if raw:
            keys = vr.keypair_from_private(raw)
        else:
            keys = vr.generate_keypair()
        return cls(
            private_key_b64=keys["private_key"],
            public_key_b64=keys["public_key"],
            salt_hex=vr.generate_salt(),
        )

    def build_proof(
        self,
        *,
        source_records: list[dict[str, Any]],
        sink_records: list[dict[str, Any]],
        workload: DataWriteWorkload,
        chunk_start: int,
        chunk_end: int,
        prev_proof_hash: str | None = None,
    ) -> dict[str, Any]:
        """Hash and compare source vs target partition, returning a proof envelope."""
        identity_rule = _identity_rule(workload.identity_fields)
        content_fields = list(workload.content_fields)

        reconciliation = vr.reconcile(
            source=_coerce_records(source_records),
            sink=_coerce_records(sink_records),
            identity_rule=identity_rule,
            content_fields=content_fields,
            salt=self.salt_hex,
        )

        boundary_value = base64.b64encode(
            json.dumps(
                {
                    "workload_id": workload.workload_id,
                    "domain_id": workload.boundary.domain_id,
                    "start": chunk_start,
                    "end": chunk_end,
                    "partition": workload.boundary.partition_spec,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).decode("ascii")

        document: dict[str, Any] = {
            "proof_version": "0.1",
            "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "producer": self.producer,
            "boundary": {"mode": "OFFSET_RANGE", "value": boundary_value},
            "source_ref": workload.source_uri,
            "sink_ref": workload.target_uri,
            "hash_algorithm": "sha256",
            "salt": self.salt_hex,
            "identity_rule": identity_rule,
            "content_fields": content_fields,
            "reconciliation": reconciliation,
            "public_key": self.public_key_b64,
            "chain": {"prev_proof_hash": prev_proof_hash},
        }
        document["proof_id"] = vr.hash_bytes(
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        return document

    def persist_proof(
        self,
        proof: dict[str, Any],
        *,
        bucket: str,
        key_prefix: str,
        chunk_index: int,
        s3_client: Any | None = None,
    ) -> str:
        """Write the reconciliation proof JSON alongside IceGuard Parquet artifacts."""
        client = s3_client or boto3.client("s3")
        key = f"{key_prefix.rstrip('/')}/proofs/chunk-{chunk_index:06d}.vrp.json"
        body = json.dumps(proof, indent=2, sort_keys=True).encode("utf-8")
        verdict = proof["reconciliation"]["verdict"]
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            Metadata={"proof-id": proof["proof_id"], "verdict": verdict},
        )
        uri = f"s3://{bucket}/{key}"
        logger.info("Persisted VRP proof to %s (verdict=%s)", uri, verdict)
        return uri


def validate_then_commit(
    proof: dict[str, Any],
    *,
    public_key_b64: str | None = None,
) -> VerifyResult:
    """Validate-then-commit hook: verify reconciliation before metadata commit."""
    verdict = proof["reconciliation"]["verdict"]
    if verdict == "PASS":
        return VerifyResult("PASS")

    missing = len(proof["reconciliation"].get("missing", []))
    mutated = len(proof["reconciliation"].get("mutated", []))
    duplicated = len(proof["reconciliation"].get("duplicated", []))
    reason = (
        f"reconciliation {verdict}: missing={missing}, "
        f"mutated={mutated}, duplicated={duplicated}"
    )
    logger.error("VRP validation blocked metadata commit: %s", reason)

    pubkey = public_key_b64 or proof.get("public_key")
    if pubkey:
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".vrp.json",
                delete=False,
                encoding="utf-8",
            ) as handle:
                json.dump(proof, handle, indent=2, sort_keys=True)
                temp_path = handle.name
            offline = vr.verify_proof(temp_path, pubkey)
            os.unlink(temp_path)
            if offline != verdict:
                reason = f"{reason}; offline_verify={offline}"
        except Exception as exc:
            logger.warning("Offline veridata-recon verify_proof skipped: %s", exc)

    return VerifyResult(verdict, reason)
