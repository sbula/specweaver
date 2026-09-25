# C-VAL-06 — Structural Code-Health Rules (Cognitive Complexity, God Object, Signature Shape)

**Status**: STUB — not yet run through the `specweaver-design` skill · **Topic**: 05 (Validation
Engine) · **Feature ID**: C-VAL-06 · **Origin**: user-driven metric review, 2026-07-28

| | |
|---|---|
| Uses | `C-VAL-03` — the DAL policy layer; these rules plug into its risk-ruleset resolution |
| Not touched | LCOM4 / coupling metrics (`B-VAL-06`) · mutation testing (`A-VAL-03`) |

## What it does

Three DAL-C rules that see structural problems cyclomatic complexity cannot:

| Rule | Measures | Default | Catches what CC cannot |
|---|---|---|---|
| **Cognitive complexity** | breaks in linear flow, **+1 per nesting level**; shorthand ignored; `switch` counts once | 15/function | short-but-deeply-nested code; stops punishing flat dispatch tables |
| **Instance-attribute count** | annotated fields per class | 7 (pylint `R0902` default) | god objects — zero branches, so CC scores them 1 |
| **Signature shape** | boolean parameters; parameter count | `FBT001/2`; `PLR0913` max 5 | a bool arg is nearly always two functions with a caller-side `if` |

## Why not cyclomatic complexity

The code battery's structural signal is CC, the weakest metric available.

- **CC is close to a proxy for line count.** Jay et al. found a *stable linear relationship* between
  CC and SLOC; Landman et al. softened that to "moderate correlation with increasingly high variance
  — not strong enough to conclude CC is redundant." Either way, gating on CC largely re-measures
  size.
- **CC is blind to god objects.** Field declarations contain no branches, so a god object scores 1.
  On this repo, `RunContext` grew from the 23 fields `TECH-006` set out to reduce to **32**, with
  every gate green. Nothing in the battery, `tach` or the file-size check sees it:
  `handlers/base.py` is 250 lines, inside every threshold.

**Cognitive complexity is the only one of the three with published validation.** A meta-analysis
of ~24,000 understandability evaluations over 427 snippets found it correlates with comprehension
time and subjective ratings, with **mixed** results on comprehension correctness and physiological
measures. Partial, but more than anything else in this family. It *replaces* the cyclomatic gate,
not adds to it — keeping both gates two correlated proxies.

## Open decisions (not yet designed)

- **Cognitive complexity:** `complexipy` (Rust; fast enough to run inside the `implement`/`lint_fix`
  loop, not only at gates) vs. a flake8 plugin vs. computing it from the existing AST layer.
  Build-vs-buy is real: `workspace/ast/` already parses everything.
- **Attribute count:** pylint `R0902` is the known implementation; ruff does not have it. Adding
  pylint for one rule is a cost to state explicitly; computing it from the AST layer may be cheaper.
- **Signature shape:** two ruff codes, effectively free — may not deserve to be its own rule.

## Non-goals (proposed, pending design)

- **Not LCOM4 or coupling metrics** — `B-VAL-06`, deliberately separated: those need tooling that
  does not exist for Python, and this capability must not be held hostage to building it.
- **Not mutation testing** — already `A-VAL-03`.
- **Not the DAL policy layer** — delivered as `C-VAL-03`; these rules consume it.
- Not a fix for existing violations. Ship the rule with a baseline if needed; each site's own
  ticket clears it.

**Next**: run `specweaver-design`. Every rule has a live failing instance here — point the
attribute-count rule at `RunContext` (32) and the cognitive-complexity rule at
`decompose.py::execute`; confirm both go **red before** they are trusted going green.
