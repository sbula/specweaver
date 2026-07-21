# Design: Rubrics-as-Content Validation (Rules as Code, Rubrics as Content)

- **Feature ID**: C-VAL-05
- **Epic**: Topic 05 (Validation Engine)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Architecture-direction review (2026-07-21, Steve Bula + Claude) — the "middle way" between
  hardcoded rules and flexible skills: keep the battery **engine** hardcoded (guarantees), externalize the
  **semantic judgment content** as editable rubric files (skill-shaped knowledge).
- **DAL**: C (Enterprise Standard)

## Problem Statement

The validation battery is mostly the *right kind* of hardcoding — 21 of 23 rules are mechanical (syntax,
tests-pass, coverage, import direction, type hints, traceability...). But the **semantic** rules are prompts
wearing a Python costume: `s03_stranger.py` (stranger test) and `s07_test_first.py` embed their LLM judgment
criteria in code, and the review handlers' rubrics are likewise frozen in handler prompts. Consequences:
editing judgment criteria requires a code change + release; projects cannot tune criteria to their domain;
the criteria cannot improve independently of the engine; and the same pattern will repeat for every future
semantic check (`B-VAL-03` Semantic Test Completeness, `E-VAL-04` Multi-Stage Reviews).

## Goal

**Rules as code, rubrics as content.** The battery runner, rule IDs, verdict aggregation, DAL thresholds and
strict-mode semantics stay hardcoded. Semantic rules load their judgment criteria from **markdown rubric
files** (shipped defaults + per-project overrides), so:

1. `S03`/`S07` (and review criteria) become thin engine shims that apply a rubric file via the LLM — same
   rule IDs, same battery, same reports, same gates.
2. Rubrics are versioned, per-project overridable (`.specweaver/rubrics/` over shipped defaults), and
   **DAL-gated** (e.g. stricter rubric variants selected at DAL-A/B; override authority may itself be
   DAL-restricted).
3. New semantic checks are added by *writing a rubric*, not a rule class — the extension point future
   semantic capabilities (`B-VAL-03`, `E-VAL-04`, `B-INTL-08` Semantic Code Review) build on instead of
   re-freezing prompts in Python.

## Relationship
- **Complements**: `C-FLOW-11` (graduated autonomy) — together they form the middle way: execution mode and
  judgment content both become policy/content, while every guarantee stays code.
- **Feeds**: `B-VAL-03`, `E-VAL-04`, `B-INTL-08` should be designed **rubric-first** on this substrate.
- **Touches**: `assurance/validation` (rule shims + rubric loader), review workflow prompts; NOT the
  mechanical rules, NOT the battery engine contract.

## Candidate Approaches (not yet designed)
1. Rubric file format: plain markdown with a small frontmatter (id, version, dal_variants) — recommended;
   resist inventing a DSL.
2. Loader precedence: project `.specweaver/rubrics/<rule>.md` → shipped default; checksum recorded in the
   validation report for auditability (DAL-C: *which* rubric judged this run must be traceable).
3. Migration: S03 + S07 first (proof), then the review-handler criteria.

## Non-Goals (proposed, pending design)
- Softening mechanical rules (C01–C13 and the 21 mechanical spec rules stay code).
- Changing battery/report/gate contracts.
- User-defined *rule IDs* (custom rules remain `D-VAL-02` territory; this externalizes judgment content of
  existing/blessed semantic checks).

## Next Step
Run `specweaver-design C-VAL-05`. Recommended first bite of the middle-way direction (low-risk, no execution
path touched, establishes the "engine hard / content soft" precedent).
