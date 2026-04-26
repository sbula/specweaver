# Implementation Plan: Feature 3.20a [SF-6: Global Implicit Namespace Conversion]
- **Feature ID**: 3.20a
- **Sub-Feature**: SF-6 — Global Implicit Namespace Conversion
- **Design Document**: docs/roadmap/features/topic_06_sandbox/C-EXEC-01/C-EXEC-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-6
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-01/C-EXEC-01_sf6_implementation_plan.md
- **Status**: COMPLETED

## 1. Description
This plan executes SF-6: The final completion of SpecWeaver's transition into a PEP-420 architecture. We will delete all remaining `__init__.py` boilerplate encapsulation proxy files inside `src/specweaver/` and enforce global strict topology checks using Tach. 

---

## 2. Technical Implementation Steps

### Step 1: De-Encapsulation (Delete Proxy Files)
#### [DELETE] `src/specweaver/**/__init__.py`
Hard-delete the 20 internal `__init__.py` files physically inside the `src/specweaver/` tree.
> [!IMPORTANT]
> Do NOT touch the `tests/` directory unless strictly necessary. This conversion is purely aimed at decoupling the structural boundaries of the `src/` runtime engine.

### Step 2: Pytest PYTHONPATH Fix
#### [MODIFY] `pyproject.toml`
Turning `src/specweaver/` into an implicit namespace package removes its inherent discoverability. To prevent all 3,700+ tests from catastrophically failing with `ModuleNotFoundError`, we must point pytest to our runtime root.
- Add `pythonpath = ["src"]` explicitly inside the `[tool.pytest.ini_options]` block.

### Step 3: Global Strict Topology (Tach)
#### [MODIFY] `tach.toml`
Currently, SpecWeaver defines layer boundaries but doesn't strictly shut out undeclared lateral crossings.
- Set global `strict = true` or `exact = true` globally for strict enforcement depending on our exact Tach configuration to mathematically lock down remaining isolation barriers. Ensure any newly flagged implicit dependencies are documented or explicitly whitelisted.

---

## 3. Backlog / Deferred
None.

---

## 4. Verification Plan

### Automated Tests
1. `tach check` must succeed.
2. The entire test suite (`python -m pytest tests/`) must effortlessly complete exactly as it did before.
3. E2E pre-commit hooks `/pre-commit` must be utilized.
