# Multi-domain example: Orders + Payments

Demonstrates **cross-domain atomicity** under the Vaquar Pattern: two domain writers
share a mesh transaction; if **payments** VRP fails, the mesh outcome is
`verification_failed` and consumers do not receive a partial publish.

## Layout

```
multi-domain-orders-payments/
├── coordinator_config.yaml   # Mesh transaction declaration
├── domains/
│   ├── orders/handler.py     # Orders domain writer
│   └── payments/handler.py   # Payments domain writer
├── test_atomicity.py         # Local demo (no AWS)
└── README.md
```

## Run locally (no AWS)

```bash
python examples/multi-domain-orders-payments/test_atomicity.py
```

**Scenario A:** Both domains clean → `mesh_outcome=committed`

**Scenario B:** Payments corrupt row → `mesh_outcome=verification_failed`

## Production wiring

In AWS, replace local runtime with:

1. Step Functions **Parallel** state invoking both domain Lambdas
2. **Leader evaluate** state: commit mesh snapshot only if all domains `committed`
3. On any `verification_failed`: abort metadata, emit alarm, retain Steward proofs

See [data-mesh-end-to-end.md](../../docs/data-mesh-end-to-end.md) for three-account IAM.

## Related

- [Vaquar Pattern](../../docs/vaquar-pattern.md)
- [Mesh Orchestrator roadmap](../../docs/data-mesh-patterns.md) (Step Functions Map fan-out)
