# Implementation Plan: Dynamic Risk-Based Rulesets (DAL) [SF-4: Generative HARA (AI Governance Proposal)]

- **Feature ID**: 3.20b
- **Sub-Feature**: SF-4 — Generative HARA (AI Governance Proposal)
- **Design Document**: docs/roadmap/phase_3/feature_3_20b/feature_3_20b_design.md
- **Design Section**: §5 Sub-Feature Decomposition → SF-4
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_20b/feature_3_20b_sf4_implementation_plan.md
- **Status**: IMPLEMENTED

## 1. Goal Description

Update the interactive feature scaffolding (`/design`) and the autonomous capability decomposition (`sw draft --feature`) to support Dynamic Risk-Based Rulesets (DAL). LLM agents will now systematically evaluate technical/business scope utilizing Hazard Analysis and Risk Assessment (HARA) heuristics, guaranteeing that new architectures possess formally declared safety/impact thresholds before code generation begins.

## 2. Proposed Changes

### Configuration/Enums
No changes. The `DALLevel` was implemented in SF-1.

---

### Drafting Models
#### [MODIFY] `src/specweaver/drafting/decomposition.py`
- Modify the `ComponentChange` Pydantic model to mandate a `proposed_dal: str` field.
- **Strict Requirement**: As dictated by HITL decision (Q2 -> C), there will be NO DEFAULT VALUE (e.g., no `default="DAL_E"`). The LLM MUST confidently classify the DAL for every affected component or Pydantic will rightfully reject the structured output.
- **Docstring**: Add explicit instructions detailing DO-178C levels (DAL_A to DAL_E) so the OpenAI/Gemini structured parser naturally respects the constraints.

#### [MODIFY] `tests/unit/drafting/test_decomposition.py` (and any related test fixtures)
- **Agent Handoff Risk**: Because `proposed_dal` has no default, any existing mock instances of `ComponentChange` in the test suite will instantly crash with `ValidationError`. 
- Find and fix all test fixtures by explicitly adding `proposed_dal="DAL_E"` (or another valid DAL) to the mock `ComponentChange` initializations.

> **DEVIATION NOTE (Implemented During TDD Phase 4)**: The `proposed_dal` field in `ComponentChange` was structurally upgraded from `str` to the `DALLevel` Enum. This prevents LLMs from hallucinating invalid safety categories (e.g. `DAL_Z`), shifting architectural reliability onto Pydantic's underlying Rust parser instead of relying on string-matching heuristics. Extra integration tests were successfully added to prove the boundary protection.

---

### Feature Drafter (Interactive Scaffolding)
#### [MODIFY] `src/specweaver/drafting/feature_drafter.py`
- Append a new section definition, `"Risk Assessment (DAL)"`, to the `FEATURE_SECTIONS` list.
- **Section Config**:
  - `name`: "Risk Assessment (DAL)"
  - `heading`: "## Risk Assessment (DAL)"
  - `question`: "What is the severity of failure for this feature? Please assess data sensitivity and operational criticality."
  - `prompt`: Inject DO-178C definitions directly into the prompt (Q3 -> B constraint) — e.g., "Propose a DAL using strict DO-178C logic: DAL_A (Catastrophic), DAL_B (Hazardous), DAL_C (Major), DAL_D (Minor), DAL_E (No Safety Effect). Ground your output securely in these categorizations."
  - `inject_topology`: `True`
- Update `_FEATURE_SPEC_TEMPLATE`'s Done Definition checklist to append `- [ ] Risk Assessment explicitly declares a DAL level`.

## 3. Architecture Verification
This plan respects module boundaries perfectly:
- `decomposition.py` owns models, so adding a field is safe.
- `feature_drafter.py` orchestrates interaction and template generation, so appending to `FEATURE_SECTIONS` is fully compliant.
- No new cross-module dependencies are introduced. The design is strictly additive inside `specweaver/drafting/`.

## 4. Verification Plan

### Automated Tests
- Run `pytest tests/unit/drafting/ test_cli_draft_feature_e2e.py` (if any exist) to guarantee our new `proposed_dal` property hasn't broken standard feature creation flows.
- Confirm `ComponentChange(component="foo", ...)` raises Pydantic errors natively when `proposed_dal` is missing.

### Manual / CLI Verification
- Invoke the interactive drafter using either of its native routes: `sw draft --feature` or any active scaffold wrappers to confirm the "Risk Assessment (DAL)" question successfully pauses for user ingestion.
