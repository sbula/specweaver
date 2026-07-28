# Design: Structural Code-Health Rules (Cognitive Complexity, God Object, Signature Shape)

- **Feature ID**: C-VAL-06
- **Epic**: Topic 05 (Validation Engine)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: User-driven metric review, 2026-07-28.

## Problem Statement

The code battery's structural signal is cyclomatic complexity, and the research says it is the
weakest metric available.

**Cyclomatic complexity is close to a proxy for line count.** Jay et al. found a *stable linear
relationship* between CC and SLOC; Landman et al. softened that to "moderate correlation with
increasingly high variance — not strong enough to conclude CC is redundant." Either way, gating on
CC largely re-measures size.

**And it is structurally blind to the failure it is most often credited with catching.** A god
object scores 1: field declarations contain no branches. Measured on this repo — `RunContext` grew
from the 23 fields `TECH-006` set out to reduce, to **32**, with every gate green the whole way.
Nothing in the battery, `tach`, or the file-size check can see it: `handlers/base.py` is 250 lines,
comfortably inside every threshold.

## In Scope (proposed)

Three rules, all DAL-C, all plugging into `C-VAL-03`'s existing risk-ruleset resolution:

| Rule | Measures | Default | Catches what CC cannot |
|---|---|---|---|
| **Cognitive complexity** | breaks in linear flow, **+1 per nesting level**; shorthand ignored; `switch` counts once | 15/function | short-but-deeply-nested code; stops punishing flat dispatch tables |
| **Instance-attribute count** | annotated fields per class | 7 (pylint `R0902` default) | god objects — zero branches, so CC scores them 1 |
| **Signature shape** | boolean parameters; parameter count | `FBT001/2`; `PLR0913` max 5 | a bool arg is nearly always two functions with a caller-side `if` |

**Cognitive complexity is the only one of the three with published validation** — a meta-analysis
of ~24,000 understandability evaluations over 427 snippets found it correlates with comprehension
time and subjective ratings, with **mixed** results on comprehension correctness and physiological
measures. Partial validation, which is still more than anything else in this family has. It should
be introduced as a *replacement* for the cyclomatic gate, not an addition — keeping both gates two
correlated proxies.

## Candidate Approaches (not yet designed)

- Cognitive complexity: `complexipy` (Rust; fast enough to run inside the `implement`/`lint_fix`
  loop rather than only at gates) vs. a flake8 plugin vs. computing it from the existing AST layer.
  The build-vs-buy question is real here because `workspace/ast/` already parses everything.
- Attribute count: pylint `R0902` is the known implementation and ruff does not have it. Adding
  pylint to the toolchain for one rule is a cost worth stating explicitly; computing it from the
  AST layer may be cheaper than the dependency.
- Signature shape is two ruff codes and effectively free — it may not deserve to be its own rule.

## Non-Goals (proposed, pending design)

- **Not LCOM4 or coupling metrics** — `B-VAL-06`, deliberately separated: those need tooling that
  does not exist for Python, and this capability must not be held hostage to building it.
- **Not mutation testing** — already `A-VAL-03`.
- **Not the DAL policy layer** — already delivered as `C-VAL-03`; these rules consume it.
- Not a fix for any existing violation. Introducing a rule and remediating what it finds are
  separate; ship the rule with a baseline if needed, and let each site's own ticket clear it.

## Next Step

Run the `specweaver-design` skill. Every rule here has a live failing instance on this repo — point
the attribute-count rule at `RunContext` (32) and the cognitive-complexity rule at
`decompose.py::execute` and confirm they go **red before** they are trusted going green.
