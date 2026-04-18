# Implementation Plan: Protocol & Schema Analyzers [SF-4: Contract Drift Validation Rules]
- **Feature ID**: 3.31
- **Sub-Feature**: SF-4 — Contract Drift Validation Rules
- **Design Document**: docs/roadmap/phase_3/feature_3_31/feature_3_31_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-4
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_31/feature_3_31_sf4_implementation_plan.md
- **Status**: APPROVED

## Goal Description
Implement `c13_contract_drift.py` inside the Validation Engine framework. This rule programmatically compares codebase CodeStructure paths (extracted from backend Python/TS) with the expected `ProtocolEndpoint` topologies injected dynamically via context from the previous Schema tools.

## Proposed Changes

### `assurance/validation/rules/code/`
#### [NEW] `src/specweaver/assurance/validation/rules/code/c13_contract_drift.py`
- **What it does**: Maps the schema schemas populated dynamically in `self.context.get("protocol_schema")` natively against detected framework routers.
- **Rule Constraints**:
  - Requires context: If `self.context` does not map `ast_payload` properly, returns `Status.SKIP` instructing Orchestrator constraints.
  - Generates `DriftFinding` results for any `ProtocolEndpoint` mapped in the YAML or Proto that does not natively reflect an active tree-sitter node routing.

#### [MODIFY] `src/specweaver/assurance/validation/rules/code/context.yaml`
- **What it does**: Small update declaring `C13ContractDriftRule` in the `exposes:` array preventing registry lookup failures.

### `assurance/validation/rules/code/register.py`
#### [MODIFY] `src/specweaver/assurance/validation/rules/code/register.py`
- **What it does**: Imports `C13ContractDriftRule` and cleanly loads it structurally.

## Verification Plan

### Automated Tests
- Unit Test `test_c13_contract_drift.py`: Generates dummy `ProtocolEndpoint` contexts, tests rule `check` matching identical router stubs in test-bound file targets, asserting `Status.PASS` and identifying `Status.FAIL` drops correctly over missing path maps.

### Manual Verification
Ensure dummy Pipeline tests properly cascade Flow Engine Atoms (SF-3) payload assignments downward to Validation `step.params`.

## Research Notes
- **Critical Dependency Alignment**: Because standard L2 Pure-Logic validation explicitly `forbids: specweaver/loom/*` dependencies, C13 avoids manual parser instantiations by strictly relying on `rule.context` `ast_payload` dictionary bridging.

## Session Handoff
- Run `/dev docs/roadmap/phase_3/feature_3_31/feature_3_31_sf4_implementation_plan.md` seamlessly.
