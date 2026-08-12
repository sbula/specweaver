# Design: Chronically Failing Class-Health Gate (23 Classes)

- **Feature ID**: TECH-035
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found 2026-08-12 during `TECH-023` batch 2. The gate fired for the first time in the
  session because that commit finally *changed* a file it covers — see "Why nobody had seen this".

## Problem Statement

`check_class_health.py` fails on a **clean tree**: **23 classes out of 397** — 1 oversized and 22
incohesive — reproducible with:

```
python scripts/check_class_health.py src
```

Confirmed unrelated to any work in flight by running it against a stashed tree: identical output
with or without the changes applied.

### Why nobody had seen this

The gate's scope is `{"cb": "changed", "sf": "module", "feature": "all"}`. At a commit boundary it
only inspects files the commit touched, so **it is skipped entirely whenever a commit happens not
to touch one of the 23**. It had been reporting `skip class_health changed 0.0s nothing in scope`
for the whole session while 23 classes were failing.

That is the same shape as two other defects found this week — `R-OWNER` shipping inert, and
`-p no:randomly` being a silent no-op for a plugin that was never installed. **A check that
silently does not run is indistinguishable from a check that passes**, and all three were found by
accident rather than by the gate.

Whatever else this ticket does, that property deserves its own answer: a scope-gated check should
be able to say "I inspected nothing" loudly enough that a reader notices.

## The debt is mostly ONE design repeated, not 23 unrelated classes

| Group | Count | Classes |
|---|---|---|
| **AST parsers** | **11** | `BaseTreeSitterParser` (LCOM4=6), `TypeScript` (6), `Java` (5), `Kotlin` (5), `Cpp`/`Go`/`Markdown`/`Python`/`Rust`/`Sql` (4), `C` (3) |
| **Standards analyzers** | **3** | `PythonStandardsAnalyzer` (6), `JSStandardsAnalyzer` (5), `TSStandardsAnalyzer` (3) |
| Protocol parsers | 2 | `AsyncAPIParser`, `GRPCParser` — both split identically into `extract_endpoints` / `extract_messages` |
| Sandbox atoms | 3 | `FileSystemAtom`, `GitAtom`, `QARunnerAtom` — each splits its `_intent_*` handlers from `run` |
| Other | 4 | `TopologyGraph`, `RichPipelineDisplay`, `MCPExplorerTool`, `Task` (16 attributes — the oversized one) |

**14 of 23 are "one class per language"** — the AST parsers and the standards analyzers are the
same pathology in two different packages. The remaining groups also cluster: two protocol parsers
with an identical split, and three atoms that each separate intent-dispatch from execution.

So this is not 23 independent refactors. It is roughly **five** decisions.

## Relationship to other tickets — read before starting

- **`TECH-034` owns the 11 AST parsers.** Its proposed paradigm split is aimed at exactly the
  incoherence `LCOM4` is measuring here, and `check_class_health`'s component breakdown is the
  natural before/after evidence for it. **Do not refactor the parsers here** — that would be two
  overlapping refactors of the same files, the mistake `TECH-023`/`TECH-024` sequencing already
  avoided once.
- **The 3 standards analyzers are the same shape and belong to nobody.** They are the strongest
  candidate for this ticket's own scope, and worth designing *alongside* `TECH-034` so both land on
  one answer rather than two different ones for the same problem.
- **`TECH-023`** is complexity, not cohesion. They correlate but are not the same measure — a class
  can be perfectly cohesive and still have one enormous method.

## Candidate Approaches (not yet designed)

- **Ratchet it, as `TECH-023` did for complexity.** A frozen per-class baseline turns a
  permanently-red, scope-skipped gate into one that blocks a *new* incohesive class immediately.
  Cheapest thing that stops the bleeding, and it is the established pattern here
  (`check_suppressions`, R6, R7, `check_complexity`).
- **Fix the groups, not the classes.** Five decisions rather than 23, sequenced so `TECH-034` takes
  the parsers first and this ticket follows the same answer for the analyzers.
- **Decide what `LCOM4` should mean for a dispatcher.** `FileSystemAtom`, `GitAtom` and
  `QARunnerAtom` split into "the `_intent_*` handlers" and "`run`". That is arguably the *correct*
  shape for an intent dispatcher, not a defect — in which case the answer is a documented,
  reviewable exemption rather than a forced split. **This must be decided before any of the three
  are touched**, because "the metric is wrong here" and "the class is wrong here" lead to opposite
  work.

## Non-Goals (proposed, pending design)

- **Not** the AST parsers — `TECH-034` owns them.
- **Not** behaviour change of any kind; this is cohesion restructuring.
- **Not** raising or relaxing the `LCOM4` threshold to make the number go away. If a specific
  shape is legitimately exempt (see the dispatcher question), that is an explicit, reviewed
  exemption — not a moved goalpost.

## Verification the design must specify

- The full suite passes untouched at every boundary — this is structural.
- Whatever mechanism is chosen, a **new** incohesive class must fail the gate, verified by planting
  one rather than by reading the checker. Every guardrail added this week that was *not* probed
  that way turned out to be inert.
- The scope-gating problem is separately verifiable: a run that inspects nothing should be
  distinguishable, in its output, from a run that inspected everything and found nothing.

## Next Step

Run through `specweaver-design`. Settle the dispatcher question first — it decides whether three of
the 23 are debt at all.
