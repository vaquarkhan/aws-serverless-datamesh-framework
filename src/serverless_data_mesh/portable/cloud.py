"""Portable cloud abstractions (AWS primary; GCP/Azure adapters for federation)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class ObjectStore(Protocol):
    def list_prefix(self, uri: str) -> list[str]: ...
    def read_bytes(self, uri: str) -> bytes: ...
    def write_bytes(self, uri: str, data: bytes) -> str: ...


@runtime_checkable
class ServerlessWriter(Protocol):
    def invoke(self, payload: dict[str, object]) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class CloudProfile:
    provider: str  # aws | gcp | azure
    region: str
    account_id: str


class AWSAdapter:
    """AWS S3 + Lambda (production path)."""

    provider = "aws"

    def list_prefix(self, uri: str) -> list[str]:
        import boto3

        bucket, _, prefix = uri.removeprefix("s3://").partition("/")
        client = boto3.client("s3")
        keys: list[str] = []
        token = None
        while True:
            kwargs: dict[str, object] = {"Bucket": bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            resp = client.list_objects_v2(**kwargs)
            keys.extend(obj["Key"] for obj in resp.get("Contents", []))
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return keys

    def read_bytes(self, uri: str) -> bytes:
        import boto3

        bucket, _, key = uri.removeprefix("s3://").partition("/")
        return boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()

    def write_bytes(self, uri: str, data: bytes) -> str:
        import boto3

        bucket, _, key = uri.removeprefix("s3://").partition("/")
        boto3.client("s3").put_object(Bucket=bucket, Key=key, Body=data)
        return uri


class GCPAdapter:
    """GCS stub — map gs:// URIs; swap ObjectStore in portable pipelines."""

    provider = "gcp"

    def list_prefix(self, uri: str) -> list[str]:
        raise NotImplementedError("Install google-cloud-storage and wire GCPAdapter for GCS")

    def read_bytes(self, uri: str) -> bytes:
        raise NotImplementedError("GCP read_bytes not configured")

    def write_bytes(self, uri: str, data: bytes) -> str:
        raise NotImplementedError("GCP write_bytes not configured")


class AzureAdapter:
    """Azure Blob stub — map abfs:// URIs."""

    provider = "azure"

    def list_prefix(self, uri: str) -> list[str]:
        raise NotImplementedError("Install azure-storage-blob and wire AzureAdapter")

    def read_bytes(self, uri: str) -> bytes:
        raise NotImplementedError("Azure read_bytes not configured")

    def write_bytes(self, uri: str, data: bytes) -> str:
        raise NotImplementedError("Azure write_bytes not configured")


def get_adapter(provider: str) -> ObjectStore:
    adapters: dict[str, ObjectStore] = {
        "aws": AWSAdapter(),
        "gcp": GCPAdapter(),
        "azure": AzureAdapter(),
    }
    key = provider.lower()
    if key not in adapters:
        raise ValueError(f"Unknown provider {provider!r}; choose aws|gcp|azure")
    return adapters[key]
