# Design: Protocol & Schema Analyzers

- **Feature ID**: 3.31
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_05_validation/A-VAL-01/A-VAL-01_design.md

## Feature Overview

Feature 3.31 adds Protocol & Schema Analyzers to the CodeStructure framework via a new Architecture-aligned `commons/protocol` module. It solves the problem of contract drift across microservices by parsing OpenAPI, AsyncAPI, and gRPC `.proto` files structurally without building heavy toolchains (using native Python `ruamel.yaml` and `tree-sitter-proto` respectively). It interacts with the existing validation engine and pipeline components to mathematically assert that backend API implementations match the externally facing contracts, without invoking `protoc` or C++ build extensions.
Key constraints: pure python/tree-sitter approach to avoid compilation errors; lightweight integration into existing `assurance/validation` engine.

## Research Findings

### Codebase Patterns
Existing AST extraction uses `tree-sitter` in `core/loom/commons/language/` to enforce CodeStructure Interface for programming languages. To avoid forcing YAML or `.proto` into code interfaces, we will introduce `commons/protocol` designed specifically for APIs. We will reuse `ruamel.yaml` already defined in `pyproject.toml`.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| ruamel.yaml | >=0.18 | Schema deserialization | PyPI (already in project) |
| tree-sitter-proto | >=latest | AST parsing | PyPI |
| proto-schema-parser | >=latest | AST parsing | PyPI (Alternative) |

### Blueprint References
None specific from ORIGINS.md beyond general drift-prevention alignment.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Parse YAML schemas | System | Uses `ruamel.yaml` to read OpenAPI and AsyncAPI | Abstract endpoint and message dictionaries are extracted |
| FR-2 | Parse Proto schemas | System | Uses `tree-sitter-proto` (or `proto-schema-parser`) to extract `.proto` AST | Service and RPC skeletons and message payloads are extracted |
| FR-3 | Implement Interface | System | Provides `ProtocolSchemaInterface` mapping | Unifies YAML and `.proto` output into standard components, endpoints, and schema models |
| FR-4 | Implement Engine Connectors | System | Provides `ProtocolTool` and `ProtocolAtom` | Maps `ProtocolSchemaInterface` into Flow engine capabilities |
| FR-5 | Catch Contract Drift | Validation | Compares Code ASTs against Protocol definitions | Emits ERRORs on missing/mismatched signatures |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Speed / Overhead | Parsing must be < 50ms per file to avoid blocking pipeline. |
| NFR-2 | Build Toolchains | Must operate fully natively without requiring `protoc` or C++ binary extensions. |
| NFR-3 | Compatibility | Output models must natively match/compare against `core/loom/commons/language` AST nodes. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| tree-sitter-proto | >=2.0 | tree-sitter grammar | Y | Pure tree-sitter extension |
| proto-schema-parser | >=0.5.0 | Parser().parse(txt) | Y | Fallback pure python parser |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Create `core/loom/commons/protocol` | Splits interface schemas (OpenAPI/proto) out of programming code (Python/Rust) AST Extractors. | Yes — approved by steve on 2026-04-18 |
| AD-2 | Avoid official `protobuf` | Official library does not parse `.proto` at runtime without external `protoc` generation binary overhead. | No |

## Developer Guides Required

Evaluate if this feature introduces a new sub-system, paradigm, or extension layer that requires a Developer Guide for onboarding engineers.

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Protocol Analyzers | Integrating new schemas/protocols into `commons/protocol` | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: ProtocolSchemaInterface & YAML Parsers
- **Scope**: Creates the `commons/protocol` core boundaries and implements YAML-based extractors.
- **FRs**: [FR-1, FR-3]
- **Inputs**: OpenAPI / AsyncAPI raw file content 
- **Outputs**: Normalized Protocol Schema DTOs (Endpoints, Messages)
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_05_validation/A-VAL-01/A-VAL-01_sf1_implementation_plan.md

### SF-2: gRPC Protobuf Parser
- **Scope**: Adds `.proto` parsing capabilities extending the `ProtocolSchemaInterface`.
- **FRs**: [FR-2]
- **Inputs**: raw `.proto` definitions
- **Outputs**: Normalized Protocol Schema DTOs mapped from RPC services
- **Depends on**: [SF-1]
- **Impl Plan**: docs/roadmap/features/topic_05_validation/A-VAL-01/A-VAL-01_sf2_implementation_plan.md

### SF-3: Core Flow Engine Alignment (Atom/Tool)
- **Scope**: Exposes the schema extractors securely to the Validation and Review layer via Engine Atoms.
- **FRs**: [FR-4]
- **Inputs**: File intents from LLM adapters
- **Outputs**: Extracted Schema Nodes returned to orchestrator context
- **Depends on**: [SF-1, SF-2]
- **Impl Plan**: docs/roadmap/features/topic_05_validation/A-VAL-01/A-VAL-01_sf3_implementation_plan.md

### SF-4: Contract Drift Validation Rules
- **Scope**: Connects `ValidationEngine` Rules (e.g. `C13_Contract_Drift.py`) to mathematically assert backend code matches Protocol payloads.
- **FRs**: [FR-5]
- **Inputs**: AST Code nodes and Protocol Schema nodes
- **Outputs**: Validation Findings (PASS or ERROR)
- **Depends on**: [SF-3]
- **Impl Plan**: docs/roadmap/features/topic_05_validation/A-VAL-01/A-VAL-01_sf4_implementation_plan.md

## Execution Order

Topological sort.
1. SF-1 (no deps — start immediately)
2. SF-2 (depends only on SF-1)
3. SF-3 (depends on SF-1 and SF-2)
4. SF-4 (depends on SF-3)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | ProtocolSchemaInterface & YAML Parsers | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | gRPC Protobuf Parser | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-3 | Core Flow Engine Alignment (Atom/Tool) | SF-1, SF-2 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-4 | Contract Drift Validation Rules | SF-3 | ✅ | ✅ | ✅ | ✅ | ⬜ |

## Session Handoff

**Current status**: SF-4 Completed ✅. Feature 3.31 has been perfectly integrated and validated mathematically by the AST Engine!
**Next step**: Run `git commit` and trigger Phase 4 roadmap.
in any row and resume from there using the appropriate workflow.
