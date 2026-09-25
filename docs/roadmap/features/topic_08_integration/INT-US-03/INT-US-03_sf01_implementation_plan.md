# INT-US-03 SF-01 — Generation → QA Test Loop

**Status**: APPROVED — approved by Steve Bula on 2026-07-17. Audit Q1–Q6 all resolved to option
**(a)**. Implemented 2026-07-18. · **FRs owned**: FR-1, FR-3, FR-4, FR-6, FR-7 · **Depends on**: — ·
Design: [INT-US-03_design.md](INT-US-03_design.md) §Sub-features → SF-01

## Goal

Generated code + tests are validated **in-pipeline**: append `run_tests` (`VALIDATE`/`TESTS`,
coverage) and `validate_code` (`VALIDATE`/`CODE`, C01–C08) to the inline `implement_spec` pipeline,
resolve QA targets to this run's generated files, add the loop-back-on-fail gate, report QA results
inline.

Out of scope: FR-2 lint-fix (SF-02); FR-5 isolation / `enforce_isolation` threading + FR-8 e2e proof
(SF-03); Podman/containers (whole feature). SF-01 runs QA in **host mode** and must not regress the
default-off isolation behavior (NFR-2).

## Where it plugs in

| Fact | Where |
|---|---|
| `sw implement` (`D-INTL-01`) builds an **inline** `PipelineDefinition(name="implement_spec", ...)` with two steps: `generate_code` (`GENERATE`/`CODE`) + `generate_tests` (`GENERATE`/`TESTS`), run via `PipelineRunner` (`cli.py:150-151`) | `src/specweaver/workflows/implementation/interfaces/cli.py:120-151` (steps `workflows/implementation/interfaces/cli.py:120-135`) |
| Output paths `src/<stem>.py` / `tests/test_<stem>.py`, `stem = spec.stem − "_spec"` (`spec_path.stem.removesuffix("_spec")`, `cli.py:99`) | `cli.py:99-104` |
| Its `RunContext` sets `config`/`llm`/`db`/`topology` but **not** `output_dir` and **not** `enforce_isolation` (defaults `False`) | `cli.py:137-147` |
| Ends by printing a stale "Next steps: `sw check --level=code …`" — QA was a **manual, disconnected** follow-up | `cli.py:165-170`; reporting loop `cli.py:157-170` |
| `OnFailAction.{ABORT,RETRY,LOOP_BACK,CONTINUE}`, `GateCondition.{ALL_PASSED,ACCEPTED,COMPLETED}` | `models.py:78-84`, `70-75` |
| `(VALIDATE,TESTS)`, `(VALIDATE,CODE)`, `(LINT_FIX,CODE)` are in `VALID_STEP_COMBINATIONS` | `models.py:104-137` |
| `PipelineDefinition.max_total_loops` defaults to 20 — the backstop against runaway loop-backs | `models.py:248` |
| QA Runner (`D-VAL-01`): `QARunnerAtom`, invoked by `ValidateTestsHandler` on a `VALIDATE`/`TESTS` step. Input `{intent:"run_tests", target:"<rel path>", kind, coverage, coverage_threshold}` | `src/specweaver/sandbox/qa_runner/core/atom.py:71`, `src/specweaver/core/flow/handlers/validation.py:335` |
| `ValidateTestsHandler` reads `step.params.get("target")`, passes it (relative to the atom `cwd`) to `QARunnerAtom.run({"intent":"run_tests", ...})` | `core/flow/handlers/validation.py:335-401` |
| `cwd = context.execution_root or context.project_path` | `validation.py:403-415` |
| `_resolve_targets` returns `[target]` **unless** `target ∈ {".", "", "src", "src/", "tests", "tests/"}` **and** `context.stale_nodes is not None` | `validation.py:417-421` |
| Code Validation Rules (`D-VAL-05`): `VALIDATE`/`CODE` → `ValidateCodeHandler` | `validation.py:200` |
| `ValidateCodeHandler._find_code_path` locates code by `context.output_dir.glob("*.py")[0]` — **None** when `output_dir` is unset, an **arbitrary first file** in a multi-file dir | `validation.py:255-261` |
| Generate handlers write code to `context.output_dir or project_path/"src"` and tests to `context.output_dir or project_path/"tests"` | `generation.py:111-112`, `217-218` |
| Lint-Fix loop (`D-VAL-01`): `LintFixHandler`, key `lint_fix+code`; passes `sandbox_settings=context.config.sandbox` to its atom | `src/specweaver/core/flow/handlers/lint_fix.py:23`, `lint_fix.py:215-216` |
| US-9 Core isolation (`INT-US-09`, ✅ Done 2026-07-17): `RunContext.enforce_isolation` (default `False`) + `execution_root` rebind untrusted-process cwd to an ephemeral git worktree. `PipelineStep.use_worktree`: `True`=force, `False`=off, `None`=defer to policy | `src/specweaver/core/flow/handlers/base.py:56`, `base.py:57` |
| Loop-back precedent: `run_tests` gates `on_fail: loop_back → generate_code, max_retries: 2, condition: all_passed`; `validate_code` uses `on_fail: abort`; SF-01 uses `on_fail: continue` instead (Q2) | `src/specweaver/workflows/pipelines/new_feature.yaml:50-62` |

