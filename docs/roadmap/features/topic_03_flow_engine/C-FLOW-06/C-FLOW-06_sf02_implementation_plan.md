# C-FLOW-06 SF-02 — Impact-Aware Testing & DAL Enforcements

**Status**: FINAL — HITL Phase 4 Approved · **Feature ID**: 3.32d · **FRs owned**: FR-3 (this
plan); FR-2 is missing here — see [README_BEFORE_CONTINUE.md](README_BEFORE_CONTINUE.md) ·
**Depends on**: SF-01 · Design: [C-FLOW-06_design.md](C-FLOW-06_design.md)

## Changes

1. `src/specweaver/commons/enums/dal.py` — map `DALLevel` to a `strictness_level` or confidence
   threshold (`DAL_A` = absolute strictness, `DAL_E` = high tolerance). Add threshold helpers such
   as `is_strictly_enforced(dal_level: DALLevel) -> bool`.
2. `src/specweaver/core/flow/engine/runner.py` — `PipelineRunner` loads the target's `DALLevel` via
   `DALResolver` and puts it in the execution context, so handlers adapt strictness to the file's
   safety boundary.
3. `src/specweaver/interfaces/cli/validation.py` — `sw check` becomes **Fail-at-end**:
   - run the whole validation pipeline across all targeted files, not stop at the first failure;
   - aggregate warnings and errors into one final console report;
   - if any violation breaches the target's `DALLevel` strictness, exit non-zero
     (`typer.Exit(code=1)`) at the very end.
4. `tests/unit/interfaces/cli/test_cli_standards.py` — remove `TestScanCiMode`; the `--ci` flag was
   rejected in the architectural audit.

## Tests

`tests/unit/interfaces/cli/test_cli_validation.py`:

| Case | Expect |
|---|---|
| Fail-at-end | `sw check` reports all failures before exiting |
| `DAL_A` target with warnings | warnings become hard failures, `exit_code == 1` |
| `DAL_E` target with minor warnings | exits `0` |

## Decisions (audit)

- **DAL enforced in the runner, not behind `--ci`.** Hiding safety constraints behind a CLI flag is
  an anti-pattern. `DALResolver` bounds live in `PipelineRunner`, so strictness is the same on the
  developer's machine and the CI server.
- **Fail-at-end.** Developers should not fix errors one by one: complete the run, aggregate all
  violations, print one summary, then decide the exit code.
- **CLI verb debt.** The `sw scan` vs `sw check` confusion exposed debt in the CLI verbs. A backlog
  item isolates Discovery commands from Validation commands in a future refactor.
