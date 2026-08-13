# Design: `sw run --verbose` Is a Dead Flag

- **Feature ID**: TECH-040
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found 2026-08-13 while fixing `TECH-017`'s vacuous-assertion findings — the test
  named `test_run_validate_only_verbose` asserted `exit_code in (0, 1)` under a docstring claiming
  *"produces detailed output"*, so the flag's deadness was invisible.

## Problem Statement

`sw run --verbose` / `-v` is documented as **"Show detailed handler output."** It is declared on
two commands (`core/flow/interfaces/cli.py:167` and `:488`), threaded through `_create_display`,
and passed into `RichPipelineDisplay(verbose=verbose)`, which stores it:

```python
self._verbose = verbose      # display.py:99
```

**`self._verbose` is never read.** A repo-wide search for the name across `src/` returns exactly
one hit — that assignment. The flag changes nothing.

Measured, not inferred: running `sw run validate_only <spec> --project <dir>` with and without
`--verbose` produces byte-identical output once per-invocation noise is normalised away (run
uuids, the short `run abc12345` form, and Rich's `[HH:MM:SS]` column, which it prints on the first
log line and blanks thereafter). The last of those three is why an earlier naive comparison
appeared to show a difference — worth recording, since it is the shape that would make a lazy fix
look like it worked.

**Severity: low, but it is a lie in the CLI's own `--help`.** A user reaching for `--verbose` while
debugging a failing pipeline gets no more information and no indication that the flag is inert.

## Candidate Approaches (not yet designed)

1. **Implement it.** `RichPipelineDisplay` already receives step results; `--verbose` should render
   handler output/errors per step instead of the one-line status. Decide what "detailed" means —
   step stdout, the `StepResult.error_message`, or the full traceback the `except` path already
   suppresses behind *"Run with --verbose for full traceback"* (`cli.py:236`, which is itself a
   promise this defect breaks).
2. **Remove it.** Cheaper and honest, but the traceback message above already advertises it, so
   removal means changing that too.

(1) is preferred: something already tells the user to run with `--verbose` for a traceback.

## Guardrail to Ship With the Fix

`check_story_preconditions.py::check_no_dead_promises` already enforces "a field documented as
*(set by X)* must actually be written". This is the mirror image — **a constructor argument stored
and never read** — and the same detector shape would catch it. Consider widening that check rather
than adding a new one.

## Non-Goals (proposed, pending design)

- The `--json` flag, which is separately implemented and works.
- Redesigning `RichPipelineDisplay`'s non-verbose rendering.
- The `TECH-017` audit that surfaced this.

## Verification

`tests/e2e/.../test_pipeline_e2e.py::test_run_validate_only_verbose` is already written as the test
that SHOULD pass, marked `xfail(strict=True)` — the shape `TECH-021` used, so it flips to
`XPASS(strict)` and fails the suite the moment the flag is wired up, forcing the marker's removal.

## Next Step

Run the `specweaver-design` skill against this stub before any implementation.
