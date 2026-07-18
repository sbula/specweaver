# Implementation Plan: Autonomous Implementation Integration — SF-01: Generation → QA Test Loop

- **Feature ID**: INT-US-03
- **Sub-Feature**: SF-01 — Generation → QA Test Loop
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_sf01_implementation_plan.md
- **Status**: APPROVED — approved by Steve Bula on 2026-07-17. Audit Q1–Q6 all resolved to option **(a)**.

## Scope (from the Design Document)

Extend the inline `implement_spec` pipeline so generated code + tests are validated **in-pipeline**:
append a `run_tests` step (`VALIDATE`/`TESTS`, coverage) and a `validate_code` step (`VALIDATE`/`CODE`,
C01–C08), resolve QA targets to this run's generated files, add the loop-back-on-fail gate, and report
QA results inline. **FRs owned: FR-1, FR-3, FR-4, FR-6, FR-7.** (FR-2 lint-fix = SF-02; FR-5 isolation
+ FR-8 e2e proof = SF-03.)

**Out of scope for SF-01:** worktree isolation / `enforce_isolation` threading (SF-03), the `lint_fix`
step (SF-02), Podman/containers (whole feature — excluded). SF-01 runs QA in **host mode**; it must not
regress the default-off isolation behavior (NFR-2).

---

## Research Notes (Phase 0)

Findings that constrain or change a technical decision in this plan. All citations verified against
the current tree.