Step/gate models are Pydantic, built in Python (`core/flow/engine/models.py`):
`PipelineStep(name, action: StepAction, target: StepTarget, params: dict, gate: GateDefinition|None, router, description, use_worktree: bool|None)`
(`models.py:202-223`);
`GateDefinition(type=GateType.AUTO, condition=GateCondition, on_fail=OnFailAction, loop_target: str|None, max_retries: int=3)`
(`models.py:145-161`).

**Isolation proof pattern** — `tests/e2e/sandbox/test_step_worktree_isolation_e2e.py`: a
`VALIDATE`/`TESTS` step with `use_worktree=None` + `enforce_isolation=True` runs
`QARunnerAtom`→pytest **worktree-bounded**, with a paired un-isolated control guarding against a
0-collected vacuous pass. Container-free; needs only git+bash; skips cleanly otherwise.

Constraints that shape the changes:

- **FR-4 for tests is trivial:** `params["target"] = "tests/test_<stem>.py"` is a specific file, not in
  the short-circuit set → runs exactly that file.
- **`validate_code` does NOT honor `target` (the SF-01 crux, Q1).** A single `output_dir` cannot both
  keep code in `src/` + tests in `tests/` and point `validate_code` at one file. Fix: teach
  `_find_code_path` to honor `params["target"]` — ~4 lines, in `core/flow/handlers/validation.py`,
  i.e. **outside** `workflows/implementation`.
- **Static QA is project-root-bound** (`pipeline_engine_guide.md §7`, INT-US-09): only execution
  handlers (`run_tests`/pytest, `bash`) rebind cwd to the worktree; `validate_code` and `lint_fix`
  (ruff) "parse but never execute". So both read the generated file at the **real** `src/<stem>.py`
  regardless of isolation, and the target fix is correct for host and isolated modes.
- **`stale_nodes` short-circuit** (`pipeline_engine_guide.md §9`): `context.stale_nodes == []` (empty
  list, not None) makes `ValidateTestsHandler` return a "pristine" `SUCCESS` **without running
  pytest**. The implement `RunContext` leaves `stale_nodes` unset (None). SF-01 MUST NOT set it to an
  empty list (vacuous pass). A documented guard, not a code change.
- **Existing tests break** (`tests/integration/interfaces/cli/test_cli_implement.py`): they mock
  `create_llm_adapter`, return trivial LLM text, and assert `exit_code == 0` + "Implementation
  complete" + files exist (`test_implement_generates_files`, `test_implement_spec_suffix_removal`,
  `test_full_pipeline`). Real QA makes mock-generated tests fail → exit 1. Convention:
  `typer.testing.CliRunner`, `_make_mock_adapter`, `_scaffold_project` via `sw init`.
- **Module boundary** (`workflows/implementation/context.yaml`): `archetype: orchestrator`,
  `consumes: [llm, config, validation]`, `forbids: []`. Importing
  `GateDefinition`/`GateType`/`GateCondition`/`OnFailAction` from `core.flow.engine.models` adds no
  new cross-layer dependency.

External: none new. pytest + ruff are already invoked by `QARunnerAtom`. No `pyproject.toml` change.

## Changes

