# Task List: INT-US-09 — Zero-Trust Sandbox Base Integration Contract

- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-09/INT-US-09_implementation_plan.md
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-09/INT-US-09_design.md
- **Commit boundaries**: 4 (CB-1 config surface + composition-root wiring; CB-2 execution-root + tri-state + gate; CB-3 boundary hand-off in the two untrusted handlers; CB-4 e2e proof + fail-closed + docs)
- **Scope**: STRICTLY CONTAINER-FREE. Integrate US-5 (Worktree Bouncer) + E-EXEC-01 (SubprocessExecutor) + C-EXEC-02 (BashActionAtom). Excludes B-EXEC-01/D-EXEC-01 and INT-US-09-SF01..SF04.

## Adversarial Test Matrix

| Bucket | Covered by |
|--------|-----------|
| **Happy path** | policy on + `use_worktree=None` bash step → isolated; settings load; execution_root set; handler cwd = worktree |
| **Boundary/edge** | tri-state (True/False/None) × policy (on/off) truth table; `.specweaver` absent; execution_root None → project_path |
| **Graceful degradation** | policy on + non-git project → actionable fail-closed error (GitAtom real message); git/bash absent → e2e skips |
| **Hostile/wrong input** | script path traversal stays fail-closed under worktree rebind (`.specweaver/scripts` canonical containment); credential stripping preserved |

## CB-1 — Config surface + composition-root wiring

- [x] **T1** — Add `enforce_worktree_isolation: bool = False` to `SandboxSettings`. src: `src/specweaver/core/config/settings.py`. test: `test_settings_loader.py` (default False; accepts True; coexists w/ execution_mode; rejects non-bool; TOML load). ✅ 9 new tests green.
- [x] **T2** — Resolve the isolation policy at the composition root (`cli.py` run + resume) into a dedicated `RunContext.enforce_isolation: bool` flag (added `enforce_isolation` field to RunContext — pulled forward from CB-2). **Container-neutrality guard (user decision / Red/Blue finding):** do NOT populate `context.config` (that would activate B-EXEC-01 container QA on `sw run` — out of scope; it also broke `test_lint_fix_retains_tag`, now fixed). Graceful try/except → default off. tests: `TestRunContextConfigWiring` (policy resolved, container-neutral: `config is None`), resume wiring, +integration `test_container_execution_mode_stays_dormant_on_run`. ✅ green.
- [~] **T3** — API sites `pipelines.py:84/225/312`: **DEFERRED to Backlog** (documented gap, not silently dropped). Settings are resolvable (`db` + `body.project`/`run.project_name`) but driving the async background-run endpoints test-first is disproportionate for CB-1; a NOTE at the site + Backlog entry track it. API-launched runs won't honor the policy until wired.
- [x] **T4** — No new `tach.toml` edge needed (`load_settings` already imported in `cli.py`; API deferred). `tach check` OK; ruff + mypy clean; full unit+integration suite green (5057 passed; 1 unrelated pre-existing DB-concurrency flake).
### CB-1 pre-commit
- [x] Phase 1 — Architecture: clean (tach OK; no new edge; additive stable config field). No violations.
- [x] Phase 2 — Test-gap analysis (HITL approved): added graceful-degradation + resume unit tests + 3 real-toml→context integration tests.
- [x] Phase 3 — Implement missing tests: `test_cli_pipelines.py` (+graceful-degradation, +resume wiring) and NEW `tests/integration/core/flow/test_cli_config_integration.py` (real `specweaver.toml` → `load_settings` → context: policy true on run, absent→false, true on resume). All green; ruff clean.
- [x] Phase 5 — Code quality: mypy / ruff / complexity (C901) / file-size all clean.
- [x] Phase 7.5 — Red/Blue on code changes: found the container side-effect (config population activating B-EXEC-01 on `sw run`). Resolved via the container-neutrality guard (user chose "guard it out") — dedicated `enforce_isolation` flag; `context.config` stays None. Verified: fixes `test_lint_fix_retains_tag`.
- [x] Phase 4 — Full suite (post-guard): 5202 passed, 21 skipped; 1 failure = the known pre-existing DB-concurrency flake `test_story_3_concurrent_reads_happy_path` (unrelated, not in diff). `test_lint_fix_retains_tag` now passes (guard fixed it).
- [x] Phase 6 — Documentation: CB-1 is internal plumbing; dev-guide updates land in CB-2/CB-4 pre-commit per plan. Impl plan + task.md synced to the guard decision.
- [x] Phase 7 — Walkthrough: presented at the commit gate.

