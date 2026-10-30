# Walkthrough: TECH-087 SF-01 — A check that did not run is never clean

Plan: [TECH-087_sf01_implementation_plan.md](TECH-087_sf01_implementation_plan.md).

## CB-1 — runners never return a false clean (FR-1, FR-2, FR-3)

### What changed

- `sandbox/language/core/toolchain.py`: `timed_out`, `clear_old_report`, `unreadable_report` beside
  the `failed_*` factories.
- `sandbox/language/core/sarif.py`: `read_sarif_report` returns `None` for a report it cannot read
  as a SARIF object (was `{}`); `run_sarif_analysis` runs one PMD or detekt analysis and returns
  today's report or the reason there is none (old report cleared first, then timeout, did-not-run,
  no report, unreadable).
- Python: no engine, a timeout, and ruff output that is not a JSON list now return
  `failed_lint` / `failed_complexity`; the did-not-run branches use the same factories (file
  `<toolchain>`, was `<validation_engine>`); complexity names ruff, not "complexipy".
- Java and Kotlin read through `run_sarif_analysis`; Kotlin's inline `json.loads` (which let an
  `OSError` escape) is gone.
- Rust: a timed-out clippy run is not run; the exception branch uses `failed_complexity`.
- TypeScript: `run_complexity` returns `failed_complexity("TypeScript complexity checks are not
  implemented", …)`.

### Red first

`tests/unit/sandbox/language/core/language/test_no_false_clean.py`: 28 of 34 cases failed before the
change (S1–S12 of the plan); the 6 controls (a real empty verdict stays clean, today's finding is
counted) passed. Two pinned tests flipped (`test_python_runner.py` engine-unavailable lint and
complexity) and the TS stub test was removed. The full suite found two more:
`qa_runner/test_interface.py` `test_linter_timeout` (asserted `error_count >= 0`, which cannot fail)
and `test_complexity_timeout` (asserted 0); both now assert the not-run result. `test_lost_results_warn.py` now expects `None` from
the two readers. Five older Java/Kotlin tests wrote the report before the run; their executor now
writes it during the run, since the runner removes an earlier run's report.

### Proof

Six corpus mutants in `TECH-087_mutants.json`, all killed: Python lint timeout back to zero;
timeout check removed from `run_sarif_analysis`; TS stub back to zero; ruff garbage back to `[]`;
`read_sarif_report` back to `{}`; old report not cleared.

### Gate notes

- `tests.py cb TECH-087 --kind bugfix`: unit 492, integration 473 passed. `quality.py cb` and `doc`
  green.
- Duplication: the Java↔Kotlin clone frozen at 17 lines is now two smaller ones (the lint and
  complexity methods, 12 lines; the import block, 18 lines, identical once Kotlin stopped importing
  `json`). Re-frozen deliberately: SF-04 (FR-13) gives Java and Kotlin one JVM base, which removes
  both.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) a report path that is a symlink to a file outside the project. Blue: `unlink` removes
  the link only; `test_an_old_report_that_links_outside_removes_only_the_link` holds it.
- R2 (MEDIUM) lint and complexity run the same analysis and share one report; run in parallel they
  would remove each other's report. Accepted risk: the atom runs intents one at a time, and the
  result of a race is a not-run result, never a false clean.
- R3 (LOW) container mode with Maven's overlay workspace never writes the report to the host. Not
  changed by this boundary: it was already a missing report, now reached after the clear.
- Cycle 2: no new finding.

## CB-2 — the lint step stops on a lint that did not run (FR-4, P-1)

### What changed

- `toolchain.did_not_run_reason(errors)`: the reasons of the `ToolchainUnavailable` entries among a
  lint's exported errors (AD-2), exposed in `tach.toml` for the handler.
- `core/flow/handlers/lint_fix.py`: after the first lint, the re-lint after the linter's auto-fix, and
  each re-lint after a model fix, a lint that did not run returns FAILED "The linter did not run:
  <reason>" at once. Found in Phase 2 and fixed here: a lint result with no `error_count` (the atom
  refused the target, or failed before linting) read as zero errors and the step PASSED; it is now
  a lint that did not run. `execute` was split (`_verdict_without_model`, `_model_fix`) to stay
  under the complexity limits.
- `docs/dev_guides/pipeline_engine_guide.md`: one rule line.

### Red first

- P-1 `tests/integration/core/flow/handlers/test_lint_step_tool_did_not_run.py`: real handler, atom,
  Python runner and container executor, `PATH` with no Podman or Docker. Before the change the step
  spent both model reflections and failed with "Lint-fix exhausted after 2 reflections".
- `test_lint_fix_handler.py::TestLintThatDidNotRun`: five cases (first lint, re-lint after auto-fix,
  re-lint after a model fix, a refused lint, a result with no exports); all failed before.
- `test_did_not_run_reason.py`: the helper on the factory's own output (`asdict(failed_lint(...))`).

### Proof

Three FR-4 mutants, all killed: the not-run check in `_verdict_without_model` removed; the code
compared against a wrong string; the "no `error_count`" branch disabled.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) a project lint rule whose code is literally `ToolchainUnavailable` would stop the step.
  Accepted: ruff, ESLint, PMD, detekt and clippy emit no such code, and the outcome fails closed.
- R2 (MEDIUM) the auto-fix call's own result is not read. Blue: the re-lint after it is, and that is
  the lint that decides.
- R3 (LOW) the refused-lint message is the atom's text. Blue: it names the target and why.
- Cycle 2: no new finding.

## CB-3 — C05 skips what was not built; the guide says so (FR-5, FR-19, P-2, P-6)

### What changed

- `c05_import_direction.py`: zero violations and a `note` → SKIPPED with the note. A note never
  hides a violation (found in Phase 2: the first version checked the note first).
- `docs/dev_guides/language_support_guide.md`: the "static no-op violation array" advice is gone;
  each QA method ends as ran / did not run (shared `failed_*`) / not built (`note`, or `failed_*`
  with "not implemented"), never a bare zero.

### Red first

- P-2 `tests/integration/assurance/validation/test_c05_not_built.py`: real atom with the Kotlin and
  the Rust runner → `_hydrate_architecture` → C05. Both PASSED before the change.
- `test_code_rules.py`: note → SKIP (failed before), note with a violation → FAIL (failed against
  the first version), empty note → PASS (control).
- `tests/unit/test_language_guide_says_no_bare_zero.py`: both cases failed on the old guide.
- P-6 `test_qa_runner_tool.py::TestComplexityNotBuilt`: green on arrival (CB-1 built it); the CB-1
  mutant `ts-complexity-stub-clean` kills it (probe, one test protects it from this side).

### Proof

Mutant `c05-ignores-note` killed. Corpus: 10 mutants over FR-1..FR-5, all killed.
`check_fr_coverage.py TECH-087`: FR-1..FR-5 and FR-19 carried and cited; FR-6..FR-18 belong to
SF-02..SF-05.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) a note beside a violation would hide it. Fixed: the skip needs zero violations.
- R2 (LOW) a non-string note. Blue: `str(note)`; runners always set a string.
- R3 (LOW) `sw check` output for Kotlin projects changes from PASS to SKIP. Intended (FR-5,
  `[agreed 2026-10-29]`); the live demo in the design's Works For Real runs at closure.
- Cycle 2: no new finding.
