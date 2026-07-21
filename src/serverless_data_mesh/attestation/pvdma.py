"""PVDM-A: Decision Attestation — cryptographic provenance for governed writes.

Binds a decision (human or agent) to a VRP proof URI so mesh stewards can
audit *who* allowed a commit and *which* proof it depended on.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3

logger = logging.getLogger(__name__)

ATTESTATION_VERSION = "1.0"


def _sha256_hex(payload: str | bytes) -> str:
    data = payload if isinstance(payload, bytes) else payload.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True)


@dataclass(slots=True)
class DecisionAttestation:
    """Provenance record linking a decision to a VRP proof."""

    attestation_id: str
    agent_id: str
    domain_id: str
    workload_id: str
    decision: str  # allow_commit | deny | quarantine
    vrp_verdict: str
    vrp_proof_uri: str | None = None
    vrp_proof_id: str | None = None
    session_id: str | None = None
    tool_name: str | None = None
    prompt_hash: str | None = None
    tool_args_hash: str | None = None
    chunk_index: int | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )
    attestation_version: str = ATTESTATION_VERSION
    content_hash: str | None = None

    def seal(self) -> DecisionAttestation:
        """Compute content_hash over all fields except content_hash itself."""
        body = {k: v for k, v in asdict(self).items() if k != "content_hash" and v is not None}
        self.content_hash = f"sha256:{_sha256_hex(_canonical_json(body))}"
        return self

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecisionAttestation:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def create_attestation(
    *,
    domain_id: str,
    workload_id: str,
    decision: str,
    vrp_verdict: str,
    agent_id: str | None = None,
    vrp_proof_uri: str | None = None,
    vrp_proof_id: str | None = None,
    session_id: str | None = None,
    tool_name: str | None = None,
    prompt: str | None = None,
    tool_args: dict[str, Any] | None = None,
    chunk_index: int | None = None,
) -> DecisionAttestation:
    """Build and seal a PVDM-A attestation."""
    if decision not in ("allow_commit", "deny", "quarantine"):
        raise ValueError(f"invalid decision: {decision}")

    agent = agent_id or os.environ.get("SDM_AGENT_ID") or "human/operator"
    att = DecisionAttestation(
        attestation_id=f"pvdma-{uuid.uuid4().hex[:16]}",
        agent_id=agent,
        domain_id=domain_id,
        workload_id=workload_id,
        decision=decision,
        vrp_verdict=vrp_verdict,
        vrp_proof_uri=vrp_proof_uri,
        vrp_proof_id=vrp_proof_id,
        session_id=session_id or os.environ.get("SDM_SESSION_ID"),
        tool_name=tool_name or os.environ.get("SDM_TOOL_NAME"),
        prompt_hash=f"sha256:{_sha256_hex(prompt)}" if prompt else None,
        tool_args_hash=(
            f"sha256:{_sha256_hex(_canonical_json(tool_args))}" if tool_args is not None else None
        ),
        chunk_index=chunk_index,
    )
    return att.seal()


def verify_attestation(attestation: DecisionAttestation | dict[str, Any]) -> bool:
    """Return True if content_hash matches the sealed payload."""
    if isinstance(attestation, dict):
        attestation = DecisionAttestation.from_dict(attestation)
    if not attestation.content_hash:
        return False
    expected = attestation.content_hash
    clone = DecisionAttestation.from_dict(attestation.to_dict())
    clone.content_hash = None
    clone.seal()
    return clone.content_hash == expected


def _write_local(local_dir: str, prefix: str, filename: str, body: bytes) -> str:
    dest_dir = Path(local_dir) / prefix.replace("/", os.sep)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / filename
    path.write_bytes(body)
    return str(path)


def persist_attestation(
    attestation: DecisionAttestation,
    *,
    bucket: str | None = None,
    key_prefix: str | None = None,
    s3_client: Any | None = None,
    local_dir: str | None = None,
) -> str:
    """Persist attestation JSON to S3 (or local dir for demos). Returns URI/path."""
    if not attestation.content_hash:
        attestation.seal()

    body = json.dumps(attestation.to_dict(), indent=2, sort_keys=True).encode("utf-8")
    prefix = key_prefix or (
        f"attestations/{attestation.domain_id}/{attestation.workload_id}"
    )
    filename = f"{attestation.attestation_id}.pvdma.json"

    if local_dir:
        dest = _write_local(local_dir, prefix, filename, body)
        logger.info("Persisted PVDM-A attestation to %s", dest)
        return dest

    bucket_name = bucket or os.environ.get("VRP_PROOF_BUCKET") or os.environ.get("PROOF_BUCKET")
    if not bucket_name:
        raise ValueError("bucket or VRP_PROOF_BUCKET required to persist attestation")

    client = s3_client or boto3.client("s3")
    key = f"{prefix.rstrip('/')}/{filename}"
    client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=body,
        ContentType="application/json",
        Metadata={
            "attestation-id": attestation.attestation_id,
            "decision": attestation.decision,
            "vrp-verdict": attestation.vrp_verdict,
        },
    )
    uri = f"s3://{bucket_name}/{key}"
    logger.info("Persisted PVDM-A attestation to %s", uri)
    return uri


def maybe_attest_outcome(
    *,
    domain_id: str,
    workload_id: str,
    decision: str,
    vrp_verdict: str,
    vrp_proof_uri: str | None = None,
    vrp_proof_id: str | None = None,
    chunk_index: int | None = None,
    proof_bucket: str | None = None,
    local_dir: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any] | None:
    """Create + persist attestation when SDM_ATTESTATION_ENABLED is truthy (default on)."""
    if enabled is None:
        flag = os.environ.get("SDM_ATTESTATION_ENABLED", "1").strip().lower()
        enabled = flag not in ("0", "false", "no", "off")
    if not enabled:
        return None

    att = create_attestation(
        domain_id=domain_id,
        workload_id=workload_id,
        decision=decision,
        vrp_verdict=vrp_verdict,
        vrp_proof_uri=vrp_proof_uri,
        vrp_proof_id=vrp_proof_id,
        chunk_index=chunk_index,
    )
    try:
        uri = persist_attestation(
            att,
            bucket=proof_bucket,
            local_dir=local_dir,
        )
    except Exception as exc:
        logger.warning("PVDM-A persist skipped: %s", exc)
        return {**att.to_dict(), "persist_error": str(exc)}
    return {**att.to_dict(), "uri": uri}
