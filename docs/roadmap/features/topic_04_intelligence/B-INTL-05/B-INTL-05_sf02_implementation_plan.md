# B-INTL-05 SF-02 — Dynamic Tool Gating Intercept

**Status**: APPROVED · **Feature ID**: 3.30a · **FRs owned**: FR-3, FR-4 · **Depends on**: SF-01 ·
Design: [B-INTL-05_design.md](B-INTL-05_design.md) §Sub-features → SF-02

## Goal

Carry the `hidden_intents` of `CodeStructureAtom`'s mapped schemas to the agent-facing
`ToolDispatcher`, and drop those tools from the definitions.

Constructor injection of `hidden_intents` was HITL approved to close the boundary isolation gap. All
Phase 2 & Phase 3 questions are resolved.

## Changes

1. **`src/specweaver/core/loom/dispatcher.py`** — in `ToolDispatcher.create_standard_set`, right after
   `atom = CodeStructureAtom(...)`:
   - extract the plugin-suppressed intents:
     `hidden_intents = atom.active_evaluator.get("intents", {}).get("hide", [])`
   - pass them down:
     `CodeStructureTool(atom=atom, role=role, grants=grants, hidden_intents=hidden_intents)`
2. **`src/specweaver/core/loom/tools/code_structure/tool.py`** — role masking and plugin masking on
   the same definitions:
   - `CodeStructureTool.__init__` accepts `hidden_intents: list[str] | None = None`, stored as
     `self._hidden_intents`.
   - `CodeStructureTool.definitions()` returns from `all_defs` only definitions where
     `.name in allowed` AND `.name not in self._hidden_intents`.

> [!NOTE]
> **Why injection**: the Tool must not read `self._atom.active_evaluator`. Tools (Agent boundaries)
> are forbidden from reading internal `atoms/*` attributes, which keeps the facade decoupled from
> I/O schemas (`src/specweaver/core/loom/tools/context.yaml`).

## Tests

`tests/integration/core/loom/test_code_structure_tool_evaluator.py` [MODIFY] — in
`test_tool_dispatcher_intent_hide_with_plugins`, change the tested `role` from `"planner"` to
`"implementer"`.

> [!CAUTION]
> **False-positive masking**: the `"planner"` role already drops internal write scopes. With
> `"implementer"`, dropping `read_unrolled_symbol` can be caused *only* by the new
> `plugins: [security]` YAML hiding logic.
