# Implementation Plan: 3.30a SF-2 (Dynamic Tool Gating Intercept)

This implementation plan formally closes the loop on FR-3 and FR-4 of the Dynamic Tool Gating architecture, securing the injection interface between `CodeStructureAtom` mapped schemas and the outward facing Agent `ToolDispatcher`.

## User Review Required

> [!IMPORTANT]
> **Sub-Feature Rollup**: Due to the required mathematical structure of the `active_evaluator` deep-merge logic, the actual Python implementation mapping the `intents.hide` intercept logic inside `ToolDispatcher.available_tools()` was deployed simultaneously with **SF-1** (Commit Boundary 1). This resulting plan therefore requires zero lines of application logic code delta. It officially tracks the formal boundary validation for architectural completeness.

## Proposed Changes

### `specweaver/core/loom/dispatcher.py`

#### [MODIFY] [dispatcher.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/dispatcher.py)
- **Concept:** Expose the aggregated hidden intent list natively intercepting schema rendering.
- **Implementation (Already Deployed):**
  - Overrode `ToolDispatcher.available_tools()`. 
  - Iterates interface bindings. Identifies `CodeStructureTool` and parses `_atom.active_evaluator.get("intents", {}).get("hide", [])`.
  - Mathematically filters `.name` matching `ToolDefinition`s completely out of the array before returning payload to the `PromptBuilder`.

## Open Questions

- None. The mathematical routing enforces zero-trust LLM decoupling perfectly without external bindings and is fully synchronized.

## Verification Plan

### Automated Tests
- ✅ **Integration Complete:** Ensure `tests/integration/core/loom/test_code_structure_tool_evaluator.py::test_tool_dispatcher_intent_hide_with_plugins` strictly enforces both array composition (`active_evaluator`) and Schema Gating (asserting the LLM string never contains the excluded JSON schema payloads). This guarantees E2E security isolation natively. No further test expansions required.
