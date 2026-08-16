# Implementation Plan: 28 Tests Fail Whenever an Agent Runs Them

- **Feature ID**: TECH-050
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-050/TECH-050_design.md
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-050/TECH-050_implementation_plan.md
- **Status**: APPROVED

**FRs owned: FR-1, FR-2, FR-3.** Single feature — no decomposition.

> **Proportionality.** A test-infrastructure fix. One commit boundary; the approaches were decided
> at a grill rather than through the full design skill.

## Research notes

Measured, not recalled.

| Fact | Evidence |
|---|---|
| `shows()` + strip-ANSI covers **every** observed shape; `shows()` alone covers only wrapping | executed against five real failure strings |
| Colour lands **inside** tokens: `SpecWeaver v0.1.0` renders as `v0.\x1b[1;36m1.0\x1b[0m`, so `0.1.0` splits in two | executed |
| **Rich never reads `PY_COLORS`.** It reads `NO_COLOR` and `FORCE_COLOR` | read `rich/console.py:734,970` |
| pytest reads `PY_COLORS` first in `should_do_markup` — a different consumer entirely | read `_pytest/_io/terminalwriter.py` |
| The CLI's `Console` is built at **module import** (`interfaces/cli/_core.py:37`), so a fixture cannot change its mind | read |
| No `tests/conftest.py` existed | `find` |

## Commit boundary — CB-1

**Delivers:** `shows()` strips ANSI (FR-1); `tests/conftest.py` pins the suite colour-free (FR-2);
a subprocess e2e proving `sw` colours and de-colours (FR-3). Plus the four `--help` assertions that
were failing on **wrapping** routed through `shows()` — opportunistic, not a sweep.

**Tests:**
- *unit* — `shows()` against every shape: plain, soft-wrapped, spaces in the needle, colour around a
  word, **colour inside a token**, and two absence cases so a tolerant matcher cannot match
  everything.
- *unit* — the environment is actually pinned, asked of Rich and of pytest separately.
- *e2e* — the shipped command as a **subprocess**, colour forced on and off, asserting escapes
  appear, do not appear, and never change the content.

**Done when** the measurement flips: `FORCE_COLOR=3` full suite goes from **28 failures to 0**, and
the colour-free run stays at 0.

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R-1 | Pinning colour off hides a renderer regression | FR-3's e2e is the whole answer; without it this trade would be unsafe |
| R-2 | A future test forgets `shows()` | FR-2 protects it anyway — that is why both halves exist |
| R-3 | The e2e passes because the CLI emits nothing at all | It asserts the *content* is identical in both modes, not merely that escapes differ |

## Out of scope

The 124 test files that assert on CLI output but do not currently fail. A `shows()` migration
across all of them is a separate concern from the colour class this ticket names.
