# Design: Polyglot Architecture Checks Report Success Where They Do Nothing

- **Feature ID**: TECH-064
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
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

## Candidate Approaches (not yet designed)

- **Kotlin extraction**: find why the tree-sitter query yields nothing for `import` statements. Compare
  against the Java parser, which works on structurally similar input. Likely a query or node-type
  mismatch rather than a design problem.
- **Unsupported must not look like clean.** Return a distinct outcome — an explicit "unsupported" status,
  or a raised typed error — so a caller cannot read silence as approval. This is the decision worth taking
  deliberately: it changes what a pipeline step does when it meets Kotlin or Rust, and "fail the step" and
  "skip the step loudly" are different products.
- **A guard against the class, not the instances.** Three separate paths had the same shape. A test that
  asserts every language runner either performs a check or reports that it cannot would stop a fourth.

## Non-Goals (proposed, pending design)

- **Not** implementing architecture enforcement for Kotlin and Rust. That is `B-SENS-07`'s to answer, and
  answering it here would build a fourth per-language mechanism — the thing that capability exists to stop.
- **Not** the `context.yaml` → `tach.toml` generation defects. Those belong to `B-SENS-07`.
- **Not** `consumes` versus `forbids`. Same reason.

## Next Step

Run `specweaver-design`, starting from the Kotlin parser, since it is the one item that is a plain bug
with a plain fix and no scope question attached.
