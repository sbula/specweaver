# Design: Context-Aware Flow Orchestration Integration (INT-US-04)

- **Feature ID**: INT-US-04
- **Phase**: 6
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_08_integration/INT-US-04/INT-US-04_design.md

## Feature Overview

Feature INT-US-04 adds the integration layer connecting the Validation Engine (E-VAL-01) to the SQLite Config DB (E-FLOW-01).
It solves the problem of stateless context passing by persisting validation outputs statefully, allowing the Pipeline Runner (D-FLOW-01) to fetch sanitized, verified context for subsequent prompt generation.
It interacts with the Config DB, Pipeline Runner, and Validation Engine, and does NOT touch external systems outside the Flow Execution domain.
Key constraints: Must satisfy the E2E integration test `tests/e2e/capabilities/assurance/test_mcp_flow_e2e.py`.

## Research Findings

### Codebase Patterns
The `PipelineRunner` coordinates steps via `RunContext`. `ValidateSpecHandler` produces validation results which must be captured.
The `Config DB` (`config/database.py`) and `flow/store.py` (`FlowRepository`) currently support generic `ArtifactEvent`. We will need to capture and link validation results against the `run_id` securely. The `RunContext` is already passed down, enabling robust integration. The boundary constraints enforce that `flow` can consume `config` and `validation`.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| SQLite | N/A | SQLAlchemy async mapping | `pyproject.toml` |

### Blueprint References
No external blueprint references. Driven by the existing Flow Architecture reference.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Validation Persistence | Engine | The system SHALL extract validation findings from `E-VAL-01` | Findings are securely available within `StepResult.outputs`. |
| FR-2 | Stateful DB Write | FlowRepository | The system SHALL persist the validation context against the current `run_id` | Data is stored in SQLite Config DB (`E-FLOW-01`). |
| FR-3 | Context Injection | PipelineRunner | The system SHALL fetch persisted validation context | The context is injected into subsequent generation steps. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | DB writes must use async session execution without locking the thread. |
| NFR-2 | Architecture Compliance | Changes must occur in `core.flow` or `core.config` adhering to `consumes` boundaries. |
| NFR-3 | Compatibility | Must pass existing E2E testing: `test_mcp_flow_e2e.py` without regressions. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| SQLAlchemy | 2.0+ | `ext.asyncio.AsyncSession` | Y | Standard stack dependency. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Extend `FlowRepository` | Centralizes flow state rather than adding logic to `validation` (which forbids DB I/O). | No |
| AD-2 | Leverage `RunContext.db` | Context is universally available in pipeline steps ensuring DI compatibility. | No |

## Developer Guides Required

Evaluate if this feature introduces a new sub-system, paradigm, or extension layer that requires a Developer Guide for onboarding engineers.

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Pipeline Context State | Documenting how Handlers can persist their outputs robustly. | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-01: Core Flow DB Integration
- **Scope**: Implements the persistent handshake from validation output to configuration state.
- **FRs**: [FR-1, FR-2, FR-3]
- **Inputs**: Validation Engine `RuleResult` findings via `ValidateSpecHandler`.
- **Outputs**: Stateful SQLite records accessible to `GenerateCodeHandler`.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-04/INT-US-04_sf01_implementation_plan.md

### SF-02: Security Defenses Integration (Pending Design)
- **Scope**: Token-Burn Circuit Breakers (EDoS Prevention) integration contract.
- **FRs**: [FR-1: Record aggregate token usage per `run_id`, FR-2: Halt execution and throw `CircuitBreakerException` if budget exceeded]
- **Inputs**: Token usage metrics from `LLMAdapter` responses.
- **Outputs**: `CircuitBreakerEvent` logged to the Config DB; Pipeline halts securely.
- **Depends on**: SF-01
- **Impl Plan**: ⬜

### SF-03: Parallel Multi-Spec Execution Integration (✅ Integrated)
- **Scope**: Multi-Spec Pipeline Fan-Out integration contract.
- **FRs**: [FR-1: Support hierarchical state tracking via `parent_id`, FR-2: Aggregate validation findings from all fan-out sub-runs]
- **Inputs**: Array of Spec Targets triggering a `fan_out` pipeline action.
- **Outputs**: Hierarchical `ArtifactEvent` records in the DB; aggregated `StepResult`.
- **Depends on**: SF-01
- **Impl Plan**: ✅

