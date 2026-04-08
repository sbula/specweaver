# Implementation Plan: Bi-Directional Spec Rot Interceptor [SF-2: Dynamic Flow Handler]
- **Feature ID**: 3.23
- **Sub-Feature**: SF-2 — Dynamic Flow Handler (Detect Rot)
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3_23/feature_3_23_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_23/feature_3_23_sf2_implementation_plan.md
- **Status**: APPROVED

## 1. Goal

Finalize the "Bi-Directional Spec Rot Interceptor" by implementing the logic inside the Git pre-commit hook handler (`sw drift check-rot --staged`). This sub-feature will dynamically extract staged code files, resolve their parent `PlanArtifacts` (enforcing **Option A: Trace-to-Plan**), and execute the deterministic AST Drift Engine. If structural drift is detected, the command must abort the shell with a deterministic non-zero exit code (`42`), forcing the human developer to resolve the code-to-spec inconsistency. 

## 2. Context & Handoff (For New Agents Resuming)

> [!NOTE]
> **To any Agent resuming this task:**
> You do NOT need to recall previous sessions or missing knowledge to execute this!
> 
> 1. CLI Hook Mechanism: SF-1 is complete. Standard git hooks now execute `sw drift check-rot --staged`. 
> 2. `drift.py`: The `check-rot` command currently acts as a passive stub (printing text). You must replace this stub with the logic defined below.
> 3. Execution Standard: NFR-1 strictly limits execution to `<500ms` preventing any LLM usage for the pre-commit hook itself. The existing `detect_drift` logic inside `src/specweaver/validation/drift_detector.py` is lightning-fast and requires a structured `PlanArtifact`, not raw Markdown.

## 3. Proposed Changes

### [x] `src/specweaver/cli/drift.py`

Update the `drift_check_rot` function (the sub-command for `sw drift check-rot`).

**Logic Flow:**
- [x] **Locate Target Files**: Extract the staged files from Git.
- [x] **Resolve Plans**: The interceptor uses Option A (Trace-to-Plan).
- [x] **Delegation**: For every staged file matched to a Plan, dynamically create a single step.
- [x] **Enforcement**: If drift is detected, compile an aggregate report.
- [x] **Termination**: Print a clean `Rich` console table to stderr highlighting the drift, and strictly `raise typer.Exit(code=42)`.

### [x] `tests/integration/cli/test_drift_rot_handler.py`

- [x] Use mocked `subprocess.run` to simulate `git diff --cached` returning sample file paths.
- [x] Setup a temporary workspace.
- [x] Assert `sw drift check-rot --staged` exits with `42` and emits the Drift Table.
- [x] Assert a healthy file exits with `0`.

## 4. Open Questions
**None.** The human engineer explicitly approved Option A (Trace-to-Plan), and standard codebase pathing natively handles pipeline inputs. No further blockers exist.

## 5. Verification Plan
- **Automated Verification:** The newly defined `tests/integration/cli/test_drift_rot_handler.py` module will explicitly verify execution edge-cases (single staged file, multiple staged files across different plans, un-planned files ignored).
- **End-to-End Environment**: We will rely on existing E2E infrastructure (`test_hooks_e2e.py`) created in SF-1 to assert OS-level `exit 1` blockades, eliminating the need for a secondary E2E layer for SF-2.
