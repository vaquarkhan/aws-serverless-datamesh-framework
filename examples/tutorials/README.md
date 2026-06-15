# Tutorials

Runnable companions to [docs/getting-started.md](../../docs/getting-started.md).

## Interactive walkthrough

Runs each developer step locally (no AWS required for steps 1–9):

```bash
# From repo root (Python 3.12+):
python examples/tutorials/walkthrough.py

# Run a single step:
python examples/tutorials/walkthrough.py --step 7

# List steps:
python examples/tutorials/walkthrough.py --list
```

## Steps covered

| Step | Topic |
|------|-------|
| 1 | Install & import |
| 2 | Domain transaction boundary |
| 3 | Workload definition |
| 4 | Source reader |
| 5 | Batch writer |
| 6 | MeshSettings |
| 7 | VRP verification (requires `veridata-recon`) |
| 8 | Glue REST catalog adapter |
| 9 | Coordinator composition |
| 10 | Lambda handler |
| 11 | SAM deploy |
| 12 | Outcome interpretation |

## Production example

See [../domain_writer/README.md](../domain_writer/README.md) for the deployable Lambda handler.
