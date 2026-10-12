# D-VAL-05 — Code Validation Rules (C01–C08)

**Status**: ✅ Finished — signed off by the user 2026-10-12. · **Phase**: 1 (Step 5)

| | |
|---|---|
| Touches | `assurance/validation/rules/code/` · `core/flow/handlers/validation_hydrator.py` · the language QA runners |
| Uses | `E-VAL-01` (the engine) · `D-VAL-03` (the QA runners) · `sw scan` (writes `tach.toml`) |
| Plan | [as built](D-VAL-05_implementation_plan.md) |

## What it does

`sw check <file> --level code`, and the validate step of `sw implement` and `sw run`, check a code
file mechanically before any model judges it. The flow layer runs the file's own test, its
coverage and the architecture check, and hands the results to the rules as data; the rules decide.

## Functional Requirements

| # | FR | Rule | Action | Outcome |
|---|-----|------|--------|---------|
| FR-1 | Syntax | C01 | SHALL fail a file the Python parser rejects, naming the line | broken code stops first |
| FR-2 | Test exists | C02 | SHALL fail a file with no `tests/**/test_<stem>.py` | no untested code passes |
| FR-3 | Test passes | C03 | SHALL run the file's test with the file's folder on the import path, and fail when it fails or cannot run `[agreed 2026-10-12]` | a generated test that imports its module by name runs in any project |
| FR-4 | Coverage | C04 | SHALL fail when the file's own coverage is below the threshold (default 70%), and warn when the language's runner does not measure it | coverage is of the file, never a guess |
| FR-5 | Import direction | C05 | SHALL fail an import that `context.yaml` forbids or `tach` refuses; without `tach.toml`, SHALL fail and say to run `sw scan` `[agreed 2026-10-12]` | layering holds; a missing setup says how to fix it |
| FR-6 | No bare `except` | C06 | SHALL warn on a bare `except:` | errors are not swallowed silently |
| FR-7 | No orphan TODO | C07 | SHALL warn on a TODO/FIXME | unfinished code is visible |
| FR-8 | Type hints | C08 | SHALL fail a function without type hints | interfaces are explicit |

## Accepted limits

- C01, C06 and C08 read Python only; an archetype's own pipeline leaves them out for other
  languages (`B-INTL-01`).
- Only the Python runner measures coverage; Java, Kotlin, TypeScript and Rust report it as not
  measured, so C04 warns there.

## Live demo

A project as `sw init` leaves it, then `sw scan`: `src/good.py` with `tests/test_good.py`
(`from good import add`) passes C01 to C08 and C04 reports 100%. One file per mistake — a syntax
error, no test, a failing test, low coverage, a forbidden import, a bare `except`, a TODO, no type
hints — fails or warns on its own rule. Before `sw scan`, C05 says to run it.
`tests/e2e/capabilities/assurance/test_code_rules_on_a_fresh_project_e2e.py` does exactly this.
