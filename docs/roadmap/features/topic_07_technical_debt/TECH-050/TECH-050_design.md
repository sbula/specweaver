# Design: 28 Tests Fail Whenever an Agent Runs Them

- **Feature ID**: TECH-050
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-16 — scoped small enough that the three approaches below were decided at a grill rather than through the full design skill
- **Origin**: 2026-08-15, found while running the full suite at `TECH-049` SF-01 CB-1. The sibling of
  the `_mutate.py` defect closed the same day in `72b82df8` — same root cause, suite scale.

## Problem Statement

**Measured 2026-08-15, twice, on the same tree:**

| Environment | Result |
|---|---|
| `FORCE_COLOR=3` (any agent shell) | **28 failed**, 6940 passed, 11 skipped |
| `FORCE_COLOR` unset (a human at a terminal) | **0 failed**, 6968 passed, 11 skipped |

Same tests, same commit, 60 s each. The only difference is one environment variable.

**`FORCE_COLOR` is set by the agent harness**, not by this repo — Claude Code's Bash tool sets
`FORCE_COLOR=3`. Rich then emits SGR escapes even into a pipe, and a test asserting
`"Error: Unsupported MCP Target" in result.output` compares against
`"\x1b[31mError:\x1b[0m Unsupported MCP Target"` and fails.

**Pre-existing, not introduced.** Verified by running the same tests in a detached worktree at
`72b82df8^` — the commit before any of this work — where 8 of them fail identically.

### Blast radius

**28 failures across 14 files** — unit 14, integration 7, e2e 7. Concentrated in CLI-output tests;
the worst single file carries 8.

**Do not work from a list — regenerate it.** Any list committed here is stale the next time someone
touches a CLI string, and the whole point is that these failures are environment-dependent:

```bash
FORCE_COLOR=3 .venv/bin/python -m pytest -n auto -q --tb=no | grep '^FAILED'
```

Run it again with `env -u FORCE_COLOR` and the same command must print nothing. The difference
between the two runs **is** the work list, and it is the only definition that stays true.

### Why this matters more than 28 red dots

`CLAUDE.md` states the suite is green with **no accepted deltas** — *"a failure you see is a failure
you caused."* Under an agent that instruction is unfollowable: 28 failures are always present and
never anyone's fault, so the only workable habit becomes ignoring them. That is precisely the state
the "no accepted deltas" rule exists to prevent, and it also hides any real regression that lands in
those 14 files.

It is not hypothetical that this class of bug hides real defects. The same root cause in
`scripts/_mutate.py` made the mutation runner report **every mutant as `SURVIVED`** — a tool
manufacturing false confidence, invisible to a human because a pipe suppresses colour, and invisible
to its own 15 tests because every fixture was plain text.

### The colour is not the problem

200 Rich markups across 22 files in `src/` — `sw` is a human-facing CLI and colour is real UX, not
dead code. The defect is the **coupling**: 124 test files assert on CLI output, and the fragile ones
compare raw strings against output whose escapes depend on an environment variable no test declares.

This repo already solved the sibling problem. `tests/rendering.py::shows()` exists because Rich
soft-wraps at `COLUMNS`, so `result.output` could contain `orp\nhan.py` and a raw `in` check passed
or failed on terminal width. `TECH-017` found that **twice, both in the cited proof of a delivered
contract**. Colour is the same bug with a different trigger and has no equivalent helper.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Colour-tolerant matching | `shows` | The helper SHALL strip SGR escapes as well as squashing whitespace, so a needle split **inside** a token still matches | `0.1.0` is found in `v0.\x1b[1;36m1.0\x1b[0m`, which whitespace-squashing alone cannot do |
| FR-2 | Deterministic rendering | Suite | `tests/conftest.py` SHALL pin the suite colour-free by setting `NO_COLOR`, clearing `FORCE_COLOR`, and setting `PY_COLORS` — at import time, before any `Console` is constructed | Tests nobody has written yet inherit the guarantee without their author knowing it exists |
| FR-3 | The coloured path stays exercised | `sw` | An e2e SHALL run the shipped command as a **subprocess** with colour forced on and forced off, asserting escapes appear, do not appear, and never change the content | Pinning the suite colour-free cannot silently stop `sw` from colouring at all |

## Candidate Approaches (decided at the grill, 2026-08-16)

1. **Strip ANSI inside `shows()`, and route the 28 through it.** The helper already normalises
   whitespace for exactly this reason; escapes are the same class of noise. Both modes keep working,
   and the coloured path stays exercised. Cost: touching 14 files.
2. **Force `PY_COLORS=0` (or `NO_COLOR`) suite-wide in `conftest.py`.** One line, all 28 pass. But
   then **no test ever sees coloured output**, and a Rich markup regression becomes invisible —
   trading a loud failure for a silent blind spot, which is the trade this repo keeps refusing.
3. **Both, split by intent**: default the suite to colour-free, and add a small number of tests that
   deliberately force colour on to prove the CLI renders and degrades correctly.

**Chosen: 3, all three parts.** Approach 2's cost turned out smaller than this ticket first
claimed — none of the 28 asserts colour, and a malformed markup tag renders literally in colour-free
mode too, so content assertions still catch it. What decided it is the tests nobody has written
yet: approach 1 fixes the 28 that exist, while a conftest default protects every CLI test written
from now on. Approach 3 keeps the coverage approach 2 alone would lose.

The same belt-and-braces `scripts/_mutate.py` uses, and for the same reason: one guard is one
environment variable away from failing.

## Non-Goals (proposed, pending design)

- Removing or reducing colour in `src/`. It is deliberate UX.
- Re-fixing `scripts/_mutate.py` — closed in `72b82df8`.
- A general CLI-output snapshot framework. The failure is narrow and mechanical.

## The open question, answered

**Is `NO_COLOR` honoured by `sw` at all?** Yes — and it is now asserted rather than assumed.
Nothing in `src/` mentions it, so the behaviour comes from Rich rather than from us
(`rich/console.py:734`). `FR-3`'s e2e pins it from the outside: the shipped command emits no escapes
under `NO_COLOR=1` and does emit them under `FORCE_COLOR=3`, with identical content either way.
That was the *probably* which made this a ticket.

## Delivered

`FORCE_COLOR=3` full suite: **28 failures → 0**. Colour-free run unchanged at 0.

Two self-inflicted findings along the way, both caught by this repo's own gates:

- **The first attempt used `PY_COLORS=0` and fixed one test out of 28.** That is pytest's variable;
  Rich has never heard of it. Two consumers, two variables — the conftest now sets both and clears
  `FORCE_COLOR`, which would otherwise beat them.
- **The new test file was named `test_cli_rendering_helpers.py`**, and `R7` refused it: `helpers` is
  a grab-bag name that accretes anything. Renamed to `test_cli_output_matching.py`.

Four `--help` assertions that were failing on **wrapping** rather than colour were routed through
`shows()` at the same time — opportunistic, since they were in the blast radius.
