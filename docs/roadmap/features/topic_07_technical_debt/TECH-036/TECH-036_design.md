# Design: Lineage Telemetry Takes Down a Lint Fix That Already Succeeded

- **Feature ID**: TECH-036
- **Epic**: Topic 07 (Technical Debt)
- **Status**: **RESOLVED 2026-08-12 by `TECH-016` §2**, hours after being filed, and closed without
  its own implementation. `TECH-016` unified the `log_artifact_event` tail across all seven sites;
  a shared helper cannot ship a known defect, so `log_artifact_lineage` carries the `None` guard
  **and** the never-raises `try` by construction. See §Resolution.
- **Origin**: Found 2026-08-12 while measuring `TECH-016` §2's six write sites against the code.
  Not `TECH-016`'s subject — that ticket is serialization format and the duplicated write tail —
  so it is filed separately per the scope rules in `specweaver-ticket`.

## Problem Statement

`LintFixHandler._llm_fix` opens a telemetry session **without checking that a database exists**
(`src/specweaver/core/flow/handlers/lint_fix.py:333`):

```python
code_path.write_text(fixed_code + "\n", encoding="utf-8")   # <- the fix is now on disk

if artifact_uuid:
    from specweaver.core.flow.store import FlowRepository

    async with context.db.async_session_scope() as session:   # <- context.db may be None
```

`RunContext.db` is declared `db: Any = None` (`handlers/run_context.py:158`) and is populated only
by the CLI/API composition roots when telemetry is configured. So whenever no telemetry DB is
configured **and** the source file already carries a lineage tag, this raises
`AttributeError: 'NoneType' object has no attribute 'async_session_scope'`.

### Why it is worse than a crash

The raise happens **after** `code_path.write_text` — the corrected file is already durably on
disk. `execute` wraps the call in `except Exception` (`lint_fix.py:161`) and converts it to:

```python
return StepResult(status=StepStatus.ERROR, error_message=str(exc), ...)
```

So a lint fix that **succeeded** is reported as a failed step, and the reader is sent to the LLM
and the lint output rather than to the telemetry configuration. Paid-for work discarded, with the
diagnosis pointing at the wrong subsystem.

### It is the one site that does not follow the established pattern

Every other lineage tail in the same package guards or swallows:

| Site | Guard |
|---|---|
| `draft.py:204` | `if context.db:` |
| `draft.py:_log_lineage` | `if not context.db: return` |
| `decomposition_artifacts.py:137` | `if not context.db: return`, **plus** a `try/except` that never raises |
| `generation.py` | `if context.db:` |
| **`lint_fix.py:333`** | **none** |

`log_decomposition_lineage`'s docstring already states the rule this site violates, and states it
against exactly this failure mode:

> **Never raises.** Lineage is telemetry, and by the time it runs the decomposition has already
> been paid for with an LLM call and durably written to disk. Letting a DB problem propagate hands
> it to `execute`'s `except Exception`, which returns `ERROR` with no `output` — throwing the plan
> away.

That contract was written for the decomposition handler in response to a real CB-1 pre-commit
failure (2026-07-26) and never generalised. This ticket is the generalisation.

## Candidate Approaches (not yet designed)

- **Guard it like its four siblings** (`if not context.db: return`). Minimal, matches the
  surrounding code, fixes the reported defect and nothing else.
- **Adopt `log_decomposition_lineage`'s stronger contract** — guard *and* `try/except` with
  `logger.exception`, so a *configured-but-broken* database also cannot discard a completed fix.
  The `None` case is the one reproduced; the broken-DB case is the same class and currently
  unguarded at three of the five sites.
- **Extract the tail once** so there is a single place the contract lives. This overlaps
  `TECH-016` §2, whose corrected scope is exactly `ensure_artifact_tag` + the lineage event across
  all six sites — **sequence after it, or fold in deliberately**, but do not build a second helper.

## Non-Goals (proposed, pending design)

- **Not** a change to when lineage events are *emitted*, only to what happens when they cannot be.
- **Not** `TECH-016`'s serialization subject (`§1`, delivered) or its write-tail unification (`§2`).
- **Not** making `RunContext.db` non-optional. Running without telemetry is supported, and
  narrowing the type to force the issue is a much larger change than the defect warrants.

## Verification the design must specify

- A test that **plants the condition**: `context.db = None` with a tagged source file, asserting
  the step reports `PASSED` and the fixed file is on disk. Reading the guard is not verification —
  this defect exists today *because* four correct siblings made the fifth look right.
- The `RunContext.db` default is what makes the path reachable; if a fixture supplies a database by
  default, the test proves nothing. Assert the `None` explicitly rather than relying on the default.

## Execution Constraint

One commit, never bundled into a feature commit. Full suite green.

## Resolution, 2026-08-12

Closed by `TECH-016` §2's event-tail unification, not by separate work.

**Both open questions answered by construction.** The shared `log_artifact_lineage` adopts the
**never-raises** contract, not guard-only — of the seven sites it replaced, one had the guard *and*
the `try`, five had only the guard, and this one had neither, so guard-only would have left five
sites still able to discard finished work on a *configured-but-broken* database. And it landed
**inside** `TECH-016` §2 rather than after it: unifying a tail that contains a known defect would
have copied the defect into shared code.

**Verified to this ticket's own stated bar.** `test_a_fix_survives_having_no_telemetry_database`
plants `context.db = None` with a tagged source file and asserts `PASSED` with the fix on disk.
Probed against the pre-fix code:

```
'NoneType' object has no attribute 'async_session_scope'
assert <StepStatus.ERROR> == <StepStatus.PASSED>
```

**The first probe was invalid**, and it is worth recording: reverting the whole file to `HEAD` also
reverted `TECH-016`'s module rename, so the test failed with `ModuleNotFoundError` — right colour,
wrong cause. Reverting *only* the lineage tail produced the failure above. Same trap as
`TECH-035`'s first class-health probe.

**Why it was reachable.** `_make_context` in `test_lint_fix_handler.py` supplied a mock database
unconditionally, so every test in the file exercised the branch that works — the same shape as this
repo's other silent-check findings. `db` is now a parameter, defaulting to the mock so existing
tests are unchanged.

## Why this ticket still earned its ID

It was filed on the reading that `TECH-016` §2 would not touch the lineage tail. That reading was
wrong — the tail is §2's own scope — and correcting it is what closed this. The ticket is kept
rather than deleted because the *defect* was real, measured and reproduced, and the record of how
it was found and fixed is worth more than a clean-looking registry. It also names the missing test
that let it survive, which outlives the fix.

## The observable failure, carried down from the topic entry (2026-08-13, `TECH-044`)

`execute`'s blanket `except Exception` converts the `AttributeError` into
`StepResult(status=ERROR)` — so a lint fix that **succeeded**, and whose corrected file is already
on disk, is reported as a failed step. The reader is then sent to the LLM output and the lint
results rather than to the telemetry configuration that actually caused it.