- **→ Commit boundary CB-1: full suite ✅ + pre-commit ✅ + committed as `85d02be4`.**

## CB-2 — Execution-root field + tri-state flag + policy gate

- [x] **T5** — Add `execution_root: Path | None = None` to `RunContext`. src: `src/specweaver/core/flow/handlers/base.py`. test: model default None. (Note: sibling `enforce_isolation` field already landed early in CB-1.)
- [x] **T6** — `PipelineStep.use_worktree: bool = False` → `bool | None = None`. src: `src/specweaver/core/flow/engine/models.py:221`. test: 3-state model test.
- [x] **T6b** — Audit/update existing readers/tests of `use_worktree` for tri-state (`tests/integration/core/flow/engine/test_runner_sandbox.py`, `tests/unit/core/flow/engine/test_models.py`).
- [x] **T7** — Policy-aware runner gate at `runner.py`: extracted a pure `resolve_should_isolate(step_def, context)` helper (`step.use_worktree if not None else getattr(context, "enforce_isolation", False)`, strict-bool, defensive on both reads) so it's DIRECTLY unit-testable (not transitively). tests: runner truth table (integration) + NEW `test_isolation_gate.py` (**20 cases**: happy tri-state×policy; boundary `is not None`-not-truthiness (`0`/`""`→False, `1`→True); hostile non-bool coercion + present-but-None; graceful degradation — missing fields either/both, whole `None` objects either/both, explicit short-circuit; strict-bool return). Reads the flag from CB-1 — NOT `context.config.sandbox` (container-neutrality guard).
- [x] **T8** — `execute_in_sandbox` sets `isolated_context.execution_root = project_path / wt_path`. src: `src/specweaver/core/flow/engine/runner_utils.py`. test: assert set (GitAtom.run patch pattern).
- **→ Commit boundary CB-2: full suite ✅ (5222 passed) + pre-commit ✅ + committed as `f4077870`.**

## CB-3 — Boundary hand-off in the two untrusted handlers

- [x] **T9** — `bash_action.py`: `BashActionAtom(cwd=context.execution_root or context.project_path)`. src: `src/specweaver/core/flow/handlers/bash_action.py`. test: isolated → worktree cwd; non-isolated → project_path.
- [x] **T10** — `validation.py` (ValidateTests): `QARunnerAtom(cwd=context.execution_root or context.project_path, sandbox_settings=...)`. src: `src/specweaver/core/flow/handlers/validation.py`. test: isolated → worktree cwd; non-isolated unchanged. (Do NOT touch lint_fix / static QA.)
- **→ Commit boundary CB-3: full suite ✅ (5238 passed) + pre-commit ✅ + committed as `bd6913c6`.**

## CB-4 — Verifiable proof (e2e) + fail-closed + docs

- [x] **T11** — Fail-closed: improve `execute_in_sandbox` `worktree_add` failure message using GitAtom's actual `add_res.message` + actionable git-repo hint (no raw `.git` probe). src: `runner_utils.py`. test: integration — policy-on non-git project raises actionable error.
- [x] **T12** — Real-worktree unmocked e2e proof (`tests/e2e/sandbox/test_int_us_09_isolation_e2e.py`, **5 scenarios**): bash isolated via explicit `use_worktree=True` AND via the policy (`enforce_isolation`), each proving `pwd` inside `.worktrees` + **real source root NOT mutated** (FR-6 blast-radius); bash control (`use_worktree=False`) → real root. **`run_tests`/pytest surface** (user-requested #3): isolated → probe pytest asserts its own cwd is in the worktree (`passed==1`), paired with a non-isolated control (`failed==1`) — the count guards defeat a 0-collected false pass (caught during dev: the QA runner's `-m unit` filter excluded an unmarked probe → `kind=""`). Committed-script approach so it runs cross-platform (Windows too). git/bash skip guard.
- [x] **T13** — Docs: `pipeline_engine_guide.md` §7, `subprocess_execution.md` (during pre-commit).
- **→ Commit boundary CB-4 (final): full suite ✅ (5245 passed) + pre-commit ✅ + committed. Design Progress Tracker flipped Dev/Pre-Commit/Committed ✅. INT-US-09 COMPLETE.**