1. **Extend the inline pipeline** (FR-1, FR-3, FR-6) · `cli.py` — append after `generate_tests`:
   - `run_tests` — `PipelineStep(action=VALIDATE, target=TESTS)`:
     - `params = {"target": "tests/test_<stem>.py", "kind": "unit", "coverage": True, "coverage_threshold": <from settings, default 70>}`
     - `gate = GateDefinition(type=AUTO, condition=ALL_PASSED, on_fail=LOOP_BACK, loop_target="generate_code", max_retries=2)`
   - `validate_code` — `PipelineStep(action=VALIDATE, target=CODE)`:
     - `params = {"target": "src/<stem>.py"}`
     - `gate = GateDefinition(type=AUTO, condition=ALL_PASSED, on_fail=CONTINUE)`  # report-only, never abort

   Targets are **relative** (atom cwd = project root in host mode). Leave `use_worktree` unset
   (`None`); do **not** set `output_dir`/`enforce_isolation` (SF-03). Generate steps unchanged.
2. **`validate_code` honors an explicit target** (FR-3, FR-4) · `validation.py` —
   `ValidateCodeHandler._find_code_path(step, context)`:
   1. if `step.params.get("target")` is set → resolve against `context.project_path`; return it if it
      exists.
   2. else the **existing** `context.output_dir.glob("*.py")[0]` (no current caller sets `target` on a
      validate/code step — verified against `new_feature.yaml` and the validation pipelines).

   No signature change, no new import.
3. **Inline QA reporting; drop the stale message** (FR-7) · `cli.py` — replace the post-run
   `step_records` loop + "Next steps" block, per step:
   - `generate_*`: print `generated_path` (as today).
   - `run_tests`: `record.result.output` → pass/fail counts + `coverage_pct`.
   - `validate_code`: `record.result.output` → `passed/failed` + failed `rule_id`s.
   - Exit non-zero if the final run status is not `completed` **or** `run_tests` failed after retries
     (Q3). `validate_code` failures are report-only (gate `CONTINUE`).

| File | Change | FRs |
|------|--------|-----|
| `src/specweaver/workflows/implementation/interfaces/cli.py` | Append `run_tests` + `validate_code` steps w/ gates + params; rewrite reporting/exit; new imports (`GateDefinition`,`GateType`,`GateCondition`,`OnFailAction`) | FR-1, FR-3, FR-4, FR-6, FR-7 |
| `src/specweaver/core/flow/handlers/validation.py` | `ValidateCodeHandler._find_code_path`: honor `params["target"]`, fallback to existing glob | FR-3, FR-4 |
| `tests/integration/interfaces/cli/test_cli_implement.py` | Update existing tests to stub QA; add wiring/reporting/loop-back/exit tests | all |
| `tests/unit/core/flow/handlers/…validate_code…` | Unit test for the new target-resolution branch | FR-3, FR-4 |

No new files, no new module, no DB migration, no YAML pipeline file (inline per AD-1).

## Tests

Four adversarial buckets, per `tests/CLAUDE.md`.

