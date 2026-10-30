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
