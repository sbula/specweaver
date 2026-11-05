# Implementation Plan: Domain Logic Lives in the Flow Engine [SF-07: Skipped rules are counted]
- **Feature ID**: TECH-082
- **Sub-Feature**: SF-07 — Skipped rules are counted
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-07
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf07_implementation_plan.md
- **Status**: APPROVED

## Scope

`sw check` and `POST /api/v1/check` count skipped rules and never call a run where no rule judged
"passed". FRs: **FR-13, FR-14**. NFRs carried: NFR-1 (FR-13/FR-14 change behaviour by design),
NFR-2. Kind: `refactor` (the ticket's kind; these two FRs are its agreed behaviour fix). Depends on
SF-01 (committed: `execute_validation_flow` lives in `assurance/validation/orchestration`).

Today (re-measured 2026-11-05):

- `_print_summary` (`assurance/validation/interfaces/cli.py:71-96`) counts FAIL and WARN only. No
  FAIL and no WARN prints `ALL PASSED` and exits 0, even when every row is SKIP or there is no row.
- `run_check` (`interfaces/api/v1/validation.py:123-136`) counts PASS, FAIL, WARN; `overall` is
  `FAIL`, `WARN` or `PASS`, so an all-skip run is `PASS`. `CheckResponse` (`schemas.py:89-97`) has
  no `skipped`.
- The two count the same results twice, with two rule sets that already differ (the API counts
  PASS, the CLI does not).
- `Status` has four values: `PASS`, `FAIL`, `WARN`, `SKIP` (`models.py:30-36`).
- Summary strings in tests: 9 assertions in 5 files (design §Research); all check `PASSED with
  warnings`, `ALL PASSED` or `FAILED` as substrings, so a `(N skipped)` suffix keeps them true. Only a
  test that expects an all-skip run to pass changes, and that is FR-13's behaviour change.
- No guide quotes a summary line; `1_installation_and_setup.md:336` describes the SKIP rows.

## Findings reviewed by the user (Phase 4)

None needed a choice: the design fixed the strings, the exit code and the `overall` value
`[agreed 2026-11-02]`. The user accepted F-1..F-6 as written `[agreed 2026-11-05]`.

### F-1 (HIGH) One summary, used by both doors

New `assurance/validation/summary.py` (pure): `summarize(results, *, strict) -> Summary`, a frozen
dataclass with `passed`, `failed`, `warned`, `skipped`, `total` and a verdict
(`FAILED` / `PASSED_WITH_WARNINGS` / `ALL_PASSED` / `NOTHING_CHECKED`). The CLI prints from it and
exits from it; the API maps it to `CheckResponse`. One count, so the CLI and the API cannot disagree
again. `assurance/validation` is `pure-logic`; this is a count over values, no I/O. It joins the
module's `exposes` and tach's `[[interfaces]]` (`summary`, `summary.Summary`, `summary.summarize`),
which `test_validation_context_exposes.py` keeps equal.

### F-2 (MEDIUM) The CLI lines

Following the design's example `ALL PASSED (3 skipped)`, every line gets the same suffix when
N > 0, and none when N = 0 (today's lines stay byte for byte):

| Verdict | Line | Exit |
|---|---|---|
| a FAIL | `FAILED: 2 rule(s) failed, 1 warning(s) (3 skipped)` | 1 |
| a WARN, no FAIL | `PASSED with warnings: 1 warning(s) (3 skipped)` | 0, or 1 with `--strict` / a strict DAL |
| only PASS and SKIP | `ALL PASSED (3 skipped)` | 0 |
| no PASS, FAIL or WARN | `NOTHING CHECKED: 3 skipped` (also `0 skipped` for no result) | 1 |

`NOTHING CHECKED` wins over `--strict`; both exit 1.

### F-3 (MEDIUM) The API

`CheckResponse` gains `skipped: int`. `overall` is `NOTHING_CHECKED` when no rule judged, before the
strict rule; otherwise as today. HTTP status stays 200: a check that ran and judged nothing is a
result, not a request error. `passed` keeps meaning PASS rows.

### F-4 (MEDIUM) Proof tiers

- Unit: `summarize` (every verdict, strict, empty, all-skip), the CLI lines and exit codes
  (`CliRunner`), the API mapping.
- Integration (P-2, the API door): `POST /api/v1/check` through the real app and the real validation
  pipeline, on a project whose local pipeline holds only a rule that skips → `NOTHING_CHECKED`,
  `skipped` = 1. Plus an agreement test: the same results give the CLI's verdict and the API's
  `overall` from one `Summary`.
- E2E (P-1): `sw check --level code --pipeline only_skips` in a temporary project (isolated home, as
  the other `sw check` e2e tests do) → `NOTHING CHECKED: 1 skipped`, exit 1. The project-local
  pipeline (`.specweaver/pipelines/only_skips.yaml`, `pipeline_loader.py:77`) holds C13, which skips
  without a `protocol_schema` (`test_contract_drift_reaches_the_check_e2e.py:167-173`).
- Each is written red first: today the CLI prints `ALL PASSED` and exits 0; the API says `PASS`.

### F-5 (LOW) One commit boundary

The two FRs share `summarize`; the change is about 60 lines of source. One boundary, which closes
SF-07 (HITL).

### F-6 (LOW) Out of scope

- Other places that print a validation summary inside a run (`sw implement`'s report, the drafting
  CLI) list rows and print no verdict line; the flow's validate steps gate on FAIL, not on a summary.
  FR-13 and FR-14 name `sw check` and `POST /check`.

### Phase 3 (architecture), no violation

| Mechanism | `summary.py` |
|---|---|
| I/O & state | none |
| Execution | none |
| LLM | none |
| Dependencies | `models` (same module) |
| Domain | validation results (module purpose) |

The CLI (`assurance/validation/interfaces`) and the API (`interfaces/api`) already depend on
`specweaver.assurance.validation` in `tach.toml`; no edge is added; no cycle.

## Decisions (no user choice needed)

### D-1 Mutants

New campaign TECH-082 FR-13 / FR-14: `skip-not-counted` (the suffix drops), `all-skip-passes`
(`NOTHING_CHECKED` never chosen), `strict-beats-nothing-checked`, `api-skipped-zero`. Stale ones
after the green step: re-run, refresh only those that still object.

### D-2 Documents

- `docs/user_guides/2_drafting_effective_specs.md`: the summary lines, the exit codes, `NOTHING
  CHECKED` (the design's guide row).
- `docs/user_guides/1_installation_and_setup.md:336`: a file where every rule is SKIP now exits 1.
- No guide describes `CheckResponse`; the OpenAPI schema comes from the model, so `skipped` appears there by itself.
- `.agents/STATE.md` "Still missing": the `sw check` SKIP line goes (this SF delivers it).
- README test counts at feature close (not here).

## Path List rows this SF owns

| Row | Tier | Written |
|---|---|---|
| P-1 `sw check <file>` → … → printed table and summary | e2e | CB-1, red first |
| P-2 `POST /api/v1/check` → … → response | integration | CB-1, red first |

## Commit Boundaries

### CB-1 (closes SF-07, HITL): skipped rules are counted — FR-13, FR-14

| # | Task | Files |
|---|---|---|
| T1 red | `tests/unit/assurance/validation/test_summary.py`: every verdict; strict; empty; all-skip; suffix only when N > 0 | tests |
| T2 red | CLI lines and exits (`CliRunner`, F-2); API mapping (`skipped`, `NOTHING_CHECKED`, strict order) | CLI and API unit tests |
| T3 red | integration P-2 and the agreement test; e2e P-1 | `tests/integration/interfaces/api/…`, `tests/e2e/capabilities/assurance/test_nothing_checked_e2e.py` |
| T4 green | `summary.py`; `_print_summary` and `run_check` use it; `CheckResponse.skipped`; exposes and tach interface | as listed |
| T5 | tests that expected an all-skip or empty run to pass follow FR-13 (below); mutants (D-1); docs (D-2) | |

T5's known test: `tests/unit/interfaces/cli/test_cli_helpers.py::test_empty_results_no_exit` (no
result now exits 1); the full suite names any other.

**Done when**: every new test green after a recorded red; each FR-13/FR-14 mutant objects;
`stale_mutants.py` reports none.

## Research Notes

- `_print_summary(results, *, strict)` is called once (`cli.py:310`); `effective_strict` comes from
  `--strict` or the DAL (`cli.py:290`).
- `run_check` builds `overall` at `validation.py:126-129`; `body.strict` applies after.
- `RuleResult.status` is a `Status` (`StrEnum`); the API compares `.value` strings today.
- `tests/unit/assurance/validation/test_validation_context_exposes.py` pins `exposes` equal to tach.

## Red/Blue (Phase 5), 2 cycles

- R1 (MEDIUM, recorded) `_print_summary` serves every `sw check` level, so an all-skip spec or
  feature check also exits 1 now. FR-13 names `sw check`, not one level; the user guide says so.
- R2 (MEDIUM, checked) Does any repo script, skill or bundled pipeline run `sw check` and rely on
  exit 0? `grep -rln "sw check" scripts .claude .agents src/specweaver/workflows/pipelines`: only
  prose (`_mutate*.py` docstrings, `PROJECT.md`, `STATE.md`). None.
- R3 (LOW, fixed) `STATE.md` lists this defect under "Still missing"; D-2 removes the line in CB-1.
- R4 (LOW) `summary.py` must join both `exposes` and tach's interfaces in one edit, or
  `test_validation_context_exposes.py` fails; T4 says so.
- R5 (LOW) The CLI lines carry Rich markup; the tests strip ANSI codes, as the existing e2e tests do
  (`test_code_dal_strictness_e2e.py:131`).
- Cycle 2: challenged F-3 (should `NOTHING_CHECKED` be an HTTP error?): no; the request was valid and
  the check ran. Challenged F-2's suffix on the `FAILED` line (`… warning(s) (3 skipped)`): it follows
  the design's one example; every line has the same shape. No new finding above LOW.
