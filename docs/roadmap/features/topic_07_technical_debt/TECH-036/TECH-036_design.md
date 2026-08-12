# Design: Lineage Telemetry Takes Down a Lint Fix That Already Succeeded

- **Feature ID**: TECH-036
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
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

## Next Step

Run through `specweaver-design`. Settle first whether the fix adopts the guard-only or the
never-raises contract, and whether it lands before or inside `TECH-016` §2's tail extraction.
