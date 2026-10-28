# Walkthrough: TECH-081 SF-03 — The sandbox sits below the workflows

Plan: [TECH-081_sf03_implementation_plan.md](TECH-081_sf03_implementation_plan.md).

## CB-1 — `commons` is pure (FR-9)

### What changed

- `commons/prepare_plan.py` and `commons/tooling_sources.py` moved whole to `workspace/project/`
  `[agreed 2026-10-28]`. The plan first said `sandbox/execution` with the `sw sandbox` CLI moved
  into the sandbox (AD-4); in dev that broke `TECH-002` FR-6 (`interfaces/` may not import the
  sandbox, `tests/unit/test_layer_import_isolation.py`). The user chose `workspace/project`: it
  already does project discovery, and the router stays in the shell. AD-4 is dropped.
- `tach.toml`: `sandbox` and `core.flow` depend on `workspace.project` (plain edges); its interfaces
  expose the six names they use. `_DEFAULT_GROUP` and `_LAST_RESORT_RUNNER` crossed a module
  boundary, so they are public now (`DEFAULT_GROUP`, `LAST_RESORT_RUNNER`).
- `commons` is `pure-logic`. `sandbox` and `core/flow` manifests consume `workspace/project`.
- The three unit test files moved to `tests/unit/workspace/project/`; the `TECH-031` corpus points
  at the new paths (0 stale mutants).

### Red first

`tests/unit/test_pure_modules_do_no_io.py` failed on `prepare_plan.py` and `tooling_sources.py`
before the move.

### Proof

Mutant `commons-reads-again` (`commons/json.py` `load` opens a file): OBJECTED.

### Gate notes

Full suite 11822 passed, 9 skipped; `tests.py cb --kind tooling`, `quality.py cb`, `doc`, `tach check`
green. Ruff sorted two moved imports.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) `sandbox → workspace.project` lets the low sandbox reach `assurance.graph` and `graph`
  transitively. Blue: measured, no loop; the sandbox uses only the prepare plan. SF-08's loop ban
  keeps it that way.
- R2 (MEDIUM) renaming two constants is not a pure move. Blue: names only; every user changed in the
  same diff; the suite is green.
- R3 (LOW) `TECH-079`'s design cites `commons/prepare_plan.py` lines. Blue: dated filing evidence
  for an audit ticket, re-measured before it is planned.
- Cycle 2: no new finding.
