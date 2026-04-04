# Implementation Plan: AST Drift Detection & AI Root-Cause Analysis [SF-1: AST Drift Engine]
- **Feature ID**: 3.14a
- **Sub-Feature**: SF-1 — AST Drift & Coverage Engine
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3_18/feature_3_18_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_18/feature_3_18_sf1_implementation_plan.md
- **Status**: COMPLETE (2026-04-02)

> **Implementation Notes:**
> - Modified task model deviation: `expected_signatures` maps file layout via `dict[str, list[MethodSignature]]` rather than a flat list.
> - Handled `tree-sitter` complexities by introducing native Python syntax mappings (`*args`, `@staticmethod`).
## Scope
SF-1 builds the pure-logic engine that accepts a source Code AST and its parent `PlanArtifact` specification, structurally comparing them to identify implementation drift and test coverage gaps without invoking an LLM.

## Research Notes
- **Lineage**: The `# sw-artifact` UUID tracks the file. The database (`LineageMixin.get_artifact_history`) contains the parent trace leading back to the `run_id` and the associated structured `PlanArtifact`.
- **Plan Format**: `PlanArtifact` (from `specweaver.planning.models`) models the strict tech stack, file layout, constraints, and tasks (schema stored in YAML).
- **AST Parser**: `src/specweaver/standards/tree_sitter_base.py` exposes `TreeSitterAnalyzer` for language-agnostic structural parsing into AST nodes.

## Proposed Changes

### 1. `src/specweaver/planning/models.py`
**[MODIFY]**
- Add `MethodSignature(BaseModel)`: Fields for `name`, `parameters` (list of types), and `return_type`.
- Add `sequence_number: int` (auto-incrementing) and `expected_signatures: list[MethodSignature] = Field(default_factory=list)` **directly onto the `ImplementationTask` model** (the "story") instead of the root `PlanArtifact`.

### 2. `src/specweaver/planning/planner.py`
**[MODIFY]**
- Update the extraction prompts to instruct the LLM to strictly populate `expected_signatures` when generating the Plan artifacts.

### 3. `src/specweaver/validation/models.py`
**[MODIFY]**
- Add `DriftFinding(BaseModel)`: Represents a structural gap. Fields: `severity`, `node_type`, `description`, `expected_signature`, `actual_signature`. (This semantic schema perfectly feeds the LLM for the optional `--analyze` hook later).
- Add `DriftReport(BaseModel)`: High-level list of findings and a boolean `is_drifted`.

### 4. `src/specweaver/validation/drift_detector.py`
**[NEW]**
- **Purpose**: Pure logic structural comparator.
> [!IMPORTANT]
> **Architecture Constraint**: This component MUST remain pure-logic. The SQLite lookup to fetch the `PlanArtifact` via the UUID happens purely in `flow/_drift.py` (SF-2). `detect_drift` strictly accepts the pre-loaded AST and Plan.
- **Function**: `def detect_drift(file_ast: tree_sitter.Tree, plan: PlanArtifact) -> DriftReport:`
- **Logic**:
  1. Translate `PlanArtifact.file_layout` (for module-level existence) and `PlanArtifact.tasks` (for structural functions) into node baseline expectations.
  2. Walk the `file_ast` using `tree_sitter_base`.
  3. Flag expected method signatures, class definitions, or module requirements that are missing or structurally mutated.

### 5. `tests/unit/validation/test_drift_detector.py`
**[NEW]**
- TDD cases using manually crafted static JSON/YAML fixtures mimicking Phase 3.6 planner output to guarantee < 10ms execution times and zero LLM dependence.
- Covers: Missed method gap, added unauthorized method drift, and perfect match scenarios.

---
## Backlog
- Integration with external `flow/` pipeline hooking (Deferred to SF-2).

## Verification Plan
1. **Automated Tests**:
   - `python -m pytest tests/unit/validation/test_drift_detector.py -v` must pass 100% and execute in under 500ms.
   - Run `ruff check` on modified codebase.
2. **Architecture Scrutiny**:
   - Ensure `specweaver.validation` does not import `specweaver.config.Database` or `LineageMixin`.
