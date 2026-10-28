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

## CB-2 — the sandbox imports no workflow (FR-10) — closes SF-03

### What changed

- `tach.toml` and the ledger lost four owed edges: `core.flow → workflows.evaluators`,
  `sandbox → workflows.scenarios`, `sandbox → workflows.evaluators`, `sandbox → core.flow`.
- `workflows/scenarios/scenario_models.py` → `commons/scenario_models.py` (AD-5).
- `ScenarioConverter` moved into `sandbox/language/core/python/scenario_converter.py` beside
  `PythonScenarioConverter`, which now calls it directly; the lazy import "to break a circular import"
  and `workflows/scenarios/scenario_converter.py` are gone (NFR-3).
- `workflows/evaluators/loader.py` → `sandbox/evaluator_schemas.py` (AD-6). The YAML stays and is
  read as a package resource; `workflows/evaluators` is `data` with no `depends_on`.
- `sandbox/security.py` types `from_run_context` with `BoundaryContext`, a Protocol of its own
  (AD-14).
- Tests moved to mirror the new homes; three proof citations (`US-24.md`, the integration proof
  matrix, `TECH-031` design) point at the new paths. Ten mutants in five corpora were re-pinned:
  only import lines inside their symbols changed, every anchor still matches.
- The duplication baseline was re-frozen: the same two converter clone pairs, re-keyed because an
  import line inside them changed.

### Red first

Deleting the four edges first turned `test_tach_architectural_boundaries` red; the moves turned it
green.

### Proof

Mutants `sandbox-imports-workflows` and `security-imports-runcontext`: OBJECTED.
`flow-imports-evaluators` came back SILENT and was dropped: `workflows/evaluators` holds no Python
now, so there is nothing an import could reach.

### Gate notes

Full suite 11822 passed, 9 skipped; `quality.py cb`, `doc`, `tach check` green. Kind `tooling`, not
`refactor`: ruff merged two imports in `test_scenario_converters.py` into one, which the refactor
rule cannot read as path-only (plan R4).

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) `evaluator_schemas.py` still names `specweaver.workflows.evaluators.frameworks` as a
  string, a dependency tach cannot see. Blue: it is data, not code (AD-6); `test_framework_schemas`
  fails if the package moves.
- R2 (MEDIUM) `BoundaryContext` duplicates two fields of `RunContext`. Blue: a structural type, not
  a copy; mypy checks `review.py` passes a `RunContext`.
- R3 (LOW) `tests/unit/workflows/scenarios/` still holds the generator tests. Blue: the generator
  stayed in `workflows/scenarios`.
- Cycle 2: no new finding.
