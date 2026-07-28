# Design: Cohesion & Coupling Metrics (LCOM4, CBO, Instability)

- **Feature ID**: B-VAL-06
- **Epic**: Topic 05 (Validation Engine)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: User-driven metric review, 2026-07-28. Split out of `C-VAL-06` because it needs
  tooling that does not exist for Python and must not gate the cheap rules.

## Problem Statement

`C-VAL-06`'s attribute-count rule detects that a class is a god object. It cannot say **where to
cut it**, and a finding an agent cannot act on is a finding that gets suppressed.

**LCOM4** answers exactly that. Build a graph over one class — nodes are methods and fields, an
edge exists where a method touches a field or calls another method — and count connected
components. A result of 1 is cohesive. A result of 3 means the class is literally three independent
classes sharing a name, **and the three components are the split**. That is a refactoring
instruction, not a score.

Coupling is the orthogonal axis and is genuinely not covered today. `tach` enforces *declared*
layer boundaries and `C-EXEC-01` enforces internal layers — both answer "is this import allowed".
Neither answers "how much does this module depend on, how much depends on it, and is it stable
enough to carry that weight". Nor do they find **undeclared** cycles.

## In Scope (proposed)

| Metric | Measures | Signal |
|---|---|---|
| **LCOM4** | connected components over methods ∪ fields | >1 ⇒ split, and the components name the pieces |
| **CBO** | classes this class couples to | typical threshold 9–14 |
| **Fan-in / fan-out** | dependents vs dependencies | high fan-in ⇒ must be stable |
| **Instability / abstractness** | `I = Ce/(Ca+Ce)`, `A`, distance `D = \|A + I − 1\|` | high `D` ⇒ *zone of pain* (concrete + depended-on = rigid) or *zone of uselessness* |
| **Dependency cycles** | Tarjan SCC | undeclared loops `tach` cannot see |

**Naming hazard worth pinning down at design time:** "LCOM" is ambiguous. LCOM1–3
(Chidamber–Kemerer) are known-flawed and produce misleading results; **LCOM4** (Hitz & Montazeri)
is the usable definition. A design that says only "LCOM" will get the wrong one implemented.

## Candidate Approaches (not yet designed)

- **Build vs. buy is the whole decision.** No mainstream Python linter emits LCOM4, CBO or
  instability — they come from platforms (CodeScene, SonarQube, Moderne) or from computing them.
  SpecWeaver already has `workspace/ast/` with a polyglot extractor and `graph/` with a
  NetworkX knowledge graph, so the graph substrate exists. LCOM4 over an existing AST is modest
  work; the honest cost driver is the *polyglot* requirement, not the algorithm.
- Whether these are battery rules (pass/fail per file) or graph queries surfaced as advice. LCOM4
  as a hard gate on legacy code is unshippable; as ranked refactoring guidance it is immediately
  useful. This is the central design question.
- Where the output lives. Metrics on a dashboard are invisible to an agent; the finding worth
  acting on is that they should be **materialised as versioned repo files** an agent reads before
  editing — which is the same primitive as the spec battery, not a new one.

## Non-Goals (proposed, pending design)

- **Not** replacing `tach`. Layer enforcement stays declarative; this measures degree and finds
  undeclared cycles.
- Not adopting a commercial platform. CodeScene's Code Health benchmarked best against human expert
  assessment (out-performing the average expert, where SonarQube's Maintainability Rating produced
  enough false positives that the authors questioned prior studies using it as ground truth) — but
  buying a platform is a different decision from shipping a rule, and is out of scope here.
- Not the Maintainability Index. Same benchmark rated it poorly; it should not be built.
- Not mutation testing (`A-VAL-03`), not the DAL policy layer (`C-VAL-03`, delivered).

## Next Step

Run the `specweaver-design` skill — **after** `C-VAL-06` ships, so the cheap attribute-count rule is
already catching god objects while this decides how to say where to cut them.

First design question to settle: gate or advice. Everything else follows from it.
