# Implementation Plan: Protocol & Schema Analyzers [SF-2: gRPC Protobuf Parser]
- **Feature ID**: 3.31
- **Sub-Feature**: SF-2 — gRPC Protobuf Parser
- **Design Document**: docs/roadmap/features/topic_05_validation/A-VAL-01/A-VAL-01_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/features/topic_05_validation/A-VAL-01/A-VAL-01_sf2_implementation_plan.md
- **Status**: APPROVED

## Goal Description
Implement the gRPC Protocol parser relying on `proto-schema-parser` to extract AST schemas from `.proto` logic, mapping services directly into the normalized `ProtocolSchemaInterface` Pydantic bounds drafted in SF-1.

## Proposed Changes

### `pyproject.toml`
#### [MODIFY] pyproject.toml
- **What it does**: Adds `proto-schema-parser>=0.5.0` to the `dependencies` array.

### `core/loom/commons/protocol`
#### [MODIFY] `src/specweaver/core/loom/commons/protocol/models.py`
- **What it does**: Small addition if necessary (handled mostly dynamically via generic `payload: dict` or custom properties in existing models) to capture gRPC-specific semantics while resolving into standard `ProtocolEndpoint`.

#### [NEW] `src/specweaver/core/loom/commons/protocol/grpc_parser.py`
- **What it does**: Implements `ProtocolSchemaInterface` using `proto_schema_parser.parser.Parser`.
- **Parsing Rules**:
  - Top-level `service` nodes iterate their nested `rpc` methods.
  - Each `rpc` method maps out to `ProtocolEndpoint` (`method` ="RPC", `path`="{service_name}/{rpc_name}").
  - `message` items are directly captured into `ProtocolMessage` models.
> [!NOTE] 
> Based on HITL approval, gRPC abstractions are forcibly mapped inside standard `ProtocolEndpoint` boundaries to maintain polymorphism for downstream Flow pipelines natively checking missing endpoints. 

## Verification Plan

### Automated Tests
- Unit Test `test_grpc_parser.py` extracting nodes from complex layered `.proto` definitions successfully capturing RPC request/response data types. 
- Validation confirming NFR-2 bounds (zero build extensions invoked, native execution relies exclusively on standard Python `ast`-style visiting).

### Manual Verification
N/A (Covered entirely by pure logic unit tests)

## Research Notes
- `tree-sitter-proto` omitted specifically to prevent native `.so` library compilation crashing CI/CD sandboxes locking GCC builds.
- Mapping gRPC Services seamlessly correlates RPC parameters matching Request types and Returns payload typing to Response Types, satisfying generic schemas.

## Session Handoff
- Wait until full `/feature` plans are constructed, then run `/dev docs/roadmap/features/topic_05_validation/A-VAL-01/A-VAL-01_sf2_implementation_plan.md`.
