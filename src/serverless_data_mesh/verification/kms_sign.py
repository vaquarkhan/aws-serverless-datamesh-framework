"""Optional AWS KMS signing for VRP proof envelopes.

When ``VRP_KMS_KEY_ID`` (or ``VRP_KMS_KEY_ARN``) is set, attach a KMS signature
over the proof payload so auditors can verify with KMS Verify — in addition to
the existing veridata keypair fields.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def kms_key_id_from_env() -> str | None:
    key = os.environ.get("VRP_KMS_KEY_ID") or os.environ.get("VRP_KMS_KEY_ARN")
    return key.strip() if key else None


def _digest_bytes(proof: dict[str, Any]) -> bytes:
    """Stable digest excluding any existing kms_signature block."""
    payload = {k: v for k, v in proof.items() if k != "kms_signature"}
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).digest()


def attach_kms_signature(
    proof: dict[str, Any],
    *,
    key_id: str | None = None,
    kms_client: Any | None = None,
) -> dict[str, Any]:
    """Mutate proof with ``kms_signature`` when a key id is configured. No-op otherwise."""
    kid = key_id if key_id is not None else kms_key_id_from_env()
    if not kid:
        return proof

    client = kms_client or boto3.client("kms")
    digest = _digest_bytes(proof)

    for algorithm in ("RSASSA_PSS_SHA_256", "ECDSA_SHA_256"):
        try:
            response = client.sign(
                KeyId=kid,
                Message=digest,
                MessageType="DIGEST",
                SigningAlgorithm=algorithm,
            )
            proof["kms_signature"] = {
                "key_id": response.get("KeyId", kid),
                "mode": "sign",
                "algorithm": response.get("SigningAlgorithm", algorithm),
                "signature_b64": base64.b64encode(response["Signature"]).decode("ascii"),
                "digest_sha256": digest.hex(),
            }
            logger.info("Attached KMS signature to proof %s", proof.get("proof_id"))
            return proof
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in (
                "InvalidKeyUsageException",
                "UnsupportedOperationException",
                "ValidationException",
            ):
                continue
            logger.warning("KMS sign failed (%s): %s", code, exc)
            return proof
        except Exception as exc:
            logger.warning("KMS sign skipped: %s", exc)
            return proof

    # Symmetric CMK fallback: encrypt digest as envelope marker
    try:
        response = client.encrypt(KeyId=kid, Plaintext=digest)
        proof["kms_signature"] = {
            "key_id": kid,
            "mode": "encrypt_digest",
            "algorithm": "SYMMETRIC_DEFAULT",
            "ciphertext_b64": base64.b64encode(response["CiphertextBlob"]).decode("ascii"),
            "digest_sha256": digest.hex(),
        }
        logger.info("Attached KMS encrypt-digest envelope to proof %s", proof.get("proof_id"))
    except Exception as exc:
        logger.warning("KMS encrypt-digest skipped: %s", exc)
    return proof


def verify_kms_signature(
    proof: dict[str, Any],
    *,
    kms_client: Any | None = None,
) -> bool:
    """Verify KMS signature block if present. Returns True when absent (N/A)."""
    block = proof.get("kms_signature")
    if not block:
        return True
    if block.get("mode") != "sign":
        return bool(block.get("ciphertext_b64") and block.get("digest_sha256"))

    client = kms_client or boto3.client("kms")
    digest = _digest_bytes(proof)
    if digest.hex() != block.get("digest_sha256"):
        return False
    try:
        result = client.verify(
            KeyId=block["key_id"],
            Message=digest,
            MessageType="DIGEST",
            Signature=base64.b64decode(block["signature_b64"]),
            SigningAlgorithm=block.get("algorithm", "RSASSA_PSS_SHA_256"),
        )
        return bool(result.get("SignatureValid"))
    except Exception as exc:
        logger.warning("KMS verify failed: %s", exc)
        return False
