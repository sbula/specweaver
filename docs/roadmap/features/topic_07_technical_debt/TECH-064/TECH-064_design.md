# Design: Polyglot Architecture Checks Report Success Where They Do Nothing

- **Feature ID**: TECH-064
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-19
- **Origin**: found 2026-08-18 while writing the `INT-US-20` P-5 journey test. Measurements:
  [`docs/analysis/polyglot_dependency_resolution_2026-08-18.md`](../../../../analysis/polyglot_dependency_resolution_2026-08-18.md)

## Problem Statement

Three delivered code paths answer an architecture question with "nothing wrong here" when what they mean
is "I did not look". Each is small; together they are the reason a polyglot repository can pass an
architecture review that never ran.

**1. Kotlin import extraction returns nothing.** `KotlinAnalyzer.extract_imports` returned an empty list
for two valid samples — one with a package declaration, one without. It does not raise; the file simply
reports that it imports nothing.

The silence propagates. Archetype inference reads the imports, finds none, and classifies the module
`pure-logic`. **Missing data becomes a confident wrong answer**, and the wrong answer is an architectural
classification that downstream consumers trust.

**2 and 3. Kotlin and Rust `run_architecture_check` are stubs that return success.**

```python
"""Run architectural checks (Deferred to Feature 3.20b)."""
return ArchitectureRunResult(violation_count=0, violations=[])
```

"Deferred" is honest in a docstring and dishonest as a return value. A caller cannot distinguish *checked,
nothing wrong* from *not implemented* — they are the same object. Every other unsupported path in this
codebase degrades explicitly; `NoOpLimiter` logs that limits will not be enforced, and the QA runner's
absent-toolchain path is a tested behaviour rather than a clean result.

## Why this is not deferred to `B-SENS-07`

`B-SENS-07` will replace how the verdict is reached. These three are wrong *now*, on the current code, and
the rule is that a live defect does not wait for an unbuilt feature. A Kotlin repository scanned today
records the wrong archetypes and passes an architecture check that did not happen.

The Kotlin extraction defect is also **upstream of `B-SENS-07`, not superseded by it**: any resolver still
needs the parser to produce imports in the first place. Fixing it makes `B-SENS-07` cheaper rather than
redundant.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Kotlin imports are extracted | `KotlinCodeStructure` | queries the parsed tree for import statements | the imports a file declares are returned, so archetype inference reads data rather than silence |
| FR-2 | A runner may decline, but not silently | Any language runner | returns an architecture result without examining anything | the result carries a `note` saying the check did not run, and a guard fails any runner whose body is one bare return without one |
| FR-3 | The decline reaches the caller | The QA atom | reports the result of an architecture intent | the message says the check did not run and the note is in `exports`, instead of "No architectural violations" |

## What was found on re-measurement

The ticket recorded that `KotlinAnalyzer.extract_imports` *"returned an empty list"* and *"does not
raise"*. Measured 2026-08-19, it **raises**: `tree_sitter.QueryError: Invalid node type at row 0,
column 10: import_header`. The Kotlin grammar shipped here emits `(import)`; `import_header` is
Kotlin's own spec vocabulary and not a node type.

The empty list was real but one layer up. `TreeSitterAnalyzerBase.extract_imports` wraps the call in
`except Exception` and logs at DEBUG, so the crash became `[]`, and `infer_archetype` turns `[]` into
`pure-logic`. Three things had to be true for the wrong archetype: a wrong node name, a broad catch,
and a heuristic that reads absence as evidence. Only the first is repaired here — the other two are
what made a one-word error invisible for as long as it was, and that is worth saying rather than
fixing quietly.

**A fourth instance was suspected and cleared.** The first draft of FR-2's guard matched any runner
returning an empty result and flagged `JavaRunner` too. Its `if not forbids: return ...` is the true
answer when a project declares no boundaries — it looked, and there was nothing to violate. The
guard now keys on an *unconditional* return, which is what "declined without looking" actually looks
like.

## Verifiable Proof

| FR | Test |
|---|---|
| FR-1 | `tests/unit/workspace/ast/parsers/kotlin/test_kotlin_codestructure.py::TestExtractImports` — four tests; reverting the query to `(import_header)` fails all four |
| FR-2 | `tests/unit/sandbox/language/core/test_architecture_check_honesty.py::test_a_runner_that_declines_the_check_says_so` — dropping Kotlin's `note=` fails it |
| FR-3 | `tests/unit/sandbox/language/core/test_architecture_check_honesty.py::TestTheAtomSurfacesTheDecline` — forcing the atom's `if result.note` branch false fails it |

## What is knowingly not covered

**Whether declining should fail the pipeline step.** `TECH-064` named this as the decision worth
taking deliberately, and it is still open: FR-2 and FR-3 make the decline *visible*, which is what
"a caller cannot distinguish the two" asked for. "Fail the step" and "skip the step loudly" remain
different products, and the guard passes under either — so choosing later costs nothing now.

**Implementing architecture enforcement for Kotlin and Rust** stays `B-SENS-07`'s, unchanged from
the Non-Goals below. This ticket makes their absence legible; it does not fill it.

**The broad `except Exception` in `TreeSitterAnalyzerBase`.** It turned a crash into a wrong answer
and it is still there. Narrowing it is a change to a shared base class that every language parser
runs through, which is its own scope with its own blast radius.

## Candidate Approaches (as filed)

- **Kotlin extraction**: find why the tree-sitter query yields nothing for `import` statements. Compare
  against the Java parser, which works on structurally similar input. Likely a query or node-type
  mismatch rather than a design problem.
- **Unsupported must not look like clean.** Return a distinct outcome — an explicit "unsupported" status,
  or a raised typed error — so a caller cannot read silence as approval. This is the decision worth taking
  deliberately: it changes what a pipeline step does when it meets Kotlin or Rust, and "fail the step" and
  "skip the step loudly" are different products.
- **A guard against the class, not the instances.** Three separate paths had the same shape. A test that
  asserts every language runner either performs a check or reports that it cannot would stop a fourth.

## Non-Goals

- **Not** implementing architecture enforcement for Kotlin and Rust. That is `B-SENS-07`'s to answer, and
  answering it here would build a fourth per-language mechanism — the thing that capability exists to stop.
- **Not** the `context.yaml` → `tach.toml` generation defects. Those belong to `B-SENS-07`.
- **Not** `consumes` versus `forbids`. Same reason.

## Delivery

Delivered 2026-08-19 in one commit. The Kotlin parser was the plain bug with the plain fix, as the
filing predicted; the two stubs needed no design either, once the question was narrowed from *what
should Kotlin enforce* to *what must a runner say when it enforces nothing*.
