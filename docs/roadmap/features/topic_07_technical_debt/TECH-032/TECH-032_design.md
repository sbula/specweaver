# Design: The Non-Python QA Runners Report an Absent Toolchain as Success

- **Feature ID**: TECH-032
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-12 — see §Delivery.
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

## Delivery, 2026-08-12

### Demonstrated against a real toolchain, not a mock

The toolchains were installed on the Linux box the same day, which is what made this provable
rather than merely arguable. With a real `SubprocessExecutor`, `JavaRunner.run_tests` returns
**byte-identical** `passed=0 failed=0 errors=0` whether or not `javac` is on `PATH`. There is no
value a caller can inspect to tell "the toolchain is missing" from "everything passed".

That is not a hypothetical on this machine: the toolchains live under `~/.sdkman` and `~/.cargo`
and are **not** on a fresh shell's `PATH`, so the mistake is a daily one. Recorded in the testing
guide alongside the `.venv/bin` lesson.

### The count was 12, not 13

The ticket's measurement was one high. Re-measured with the executor-called check applied,
**12 paths** report success on an absent toolchain — `java.run_architecture_check` does not reach
the executor and so was never one of them.

### What shipped

`did_not_run` moved from the Python runner to `sandbox/language/core/toolchain.py`, joined by five
result factories — `failed_tests`, `failed_lint`, `failed_complexity`, `failed_architecture`,
`failed_compile`. Factories rather than a literal at each site so the reported shape cannot drift
between languages, which is how Python ended up the only runner reporting it at all.

Guards applied across Java, Kotlin, Rust and TypeScript. **The discriminator is unchanged from
`TECH-031`: empty stdout, not the exit code.**

### The guardrail is a census, not a list

`tests/unit/sandbox/language/core/test_absent_toolchain_is_reported.py` enumerates every
`(runner, method)` that actually shells out and asserts each reports a problem — so a **new**
language cannot arrive with the defect intact, which is how it reached four runners.

**The census caught itself failing.** Its first version probed with a nonexistent `cwd`; the
TypeScript methods raised while writing their config there, were skipped as "unreachable", and
silently dropped out of the parametrisation. Two paths vanished and the suite stayed green — the
exact failure this ticket exists to remove, reproduced inside its own guardrail. Discovery now uses
a real temporary directory, and a separate assertion fails if any runner disappears from the
census.

### Two things found on the way

- **The ratchet from `TECH-023` earned itself.** The guards pushed three `run_tests` methods over
  the complexity ceiling, and the ratchet blocked the commit rather than letting them through.
  Fixed by extraction — Java's JUnit harvest, Kotlin's build-tool table, Rust's JUnit tally — plus
  a shared `sarif.py` for the PMD/detekt walk that Java and Kotlin had duplicated line for line.
- **A latent Rust bug, fixed.** `TestFailure(name=...)` — the field is `nodeid`. Every failing Rust
  test raised `TypeError`, the bare `except` swallowed it, and the run reported a flat `failed=1`
  instead of the real tally. Pre-existing; surfaced only because moving the loop to module scope
  let `mypy` see it. **This is a behaviour change beyond the ticket's stated scope**, taken because
  leaving a guaranteed `TypeError` in place would have been worse.

### Out of scope, unchanged

The declared `STUB` methods that never call the executor — TypeScript's `run_tests`/`run_linter`/
`run_complexity`, and Kotlin/Rust's `run_architecture_check`. They are unimplemented, not broken,
and the census skips them explicitly rather than counting them as passing.

Full suite 6474 passed, `mypy` clean, and **`quality.py cb` reports 0 failed of 12** — all twelve
gates green, `class_health` included.

## Next Step

Done.