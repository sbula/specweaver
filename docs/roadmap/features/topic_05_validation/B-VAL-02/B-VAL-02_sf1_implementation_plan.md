# Implementation Plan: Bi-Directional Spec Rot Interceptor [SF-1: CLI Command + Git Hook Deployment]
- **Feature ID**: 3.23
- **Sub-Feature**: SF-1 — CLI Command + Git Hook Deployment
- **Design Document**: docs/roadmap/features/topic_05_validation/B-VAL-02/B-VAL-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/features/topic_05_validation/B-VAL-02/B-VAL-02_sf1_implementation_plan.md
- **Status**: APPROVED

## 1. Goal
Implement the core CLI entry points (`sw hooks install` and `sw drift check-rot --staged`) and the logic to deploy a robust, strict git `pre-commit` hook that intercepts commits for spec alignment checks.

## 2. Research Notes & HITL Decisions
- **Execution Consistency:** The `pre-commit` hook MUST use Python's `sys.executable` (determined dynamically during `sw hooks install`) to construct the hook command (e.g., `/absolute/path/to/venv/bin/python -m specweaver.interfaces.cli.main drift check-rot --staged`). This ensures the hook fires correctly regardless of virtual environment activation states.
- **Strict Adherence:** The bash hook MUST `exit 1` if it cannot resolve the python binary, strictly blocking the commit.
- **CLI Namespace & Scope:** The hook deployment belongs in `cli/hooks.py` while the actual check command belongs in `cli/drift.py` (`check-rot --staged`). Because SF-2 implements the `AST` checking atom, the `check-rot` command in SF-1 simply validates CLI arguments and gracefully finishes, acting as a stable interface for SF-2 to wire the `PipelineRunner`.

## 3. Proposed Changes

### [NEW] `src/specweaver/cli/hooks.py`
- Defines the `sw hooks` typer application namespace.
- Implements `install()` command (`sw hooks install --pre-commit`).
- Uses `sys.executable` to map the explicit interpreter path.
- Generates the `.git/hooks/pre-commit` bash script and applies executable (`chmod +x`) permissions.
> [!IMPORTANT]
> The generated bash script must hard-fail (`exit 1`) if the mapped python interpreter cannot be found or fails execution.
> The generated bash script must execute: `"$PYTHON_EXEC" -m specweaver.interfaces.cli.main drift check-rot --staged`.

### [MODIFY] `src/specweaver/cli/main.py`
- Imports `hooks` to auto-register the new `sw hooks` command group alongside existing modules.

### [MODIFY] `src/specweaver/cli/drift.py`
- Adds the `check_rot(staged: bool = typer.Option(False, "--staged"))` sub-command command onto the existing `drift` Typer app.
- For SF-1, this will act as a standalone entry point that succeeds `exit 0`. It provides the stable command boundaries that SF-2 will hook the `PipelineRunner` into.

### [NEW] `tests/cli/test_hooks.py`
- Mocks `.git/hooks/` to test that `sw hooks install` writes exactly into the target path.
- Asserts that the output script contains the `sys.executable` path execution instruction.

### [NEW] `tests/cli/test_rot_cmd.py`
- Tests the bare CLI execution logic of `sw drift check-rot --staged`.

## 4. Verification Plan
- **Automated Tests:** Execute `pytest` targeting the two new CLI test files. We will assert no regression in `drift.py`.
- **Manual Verification:** Execute `poetry run sw hooks install` (or `uv run`), physically inspect the generated file in `.git/hooks/pre-commit`, validating python path string mapping.
