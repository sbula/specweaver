# Design: Polyglot Implementation Loop

- **Feature ID**: D-INTL-08
- **Epic**: Topic 04 (Intelligence)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: 2026-08-16, from the `ADR-003` retirement re-audit. `INT-US-03-SF01`
  (Multi-Language Test Support) had been retired into `D-VAL-03`, which is delivered and so cannot
  own an FR — the scope landed nowhere. Un-retired in `d0943c36`; this capability is where it lands.

## Problem Statement

**`D-VAL-03` shipped the runners. Nothing routes to them.**

`resolve_runner` (`sandbox/qa_runner/core/factory.py:38`) is genuinely polyglot: it sniffs
`package.json` → TypeScript, `Cargo.toml` → Rust, `build.gradle[.kts]` → Kotlin, `pom.xml` → Java,
and falls back to Python. `QARunnerAtom` reaches it, and `QARunnerAtom.language` is accepted and
then **ignored** — `_resolve_runner` forwards to the factory and discards the argument
(`atom.py:39-48`).

`sw implement` can never present it with a non-Python target, because the loop is Python-only at
three separate points. Measured 2026-08-16:

| Where | What is hardcoded |
|---|---|
| `workflows/implementation/interfaces/cli.py:244-245` | `code_path = src/{stem}.py`, `test_path = tests/test_{stem}.py` |
| `workflows/implementation/interfaces/cli.py:75,82,95` | the `lint_fix`, `run_tests` and `validate_code` step params repeat those two paths |
| `workflows/implementation/generator.py:103,162` | every generated artifact is tagged `"python"` |
| `workflows/implementation/generator.py:201` | the fence stripper only knows ` ```python ` |

There is no `--language` flag on `sw implement`, and nothing infers one from the project.

So a Rust or TypeScript project running `sw implement` gets Python paths, a Python-tagged artifact,
and a `run_tests` step pointed at a `tests/test_*.py` that will never exist. The polyglot runner is
never asked.

**This is a defect in delivered code, so it is a new ticket rather than an edit to `D-VAL-03`'s
entry** (`finished-stories-immutable`). `D-VAL-03` stays `✅`: it built what it promised, and its
FR table never claimed the implement loop.

### Why it stayed invisible

`check_fr_coverage.py` judges FRs somebody wrote. No FR anywhere claims *"`sw implement` runs the
target language's toolchain"* — `D-VAL-03`'s eight FRs are all "build runner X" — so no gate had
anything to compare against the code. The one artifact that did carry the claim was the
`INT-US-03-SF01` add-on, and it was retired into a delivered capability. The gate that now catches
that shape is `scripts/check_retirement_targets.py` (`ADR-003`, 2026-08-16 addendum).

## Candidate Approaches (not yet designed)

1. **Derive everything from a detected project language.** Reuse `resolve_runner`'s manifest
   sniffing as the single source of truth, and drive path derivation, artifact tagging and fence
   stripping from it. No new flag. Cheapest, and keeps one detection rule in one place — but gives
   the user no override in a heterogeneous workspace.
2. **An explicit `--language` flag, defaulting to detection.** Makes the polyglot path testable
   without constructing a whole foreign project, and makes `QARunnerAtom.language` mean something
   again instead of being accepted and discarded. Costs a CLI surface.
3. **A language profile object** carrying source dir, test dir, filename convention, fence tag and
   runner, resolved once per run and threaded through the pipeline builder. Most work; the only
   option that stops the same four hardcodings reappearing in the next workflow that generates
   files.

Not yet decided. Note that 1 and 2 compose — detection as the default, flag as the override — and
that whichever is chosen, the multi-step e2e is written **before** the wiring, so it fails because
the loop cannot handle the target rather than because the assertion is wrong.

## Non-Goals (proposed, pending design)

- **Building or changing any language runner.** All five exist and are unit-tested; this capability
  routes to them and nothing more.
- **Container support for non-Python toolchains.** `resolve_runner` already warns that container
  sandboxing is validated for Python only (`factory.py:24-34`); widening it is `B-EXEC-01` /
  `INT-US-09-SF01` territory, not this.
- **LLM prompt quality for non-Python generation.** Whether the model writes good Rust is a
  separate question from whether the loop can carry Rust at all.
- **Heterogeneous single-run targets** (a Python project with a Rust extension, both in one
  `sw implement`). `resolve_runner` sniffs one directory; multi-target is a later bite.

## Next Step

Run `specweaver-design D-INTL-08`. The design must decide between the three approaches above, and
name which languages the first bite covers — "all five" is a plausible answer only because the
runners already exist, and is still a scope decision rather than a default.

Consumed by the `INT-US-03-SF01` add-on group
(`docs/roadmap/topics/topic_08_integration/US-03_integration.md`), whose retirement becomes valid
once this capability exists to own the seam.
