# Walkthrough: TECH-081 SF-04 — The flow engine stands alone

Plan: [TECH-081_sf04_implementation_plan.md](TECH-081_sf04_implementation_plan.md).

## CB-1 — the store and the language name (FR-16, FR-14)

### What changed

- `tach.toml` registers `specweaver.core.flow.store` (`depends_on = ["specweaver.core.config"]`: the
  tables use `StrictISODateTime`; the plan said `[]`). Bootstrap's owed edge to all of `core.flow` is
  now the plain edge to `core.flow.store`; the ledger row is gone.
- `sandbox/language/core/_detect.py` → `detect.py`; five `src` imports, two tests, the tach expose and
  `language_support_guide.md` follow.
- Manifests: bootstrap consumes `core/flow/store`; `core/flow` consumes it.
- Three mutants re-pinned (`D-INTL-08` ×2, `TECH-078`): only the import line inside their symbols
  changed; every anchor still matches.

### Red first

Registering the module and renaming the expose first turned `test_tach_architectural_boundaries`,
`test_tach_interfaces_map_to_valid_namespaces` and `test_every_allowed_dependency_is_declared` red.

### Proof

Mutant `bootstrap-imports-flow` (`get_db` imports `core.flow.engine.models`): OBJECTED.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) `core.flow` still holds `store.py` on disk while tach treats it as its own module.
  Blue: tach resolves the most specific module path; `core.flow` declares the edge to it, and the
  bootstrap mutant proves the rest of `core.flow` stays out of reach.
- R2 (LOW) old plans cite `_detect.py`. Blue: dated plan evidence, not live guides; the live guide
  is fixed.
- Cycle 2: no new finding.

## CB-2 — the caller hands the runner its registry (FR-12)

### What changed

- `PipelineRunner(..., *, registry: StepHandlerRegistry, ...)`: required, keyword-only; the engine no
  longer builds one. `runner.py` names the class under `TYPE_CHECKING` only (CB-4 replaces it with an
  engine-owned port).
- The 9 outside `src` callers pass `StepHandlerRegistry()`: `run_doors`, the API `_llm` and
  `pipelines` (2), `core/flow/interfaces/cli.py` (2), the drafting, implementation and review CLIs.
- 36 test calls in 18 files gain `registry=StepHandlerRegistry()` (an AST script found every call
  without one); two files patch `StepHandlerRegistry.get` at its home, not through `runner`.
- 49 mutants in 12 corpora re-pinned: their symbols are the callers above, and only the runner call
  changed. Anchors checked inside the symbol; three anchors sit on a decorator or a last line, which
  the symbol check cannot see, so those were checked as unique in the file.

### Red first

`test_runner_takes_its_registry.py`: no default and a runner built without a registry both failed
before the change.

### Proof

Mutant `runner-builds-its-registry` (`__init__` builds its own registry again): OBJECTED.

### Gate notes

Kind `tooling` `[agreed 2026-10-28]`: test calls gained an argument.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) nine callers each write `StepHandlerRegistry()`. Blue: the caller is the composition
  root by design (AD-7); SF-05 folds the CLI doors.
- R2 (MEDIUM) the runner still names the registry type. Blue: CB-4 swaps it for `HandlerLookup`.
- R3 (LOW) tests patch `StepHandlerRegistry.get` on the class. Blue: as before; only the path changed.
- Cycle 2: no new finding.

## CB-3 — the builder hands the draft handlers their drafters (FR-13)

### What changed

- `tach.toml` and the ledger lost the owed `core.flow → workflows.drafting` edge (two rows: the owed
  table and the violations table). `core/flow`'s `forbids: workflows/drafting` now holds.
- `run_context.py`: a `Drafters` Protocol (`spec(**kw)`, `feature(**kw)`); `ModelAccess.drafters`
  holds it. It sits in `ModelAccess`, not on `RunContext`: `RunContext` is at the 15-field limit
  (`test_check_class_health`), and the drafters are how a run's model drafts.
- `interfaces/run_setup/drafters.py`: `WorkflowDrafters` builds `Drafter` / `FeatureDrafter`.
  `build_run` sets it on every run; `run_setup` gains the plain edge to `workflows.drafting`.
