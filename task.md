# Task List: INT-US-09 SF-01 — Core QA Runner Containerized Injection

- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-09/INT-US-09_sf01_implementation_plan.md
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-09/INT-US-09_design.md
- **Commit boundaries**: 4 (grouped by the plan's natural dependency layers — executor core, QA-runner DI wiring, config plumbing, pipeline/scaffold wiring)

## Adversarial Test Matrix

| Bucket | Covered by |
|--------|-----------|
| **Happy Path** | `test_result_contract_unchanged_shape`, `test_resolve_runner_threads_executor_to_python`, `test_qa_runner_atom_container_mode_builds_container_executor`, `test_load_toml_sandbox_parses_execution_mode`, `test_validate_tests_handler_passes_sandbox_settings` |
| **Boundary/Edge Cases** | `test_image_defaults_from_requires_python` (absent/unparseable `requires-python`), `test_prepare_phase_skipped_when_lockfile_hash_unchanged` vs. `..._reruns_on_lockfile_change`, `test_deterministic_name_includes_run_id_and_uuid_suffix` (name collision avoidance), `test_user_flag_omitted_on_windows_with_warning` (platform boundary) |
| **Graceful Degradation** | `test_engine_unavailable_raises_typed_error`, `test_engine_on_path_but_not_live_raises`, `test_container_engine_unavailable_becomes_synthetic_failure`, `test_cleanup_runs_on_super_execute_exception`, `test_load_toml_sandbox_defaults_on_parse_error`, `test_qa_runner_atom_host_mode_default_unchanged` (NFR-7 zero-behavior-change fallback) |
| **Hostile/Wrong Input** | `test_extra_env_becomes_dash_e_flags_not_host_env` (env injection isolated to container, not host CLI process), `test_cwd_override_ignored_with_warning` (rejects a param that has no valid meaning for container mode rather than silently misusing it) — mount/path containment itself is NOT re-tested here: `ReadOnlyWorkspaceBoundary`/`WorkspaceBoundary`'s own traversal-hostility tests already exist and are being reused, not reimplemented (AD-3); duplicating them here would test the same code path twice. |

## Commit Boundary 1 — `ContainerSubprocessExecutor` core (foundational, self-contained)

- [x] T1. `ContainerMounts` frozen dataclass in `src/specweaver/sandbox/execution/models.py`. 2 tests.
- [x] T2. `ContainerEngineUnavailableError` + `_ensure_engine()` in `src/specweaver/sandbox/execution/container_executor.py`. 5 tests (prefers podman, falls back to docker, cached, unavailable raises, on-path-but-dead raises).
- [x] T3. `ContainerSubprocessExecutor.__init__` — lazy scratch/cache dir creation, image-tag resolution from `requires-python` (defaults `3.13`, clamps below `3.11`). 5 tests.
- [x] T4. `_build_container_cmd()` — RO/RW mounts, `--network none`, `--cap-drop ALL`/`no-new-privileges`, `--memory`/`--pids-limit` (2 GiB/128, matches `BashActionAtom`), `--user` on non-Windows (omitted+warned on Windows), `-e` flags from `extra_env`. 9 tests.
- [x] T5. `execute()` override — deterministic `specweaver-qa-{run_id}-{uuid8}` name, pre+post idempotent `rm -f` (incl. on exception via `finally`), `cwd_override` ignored+warned, unchanged `SubprocessResult` passthrough, engine-unavailable propagates before any run. 7 tests.
- [x] T6. `_ensure_prepared()` — lockfile-hash stamp file (sibling of `cache_root`, not inside it — Red/Blue fix), network-enabled `uv sync` prepare container, skips when no lockfile/pyproject, skips on unchanged hash, reruns on change, execute-phase stays `--network none`. 7 tests.

Refactor: `_resolve_image` now derives its supported-version bounds from `_SUPPORTED_TAGS` instead of duplicating `11`/`13` as separate magic numbers.

**Commit Boundary 1 results**: 33 new tests, all green. Full suite: unit 4565 passed/15 skipped, integration 428 passed/5 skipped/15 deselected, e2e 139 passed/1 skipped — zero regressions. `ruff check` clean, `mypy --ignore-missing-imports` clean (2 files), `tach check` OK (no boundary changes needed, confirmed).

### Pre-commit gate

- [x] Phase 1 — Architecture verification: clean, zero violations (adapter archetype, no new deps, no parallel security mechanism, no cycles, `tach check` OK).
- [x] Phase 2 — Test gap analysis: [artifact](https://claude.ai/code/artifact/23d1a5ae-74ca-4899-91cc-3b2ea49e7d43), 9 gaps found, user approved all 9 + requested real-engine integration tests.
- [x] Phase 3 — Implemented all 9 gap-fill unit tests (`_resolve_image` boundary/hostile branches ×4, `_ensure_engine` partial-fallback, `_ensure_prepared` failure-path + pyproject-only-fallback ×2, `execute()` `input_text`/`timeout_seconds` forwarding ×2) plus 5 new real-engine integration tests (`tests/integration/sandbox/execution/test_container_executor_integration.py`, live Podman detected on this host — RO-mount-blocks-write, RW-scratch-allows-write, network-none-blocks-egress, container-removed-after, result-contract — all 5 actually ran and passed against real Podman, not just skipped). 47 total tests for this commit boundary, all green. `ruff`/`mypy` clean.
- [x] Phase 4 — Full suite re-run: unit 4574 passed/15 skipped, integration 433 passed/5 skipped/15 deselected, e2e 139 passed/1 skipped. Zero regressions.
- [x] Phase 5 — Code quality (full repo): `ruff check src/ tests/` clean, `mypy src/` clean (303 files), `ruff --select C901` clean, file-size 0 errors/30 pre-existing warnings (none in touched files), `tach check` OK.
- [x] Phase 6 — Documentation: `docs/dev_guides/subprocess_execution.md` (new "Containerized QA Execution" section), `docs/dev_guides/special_patterns_and_adaptations.md` (§23, executor-subclassing pattern), `docs/dev_guides/testing_guide.md` (external-tool-skip entry), impl plan Commit Boundary 1 progress note. Deliberately deferred: `README.md`, `master_story_roadmap.md`/`capability_matrix.md` (Proof Mandate blocks any ✅ flip without an e2e test; SF-01 isn't done — 3 more commit boundaries).
- [x] Phase 7 — Walkthrough: [artifact](https://claude.ai/code/artifact/9ef64121-605a-4662-b3fd-a78c54d08248).
- [x] Phase 7.5 — Red/Blue adversarial review (2 cycles). Cycle 1 found 2 real HIGH findings in the actual code (not caught at design/impl-plan stage): (1) the prepare-phase container lacked the same cap-drop/resource/user hardening as the execute-phase container, despite `uv sync` being able to execute arbitrary sdist build code from PyPI; (2) the prepare-phase container relied on `--rm` alone with no deterministic name or pre/post cleanup — the exact anti-pattern AD-8 exists to prevent, and its 300s timeout is long enough for a host-side kill to orphan one. Both fixed: extracted a shared `_baseline_flags()` used by both phases, and gave the prepare phase the same name+cleanup treatment as the execute phase. 3 new tests added (45 unit total for this commit), all suites + quality checks re-run clean after the fix. Cycle 2: two LOW items surfaced and accepted as-is (Windows double-logs the non-root warning since `_baseline_flags()` is now called twice per `execute()` — accepted, matches the project's existing "don't over-build Windows shims" stance; no real-engine integration test for `_ensure_prepared()` itself — accepted, already-documented AD-7 scope boundary pending the sandbox image's own Backlog item). Converged, no further findings.

**→ Commit boundary: full test suite ✅ + pre-commit gate complete ✅ + committed as `68c34359`.**

## Commit Boundary 2 — QA runner DI wiring

**Sequencing correction found mid-implementation**: T8's `sandbox_settings: SandboxSettings | None` parameter needs `SandboxSettings` to exist, but that type was originally slotted in Commit Boundary 3 (T10). Rather than loosely type it `Any`, pulled just the `SandboxSettings` **model definition** (in `core/config/settings.py` + `context.yaml` exposes) forward into this commit — the TOML-loading wiring (`_load_toml_sandbox`, threading into `load_settings_async()`) stays in Commit Boundary 3 as planned. 4 new tests for the bare model.

- [x] T7. Widened `resolve_runner(cwd, executor=None)` in `qa_runner/core/factory.py`; centralized non-Python + container-mode `logger.warning` in `_warn_if_container_non_python()`. 11 tests (5 auto-discovery unchanged-behavior + 3 executor-passthrough + 3 warning-scoping).
- [x] T8 (+ partial T10). `SandboxSettings` model added to `core/config/settings.py` (4 tests). `QARunnerAtom.__init__` gains `sandbox_settings: SandboxSettings | None = None`; builds a `ContainerSubprocessExecutor` (mounts derived from `cwd/.specweaver/.sandbox/{scratch,cache}`) via a new `_build_container_executor()` helper when `execution_mode == "container"`. 4 tests.
- [x] T9. `PythonQARunner._run_tach_check()` skips the host-side `shutil.which("tach")` pre-check when `isinstance(self._executor, ContainerSubprocessExecutor)` (Finding #1). All 6 methods (`run_tests`, `run_linter`, `run_complexity`, `run_debugger`, `_run_tach_check`; `run_compiler` is a no-op, N/A) catch `ContainerEngineUnavailableError` and return the same kind of synthetic-failure result each already builds for its `<timeout>` case. 7 tests.

**Commit Boundary 2 results**: 26 new tests, all green (173 language-runner tests + 439 qa_runner/language/config tests overall, zero regressions). `ruff`/`mypy`/`tach check` clean.

### Pre-commit gate

- [x] Phase 1 — Architecture verification: clean, zero violations.
- [x] Phase 2 — Test gap analysis: [artifact](https://claude.ai/code/artifact/6fade480-75e9-46ae-930d-850ea1f5a59b). One real gap found — nothing tested the assembled chain end-to-end. User approved the proposed integration test.
- [x] Phase 3 — Implemented `test_container_atom_integration.py` (real Podman, full `factory` → `PythonQARunner` → `ContainerSubprocessExecutor` chain). **First run failed for real** — caught a genuine bug: `run_debugger()` used `sys.executable` (host Windows path), meaningless inside the Linux container. Fixed (bare `"python"` in container mode, matching the other 3 methods), 2 new unit tests, integration test now passes for real. 27 new tests total for this commit.
- [x] Phase 4 — Full suite re-run: unit 4605 passed/15 skipped, integration 434 passed/5 skipped/15 deselected, e2e 139 passed/1 skipped. Zero regressions.
- [x] Phase 5 — Code quality (full repo): `ruff check src/ tests/` clean, `mypy src/` clean (303 files), `ruff --select C901` clean, file-size 0 errors/33 warnings (3 new, all soft-threshold YELLOW from this commit's legitimate growth — not refactored, several sandbox files already sit further into this band), `tach check` OK.
- [x] Phase 6 — Documentation: `subprocess_execution.md` (new "Opt-In via QARunnerAtom" section + the `sys.executable` gotcha note), `special_patterns_and_adaptations.md` (§23 addendum — host-specific-path corollary lesson), impl plan Commit Boundary 2 progress note. `README.md`/roadmap status flips still deliberately deferred (same Proof Mandate reasoning as Commit 1).
- [x] Phase 7 — Walkthrough: [artifact](https://claude.ai/code/artifact/c65abb21-48c1-4f84-a3ec-7384308b7e21).
- [x] Phase 7.5 — Red/Blue adversarial review (2 cycles). One LOW finding accepted as-is (container `run_id` is random, not threaded from `RunContext.run_id` yet — flagged as a Commit 3/4 fast-follow, not a defect). No f-string-logger violations, no new race conditions beyond what the design doc's review already accepted. Converged.

**→ Commit boundary: full test suite ✅ + pre-commit gate complete ✅ + committed as `7e31ea9b`.**

## Commit Boundary 3 — `[sandbox]` config plumbing

- [x] T10 (model only — landed early in Commit Boundary 2).
- [x] T11. `_load_toml_sandbox()` in `settings_loader.py`, mirroring `_load_toml_standards` exactly; threaded into `load_settings_async()`'s final `SpecWeaverSettings(...)` construction. 3 new tests (container-mode TOML override, absent-section default, malformed-TOML graceful fallback).

**CB-3 results**: 3 new tests, all green (165 `core/config` tests overall, zero regressions). `ruff` clean, `tach check` OK. (One single-file `mypy` false-positive on pre-existing, untouched code — not reproducible in the authoritative full-repo `mypy src/` run, which stays clean at 303 files.)

### Pre-commit gate

- [x] Phase 1 — Architecture verification: clean, zero violations (pure `core.config`-internal, no cross-module imports).
- [x] Phase 2 — Test gap analysis: [artifact](https://claude.ai/code/artifact/8cf5b546-a584-4a7b-89d1-3b7e2fa3f392). Zero gaps found — coverage already exceeds the sibling `_load_toml_standards()` this mirrors.
- [x] Phase 3 — No-op (no gaps to implement).
- [x] Phase 4 — Full suite re-run: unit 4608 passed/15 skipped, integration 434 passed/5 skipped/15 deselected, e2e 139 passed/1 skipped. Zero regressions (one unrelated `graph/lineage` flake observed and confirmed non-reproducible).
- [x] Phase 5 — Code quality (full repo): `ruff check src/ tests/` clean, `mypy src/` clean (303 files), `ruff --select C901` clean, file-size 0 errors/33 warnings (unchanged from CB-2), `tach check` OK.
- [x] Phase 6 — Documentation: `subprocess_execution.md`'s "Opt-In via QARunnerAtom" section extended with "Enabling It From specweaver.toml", impl plan CB-3 progress note.
- [x] Phase 7 — Walkthrough: [artifact](https://claude.ai/code/artifact/31183bbe-a88d-4597-8a4b-a599b7885340).
- [x] Phase 7.5 — Red/Blue adversarial review (2 cycles). One LOW observation accepted as consistent with existing precedent (typo'd TOML keys silently ignored by Pydantic, same as `[standards]` already behaves — not a new gap). Converged.

**→ SF-01 CB-3: full test suite ✅ + pre-commit gate complete ✅ + committed as `8046f12c`.**

## SF-01 CB-4 (final) — Pipeline wiring, scaffolding, sandbox image spec

~~T16~~ superseded — its real-engine integration test was pulled forward into CB-1 (`tests/integration/sandbox/execution/test_container_executor_integration.py`) at the user's request; no duplicate added here.

- [x] T12. `ValidateTestsHandler._get_atom` passes `sandbox_settings=context.config.sandbox if context.config else None`. 2 tests.
- [x] T13. `LintFixHandler._get_atom` — same wiring. 2 tests.
- [x] T14. `_scaffold_gitignore_sandbox()` in `scaffold.py`, mirroring `_scaffold_gitignore_vault` — but called **unconditionally** from `scaffold_project()` (not gated behind `mcp_target`, since `[sandbox]` isn't MCP-specific). 3 tests.
- [x] T15. `Containerfile.sandbox` (repo root) — declarative Python+uv toolchain base, non-root user, no `ENTRYPOINT`/`CMD`. Not TDD.

**SF-01 CB-4 results**: 7 new tests, all green (485 `core/flow/handlers` + `workspace/project` tests overall, zero regressions). `ruff`/`mypy`/`tach check` clean.

### Pre-commit gate

- [x] Phase 1 — Architecture verification: clean, zero violations (no new imports anywhere).
- [x] Phase 2 — Test gap analysis: [artifact](https://claude.ai/code/artifact/079b6624-123e-4bc5-ab46-660e2e0c76c5). Unit coverage complete; one capstone integration test proposed (full `ValidateTestsHandler.execute()` → real container → real `pytest`, exercising the never-yet-tested `uv sync` prepare phase). User replied "please commit" without approving — treated as declined, flagged explicitly in the impl plan's progress notes, not silently dropped.
- [x] Phase 3 — N/A (test declined).
- [x] Phase 4 — Full suite: unit 4615 passed/15 skipped, integration 434 passed/5 skipped/15 deselected, e2e 139 passed/1 skipped. Zero regressions.
- [x] Phase 5 — Code quality (full repo): `ruff check src/ tests/` clean, `mypy src/` clean (303 files), `ruff --select C901` clean, file-size 0 errors/33 warnings (unchanged), `tach check` OK.
- [x] Phase 6 — Documentation: `subprocess_execution.md`'s two remaining forward-references corrected now that pipeline wiring is real; impl plan CB-4 progress note (including the SF-01-complete summary and the explicit note that roadmap/capability-matrix status flips are an open follow-up, not resolved here — Proof Mandate needs a literal e2e-tier test, everything built is unit/integration-tier).
- [x] Phase 7 — Walkthrough: [artifact](https://claude.ai/code/artifact/7e7ea8ef-2d44-4704-b5fc-d6d32465f0cf).
- [x] Phase 7.5 — Red/Blue adversarial review (2 cycles). No new findings beyond the already-flagged roadmap/e2e-proof gap. Converged.

**→ SF-01 CB-4 (FINAL): full test suite ✅ + pre-commit gate complete ✅ + HITL stop (awaiting commit).**

# SF-01 COMPLETE (pending this final commit) — 4/4 commit boundaries done.

**→ SF-01 CB-4: full test suite (next) + pre-commit gate + HITL stop.**
