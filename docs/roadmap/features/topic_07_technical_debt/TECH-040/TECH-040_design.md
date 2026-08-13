# Design: `sw run --verbose` Is a Dead Flag

- **Feature ID**: TECH-040
- **Epic**: Topic 07 (Technical Debt)
- **Status**: 🟢 **DELIVERED 2026-08-13.** Approach 1 — implemented rather than removed.
- **Origin**: Found 2026-08-13 while fixing `TECH-017`'s vacuous-assertion findings — the test
  named `test_run_validate_only_verbose` asserted `exit_code in (0, 1)` under a docstring claiming
  *"produces detailed output"*, so the flag's deadness was invisible.

## Problem Statement

> [!IMPORTANT]
> **This ticket was filed with its headline overstated, and the correction matters.** It said
> `--verbose` "does nothing". It does: `flow/interfaces/cli.py` reads it on all three error paths
> and prints a full traceback, which is the promise `cli.py`'s own *"Run with --verbose for full
> traceback"* makes. That half always worked.
>
> What never worked is the half the **help text** describes — *"Show detailed handler output."*
> `RichPipelineDisplay` accepted `verbose`, stored it as `self._verbose`, and no code in `src/`
> read it. A repo-wide search returned exactly that one assignment.
>
> The overstatement came from grepping for `_verbose` and not for `verbose`. Recorded because a
> ticket that overstates its defect gets fixed in the wrong place.

Measured rather than inferred: running `sw run validate_only <spec>` with and without `--verbose`
produced byte-identical output once per-invocation noise was normalised away — run uuids, the short
`run abc12345` form, and Rich's `[HH:MM:SS]` column, which it prints on the first log line and
blanks thereafter. That third one made a naive comparison look like the flag worked, and is the
shape a lazy fix would also pass.

**Severity: low, but it is a lie in the CLI's own `--help`.** A user reaching for `--verbose` while
debugging a *successful-but-wrong* run — the case where there is no traceback to print — gets
nothing extra and no indication that the flag has nothing to give.

## Delivery, 2026-08-13

`_StepState` gained a `detail` field; `_on_step_completed` and `_on_step_failed` populate it from
`StepResult.output` when verbose; `_render` emits it as a second, dimmed row beneath the step.

Three judgements worth keeping:

- **A step with no output adds no row.** `--verbose` must add detail where detail exists, not add
  blank lines everywhere. Pinned by a test.
- **Values are truncated at 160 characters.** A step's output can carry a whole review verdict or a
  rule-result list, and a live-updating display that reflows on one long value is worse than one
  that elides it.
- **Detail is additive, not substitutive** — the step line survives. Also pinned, because the
  obvious implementation replaces the label.

Both commands that declare the flag benefit: `run_pipeline` and `resume` each build their display
through `_create_display(use_json=..., verbose=verbose)`.

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

`test_run_validate_only_verbose` was written as the test that SHOULD pass, marked
`xfail(strict=True)`. When the display was wired up it flipped to `XPASS(strict)` and failed the
suite — which is what signalled the marker could be removed. Exactly the sequence `TECH-021` used,
and the reason to prefer a strict xfail over a skip: it tells you when it is obsolete.

Five unit tests in `test_display.py` cover the quiet/verbose split, the no-output case, additivity,
and that the two renderings genuinely differ.