| Tier | Bucket | Case |
|---|---|---|
| Unit — pipeline construction | Happy | steps are `[generate_code, generate_tests, run_tests, validate_code]`; `run_tests` loop-back gate (`loop_target="generate_code"`, `max_retries=2`); `validate_code` gate `CONTINUE`; targets `tests/test_<stem>.py` / `src/<stem>.py` |
| | Boundary | spec name with `_spec` suffix / nested/odd stem → correct relative targets |
| Unit — `_find_code_path` | Happy | `params["target"]="src/x.py"` (exists) → that path |
| | Boundary | `target` missing → `output_dir` glob (unchanged) |
| | Hostile | `target` outside project / nonexistent → None (handler's "No code file found" path); `../` traversal not resolved outside project |
| Integration — `test_cli_implement.py`, QA atom stubbed | Happy | `QARunnerAtom.run` passes + coverage ≥ threshold; `validate_code` passes → `exit_code==0`, report shows counts + coverage |
| | Degradation | `run_tests` fails twice → retries exhausted → `exit_code==1`, failure reported; `validate_code` fails under `CONTINUE` → run completes, failure reported, no exit-1 on its own |
| | Backward-compat | the three existing tests, stubbed, still assert files created + "Implementation complete" |

> [!CAUTION]
> **`test_full_pipeline` (line ~165) is a required update.** Its mock adapter returns the **same**
> text for code *and* tests, so the generated "test" file collects 0 tests and `run_tests` fails
> (exit 1). Stub the QA atom or return a genuinely passing test; never leave it asserting the old
> generate-only exit code. (Red/Blue, 2 cycles; no other significant finding survived.)

Real pytest execution + the worktree-bounded proof (FR-8) are SF-03's; SF-01 asserts wiring and
reporting only.

## Decisions (audit)

| # | Question | Options | Proposal | Severity |
|---|----------|---------|----------|----------|
| Q1 | `validate_code` can't target the specific generated file without a handler change. Approve the minimal `_find_code_path` enhancement in `core/flow/handlers/validation.py` (outside the design's stated `workflows/implementation`-only scope)? | (a) enhance handler [rec]; (b) keep validate_code but rely on `output_dir` glob (fragile/wrong in multi-file projects); (c) defer FR-3 out of SF-01. | **(a)** — smallest correct fix, backward-compatible, no boundary violation; needed for FR-3+FR-4. | **HIGH** |
| Q2 | `validate_code` gate policy. | (a) `on_fail=CONTINUE` report-only [rec]; (b) `on_fail=ABORT` like `new_feature.yaml`. | **(a)** — C01–C08 miss shouldn't kill an otherwise-passing autonomous run; surfaces in report (design Red/Blue). | MEDIUM |
| Q3 | `sw implement` exit code now reflects QA (fails → exit 1), a behavior change from "generate-only always exit 0". | (a) reflect QA outcome [rec]; (b) always exit 0, report only. | **(a)** — matches the autonomous-implementation contract ("run the tests"); update existing tests accordingly. | MEDIUM |
| Q4 | `coverage_threshold` source. | (a) from `settings.validation` (fallback 70) [rec]; (b) hard-code 70; (c) new CLI flag. | **(a)** — respects project config; no new CLI surface in SF-01. | LOW |
| Q5 | Retry budget for `run_tests` loop-back. | (a) `max_retries=2` (matches `new_feature.yaml`) [rec]; (b) configurable. | **(a)** — bounded cost (NFR-5); config can come later. | LOW |
| Q6 | Should SF-01 also emit `files_touched` in `StepResult.output` for memory-bank telemetry (`pipeline_engine_guide.md §11`)? | (a) yes, cheap [rec]; (b) skip in SF-01. | **(a)** if trivial in the report rewrite; else defer. | LOW |

Architecture check: `cli.py` builds Pydantic step/gate models (pure data) within the `orchestrator`
archetype, importing only from `core.flow.engine.models` (pre-existing edge). `validation.py` gains
pure `Path` resolution (`params["target"]` → `project_path / target`, `.exists()`), no new import;
`validate_code` stays static/root-bound. Two modules touched (`workflows/implementation`,
`core/flow/handlers`) — the intended seam; not 3+. The finder is extended, not duplicated. No
cycle, no archetype or `forbids` conflict. Q1 is a *scope* question, not an architecture violation.
NFR-2 (leave `output_dir`/`enforce_isolation` unset → code→`src/`, tests→`tests/`), NFR-3, NFR-5
(`max_retries=2`), AD-1 and AD-4 honored; AD-2/AD-5 deferred to SF-03.

## As built (2026-07-18)

`workflows/implementation/interfaces/cli.py` (`_build_implement_pipeline`,
`_report_implementation`, QA-aware exit) and `core/flow/handlers/validation.py`
(`ValidateCodeHandler._find_code_path` honors `params["target"]` with a traversal guard).

- **Q4:** `ValidationSettings` has no `coverage_threshold` field, so `run_tests` sets
  `coverage=True` and relies on the handler default (70). Precise thresholds stay the C04 rule's
  job inside `validate_code`.
- **Exit logic (FR-6/FR-7):** the existing `run_state.status != "completed"` check — `LOOP_BACK`
  exhaustion leaves the run non-completed → exit 1; `validate_code`'s `CONTINUE` gate keeps a
  passing run `completed` → exit 0. No `run_tests`-specific branch needed; runner semantics verified
  (`gates.py:89-93`, `201-231`).
- **e2e impact:** 5 pre-existing `sw implement` e2e tests broke (0-collected mock tests → exit 1).
  An opt-in `stub_implement_qa` fixture in `tests/e2e/conftest.py` is applied to them.

Tests and results: [walkthrough](INT-US-03_sf01_walkthrough.md).

**Since moved** (`c3f36d54`, 2026-08-12, `runner_utils` retired): `resolve_should_isolate` and
`apply_session_policy` → `core/flow/engine/isolation.py`; `execute_run` →
`core/flow/engine/session.py`. Line refs above are as of the plan's date.