1. **`sw implement` builds an inline 2-step pipeline** (`workflows/implementation/interfaces/cli.py:120-135`):
   `generate_code` (`GENERATE`/`CODE`) + `generate_tests` (`GENERATE`/`TESTS`), run via `PipelineRunner`
   (`cli.py:150-151`). Its `RunContext` (`cli.py:137-147`) sets `config`/`llm`/`db`/`topology` but **not**
   `output_dir` and **not** `enforce_isolation`. It ends by printing a stale "Next steps: `sw check
   --level=code …`" message (`cli.py:165-170`). This is the only file SF-01 edits (plus one handler — see #4).

2. **Step/gate model is Pydantic, constructed in Python** (`core/flow/engine/models.py`):
   `PipelineStep(name, action: StepAction, target: StepTarget, params: dict, gate: GateDefinition|None,
   router, description, use_worktree: bool|None)` (`models.py:202-223`).
   `GateDefinition(type=GateType.AUTO, condition=GateCondition, on_fail=OnFailAction, loop_target: str|None,
   max_retries: int=3)` (`models.py:145-161`). Enums: `OnFailAction.{ABORT,RETRY,LOOP_BACK,CONTINUE}`,
   `GateCondition.{ALL_PASSED,ACCEPTED,COMPLETED}` (`models.py:78-84`, `70-75`).
   `(VALIDATE,TESTS)`, `(VALIDATE,CODE)`, `(LINT_FIX,CODE)` are all in `VALID_STEP_COMBINATIONS`
   (`models.py:104-137`). `PipelineDefinition.max_total_loops` defaults to 20 (`models.py:248`) — the
   backstop against runaway loop-backs.

3. **`run_tests` target resolution honors `params["target"]`** (`ValidateTestsHandler`,
   `core/flow/handlers/validation.py:335-401`): reads `step.params.get("target")`; passes `target`
   (relative to the atom `cwd`) to `QARunnerAtom.run({"intent":"run_tests", ...})`. `cwd = context.execution_root
   or context.project_path` (`validation.py:403-415`). `_resolve_targets` returns `[target]` **unless**
   `target ∈ {".", "", "src", "src/", "tests", "tests/"}` **and** `context.stale_nodes is not None`
   (`validation.py:417-421`). Exports `{passed, failed, errors, skipped, total, duration_seconds,
   coverage_pct, failures[]}`.
   → **FR-4 for tests is trivial:** set `params["target"] = "tests/test_<stem>.py"` (a specific file, not in
   the short-circuit set) → runs exactly that file.

4. **`validate_code` does NOT honor `target`** — it locates code by `context.output_dir.glob("*.py")[0]`
   (`ValidateCodeHandler._find_code_path`, `validation.py:255-261`), returning **None** when `output_dir` is
   unset (as in `sw implement`), and an **arbitrary first file** when `output_dir` points at a multi-file dir.
   The generate handlers write code to `context.output_dir or project_path/"src"` and tests to
   `context.output_dir or project_path/"tests"` (`generation.py:111-112`, `217-218`) — so a single
   `output_dir` cannot both (a) keep code in `src/` + tests in `tests/` and (b) point `validate_code` at one
   file. **This is the SF-01 crux (Audit Q1).** Recommended fix: a **minimal, backward-compatible**
   enhancement to `_find_code_path` to honor `step.params.get("target")` (resolved against `project_path`)
   before falling back to the existing `output_dir` glob — ~4 lines, no behavior change for callers that
   don't set `target`. This one edit is in `core/flow/handlers/validation.py`, i.e. **outside**
   `workflows/implementation` (the design assumed in-module-only) → surfaced for sign-off.

5. **Static QA is intentionally project-root-bound** (dev guide `pipeline_engine_guide.md §7`, INT-US-09):
   only the *execution* handlers (`run_tests`/pytest, `bash`) rebind cwd to the worktree; `validate_code`
   and `lint_fix` (ruff) "parse but never execute" and stay project-root-bound. → In host mode (SF-01) this
   is moot; it matters for SF-03, and it means `validate_code`/`lint_fix` will read the generated file at the
   **real** `src/<stem>.py` regardless of isolation, so the #4 target fix is the correct mechanism for both
   host and isolated modes.

6. **`stale_nodes` short-circuit hazard** (`pipeline_engine_guide.md §9`): if `context.stale_nodes == []`
   (empty list, not None), `ValidateTestsHandler` returns a "pristine" `SUCCESS` **without running pytest**.
   The implement `RunContext` leaves `stale_nodes` unset (None) → no short-circuit → QA actually runs. SF-01
   MUST NOT set `stale_nodes` to an empty list (would produce a vacuous pass). (Documented guard, not a code change.)

7. **Loop-back precedent** (`workflows/pipelines/new_feature.yaml:50-62`): `run_tests` gates
   `on_fail: loop_back → generate_code, max_retries: 2, condition: all_passed`. SF-01 replicates this shape
   in Python for FR-6. `validate_code` in `new_feature.yaml` uses `on_fail: abort`; SF-01 deliberately uses
   `on_fail: continue` instead (report-only), so a C01–C08 miss surfaces in the report (FR-7) without killing
   an otherwise-successful autonomous run (Red/Blue finding from the design).

8. **Existing test impact** (`tests/integration/interfaces/cli/test_cli_implement.py`): current tests mock
   `create_llm_adapter`, return trivial LLM text, and assert `exit_code == 0` + "Implementation complete" +
   files exist (`test_implement_generates_files`, `test_implement_spec_suffix_removal`, `test_full_pipeline`).
   Appending a **real** `run_tests`/`validate_code` step changes behavior: mock-generated tests won't pass, so
   the run would fail/exit-1 and the assertions break. → SF-01 test plan must (a) mock/stub `QARunnerAtom`
   (and `ValidateCodeHandler`) at unit/integration tier so these tests assert wiring + reporting deterministically,
   and (b) real QA execution is proven only at the SF-03 e2e tier. Test convention: `typer.testing.CliRunner`,
   `_make_mock_adapter`, `_scaffold_project` via `sw init` (see the file).

9. **Module boundary** (`workflows/implementation/context.yaml`): `archetype: orchestrator`,
   `consumes: [llm, config, validation]`, `forbids: []`. `cli.py` already imports the flow symbols
   (`StepAction`, `StepTarget`, `PipelineStep`, `PipelineDefinition`, `RunContext`, `PipelineRunner`).
   Adding `GateDefinition`/`GateType`/`GateCondition`/`OnFailAction` imports from the same
   `core.flow.engine.models` module introduces **no new cross-layer dependency**. `tach`/`ruff`/`mypy --strict`
   must stay green (NFR-3).

### External Dependencies (Phase 0 Track B)
No new external tool. pytest + ruff already invoked by the pre-existing `QARunnerAtom`. No `pyproject.toml`
change. No version risk.

---

## Implementation Approach

> Pseudocode / step-lists and signatures only — the `dev` skill writes the real code test-first.

### Change 1 — Extend the inline pipeline (FR-1, FR-3, FR-6) · `cli.py`
Append two steps after `generate_tests` in the `implement_spec` `PipelineDefinition`:

- `run_tests` — `PipelineStep(action=VALIDATE, target=TESTS)`, with:
  - `params = {"target": "tests/test_<stem>.py", "kind": "unit", "coverage": True, "coverage_threshold": <from settings, default 70>}`
  - `gate = GateDefinition(type=AUTO, condition=ALL_PASSED, on_fail=LOOP_BACK, loop_target="generate_code", max_retries=2)`
- `validate_code` — `PipelineStep(action=VALIDATE, target=CODE)`, with:
  - `params = {"target": "src/<stem>.py"}`
  - `gate = GateDefinition(type=AUTO, condition=ALL_PASSED, on_fail=CONTINUE)`  # report-only, never abort

`<stem>` is the already-computed `spec_path.stem.removesuffix("_spec")` (`cli.py:99`). Targets are
**relative** (atom cwd = project root in host mode). Leave `use_worktree` unset (`None`) and do **not** set
`output_dir`/`enforce_isolation` — that is SF-03. Keep the two generate steps unchanged.

### Change 2 — Teach `validate_code` to honor an explicit target (FR-3, FR-4) · `validation.py`
Enhance `ValidateCodeHandler._find_code_path(step, context)` with an ordered resolution:
1. if `step.params.get("target")` set → resolve against `context.project_path`; return it if it exists.
2. else fall back to the **existing** `context.output_dir.glob("*.py")[0]` behavior (unchanged for all
   current callers — none set `target` on a validate/code step today; verified against `new_feature.yaml`
   and the validation pipelines).
Backward-compatible; no signature change; no new import.

### Change 3 — Inline QA reporting; drop the stale message (FR-7) · `cli.py`
Replace the post-run `step_records` loop + "Next steps" block (`cli.py:157-170`) so it, per step:
- `generate_*`: print `generated_path` (as today).
- `run_tests`: read `record.result.output` → print pass/fail counts + `coverage_pct`.
- `validate_code`: read `record.result.output` → print `passed/failed` + any failed `rule_id`s.
- Set the process exit: non-zero if the final run status is not `completed` **or** `run_tests` ultimately
  failed after retries (FR-6/FR-7) — i.e. `sw implement` now reflects QA outcome, a deliberate behavior
  change (Audit Q3). `validate_code` failures are report-only and do **not** force exit-1 (its gate is
  `CONTINUE`).

### Files to modify
| File | Change | FRs |
|------|--------|-----|
| `src/specweaver/workflows/implementation/interfaces/cli.py` | Append `run_tests` + `validate_code` steps w/ gates + params; rewrite reporting/exit; new imports (`GateDefinition`,`GateType`,`GateCondition`,`OnFailAction`) | FR-1, FR-3, FR-4, FR-6, FR-7 |
| `src/specweaver/core/flow/handlers/validation.py` | `ValidateCodeHandler._find_code_path`: honor `params["target"]`, fallback to existing glob | FR-3, FR-4 |
| `tests/integration/interfaces/cli/test_cli_implement.py` | Update existing tests to stub QA; add wiring/reporting/loop-back/exit tests | all |
| `tests/unit/core/flow/handlers/…validate_code…` | Unit test for the new target-resolution branch | FR-3, FR-4 |

No new files, no new module, no DB migration, no YAML pipeline file (inline pipeline stays inline per AD-1).

---

## Test Plan (4 Adversarial Buckets — per `tests/CLAUDE.md`)

**Unit — pipeline construction** (no LLM, no pytest exec):
- Happy: `implement` builds a pipeline whose steps are `[generate_code, generate_tests, run_tests, validate_code]`; `run_tests` has the loop-back gate (`loop_target="generate_code"`, `max_retries=2`); `validate_code` gate is `CONTINUE`; targets are `tests/test_<stem>.py` / `src/<stem>.py`.
- Boundary: spec name with `_spec` suffix / nested/odd stem → correct relative targets.

**Unit — `ValidateCodeHandler._find_code_path`:**
- Happy: `params["target"]="src/x.py"` (exists) → returns that path.
- Boundary/Hostile: `target` missing → falls back to `output_dir` glob (unchanged); `target` points outside project / nonexistent → returns None (→ handler's existing "No code file found" path); path-traversal `../` string → not resolved outside project.

**Integration — `test_cli_implement.py` (QA atom stubbed):**
- Happy: stub `QARunnerAtom.run` → tests pass + coverage ≥ threshold; `validate_code` stubbed pass → `exit_code==0`, report shows pass counts + coverage.
- Graceful degradation: stub `run_tests` → fail twice → loop-back retries exhausted → `exit_code==1`, report shows failure; `validate_code` fails but gate `CONTINUE` → run still completes, failure reported, does not alone force exit-1.
- Backward-compat: the three existing tests updated to the stubbed-QA world still assert files created + "Implementation complete".

**Deferred to SF-03 (documented, not silently skipped):** real pytest execution + worktree-bounded proof (FR-8). SF-01 asserts wiring/reporting only; it does not run real pytest in CI.

---

## Audit (Phase 2) — RESOLVED (all → option (a), approved 2026-07-17)

| # | Question | Options | Proposal | Severity |
|---|----------|---------|----------|----------|
| Q1 | `validate_code` can't target the specific generated file without a handler change (Research Note #4). Approve the minimal `_find_code_path` enhancement in `core/flow/handlers/validation.py` (outside the design's stated `workflows/implementation`-only scope)? | (a) enhance handler [rec]; (b) keep validate_code but rely on `output_dir` glob (fragile/wrong in multi-file projects); (c) defer FR-3 out of SF-01. | **(a)** — smallest correct fix, backward-compatible, no boundary violation; needed for FR-3+FR-4. | **HIGH** |
| Q2 | `validate_code` gate policy. | (a) `on_fail=CONTINUE` report-only [rec]; (b) `on_fail=ABORT` like `new_feature.yaml`. | **(a)** — C01–C08 miss shouldn't kill an otherwise-passing autonomous run; surfaces in report (design Red/Blue). | MEDIUM |
| Q3 | `sw implement` exit code now reflects QA (fails → exit 1), a behavior change from "generate-only always exit 0". | (a) reflect QA outcome [rec]; (b) always exit 0, report only. | **(a)** — matches the autonomous-implementation contract ("run the tests"); update existing tests accordingly. | MEDIUM |
| Q4 | `coverage_threshold` source. | (a) from `settings.validation` (fallback 70) [rec]; (b) hard-code 70; (c) new CLI flag. | **(a)** — respects project config; no new CLI surface in SF-01. | LOW |
| Q5 | Retry budget for `run_tests` loop-back. | (a) `max_retries=2` (matches `new_feature.yaml`) [rec]; (b) configurable. | **(a)** — bounded cost (NFR-5); config can come later. | LOW |
| Q6 | Should SF-01 also emit `files_touched` in `StepResult.output` for memory-bank telemetry (`pipeline_engine_guide.md §11`)? | (a) yes, cheap [rec]; (b) skip in SF-01. | **(a)** if trivial in the report rewrite; else defer. | LOW |

## Architecture Verification (Phase 3)

- **Mechanism × constraint matrix.** `cli.py` edits: build Pydantic step/gate models + string handling (pure
  data) → within `orchestrator` archetype; imports only from `core.flow.engine.models` (already a dependency).
  No new I/O, execution, or LLM mechanism added in the CLI. `validation.py` edit: pure `Path` resolution
  (`params["target"]` → `project_path / target`, `.exists()`), no new I/O class, no new import; `validate_code`
  remains static/root-bound (Research Note #5). **No archetype or `forbids` conflict.**
- **Zoom-out / duplication.** No new module/capability — reuses existing handlers, atom, gates. `run_tests`
  target handling mirrors existing `ValidateTestsHandler` usage; the `_find_code_path` change extends an
  existing method rather than adding a parallel finder.
- **Acyclic imports.** `cli.py` → `core.flow.engine.models` is a pre-existing edge; `validation.py` change adds
  no import. No cycle introduced.
- **Common closure.** Two modules touched (`workflows/implementation`, `core/flow/handlers`); coupling is the
  intended integration seam (CLI wires steps; handler resolves the target). Not 3+; co-location not warranted.
- **Stability direction.** `validation.py` is a relatively stable module; the change is additive and
  backward-compatible (new optional `target` branch, existing behavior preserved) — no volatile dependency added.
- **Verdict:** no CRITICAL architectural violation. The only cross-module touch (Q1) is a MEDIUM/HIGH *scope*
  question, not an architecture violation.

---

## Consistency Check (Phase 5)

- **FR/NFR/AD coverage:** FR-1 (run_tests), FR-3 (validate_code), FR-4 (targets), FR-6 (loop-back gate),
  FR-7 (reporting + exit) all mapped to concrete changes. NFR-2 (leave `output_dir`/`enforce_isolation`
  unset → code→`src/`, tests→`tests/`), NFR-3 (no new cross-layer import; `tach`/`ruff`/`mypy` green),
  NFR-5 (`max_retries=2`) honored. AD-1 (inline pipeline) and AD-4 (stem convention) applied; AD-2/AD-5
  (isolation) correctly deferred to SF-03.
- **Open questions:** All resolved and documented inline (Q1–Q6 → (a)).
- **Architecture principles:** KISS — inline extension, no new module/YAML. DRY — reuses existing
  handlers/atom/gates; extends `_find_code_path` rather than duplicating a finder. SoC — CLI wires steps,
  handler resolves the target. Hexagonal — no port/adapter change. Imports acyclic (pre-existing edges only).
- **Red/Blue (2 cycles) — correction merged:** `test_full_pipeline` in `test_cli_implement.py` uses a mock
  adapter that returns the **same** text for code *and* tests, so the generated "test" file collects 0 tests
  and `run_tests` would now fail (exit 1), breaking its `exit_code==0` assertion. It MUST be updated in the
  same way as the other two tests (stub `QARunnerAtom`, or make the mock return a passing test). No other
  significant findings survived.

> [!CAUTION]
> **`test_full_pipeline` (line ~165) is a required update, not optional.** Appending real QA changes its
> outcome. Stub the QA atom or provide a genuinely passing generated test; do not leave it asserting the
> old generate-only exit code.

## Implementation Notes (as-built, 2026-07-18)

Delivered exactly the SF-01 scope. Files changed: `workflows/implementation/interfaces/cli.py`
(`_build_implement_pipeline`, `_report_implementation`, QA-aware exit) and
`core/flow/handlers/validation.py` (`ValidateCodeHandler._find_code_path` honors `params["target"]`
with a traversal guard). Tests: `test_validate_code_find_path.py` (8), `test_implement_pipeline.py` (7),
`test_implement_reporting.py` (7), `test_cli_implement.py` (+3 new, 3 updated), and 5 e2e tests updated.

Deviations / decisions confirmed during dev:
- **Q4 (coverage threshold):** `ValidationSettings` exposes no direct `coverage_threshold` field, so
  `run_tests` sets `coverage=True` and relies on the handler's built-in default (70). Precise
  thresholds remain the C04 rule's responsibility inside `validate_code`. (Refinement of Q4's "from
  settings" — no settings field to read.)
- **Exit logic (FR-6/FR-7):** implemented via the existing `run_state.status != "completed"` check —
  `LOOP_BACK` exhaustion leaves the run non-completed → exit 1; `validate_code`'s `CONTINUE` gate keeps
  a passing run `completed` → exit 0 (report-only). No extra run_tests-specific branch was needed;
  runner semantics verified empirically (`gates.py:89-93`, `201-231`).
- **e2e impact:** appending real QA broke 5 pre-existing `sw implement` e2e tests (mock-generated
  "test" files collect 0 tests → exit 1). Added an opt-in `stub_implement_qa` fixture in
  `tests/e2e/conftest.py`, applied to those 5 tests; real worktree-bounded QA execution is proven by
  SF-03's e2e (not SF-01).

Known pre-existing issues surfaced (NOT caused by SF-01, flagged for the user at the commit gate):
- `core/flow/engine/runner.py` is 606 lines (>600 limit) — untouched by SF-01.
- `test_log_artifact_event_concurrent_writes` (graph/lineage) is a SQLite-lock flake under full-suite
  load; passes in isolation; untouched module.

## Session Handoff

**Current status**: Implemented; pre-commit gate in progress (2026-07-18). Ready for commit boundary CB-1.
**Next step**: Run `/dev` for SF-01 — TDD (red→green→refactor) from the Test Plan, per commit boundary.
**If resuming**: read the Design Document Progress Tracker; SF-01 dev row is the active one.