- `draft.py`: one guard, `_can_draft` (drafters, a provider, a router); both handlers build their
  drafter through `context.model.drafters`. No drafting import is left.
- Six older test files that set a provider now also give the run `WorkflowDrafters()`; their patches
  of `Drafter` still apply, because the factory imports at call time.
- Four mutants re-pinned (`C-FLOW-13`, `TECH-077` ×3): `build_run` gained one argument.

### Red first

`test_draft_uses_injected_drafters.py` (5 tests) and
`test_build_run.py::test_a_run_gets_drafters_that_build_the_real_drafters` failed before the change;
removing the edge turned `test_tach_architectural_boundaries` red.

### Proof

Mutants `handler-imports-drafting` and `builder-forgets-drafters`: OBJECTED.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) every run gets drafters, even one with no model. Blue: a stateless object; `_can_draft`
  also needs a router and a provider, so a headless run still parks.
- R2 (MEDIUM) `assert context.model.drafters is not None` in `src`. Blue: type narrowing after the
  `_can_draft` guard, the same idiom as the other narrowing asserts in `src`.
- R3 (MEDIUM) `Drafters` returns `Any`. Blue: naming `Drafter` would import drafting; the handler only
  calls `draft`, and the seam test checks the real classes come back.
- R4 (LOW) `ModelAccess` now allows arbitrary types. Blue: needed for a Protocol field; `RunContext`
  already does.
- Cycle 2: no new finding.

## CB-4 — the engine stands alone (FR-11) — closes SF-04

### What changed

- `tach.toml`: `specweaver.core.flow` is gone. In its place: `core.flow.run_state`, `core.flow.engine`,
  `core.flow.handlers` (plus CB-1's `core.flow.store`). `engine` depends on `run_state`, never on
  `handlers`; `run_state` on neither. Every edge was pruned with tach's unused-dependency report, so
  each module lists only what it imports.
- Moved to `core/flow/run_state/`: `run_context.py`, `scenario_store.py` (from `handlers`),
  `registered.py` (from `engine`); `log_step_failure` → `failures.py` (out of `handlers/results.py`),
  `target_dal` → `dal.py` (out of `handlers/validation.py`, which imports it back for its own use).
- `engine/handler_port.py`: `HandlerLookup` and `StepRunner`, the engine's own port; `PipelineRunner`
  types `registry` with it. mypy checks that each caller's `StepHandlerRegistry` fits.
- Manifests: new `run_state` (`mixed`, forbids `engine` and `handlers`); `engine` consumes
  `run_state` and its `forbids: core/flow/handlers` now holds (the owed comment is gone); `handlers`
  and `core/flow/interfaces` consume what tach allows them.
- Imports re-pointed across `src` and tests (path-only); three tests moved to mirror `run_state`
  (`test_registered.py`, `test_run_context_session_fields.py`, `test_scenario_store.py`);
  `test_check_class_health` reads `run_context.py` at its new home.
- `layer_isolation_and_di.md`: "The flow engine knows no handler".
- Mutants: `B-FLOW-07 no-default-dal-fallback` re-pointed to `run_state/dal.py` and re-run
  (OBJECTED); the rest re-pinned after their anchors were checked.

### Red first

Splitting `core.flow` in `tach.toml` first gave 15 `[FAIL]` lines, every one an engine file reaching
`handlers`.

### Proof

Mutant `engine-imports-handlers` (`isolation.py` takes `target_dal` from `handlers.validation`):
OBJECTED.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) `handlers/validation.py` still imports `target_dal`, so a test may reach it there.
  Blue: `validation` uses it; the engine takes it from `run_state`, and the mutant proves the old
  route is refused.
- R2 (MEDIUM) `handlers` keeps 18 edges. Blue: tach-measured exact; SF-06 and SF-07 shrink the
  assurance ones.
- R3 (MEDIUM) `run_state` is `mixed`: `target_dal` and `scenario_store` read the workspace store.
  Blue: lazy, read-only, and the reason they are shared (design FR-11).
- R4 (LOW) `core/flow/context.yaml` remains with no tach module. Blue: it names the package; the
  manifest tests judge only tach modules.
- Cycle 2: no new finding.
