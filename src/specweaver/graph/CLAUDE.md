# Graph

Two graphs, one library (`networkx`, pinned 3.6.1), kept apart (ADR-006 decision 4):

- the **code graph**: what the code really is, extracted from source and stored in `graph.db`;
- the **module graph**: what the `context.yaml` files declare, built in memory for each run.

## Modules

- **core/** — the code graph. `builder/` extracts it from the AST adapters, `engine/` holds it
  (`InMemoryGraphEngine`), `store/` persists it to `graph.db` through `infrastructure/database`.
- **topology/** — the module graph (`TopologyGraph`, its `TopologyEngine`): dependencies, impact,
  cycles, the selectors that pick related modules for a prompt (`contexts_for`), and the hashes
  that say which modules changed. Pure logic; once built, the graph is frozen.
- **lineage/** — artifact lineage: which generated file came from which spec. `engine.py` walks the
  tree, `protocol.py` declares the repository it reads, `store/` writes `flow_artifact_events`
  (its one writer), `scanner.py` finds files with no lineage tag.
- **interfaces/** — the `sw graph build` and `sw lineage tag|tree` commands.

## Conventions

- One depth limit for both graphs: `MAX_NEIGHBOURHOOD_DEPTH` in `core/engine/models.py`.
- The module graph takes no write after it is built (`FrozenGraphError`).
- Nothing in `graph` imports `sandbox`.

## Test Commands

```bash
python -m pytest tests/unit/graph/ -v --tb=short
python -m pytest tests/integration/graph/ -v --tb=short
```

<!-- Last verified: 2026-11-08 -->
