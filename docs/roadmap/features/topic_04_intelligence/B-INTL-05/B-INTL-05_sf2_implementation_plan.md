# Implementation Plan: 3.30a SF-2 (Dynamic Tool Gating Intercept)
- **Feature ID**: 3.30a
- **Sub-Feature**: SF-2 — Dynamic Tool Gating Intercept
- **Design Document**: docs/roadmap/phase_3/feature_3.30a/feature_3.30a_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/phase_3/feature_3.30a/feature_3.30a_sf2_implementation_plan.md
- **Status**: APPROVED

This implementation plan formally closes the loop on FR-3 and FR-4 of the Dynamic Tool Gating architecture, securing the injection interface between `CodeStructureAtom` mapped schemas and the outward facing Agent `ToolDispatcher`.

## User Review Required

- None pending. Architectural approach (Constructor Injection of `hidden_intents`) has been explicitly HITL approved to resolve the boundary isolation gap. 

## Proposed Changes

### `specweaver/core/loom/dispatcher.py`

#### [MODIFY] [dispatcher.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/dispatcher.py)
- **Concept:** Expose the aggregated hidden intent list natively intercepting schema rendering.
- **Implementation:**
  - Inside `ToolDispatcher.create_standard_set`, immediately after initializing `atom = CodeStructureAtom(...)`, extract the plugin-suppressed intents natively via: 
    `hidden_intents = atom.active_evaluator.get("intents", {}).get("hide", [])`
  - Update the `CodeStructureTool` instantiation call to pass this new list downwards:
    `CodeStructureTool(atom=atom, role=role, grants=grants, hidden_intents=hidden_intents)`

### `specweaver/core/loom/tools/code_structure/tool.py`

#### [MODIFY] [tool.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/tools/code_structure/tool.py)
- **Concept:** Implement Role and Dynamic System masking simultaneously on tool definitions.
- **Implementation:**
  - Update `CodeStructureTool.__init__` to accept `hidden_intents: list[str] | None = None`. Map this natively to `self._hidden_intents`.
  > [!NOTE]
  > **Architectural Adherence**: We deliberately avoid having the Tool read `self._atom.active_evaluator` natively. Tools (Agent boundaries) strictly forbid reading internal `atoms/*` attributes to maintain pure facade security decoupled from I/O schemas (`src/specweaver/core/loom/tools/context.yaml`).
  - Inside `CodeStructureTool.definitions()`, filter the fetched `all_defs` returning only definitions where `.name in allowed` AND `.name not in self._hidden_intents`.

## Open Questions

- All Phase 2 & Phase 3 questions have been resolved.

## Verification Plan

### Automated Tests

#### [MODIFY] [test_code_structure_tool_evaluator.py](file:///c:/development/pitbula/specweaver/tests/integration/core/loom/test_code_structure_tool_evaluator.py)
- **Implementation:**
  - Update the `test_tool_dispatcher_intent_hide_with_plugins` test. Change the configured `role` being tested from `"planner"` to `"implementer"`. 
  > [!CAUTION]
  > **False Positive Masking Check**: The `"planner"` role natively drops internal write scopes. Using `"implementer"` guarantees that the test string dropping `read_unrolled_symbol` is mathematically caused *exclusively* by our new `plugins: [security]` YAML hiding logic executing correctly.
