# Contributing

## Development setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
make install
make test
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
  types/            # Domain contracts
tests/unit/         # Unit tests
examples/           # Lambda reference implementations
infrastructure/sam/ # AWS SAM template
docs/               # Architecture and deployment guides
```

## Pull requests

1. Branch from `develop`
2. Add or update unit tests
3. Ensure `make lint` and `make test` pass
4. Update `CHANGELOG.md` for user-visible changes
