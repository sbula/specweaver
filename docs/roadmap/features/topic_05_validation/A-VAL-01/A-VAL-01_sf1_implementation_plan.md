# Implementation Plan: Protocol & Schema Analyzers [SF-1: ProtocolSchemaInterface & YAML Parsers]
- **Feature ID**: 3.31
- **Sub-Feature**: SF-1 — ProtocolSchemaInterface & YAML Parsers
- **Design Document**: docs/roadmap/features/topic_05_validation/A-VAL-01/A-VAL-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/features/topic_05_validation/A-VAL-01/A-VAL-01_sf1_implementation_plan.md
- **Status**: APPROVED

## Goal Description
Implement the core boundaries and YAML-based extractions for `ProtocolSchemaInterface`. This securely introduces OpenAPI and AsyncAPI schema parsing via `ruamel.yaml` into the system architecture without breaking programming Code Structure workflows.

## Proposed Changes

### `core/loom/commons/protocol`
This module defines the boundaries, data models, and the YAML-based parsers.

#### [NEW] `src/specweaver/core/loom/commons/protocol/context.yaml`
- **What it does**: Establishes the `adapter` archetype for the new protocol package allowing external format ingestion, declares strict `consumes`/`forbids` boundaries preventing downward leaks into the flow Engine or Atom structures.
- **Constraints**: 
  - `archetype: adapter`
  - `consumes: [specweaver/commons]`
  - `forbids: [specweaver/loom/tools/*, specweaver/loom/atoms/*]`

#### [NEW] `src/specweaver/core/loom/commons/protocol/models.py`
- **What it does**: Defines the Pydantic models for explicit AST representation of API endpoints and schemas.
- **Models**:
  - `ProtocolEndpoint`: represents HTTP methods, paths, or gRPC RPCs.
  - `ProtocolMessage`: represents payload structures/schemas.
  - `ProtocolSchemaSet`: a collection encompassing the parsed outputs.
> [!NOTE]
> Based on HITL approval, we are explicitly enforcing strict Pydantic structures right out of the parser (rather than raw dictionaries) to prevent type hallucination later inside the Engine's AST difference checkers.

#### [NEW] `src/specweaver/core/loom/commons/protocol/interfaces.py`
- **What it does**: Defines the `ProtocolSchemaError` and the ABC `ProtocolSchemaInterface`.
- **Methods**:
  - `extract_endpoints(raw_schema: str) -> list[ProtocolEndpoint]`
  - `extract_messages(raw_schema: str) -> list[ProtocolMessage]`

#### [NEW] `src/specweaver/core/loom/commons/protocol/openapi_parser.py`
- **What it does**: Adheres to `ProtocolSchemaInterface` specifically for OpenAPI `3.x`. Uses `ruamel.yaml` safely.
> [!CAUTION]
> Based on HITL approval, embedded generic validation via `jsonschema` is avoided to honor NFR-1 speed budgets. Instead, if `openapi.yaml` structural keys like `paths` are completely malformed, failure relies natively on `ProtocolSchemaError` raised via key misses.

#### [NEW] `src/specweaver/core/loom/commons/protocol/asyncapi_parser.py`
- **What it does**: Adheres to `ProtocolSchemaInterface` specifically for AsyncAPI `3.x`. Uses `ruamel.yaml` safely. Focuses structurally on `channels` and `messages`.

## Verification Plan

### Automated Tests
- Unit Test `test_openapi_parser.py` providing valid and malformed YAML files, asserting < 5ms token generation per payload.
- Unit Test `test_asyncapi_parser.py` validating that correct explicit Pydantic properties are structurally returned.
- Tach validation to verify the `context.yaml` `forbids` bounds are respected.

### Manual Verification
N/A (covered by extensive automated testing)

## Research Notes
- `ruamel.yaml` supports `YAML(typ='safe')` natively enforcing fast IO.
- Separation of `OpenAPIParser` and `AsyncAPIParser` removes unnecessary cyclical branching logic resulting in perfectly decoupled components.

## Session Handoff
- Run `/dev docs/roadmap/features/topic_05_validation/A-VAL-01/A-VAL-01_sf1_implementation_plan.md` to begin TDD code implementation.
