# Walkthrough: TECH-081 SF-06 — Graph and assurance in one direction

Plan: [TECH-081_sf06_implementation_plan.md](TECH-081_sf06_implementation_plan.md).

## CB-1 — `TopologyContext` to `commons` (AD-5)

### What changed

- `TopologyContext` moved whole from `assurance/graph/topology.py` to `commons/topology_context.py`;
  `topology.py` imports it to build contexts. `commons` exposes it.
- `infrastructure/llm/prompt/adders.py`, `workflows/drafting/_base.py`,
  `workflows/planning/decomposer.py` and `assurance/graph/loader.py` import the new path; so do the
  11 test files (path-only).
- `tach.toml` and the ledger lost three owed edges: `infrastructure.llm`, `workflows.drafting` and
  `workflows.planning` → `assurance.graph`.
- `docs/dev_guides/pluggable_contexts.md` cites the new path.

### Red first

Deleting the three edges first turned `tach check` red on the three type-only imports.

### Proof

Mutant `llm-imports-topology` (`add_topology` imports from `assurance.graph` again): OBJECTED.
No file imports `TopologyContext` from the old path (grep).

### Gate notes

Full suite 11832 passed, 9 skipped; `tests.py cb --kind refactor`, `quality.py cb`, `doc`,
`tach check` green. 0 stale mutants.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) `topology.py` still imports the class, so `assurance.graph.topology.TopologyContext`
  resolves and a new caller could use it. Blue: it is a use, not a shim; tach marks any module that
  takes that path without an `assurance.graph` edge.
- R2 (LOW) the `commons` purpose says "logic-free", and the class renders a prompt string. Blue: a
  pure string method on frozen data, like `scenario_models`; no I/O, `test_pure_modules_do_no_io`
  green.
- Cycle 2: no new finding.
