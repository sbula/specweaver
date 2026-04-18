# Implementation Plan: Protocol & Schema Analyzers [SF-3: Core Flow Engine Alignment (Atom/Tool)]
- **Feature ID**: 3.31
- **Sub-Feature**: SF-3 — Core Flow Engine Alignment (Atom/Tool)
- **Design Document**: docs/roadmap/phase_3/feature_3_31/feature_3_31_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-3
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_31/feature_3_31_sf3_implementation_plan.md
- **Status**: APPROVED

## Goal Description
Implement the `ProtocolAtom` and `ProtocolTool` components inside the Flow Orchestrator layers. This feature safely exposes the `ProtocolSchemaInterface` mapping capabilities established in SF-1/SF-2 upward to automated pipelines and agent-LLM contexts.

## Proposed Changes

### `core/loom/atoms/protocol/`
This boundary controls raw programmatic execution bounds, interacting purely with execution dictionaries without LLM strings.

#### [NEW] `src/specweaver/core/loom/atoms/protocol/context.yaml`
- **What it does**: Declares `archetype: atom`. Consumes `commons/protocol` allowing mapping. Forbids `tools/*` avoiding down-leaks.

#### [NEW] `src/specweaver/core/loom/atoms/protocol/atom.py`
- **What it does**: Implements `ProtocolAtom(Atom)`.
- **Intents Handled**:
  - `extract_schema_endpoints`: Opens the file, dynamically loads the correct Schema Parser from the `ProtocolParserFactory`, parses it, and safely returns `.model_dump()` dictionaries of `ProtocolEndpoint`.
  - `extract_schema_messages`: Returns `.model_dump()` dictionaries of `ProtocolMessage`.
> [!NOTE] 
> Based on HITL approval, Atom results rigidly supply structural JSON/Dictionary shapes to support mathematical array intersections inside downstream Validators.

### `core/loom/commons/protocol/`
#### [NEW] `src/specweaver/core/loom/commons/protocol/factory.py`
- **What it does**: Isolates the AST protocol identification logic entirely inside the adapter layer.
> [!TIP]
> Based on HITL approval, rather than polluting the Atom with file-reading logic, this factory parses `Code` content (`ruamel.yaml` loads) looking for root keys like `openapi: "3.0"` or `asyncapi: "3.0"`, mapping them seamlessly to the underlying split parsers.

### `core/loom/tools/protocol/`
This boundary wraps the Atom securely exposing it to LLMs inside `core/agents/`.

#### [NEW] `src/specweaver/core/loom/tools/protocol/context.yaml`
- **What it does**: Declares `archetype: tool`. Consumes `atoms/protocol`.

#### [NEW] `src/specweaver/core/loom/tools/protocol/tool.py`
- **What it does**: Generates `ProtocolTool(StructuredLLMTool)` securely wrapping the `ProtocolAtom` using Strict Object schemas. Allows an Agent to issue intent actions mapping inputs dynamically via string reasoning to physical File execution bounds.

## Verification Plan

### Automated Tests
- Unit Test `test_protocol_atom.py`: Proves `ProtocolAtom` calls correctly map multiple file extensions (`.proto`/`.yaml`) seamlessly via `ProtocolParserFactory` abstraction.
- Unit Test `test_protocol_factory.py`: Provides minimal mock contents mapping correctly to OpenAPI vs AsyncAPI.
- Tach checks ensuring `context.yaml` boundaries across all 3 modules correctly obey acyclic rules.

### Manual Verification
N/A

## Session Handoff
- Wait until full `/feature` plans are constructed, then run `/dev docs/roadmap/phase_3/feature_3_31/feature_3_31_sf3_implementation_plan.md`.
