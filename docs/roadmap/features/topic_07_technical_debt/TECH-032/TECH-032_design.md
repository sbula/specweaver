# Design: The Non-Python QA Runners Report an Absent Toolchain as Success

- **Feature ID**: TECH-032
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found 2026-08-12 during `TECH-031`, which fixed the same defect in the **Python**
  runner. `TECH-031`'s own Non-Goals admit the non-Python runners *"unless the design finds the
  same assumption in them"* — the design looked, and found the symptom but not the cause, so this
  is filed separately rather than absorbed.

## Problem Statement

A QA runner whose tool is not installed returns a **clean result** instead of an error. The
subprocess exits non-zero with empty stdout, the parser sees nothing to report, and "nothing to
report" is indistinguishable from "nothing wrong". **The gate certifies a run that never
happened** — a vacuous proof inside the mechanism whose whole purpose is to prevent them, in the
same family as `TECH-017`.

### Measured, 2026-08-12

Probed by injecting `exit_code=127, stdout="", stderr="command not found"` into each runner's
executor and reading the returned result. **13 paths report success:**

| Runner | Silent-pass paths | Count |
|---|---|---|
| `JavaRunner` | `run_tests`, `run_linter`, `run_complexity`, `run_architecture_check` | 4 |
| `RustRunner` | `run_tests`, `run_linter`, `run_complexity`, `run_compiler` | 4 |
| `KotlinRunner` | `run_tests`, `run_linter`, `run_complexity` | 3 |
| `TypeScriptRunner` | `run_architecture_check`, `run_compiler` | 2 |

`TypeScriptRunner.run_compiler` is the sharpest case: it **has** a guard —
`except FileNotFoundError` — and the guard is dead, because `SubprocessExecutor` returns
`exit_code=127` rather than raising. A guard that tests the wrong thing reads as coverage while
providing none, exactly like the `shutil.which("tach")` host-PATH check `TECH-031` found.

### Why this is not `TECH-031`

`TECH-031`'s root cause is the container prepare phase: `uv sync` fails to produce a usable venv,
so the tools are genuinely absent. **The non-Python runners never go through that phase** — they
resolve their toolchains without `uv`. Same symptom, unrelated cause. Folding them together would
have attached six other languages' fixes to a container ticket that cannot explain them.

## Candidate Approaches (not yet designed)

- **Reuse the helper, which is already language-agnostic.** `did_not_run(result, tool)` in
  `sandbox/language/core/python/toolchain.py` takes a `SubprocessResult` and a tool name and has
  nothing Python-specific in it. It should move somewhere shared and be called from every runner.
  Its one non-obvious property is worth preserving deliberately: **the discriminator is empty
  stdout, not the exit code** — keying on the exit code broke `sw implement`, because pytest exits
  4 for a `tests/` directory that does not exist yet, having run correctly. Per-language exit-code
  conventions differ; "printed nothing at all" does not.
- **Ship the guardrail with the fix.** A parameterized test across every registered runner and
  every QA method, asserting an absent toolchain is reported. Without it a sixth language regrows
  this on day one, which is how it reached four runners in the first place.

## Non-Goals (proposed, pending design)

- **Not the `STUB` methods.** `TypeScriptRunner.run_tests` / `run_linter` / `run_complexity`, and
  `KotlinRunner` / `RustRunner`'s `run_architecture_check`, return zeros without calling the
  executor at all. That is unimplemented, declared as such, and a different conversation — but it
  does mean **a parameterized guardrail cannot simply assert over every method** without deciding
  what a stub should return. Deciding that is in scope; implementing the stubs is not.
- **Not** the Python runner — `TECH-031` fixed its four paths (`run_tests`, `run_linter`,
  `run_complexity`, `run_architecture_check`).
- **Not** the container prepare phase (`TECH-031`).

## Execution constraint

One runner per commit, never bundled into a feature commit — the same rule as `TECH-016`. Each
runner's fix is independently testable and there is no reason to couple them.

## Next Step

Run through `specweaver-design`. Establish first **where the shared helper should live** so that
`commons/qa.py`'s consumers and all five language runners can reach it without a boundary
violation — `tach check` decides this, not preference.
