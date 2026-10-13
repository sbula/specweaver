# E-INTL-02 — Spec Drafting

**Status**: ✅ Finished — signed off by the user 2026-10-13. · **Phase**: 1 · **Feature ID**: E-INTL-02

| | |
|---|---|
| Touches | `workflows/drafting/_base.py` · `workspace/context/provider.py` · `interfaces/cli/hitl_provider.py` |
| Plan | [as built](E-INTL-02_sf01_implementation_plan.md) |

## What it does

`sw draft <name>` (and `sw draft feature`) writes a spec with the person. For each section it asks
one question, the model writes the section, and the person sees it: Enter keeps it, typed text is a
change the model rewrites the section with, `skip` leaves a TODO `[agreed 2026-10-13]`. A provider
with nobody to ask (the REST API) keeps every section. The spec then goes to validation and to the
review that `E-INTL-03` owns.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Interactive drafting | `sw draft` | SHALL ask one question per section and have the model write that section from the answer; an unanswered question leaves a TODO | a spec from answers, not a blank page |
| FR-2 | The person decides each section | Drafter, terminal provider | SHALL show each written section and keep it on Enter, rewrite it with a typed change (sending the change and the old text), or leave a TODO on `skip` | nothing the model writes reaches the spec unseen |

## Live demo

`tests/e2e/capabilities/workflows/test_draft_section_review_e2e.py`: `sw draft greeter` at the real
terminal prompt; the Purpose is changed once and kept, the Contract skipped; the saved spec holds the
rewrite and a TODO, and the rewrite prompt carried the change and the first version.
