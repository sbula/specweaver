# Graph (In-Memory Knowledge Graph)

NetworkX-based knowledge graph engine. Builds, queries, and traverses spec/code relationships.

## Modules

- **core/** — Graph data models, builder, query engine. Uses `networkx` (pinned 3.6.1).
- **lineage/** — Change lineage tracking. Tracks how specs evolve over time. Zero external dependencies.
- **topology/** — Graph topology analysis (cycles, paths, centrality).
- **interfaces/** — CLI bindings for graph commands (depends on `interfaces.cli`).

## Conventions

- Graph is in-memory only. No persistence layer — rebuilt from workspace on each session.
- All graph operations return pure data structures (dicts, lists, dataclasses). No side effects.
- Lineage module is fully isolated — depends on NOTHING else.

## Test Commands

```bash
python -m pytest tests/unit/graph/ -v --tb=short
python -m pytest tests/integration/graph/ -v --tb=short
```

<!-- Last verified: 2026-07-12 -->
