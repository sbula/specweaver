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

## CB-2 — the CLI hands the builder its service name (FR-17) — closes SF-06

### What changed

- `GraphOrchestrator.build_target(target_path, project_path, *, service_name)`: the name is
  required and keyword-only; the builder reads no topology.
- `sw graph build` (`graph/interfaces/cli.py`) reads the name with `load_topology` and
  `resolve_service_name`, inside its existing `try`, and passes it in.
- `tach.toml` and the ledger lost the last owed edge, `graph → assurance.graph`, and the row for
  the lazy import. `graph.interfaces` depends on `assurance.graph` (plain edge; its manifest
  consumes it). `graph` now depends only on `workspace.ast.adapters`.
- `test_graph_service_name.py` runs `sw graph build` through the shell app, so `TECH-004` FR-6 is
  still proven end to end. The other test calls pass `service_name=` (kind `tooling`,
  `[agreed 2026-10-28]`). `test_declared_imports.py` no longer names the crossing as open.

### Red first

Deleting the edge turned `tach check` red on `orchestrator.py:255`. The two new unit tests (the
name reaches the repository; the name is required) failed before the signature changed.

### Proof

Mutants `graph-imports-assurance` and `llm-imports-topology` (tach), `build-ignores-name`
(`TECH-004`, re-pointed to the CLI's `build`), `ledger-cites-moved-file` (re-anchored on the
`topology.py` row): all OBJECTED. 0 stale mutants.

### Gate notes

Full suite 11834 passed, 9 skipped; `tests.py cb --kind tooling`, `quality.py cb`, `doc`,
`check_proof_tier.py`, `tach check` green. The doc gate first failed on
`Proves: A FR-x, B FR-y` on one line: the parser takes one story per tag, so each story has its own
`Proves:` line.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) a broken `context.yaml` now fails in the CLI, not in the builder. Blue: the lookup is
  inside the same `try`; `test_a_broken_topology_is_reported_not_raised` holds the message and exit
  code 1.
- R2 (MEDIUM) the CLI unit test now reads the topology of the current directory. Blue: it patches
  `load_topology`; no real files are read.
- R3 (LOW) the extraction tests pass `service_name="default"` by hand. Blue: that is what they
  stored before (no root `context.yaml`); their assertions use it.
- Cycle 2: no new finding.
