# Design: Chronically Failing Class-Health Gate

- **Feature ID**: TECH-035
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found 2026-08-12 during `TECH-023` batch 2. The gate fired for the first time in the
  session because that commit finally *changed* a file it covers — see "Why nobody had seen this".

## Problem Statement

`check_class_health.py` fails on a **clean tree**: **23 classes out of 397** when filed — 1
oversized and 22 incohesive; **20 of 400 after `TECH-034`**. Reproducible with:

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

**11 of 23 are the AST parsers.** The remaining groups also cluster: two protocol parsers with an
identical split, and three atoms that each separate intent-dispatch from execution. So this is not
23 independent refactors — it is roughly **five** decisions.

> **Correction, 2026-08-12.** This section first claimed *"14 of 23 are one class per language — the
> AST parsers and the standards analyzers are the same pathology in two different packages"*, and
> put the 3 analyzers in this ticket's scope. **Both halves were wrong**, found while researching
> `TECH-034`:
>
> - The analyzers **already have the tier** this ticket would have proposed:
>   `StandardsAnalyzer` (ABC, contract = `extract_all`) → `TreeSitterAnalyzer` (88 lines) →
>   `JSStandardsAnalyzer` → `TSStandardsAnalyzer`. They arrived there independently and earlier
>   than the parsers did.
> - `PythonStandardsAnalyzer` sits outside that tier on **stdlib `ast`**, and should stay there.
>   `ast` ships with the language and tracks its grammar exactly; its regex use is only
>   `^[A-Z][a-zA-Z0-9]*$`-style naming-convention matching on identifier strings, which is the
>   correct use of a regex rather than parsing. Moving it onto tree-sitter would trade precision
>   for symmetry.
>
> The principle already in force there is the right one — **one contract, best parser per
> language** — so their `LCOM4` is a question about *those three classes*, not about a repeated
> design. **Do not refactor them toward uniformity on that reading.**

## Relationship to other tickets — read before starting

- **`TECH-034` took the 11 AST parsers — DELIVERED 2026-08-12.** Its paradigm split targeted
  exactly the incoherence `LCOM4` measures here, and the before/after is the evidence: language
  parsers flagged **10 → 7**, every remaining one at `LCOM4=2` (was 3–6), and C++/Python/C off the
  list entirely. **Do not refactor the language parsers here.** What it left behind is the base —
  see below.
- **The 3 standards analyzers are NOT the parsers' problem repeated** — see the correction above.
  They already have their own tier and a sound contract, so whatever is left in their `LCOM4` is a
  question about those three classes alone.
- **`BaseTreeSitterParser` is now the most incohesive class in the repo (`LCOM4=8`, was 6).**
  `TECH-034` concentrated the parsers' shared mechanics into it — a deliberate trade, since fixing
  one base beats fixing ten parsers. Its components are four distinct jobs (query, walk, edit,
  format). **This is the single highest-value target in this ticket**, and it also clears three of
  `TECH-023`'s remaining violations.
- **`TECH-023`** is complexity, not cohesion. They correlate but are not the same measure — a class
  can be perfectly cohesive and still have one enormous method.

## Candidate Approaches (not yet designed)

- **Ratchet it, as `TECH-023` did for complexity.** A frozen per-class baseline turns a
  permanently-red, scope-skipped gate into one that blocks a *new* incohesive class immediately.
  Cheapest thing that stops the bleeding, and it is the established pattern here
  (`check_suppressions`, R6, R7, `check_complexity`).
- **Fix the groups, not the classes.** Roughly five decisions rather than 23 refactors. `TECH-034`
  has since taken the parsers, so the largest remaining group is **one class** —
  `BaseTreeSitterParser` — not eleven.
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
