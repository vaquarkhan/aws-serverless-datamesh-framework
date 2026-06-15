"""Unit tests for runtime configuration."""

from __future__ import annotations

import pytest

from serverless_data_mesh.config import MeshSettings


def test_from_environment_requires_checkpoint_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ICEGUARD_CHECKPOINT_BUCKET", raising=False)
    with pytest.raises(ValueError, match="ICEGUARD_CHECKPOINT_BUCKET"):
        MeshSettings.from_environment()


def test_from_environment_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ICEGUARD_CHECKPOINT_BUCKET", "my-checkpoints")
    monkeypatch.delenv("VRP_PROOF_BUCKET", raising=False)
    settings = MeshSettings.from_environment()
    assert settings.checkpoint_bucket == "my-checkpoints"
    assert settings.proof_bucket == "my-checkpoints"
    assert settings.checkpoint_interval == 5000
