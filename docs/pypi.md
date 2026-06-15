# PyPI: Publishing & Installing Serverless Data Mesh

The framework is published to **PyPI** as [`serverless-data-mesh`](https://pypi.org/project/serverless-data-mesh/).

The PyPI project page long description is **[`PYPI.md`](../PYPI.md)** (configured in `pyproject.toml`). The GitHub **[`README.md`](../README.md)** is the full product landing page with diagrams.

Create GitHub release `v0.1.1` to trigger [publish.yml](../.github/workflows/publish.yml).

---

## Install from PyPI

```bash
# Core framework (IceGuard, veridata-recon, Durable SDK, PyIceberg Glue REST)
pip install serverless-data-mesh

# + SparkRules business rules on Lambda (pure Python, no Glue ETL)
pip install "serverless-data-mesh[rules]"

# + PySpark-on-Lambda + SparkRules distributed rules
pip install "serverless-data-mesh[spark]"

# Everything (rules + spark)
pip install "serverless-data-mesh[all]"

# Development
pip install "serverless-data-mesh[dev]"
```

### PyPI dependency map

| Extra | Packages | Use on Lambda |
|-------|----------|---------------|
| *(core)* | iceguard, veridata-recon, durable-sdk, pyiceberg, boto3 | Yes |
| `[rules]` | sparkrules | Yes: pure Python `LocalRuleExecutor` |
| `[spark]` | pyspark + sparkrules | Yes: with JVM layer/container |
| `[all]` | rules + spark | Large Lambda package |

**Also on PyPI (used by core):**

| Package | PyPI | Role |
|---------|------|------|
| [iceguard](https://pypi.org/project/iceguard/) | iceguard | Physical SafeWriter |
| [veridata-recon](https://pypi.org/project/veridata-recon/) | veridata-recon | VRP proofs |
| [sparkrules](https://pypi.org/project/sparkrules/) | sparkrules | DRL rules engine |
| [aws-durable-execution-sdk-python](https://pypi.org/project/aws-durable-execution-sdk-python/) | durable-sdk | Checkpoint replay |
| [pyiceberg](https://pypi.org/project/pyiceberg/) | pyiceberg | Glue REST catalog |

---

## Lambda deployment package

Build a Linux-compatible zip (includes optional SparkRules):

```bash
# Core only
./infrastructure/terraform/scripts/package_lambda.sh

# With SparkRules rules engine
SDM_EXTRAS=rules ./infrastructure/terraform/scripts/package_lambda.sh

# Rules + PySpark (large image/layer recommended)
SDM_EXTRAS=spark ./infrastructure/terraform/scripts/package_lambda.sh
```

Windows:

```powershell
$env:SDM_EXTRAS = "rules"
.\infrastructure\terraform\scripts\package_lambda.ps1
```

---

## Publish to PyPI (maintainers)

### 1. Prerequisites

```bash
pip install "serverless-data-mesh[publish]"
# PyPI account + API token: https://pypi.org/manage/account/token/
```

### 2. Build artifacts

```bash
make build
# Produces dist/serverless_data_mesh-*.whl and .tar.gz
```

### 3. Upload

```bash
python -m twine upload dist/*
```

### Windows / veridata-recon

`veridata-recon` includes Rust extensions. **Use Python 3.12+ on Linux (CI) or install the cp312 wheel.** Building from source on Windows often fails: use WSL, Docker, or rely on GitHub Actions for full test + benchmark runs.

On git tag `v*`, the workflow `.github/workflows/publish.yml` builds and publishes using **PyPI trusted publishing** (configure on pypi.org → Your project → Publishing).

```bash
git tag v0.1.0
git push origin v0.1.0
```

### Version bump checklist

1. Update `VERSION` and run `python scripts/sync_version.py --write`
2. Update `CHANGELOG.md` and `PYPI.md` if needed
3. Tag and push (`git tag v0.1.1 && git push origin v0.1.1`)
4. Verify: `pip install serverless-data-mesh==<version>`

---

## Quick verify after install

```python
import serverless_data_mesh as sdm
print(sdm.__version__)

from serverless_data_mesh import GlueCatalogConnector, DataProductContract

# Optional: requires [rules]
from serverless_data_mesh import SparkRulesConnector
```

---

## Related docs

- [SparkRules connector](sparkrules-connector.md): rules on Lambda
- [Glue connector](glue-connector.md): catalog metadata
- [Getting started](getting-started.md): full tutorial
