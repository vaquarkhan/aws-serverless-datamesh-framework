# Portable multi-cloud interfaces

Serverless Data Mesh is **AWS-first** (Lambda + S3 + Glue Iceberg). The `serverless_data_mesh.portable` package defines object-store adapters so domain `readers.py` can be written against a common interface when federating across clouds.

## Usage

```python
from serverless_data_mesh.portable import get_adapter

store = get_adapter("aws")  # production
# store = get_adapter("gcp")   # stub — wire google-cloud-storage
# store = get_adapter("azure") # stub — wire azure-storage-blob

keys = store.list_prefix("s3://landing-bucket/orders/")
data = store.read_bytes(f"s3://landing-bucket/{keys[0]}")
```

| Provider | Status | URI scheme |
|----------|--------|------------|
| `aws` | Production | `s3://` |
| `gcp` | Stub | `gs://` |
| `azure` | Stub | `abfs://` |

Extend `GCPAdapter` / `AzureAdapter` in `src/serverless_data_mesh/portable/cloud.py` for your platform.
