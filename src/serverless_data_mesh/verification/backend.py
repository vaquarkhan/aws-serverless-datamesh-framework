"""Select veridata-recon or pure-Python fallback proof backend."""

from __future__ import annotations

from typing import Any, Protocol


class ProofGeneratorProtocol(Protocol):
    def build_proof(self, **kwargs: Any) -> dict[str, Any]: ...
    def persist_proof(self, **kwargs: Any) -> str: ...


def veridata_available() -> bool:
    try:
        import veridata_recon  # noqa: F401

        return True
    except ImportError:
        return False


def create_proof_generator() -> tuple[Any, str]:
    """Return (generator, backend_name). Prefers veridata-recon; falls back to pure Python."""
    if veridata_available():
        import veridata_recon as vr

        from serverless_data_mesh.verification.vrp import VRPProofGenerator

        keys = vr.generate_keypair()
        return (
            VRPProofGenerator(
                private_key_b64=keys["private_key"],
                public_key_b64=keys["public_key"],
                salt_hex=vr.generate_salt(),
            ),
            "veridata-recon",
        )

    from serverless_data_mesh.verification.fallback import FallbackProofGenerator

    return FallbackProofGenerator(), "pure-python-fallback"
