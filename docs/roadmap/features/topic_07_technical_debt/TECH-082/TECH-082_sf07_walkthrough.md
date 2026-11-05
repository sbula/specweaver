# Walkthrough: TECH-082 SF-07 — Skipped rules are counted

## CB-1: one summary for `sw check` and `POST /check` (FR-13, FR-14, NFR-1, NFR-2, NFR-4)

**What changed**
- New `assurance/validation/summary.py` (pure): `summarize(results, *, strict) -> Summary` with
  `passed`, `failed`, `warned`, `skipped`, `total` and a `Verdict` (`FAILED`,
  `PASSED_WITH_WARNINGS`, `ALL_PASSED`, `NOTHING_CHECKED`); `Verdict.fails` is true for `FAILED` and
  `NOTHING_CHECKED`. It joins the module's `exposes` and tach's interfaces.
- `sw check` (`_print_summary`): each line adds `(N skipped)` when N > 0; no rule judged prints
  `NOTHING CHECKED: N skipped` and exits 1, strict or not. Lines with no SKIP row are unchanged.
  The line comes from the non-strict verdict, so `--strict` with a warning still prints
  `PASSED with warnings` and exits 1, as before.
- `POST /api/v1/check`: `_check_response(results, strict=…)` builds the envelope from the same
  summary; `CheckResponse` gains `skipped`; `overall` is `NOTHING_CHECKED` when no rule judged, before
  the strict rule. HTTP status stays 200.
- Found in dev: the executor's run log counted every non-FAIL as passed (`2 rules, 2 passed` for a
  SKIP and a PASS). It now logs all four counts from `summarize`.
- Test edit (FR-13 behaviour): `test_cli_helpers.py::test_empty_results_no_exit` →
  `test_empty_results_exit_1`.
- Docs: `2_drafting_effective_specs.md` (the lines, the exit codes, the API fields),
  `1_installation_and_setup.md` (an all-skip code check exits 1), `.agents/STATE.md` (the "Still
  missing" line is gone), the design's guide row.

**Tests**
- `test_summary.py` (13), red first (no module): counts per status; every verdict; strict; empty;
  all-skip; NOTHING_CHECKED wins over strict; which verdicts fail.
- `test_check_summary.py` (9), red first (7 failed: no suffix, `ALL PASSED` exit 0 for all-skip and
  empty): every line and exit code of the F-2 table, with and without SKIP rows.
- `test_check_counts_skipped.py` (4, integration, P-2), red first (`KeyError: 'skipped'`, `PASS`): a
  real app, project and pipeline holding only C01; a Kotlin file is `NOTHING_CHECKED` with
  `skipped` 1, also under `strict`; a Python file is `PASS` with `skipped` 0; the CLI's line and the
  API's `overall` agree for four result sets.
- `test_nothing_checked_e2e.py` (2, e2e, P-1), red first (`ALL PASSED`): `sw check` on the Kotlin
  file prints `NOTHING CHECKED: 1 skipped` and exits 1; the Python control passes with no skip.
- `test_validation_executor.py::test_the_run_log_counts_a_skip_as_skipped`, red first (`2 passed`).

**Mutants**
- 1 stale (TECH-077 FR-4 `check-ignores-profile`) re-run before the refresh: OBJECTED. 0 stale.
- TECH-082 FR-13 (3) and FR-14 (2), all OBJECTED: `all-skip-passes` (10 tests), `skip-not-counted`,
  `nothing-checked-exits-zero`, `api-skipped-zero`, `strict-ignores-warnings`.

**Coverage matrix**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `summarize`, `Verdict.fails` | ✅ | ✅ through both doors | ✅ |
| `_print_summary` | ✅ | ✅ agreement test | ✅ `test_nothing_checked_e2e.py` |
| `_check_response`, `CheckResponse.skipped` | ✅ `test_validation.py` (existing envelope) | ✅ `test_check_counts_skipped.py` | — |
| executor run log | ✅ | — | — |

Composition: the CLI and the API each call `summarize` once; the e2e and the integration test drive
each door end to end. Agreement: the agreement test checks the CLI's line and the API's `overall`
come from one verdict.

**Architecture**: `summary.py` imports only `models`; both doors already depend on
`specweaver.assurance.validation`. `tach check` passes; `exposes` equals tach's interfaces.

**Red/blue (7.5)**, 2 cycles
- R1 (MEDIUM, fixed) The executor's log called a SKIP "passed", the same defect one level down. It
  now logs four counts.
- R2 (LOW) An all-skip spec or feature check also exits 1 now; FR-13 names `sw check`, and the guide
  says so (plan R1).
- R3 (LOW) The CLI line comes from the non-strict verdict while the API's `overall` uses strict. Same
  as before: the CLI shows `PASSED with warnings` and exits 1; the API says `FAIL`.
- R4 (LOW) `test_validation.py` asserts only that `overall` exists; the new integration test pins the
  values.
- Cycle 2: challenged R3 (do the doors disagree under strict?): the exit code and `overall` both
  fail; only the CLI's wording keeps the warning visible, by design of the existing line. No new
  finding above LOW.
