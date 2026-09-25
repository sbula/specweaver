# C-VAL-03 SF-04 — Generative HARA (AI Governance Proposal)

**Status**: IMPLEMENTED · **FRs owned**: FR-2 — the agent proposes a DAL per component (recorded
2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-25-SF01-MIG`) ·
Design: [C-VAL-03_design.md](C-VAL-03_design.md) §5 Sub-Feature Decomposition → SF-04 ·
Feature ID 3.20b

## Goal

The interactive scaffolding (`/design`) and the autonomous decomposition (`sw draft --feature`)
make agents rate each component with Hazard Analysis and Risk Assessment (HARA) heuristics, so every
new architecture declares a safety/impact threshold before code generation.

`DALLevel` itself comes from SF-01; no enum changes.

## Changes

1. **[MODIFY] `src/specweaver/drafting/decomposition.py`** — `ComponentChange` gets a required
   `proposed_dal` field.
   - **No default** (HITL Q2 -> C; e.g. no `default="DAL_E"`). The LLM must classify every affected
     component, or Pydantic rejects the structured output.
   - Docstring explains the DO-178C levels (DAL_A to DAL_E) so the OpenAI/Gemini structured parser
     respects them.
   - Typed `DALLevel`, not `proposed_dal: str` as planned: Pydantic rejects an invalid category
     (e.g. `DAL_Z`) instead of string matching. Integration tests prove the boundary.
2. **[MODIFY] `tests/unit/drafting/test_decomposition.py`** (and related fixtures) — with no default,
   every mock `ComponentChange` fails with `ValidationError`; add `proposed_dal="DAL_E"` (or another
   valid DAL) to each.
3. **[MODIFY] `src/specweaver/drafting/feature_drafter.py`** — append `"Risk Assessment (DAL)"` to
   `FEATURE_SECTIONS`:
   - `name`: "Risk Assessment (DAL)"
   - `heading`: "## Risk Assessment (DAL)"
   - `question`: "What is the severity of failure for this feature? Please assess data sensitivity and operational criticality."
   - `prompt`: DO-178C definitions in the prompt (Q3 -> B), e.g. "Propose a DAL using strict
     DO-178C logic: DAL_A (Catastrophic), DAL_B (Hazardous), DAL_C (Major), DAL_D (Minor), DAL_E
     (No Safety Effect). Ground your output securely in these categorizations."
   - `inject_topology`: `True`
   - `_FEATURE_SPEC_TEMPLATE`'s Done Definition gains `- [ ] Risk Assessment explicitly declares a DAL level`.

Architecture: `decomposition.py` owns the models; `feature_drafter.py` owns interaction and
templates. No new cross-module dependency; the change stays inside `specweaver/drafting/`.

## Tests

- `pytest tests/unit/drafting/ test_cli_draft_feature_e2e.py` (if present): feature creation still
  works with `proposed_dal`.
- `ComponentChange(component="foo", ...)` without `proposed_dal` raises a Pydantic error. Guard test:
  `test_a_component_without_a_proposed_dal_is_rejected`.
- Manual: `sw draft --feature` (or an active scaffold wrapper) pauses on the "Risk Assessment (DAL)"
  question for user input.

**FR-2 had no test** until then: defaulting `proposed_dal` to `DAL_E`, the lowest criticality,
passed the whole suite — an omitted rating would silently become least-critical with no architect
shown a proposal. See the design.