### SF-04: Context Mention Highlighting Integration (✅ Integrated)
- **Scope**: Auto Spec-Mention Detection integration contract.
- **FRs**: [FR-1: Query Config DB for verified state of Spec Mentions, FR-2: Append retrieved state as supplementary context into `RunContext`]
- **Inputs**: List of mentioned Spec IDs detected by the Topology Graph.
- **Outputs**: Sanitized context string containing the state of the mentioned specs injected into the prompt.
- **Depends on**: SF-01
- **Impl Plan**: ✅

### SF-05: Advanced Routing & Conditional Flows Integration (Pending Design)
- **Scope**: Deferred Router Mapping & Interactive Gate Variables integration contract.
- **FRs**: [FR-1: Persist pipeline suspension states (`GATE_PENDING`, etc.), FR-2: Serialize `RunContext` to DB and terminate thread, FR-3: Restore `RunContext` from DB on resume trigger]
- **Inputs**: `GateDefinition` rules; CLI/API approval events.
- **Outputs**: Suspended pipeline state records; Restored execution threads.
- **Depends on**: SF-01
- **Impl Plan**: ⬜

### SF-06: Infinite Memory Management Integration (Pending Design)
- **Scope**: Conversation Summarization (Token compression) integration contract.
- **FRs**: [FR-1: Trigger summarization handler when token count exceeds threshold, FR-2: Persist compressed summary and mark raw history events as `ARCHIVED`]
- **Inputs**: Token count metrics from `RunContext`; Raw history array.
- **Outputs**: Compressed `SummaryContext` injected into future steps; `ARCHIVED` status applied to old DB records.
- **Depends on**: SF-01
- **Impl Plan**: ⬜

### SF-07: Remote UI Integration (Pending Design)
- **Scope**: REST API - Enterprise Configuration integration contract.
- **FRs**: [FR-1: Expose structured query boundaries for REST API fetching without executing Runner logic, FR-2: Flush real-time progress events to DB]
- **Inputs**: HTTP GET requests from the UI.
- **Outputs**: Read-only JSON serialization of `ArtifactEvent` and `ValidationResult` states.
- **Depends on**: SF-01
- **Impl Plan**: ⬜

### SF-08: Configurable Prompt Render Profiles Integration
- **Scope**: Integrating C-INTL-05 `RenderProfile` capabilities into the pipeline orchestration layer via Step Parameter Injection and a `ProfileRegistry`.
- **FRs**: [FR-1: Expose `render_profile` in `PipelineStep.params`, FR-2: Provide a `ProfileRegistry` to resolve named profiles, FR-3: Update Handlers to resolve dynamic profiles before fallback.]
- **Inputs**: `PipelineStep` params dictionary; `ProfileRegistry` mapping.
- **Outputs**: Handlers executing with the dynamically resolved `RenderProfile`.
- **Depends on**: SF-01
- **Impl Plan**: ✅

### SF-09: Declarative Dynamic Prompt Routing Integration (Pending Design)
- **Scope**: B-INTL-10 Declarative Prompt Optimization (DSPy-style routing) integration contract.
- **Depends on**: SF-01
- **Impl Plan**: ⬜

## Execution Order

1. SF-01 (no deps — start immediately)
2. SF-02 through SF-09 can run in parallel (all depend on SF-01)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Core Flow DB Integration | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-02 | Security Defenses Integration | SF-01 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-03 | Parallel Multi-Spec Execution | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-04 | Context Mention Highlighting | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-05 | Advanced Routing & Conditional Flows | SF-01 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-06 | Infinite Memory Management | SF-01 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-07 | Remote UI Integration | SF-01 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-08 | Configurable Prompt Render Profiles Integration | SF-01 | ✅ | ✅ | ✅ | ✅ | ⬜ |
| SF-09 | Declarative Dynamic Prompt Routing Integration | SF-01 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Impl Plan APPROVED.
**Next step**: Run `/dev` for SF-08 implementation.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate workflow.
