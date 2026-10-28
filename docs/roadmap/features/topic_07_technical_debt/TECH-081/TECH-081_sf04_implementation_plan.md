# Implementation Plan: The Layer Check Reports Clean While the Layers Are Broken [SF-04: The flow engine stands alone]
- **Feature ID**: TECH-081
- **Sub-Feature**: SF-04 — The flow engine stands alone
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf04_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-11 (engine imports nothing from handlers; `core/flow/run_state`), FR-12 (`PipelineRunner` takes
its registry from its caller), FR-13 (draft handlers get their drafters from the run's builder),
FR-14 (no `_detect`), FR-16 (`core/flow/store` its own module). AD-7, AD-8, AD-10, AD-13. No
command, option or output changes (NFR-1). Two `deprecated` edges and their ledger rows go:
`core.flow → workflows.drafting` (FR-13), `core.config.bootstrap → core.flow` (FR-16).

## Research Notes

Read 2026-10-28.

- **Engine → handlers today** (12 engine files): `run_context.RunContext` in 11 (all but
  `handover.py:9` under `TYPE_CHECKING`), `registry.StepHandlerRegistry` (`runner.py:48`),
  `results.log_step_failure` (`step_execution.py:41`), `scenario_store.scenario_store`
  (`handover.py:83`), `validation.target_dal` (`isolation.py:131`). Handlers → engine: 21 files.
- **Run-state pieces**: `handlers/run_context.py` (248 lines; imports `commons`, `core.config`;
  lazy `infrastructure.llm`, type-only `assurance.validation`); `handlers/scenario_store.py`
  (26; lazy `core.config.paths`, `engine.registered`, `workspace.store`); `log_step_failure`
  (`results.py:31`, needs only `BudgetExceededError`); `target_dal` (`validation.py:39`, uses
  `DALResolver`, `registered`, `workspace.store`); `engine/registered.py` (33, no imports from
  `specweaver`). `results._error_result` uses `engine.state` and stays in handlers.
- **`PipelineRunner.__init__`** (`runner.py:77-93`): `registry: StepHandlerRegistry | None = None`,
  then `registry or StepHandlerRegistry()`. `src` builds it at 10 sites (`interfaces/cli/run_doors.py:100`,
  `interfaces/api/v1/_llm.py:50`, `pipelines.py:68,136`, `core/flow/interfaces/cli.py:343,471`,
  `engine/runner.py:136` (passes its own), the drafting `:184`, implementation `:193`, review `:94`
  CLIs). Tests: 228 calls, 153 already pass `registry=`.
- **Drafting** (FR-13): `draft.py:138` (`Drafter`) and `:326` (`FeatureDrafter`), both lazy, both
  built only when `context.context_provider` and `context.model.llm_router` are set. The only
  `RunContext(` in `src` is `interfaces/run_setup/builder.py:98` (`build_run`); both doors use it.
  `interfaces.run_setup` does not depend on `workflows.drafting` yet; drafting reaches nothing that
  reaches `run_setup` (no loop).
- **`core/flow/store.py`** (115 lines, flow tables): users `core/config/bootstrap/db_bootstrap.py:15`,
  `handlers/artifact_lineage.py:114`.
- **`_detect`** (FR-14, AD-13): `sandbox/language/core/_detect.py`; importers `core/flow/engine/task_files.py:60`,
  four inside the sandbox, `tach.toml` exposes `language.core._detect.detect_language`; tests
  `test_detect.py`, `test_language_atom.py`; `D-INTL-08` corpus (2 mutants).
- **tach**: `specweaver.core.flow` is one module with no `[[interfaces]]`. Outside importers by
  sub-package: `engine` from 9 modules, `handlers` from 6, `store` from bootstrap (measured).
- **Refactor gate**: a call that gains `registry=` is not a path-only test change.

## Approach (pseudocode, ordered)

The order keeps NFR-2: no `deprecated` edge is ever added. FR-12 and FR-13 go first, so when CB-4
splits `core.flow` into tach modules, no wrong edge is left to re-declare.

**CB-1 — the store and the language name (FR-16, FR-14)** — kind `refactor`
1. Red: `tach.toml` registers `specweaver.core.flow.store` (`depends_on = []`), bootstrap's
   `deprecated` edge becomes plain `core.flow.store`, ledger row goes; the sandbox expose
   `language.core._detect.detect_language` becomes `language.core.detect.detect_language`.
   `test_tach_architectural_boundaries` and `test_tach_sees_every_module` go red.
2. Green: `git mv sandbox/language/core/_detect.py detect.py`; fix the 5 `src` imports, the tests,
   the `D-INTL-08` corpus. `core.flow` depends on `core.flow.store`.

**CB-2 — the caller hands the runner its registry (FR-12)** — kind `tooling`
3. Red: unit test — `PipelineRunner(pipeline, context)` with no `registry` raises `TypeError`;
   `inspect.signature` shows `registry` has no default.
4. Green: `registry: StepHandlerRegistry` keyword-only and required; `runner.py` imports it under
   `TYPE_CHECKING` only. The 9 outside `src` callers pass `StepHandlerRegistry()`; the ~75 test calls
   without one gain `registry=StepHandlerRegistry()`.

**CB-3 — the builder hands the draft handlers their drafters (FR-13)** — kind `tooling`
5. Red: drop the `core.flow → workflows.drafting` `deprecated` edge and its ledger row (tach red).
   Integration test (seam `interfaces/run_setup` → `core/flow/handlers`): a context from
   `build_run` carries drafters whose `spec`/`feature` build a `Drafter`/`FeatureDrafter`.
6. Green: `RunContext` gains `drafters: Drafters | None = None`, `Drafters` a Protocol beside it
   (`spec(**kw)`, `feature(**kw)`, each returning an object with `async draft(...)`); `build_run` sets it from a small factory in `interfaces/run_setup`; the two
   handlers call `context.drafters.spec(...)`/`.feature(...)` and draft only when it is set (same
   guard as `context_provider`). `run_setup` gains the plain edge to `workflows.drafting`. Tests that
   patch `Drafter.draft` set `drafters` on their context.

**CB-4 — the engine stands alone (FR-11)** — kind `refactor` — closes SF-04
7. Red: `tach.toml` replaces `specweaver.core.flow` with `core.flow.engine`, `core.flow.handlers`,
   `core.flow.run_state` (plus CB-1's `store`); `engine` does not depend on `handlers`; every outside
   module depends on the sub-modules it uses (measured list above). Tach red.
8. Green: `git mv` `handlers/run_context.py`, `handlers/scenario_store.py`, `engine/registered.py`
   into `core/flow/run_state/`; `log_step_failure` and `target_dal` move into it beside them; fix
   the `src` and test imports (path-only) and the corpora (`.tmp/stale.py`).
   The engine stops naming `StepHandlerRegistry` even under `TYPE_CHECKING` (tach counts it): it
   owns a port, `engine/handler_port.py`, with `HandlerLookup` (`get(action, target)`, the one call
   `step_execution.py:547` makes) and the handler shape it returns. `StepHandlerRegistry` fits it
   structurally; mypy checks every caller. The port lives in `engine`, not `run_state`, because the
   handler shape names `PipelineStep`/`StepResult`, and `run_state → engine` would make a loop.
9. Manifest `core/flow/run_state/context.yaml`, archetype `mixed` (the run's data, plus
   `target_dal` and `scenario_store`, which read through the registered project); `engine` and
   `handlers` manifests consume `run_state`; the engine's `forbids: core/flow/handlers` now holds.

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| arch | `test_tach_architectural_boundaries` | FR-11, FR-14, FR-16 | the edges/exposes change before the moves |
| unit | `PipelineRunner` without `registry` raises | FR-12 | today it builds its own |
| integration | `build_run` context carries drafters that build the real drafters | FR-13 (seam) | no `drafters` field |
| unit | draft handler drafts through `context.drafters` | FR-13 | it imports drafting |
| all | the suite | NFR-1 | — |

Mutants: `runner-builds-its-registry` (default restored → unit red); `engine-imports-handlers`
(an engine file imports `RunContext` from handlers → tach red); `handler-imports-drafting`
(`draft.py` imports `Drafter` → tach red); `builder-forgets-drafters` (`build_run` leaves it None →
integration red); `bootstrap-imports-flow` (bootstrap imports `core.flow.engine` → tach red).

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–2 | suite green; `bootstrap-imports-flow` killed; commit |
| CB-2 | steps 3–4 | suite green; `runner-builds-its-registry` killed; commit |
| CB-3 | steps 5–6 | suite green; `handler-imports-drafting`, `builder-forgets-drafters` killed; commit |
| CB-4 | steps 7–9 | suite green; `engine-imports-handlers` killed; stage and stop (closes SF-04) |

## Documentation

`docs/dev_guides/layer_isolation_and_di.md`: the run-state module, the registry and drafter
injection (design: ⬜ SF-04).

## Architecture Verification (Phase 3)

- `run_state` → `commons`, `core.config`, `workspace` (store), lazy `infrastructure.llm`,
  type-only `assurance.validation`. `engine` and `handlers` → `run_state`; `run_state` imports
  neither. No loop.
- `interfaces.run_setup` → `workflows.drafting`: drafting reaches `llm`, `workspace.context`,
  `assurance.graph`; none reaches `run_setup`.
- Two `deprecated` edges removed, none added (NFR-2).

## Audit (Phase 2) — settled

❓ **Q1 — test calls that change in CB-2 and CB-3.** FR-12 makes `registry` required, so ~75 test
calls gain `registry=StepHandlerRegistry()`; FR-13 makes 3 draft-handler test files set
`drafters`. The `refactor` gate blocks any test edit that is not a path change.
- **A:** CB-2 and CB-3 run `--kind tooling`; CB-1 and CB-4 stay `refactor`; the design's kind line
  says so.
- **B:** keep `registry` optional with a default the caller module supplies; fewer test edits, but
  the engine keeps a hidden fallback and FR-12's "every caller passes it" is not true.

The user chose A `[agreed 2026-10-28]`: CB-2 and CB-3 run `--kind tooling`.

## Consistency (Phase 5)

- Red/Blue, 2 cycles:
  - R1 (HIGH) CB-2 keeps `StepHandlerRegistry` under `TYPE_CHECKING` in `runner.py`, and tach counts
    type-only imports (`ignore_type_checking_imports = false`), so CB-4's "engine does not depend on
    handlers" would stay red. Blue: CB-4 adds the engine-owned port `HandlerLookup` (step 8).
  - R2 (MEDIUM) `drafters: Any` hides a wrong call from mypy. Blue: a `Drafters` Protocol in
    `run_context.py` (step 6); it names no drafting type.
  - R3 (MEDIUM) a port in `run_state` would name engine types and make a loop. Blue: the port sits in
    `engine` (step 8); `run_state` imports neither `engine` nor `handlers`.
  - R4 (LOW) tests that patch `draft.Drafter` lose their target. Blue: they set `context.drafters`
    to a double (step 6); CB-3 is `tooling`.
  - Cycle 2: no new finding.
