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

**→ Commit boundary: full test suite ✅ + pre-commit gate complete ✅ + HITL stop (awaiting commit).**

## Commit Boundary 2 — QA runner DI wiring

- [ ] T7. Widen `resolve_runner(cwd, executor=None)` in `qa_runner/core/factory.py` + centralized non-Python warning.
- [ ] T8. `QARunnerAtom.__init__` gains `sandbox_settings`; builds `ContainerSubprocessExecutor` when enabled.
- [ ] T9. `PythonQARunner` — conditional tach pre-check skip; catch `ContainerEngineUnavailableError` in all 6 methods.

**→ Commit boundary: full test suite + pre-commit gate + HITL stop.**

## Commit Boundary 3 — `[sandbox]` config plumbing

- [ ] T10. `SandboxSettings` + `SpecWeaverSettings.sandbox` field; `context.yaml` exposes update.
- [ ] T11. `_load_toml_sandbox()` in `settings_loader.py`, threaded into `load_settings_async()`.

**→ Commit boundary: full test suite + pre-commit gate + HITL stop.**

## Commit Boundary 4 — Pipeline wiring, scaffolding, sandbox image spec

- [ ] T12. `ValidateTestsHandler._get_atom` passes `sandbox_settings`.
- [ ] T13. `LintFixHandler._get_atom` passes `sandbox_settings`.
- [ ] T14. `_scaffold_gitignore_sandbox()` in `scaffold.py`, called from `scaffold_project()`.
- [ ] T15. `Containerfile.sandbox` (repo root) — declarative, not TDD.
- [ ] T16. Integration test: `tests/integration/sandbox/execution/test_container_executor_integration.py` — real engine, `skipif` if unavailable.

**→ Commit boundary: full test suite + pre-commit gate + HITL stop.**
