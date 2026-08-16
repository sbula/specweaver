# Implementation Plan: `sw usage --since` Crashes on Unparseable Input

- **Feature ID**: TECH-052
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-052/TECH-052_design.md
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-052/TECH-052_implementation_plan.md
- **Status**: APPROVED (2026-08-16)

**FRs owned: FR-1.** One commit boundary, one guard, four tests.

> **Proportionality.** A ten-line fix. The plan exists because `TECH-051` closed the same day with
> all seven FRs reading *carried by no implementation plan* — the gate is cheap to satisfy while the
> work is being done and expensive to reconstruct afterwards.

## Scope

`sw usage --since <value>` validates its input where the user can be told what is wrong, instead of
letting a `ValueError` or a SQLAlchemy `StatementError` reach the terminal.

## The boundary

**CB-1 — the guard.** `_parse_since()` in `infrastructure/llm/interfaces/cli.py`, called from the
command body before the async query is built.

Ordered checks, not code:

1. absent `--since` → `None`, unchanged;
2. `fromisoformat` raises → console error naming the option, the value and a valid example; exit 1;
3. parsed but `tzinfo is None` → console error naming the timezone requirement and two valid
   examples; exit 1;
4. otherwise return the parsed datetime.

**Tests** (`tests/unit/infrastructure/llm/interfaces/test_usage_commands.py`, unit tier — this is
one command's own input handling, no seam):

| Bucket | Test |
|---|---|
| Hostile | `not-a-date` → exit 1, no exception, output names `--since` and the value |
| Hostile | `16/08/2026` → the message carries a well-formed example |
| Hostile | `2026-03-27` → refused for having no timezone, and the output does **not** contain `StatementError` |
| Boundary | `2026-03-27T11:00:00+02:00` → still accepted, exit 0 |

**Done when** all four mutants are killed:

| Mutant | Neutralise | Must kill |
|---|---|---|
| M-1 | `except ValueError` → `except ZeroDivisionError` | the two unparseable tests |
| M-2 | `if parsed.tzinfo is None:` → `if False:` | the naive test |
| M-3 | the example in the message → `"Bad value."` | the format test |
| M-4 | naive silently coerced to UTC instead of refused | the naive test |

M-4 is the one worth having: it is the *plausible* alternative implementation, and a test that
only checked "exit 1 on bad input" would pass with it in place.

## Out of scope

- The other two `fromisoformat` call sites. Both read values this system wrote, so a bad value is a
  data-integrity problem rather than user input — confirmed by reading them, not assumed.
- Accepting relative forms like `7d` or `yesterday`. A feature, and this is a fix.
- Assuming UTC for a naive value. Rejected in design: it mis-filters by up to a day at the boundary
  and the user cannot see it happen.
