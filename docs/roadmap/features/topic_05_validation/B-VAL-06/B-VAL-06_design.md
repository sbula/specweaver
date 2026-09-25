# B-VAL-06 — Cohesion & Coupling Metrics (LCOM4, CBO, Instability)

**Status**: STUB — not yet run through the `specweaver-design` skill · **Epic**: Topic 05
(Validation Engine) · **Feature ID**: B-VAL-06

| | |
|---|---|
| Origin | User-driven metric review, 2026-07-28 |
| Split out of | `C-VAL-06` — this needs tooling that does not exist for Python and must not gate the cheap rules |
| Not touched | `tach` layer enforcement · `C-EXEC-01` internal layers · mutation testing (`A-VAL-03`) · DAL policy layer (`C-VAL-03`, delivered) |

## What it does

Says **where to cut** a class, and how coupled a module is.

`C-VAL-06`'s attribute-count rule detects a god object but cannot say where to cut it. A finding an
agent cannot act on gets suppressed.

**LCOM4** gives the cut. Build a graph over one class: nodes are methods and fields; an edge exists
where a method touches a field or calls another method. Count connected components. 1 = cohesive.
3 = three independent classes sharing a name, **and the three components are the split**.

**Coupling** is the orthogonal axis, not covered today. `tach` enforces *declared* layer boundaries
and `C-EXEC-01` enforces internal layers — both answer "is this import allowed". Neither measures how
much a module depends on, how much depends on it, and whether it is stable enough to carry that.
Neither finds **undeclared** cycles.

## Metrics (proposed)

| Metric | Measures | Signal |
|---|---|---|
| **LCOM4** | connected components over methods ∪ fields | >1 ⇒ split, and the components name the pieces |
| **CBO** | classes this class couples to | typical threshold 9–14 |
| **Fan-in / fan-out** | dependents vs dependencies | high fan-in ⇒ must be stable |
| **Instability / abstractness** | `I = Ce/(Ca+Ce)`, `A`, distance `D = \|A + I − 1\|` | high `D` ⇒ *zone of pain* (concrete + depended-on = rigid) or *zone of uselessness* |
| **Dependency cycles** | Tarjan SCC | undeclared loops `tach` cannot see |

**Naming hazard:** "LCOM" is ambiguous. LCOM1–3 (Chidamber–Kemerer) are known-flawed and mislead;
**LCOM4** (Hitz & Montazeri) is the usable one. A design that says only "LCOM" gets the wrong one.

## Open questions

1. **Gate or advice** — battery rules (pass/fail per file) or graph queries surfaced as advice? The
   central question; everything else follows. LCOM4 as a hard gate on legacy code is unshippable; as
   ranked refactoring guidance it is useful now.
2. **Build vs. buy.** No mainstream Python linter emits LCOM4, CBO or instability — they come from
   platforms (CodeScene, SonarQube, Moderne) or are computed. The SpecWeaver substrate exists:
   `workspace/ast/` (polyglot extractor) and `graph/` (NetworkX knowledge graph). LCOM4 over an existing AST is modest
   work; the cost driver is the *polyglot* requirement, not the algorithm.
3. **Where output lives.** A dashboard is invisible to an agent. Materialise the metrics as
   **versioned repo files** an agent reads before editing — the same primitive as the spec battery,
   not a new one.

## Non-goals

- **Not** replacing `tach`. Layer enforcement stays declarative; this measures degree and finds
  undeclared cycles.
- Not adopting a commercial platform. CodeScene's Code Health benchmarked best against human expert
  assessment (beating the average expert; SonarQube's Maintainability Rating produced enough false
  positives that the authors questioned prior studies using it as ground truth). Buying a platform is
  a different decision from shipping a rule.
- Not the Maintainability Index. The same benchmark rated it poorly; do not build it.
- Not mutation testing (`A-VAL-03`), not the DAL policy layer (`C-VAL-03`, delivered).

## Next step

Run the `specweaver-design` skill **after** `C-VAL-06` ships, so the attribute-count rule already
catches god objects while this decides how to say where to cut them. Settle gate-or-advice first.
