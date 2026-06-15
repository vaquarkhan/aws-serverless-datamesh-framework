# Contributing

## Development setup

**Requires Python 3.12+** (veridata-recon ships cp312 wheels; Windows dev may need WSL or CI for Rust-backed deps).

```bash
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
make install
make test
make benchmark          # consumer safety: corrupt data never PASSes
make walkthrough        # interactive tutorial (no AWS)
```

## Governance tooling

| Tool | Purpose |
|------|---------|
| `VERSION` + `scripts/sync_version.py` | Single source of truth for package version |
| `.pre-commit-config.yaml` | Ruff, whitespace, version sync check |
| `.github/dependabot.yml` | Weekly pip + GitHub Actions updates |
| `eval/validate_then_commit_benchmark.py` | Quantitative validate-then-commit proof |
| `SECURITY.md` | Vulnerability reporting |

```bash
make pre-commit         # install hooks
make version-check      # CI: verify VERSION sync
```

## Code style

- Python 3.12+ with full type annotations
- `ruff` for lint + format (`make lint`, `make format`)
- Keep changes scoped to the task; match existing package layout

## Project layout

```
src/serverless_data_mesh/
  catalog/          # GlueCatalogConnector (Glue Iceberg REST metadata)
  orchestration/    # IceGuard + durable coordinator
  verification/     # veridata-recon VRP hooks
  rules/            # SparkRules connector
  types/            # Domain contracts
tests/unit/         # Unit tests
tests/eval/         # Benchmark integration tests
eval/               # Consumer safety benchmark script
examples/           # Lambda reference implementations
infrastructure/     # Terraform + SAM
docs/               # Architecture and deployment guides
```

## Pull requests

1. Branch from `main`
2. Add or update unit tests; run `make benchmark` if touching VRP gate
3. Ensure `make lint`, `make test`, and `make version-check` pass
4. Update `VERSION` (if release) and `CHANGELOG.md` for user-visible changes
5. Run `make pre-commit` before pushing

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting.
