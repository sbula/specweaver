# Design: Context-Aware Flow Orchestration Integration (INT-US-04)

- **Feature ID**: INT-US-04
- **Phase**: 6
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_08_integration/INT-US-04/INT-US-04_design.md

## Feature Overview

Feature INT-US-04 adds the integration layer connecting the Validation Engine (E-VAL-01) to the SQLite Config DB (E-FLOW-01).
It solves the problem of stateless context passing by persisting validation outputs statefully,
allowing the Pipeline Runner (D-FLOW-01) to fetch sanitized, verified context for subsequent prompt
generation.
It interacts with the Config DB, Pipeline Runner, and Validation Engine, and does NOT touch external systems outside the Flow Execution domain.
Key constraints: Must satisfy the E2E integration test `tests/e2e/capabilities/assurance/test_mcp_flow_e2e.py`.

## Research Findings

### Codebase Patterns
The `PipelineRunner` coordinates steps via `RunContext`. `ValidateSpecHandler` produces validation results which must be captured.
The `Config DB` (`config/database.py`) and `flow/store.py` (`FlowRepository`) currently support
generic `ArtifactEvent`. We will need to capture and link validation results against the `run_id`
securely. The `RunContext` is already passed down, enabling robust integration. The boundary
constraints enforce that `flow` can consume `config` and `validation`.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| SQLite | N/A | SQLAlchemy async mapping | `pyproject.toml` |

### Blueprint References
No external blueprint references. Driven by the existing Flow Architecture reference.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Validation Persistence | Engine | The system SHALL extract validation findings from `E-VAL-01`, **including each `Finding`'s line, severity and suggestion** | Findings are available within `StepResult.output` **without loss**. |
| FR-2 | Stateful DB Write | `StateStore` | The system SHALL persist validation results against the current `run_id` in a **queryable table in the pipeline state DB** (`flow_validation_results`), one row per rule result | Data is stored in `pipeline_state.db`, queryable by `run_id`, `step`, `rule_id`, `status`. |
| FR-3 | Context Injection | PipelineRunner | The system SHALL restore `context.feedback` from persisted validation results **on resume**, and inject it into subsequent generation steps | A resumed run regenerates against the same findings a same-session run would have seen. |

> [!IMPORTANT]
> **FR-2 and NFR-1 were amended 2026-08-14** — see *Scope decision* below. They previously named the
> **Config DB** (`E-FLOW-01`) and an async `FlowRepository` session. Amending them is legitimate
> because SF-01 was **never delivered**, so finished-stories-immutable does not attach.

### Scope decision, 2026-08-14 — taken by the user, from `TECH-017`'s audit

`TECH-017` recorded `INT-US-04` C1 as the audit's single open **decision**: the contract claims the
Config DB persists Validation Engine outputs, and no such surface exists. The decision taken is that
**persistence was intended**, and it lands as follows.

**Why not the Config DB, as FR-2 originally said.** `store.py` states the state DB is deliberately
*"isolated from the configuration database"*. Per-run validation results are runtime state, not
configuration, so writing them to `specweaver.db` would contradict that separation and split one
run's state across two files. NFR-1's *async session* clause followed from the Config DB choice
(`FlowRepository` is async; `StateStore` is sync `sqlite3`) and is re-scoped with it.

**What is already built, and must not be rebuilt:**

| | State |
|---|---|
| FR-1 extraction into `StepResult.output` | **built, lossy** — `validation.py` keeps `rule_id`/`status`/`message` and drops `Finding` (line, severity, suggestion) entirely |
| FR-2 persistence | step results already serialize into `flow_pipeline_runs.step_records` as an **opaque JSON blob** via `model_dump()`. Not queryable, and not what C1 claims |
| FR-3 injection | **built in memory** — `gates.inject_feedback` → `context.feedback` → popped by `generation.py` / `draft.py`. It never reads a store |

**The live defect that makes this load-bearing.** `context.feedback` is an in-memory field
(`run_context.py:157`). `rehydrate_from_records` rebuilds `plan_context` on resume (`INT-US-21`
FR-3) but **not** feedback — no store or hydration module references it. So a resumed run silently
loses its validation findings, and the step that regenerates after a resume repeats the mistake
validation had already caught. Closing that is FR-3's done-when.

**Out of scope, stated so it is not rediscovered:**

* **"Sanitized" (C2).** The word maps to `E-VAL-03` (AST Prompt Injection Sanitization), which is
  `🔜` unbuilt. `INT-US-04` C2's sanitization half stays `unproven` no matter how SF-01 lands, and
  SF-01 must not be widened to cover it.
* **Cross-run history and any query/CLI surface over it.** Run-scoped only. A history feature needs
  a consumer to justify it and would be its own sub-feature.

> [!CAUTION]
> **`INT-US-04` is marked `✅ Complete` in `US-04_integration.md` while SF-01 has never been built**
> (Design ✅, Impl Plan ⬜, Dev ⬜, Committed ⬜). The status marker is false today. It is left
> untouched here rather than flipped unilaterally, because other documents key off it — but it
> should be corrected as part of, or before, SF-01's delivery.

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Performance | DB writes must not block the pipeline loop. **Amended 2026-08-14:** the original *async session* wording assumed the Config DB; `StateStore` is sync `sqlite3` in WAL mode, so the constraint is bounded write cost on the existing state connection, not an async session. |
| NFR-2 | Architecture Compliance | Changes must occur in `core.flow` or `core.config` adhering to `consumes` boundaries. **[proof: arch — tach/lint gate, not pytest]** |
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
- **Scope**: Implements the persistent handshake from validation output to **pipeline run state**,
  and closes the resume gap that loses it. Run-scoped; no cross-run history (see *Scope decision*).
- **FRs**: [FR-1, FR-2, FR-3]
- **Inputs**: Validation Engine `RuleResult` findings via `ValidateSpecHandler`.
- **Outputs**: Stateful SQLite records accessible to `GenerateCodeHandler`.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-04/INT-US-04_sf01_implementation_plan.md

### SF-02: Security Defenses Integration — RETIRED by `ADR-003` (was Pending Design)
- **Scope**: Token-Burn Circuit Breakers (EDoS Prevention) integration contract.
- **FRs**: [FR-1: Record aggregate token usage per `run_id`, FR-2: Halt execution and throw `CircuitBreakerException` if budget exceeded]
- **Inputs**: Token usage metrics from `LLMAdapter` responses.
- **Outputs**: `CircuitBreakerEvent` logged to the Config DB; Pipeline halts securely.
- **Depends on**: SF-01
- **Impl Plan**: ⬜

> **Retired 2026-08-13 by `ADR-003`.** Never designed, and its requirements above are
> `B-FLOW-05`'s (Token-Burn Circuit Breakers (EDoS Prevention)) — recording token usage, halting on budget,
> persisting suspension state, summarising history, serving read-only state are things that
> capability does, not observations a third document makes about it. **The FR text above is
> kept, not deleted**: it is the intake for `B-FLOW-05`'s design, where each becomes an FR that
> `check_fr_coverage.py` enforces. Any seam it needs is an FR on the consumer; any
> user-visible journey is a journey proof. Nothing is lost — the owner changed.

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

### SF-05: Advanced Routing & Conditional Flows Integration — RETIRED by `ADR-003` (was Pending Design)
- **Scope**: Deferred Router Mapping & Interactive Gate Variables integration contract.
- **FRs**: [FR-1: Persist pipeline suspension states (`GATE_PENDING`, etc.), FR-2: Serialize `RunContext` to DB and terminate thread, FR-3: Restore `RunContext` from DB on resume trigger]
- **Inputs**: `GateDefinition` rules; CLI/API approval events.
- **Outputs**: Suspended pipeline state records; Restored execution threads.
- **Depends on**: SF-01
- **Impl Plan**: ⬜

> **Retired 2026-08-13 by `ADR-003`.** Never designed, and its requirements above are
> `C-FLOW-10`'s (Deferred Router Mapping Capabilities) — recording token usage, halting on budget,
> persisting suspension state, summarising history, serving read-only state are things that
> capability does, not observations a third document makes about it. **The FR text above is
> kept, not deleted**: it is the intake for `C-FLOW-10`'s design, where each becomes an FR that
> `check_fr_coverage.py` enforces. Any seam it needs is an FR on the consumer; any
> user-visible journey is a journey proof. Nothing is lost — the owner changed.

### SF-06: Infinite Memory Management Integration — RETIRED by `ADR-003` (was Pending Design)
- **Scope**: Conversation Summarization (Token compression) integration contract.
- **FRs**: [FR-1: Trigger summarization handler when token count exceeds threshold, FR-2: Persist compressed summary and mark raw history events as `ARCHIVED`]
- **Inputs**: Token count metrics from `RunContext`; Raw history array.
- **Outputs**: Compressed `SummaryContext` injected into future steps; `ARCHIVED` status applied to old DB records.
- **Depends on**: SF-01
- **Impl Plan**: ⬜

> **Retired 2026-08-13 by `ADR-003`.** Never designed, and its requirements above are
> `C-INTL-04`'s (Conversation Summarization (Token compression)) — recording token usage, halting on budget,
> persisting suspension state, summarising history, serving read-only state are things that
> capability does, not observations a third document makes about it. **The FR text above is
> kept, not deleted**: it is the intake for `C-INTL-04`'s design, where each becomes an FR that
> `check_fr_coverage.py` enforces. Any seam it needs is an FR on the consumer; any
> user-visible journey is a journey proof. Nothing is lost — the owner changed.

### SF-07: Remote UI Integration — RETIRED by `ADR-003` (was Pending Design)
- **Scope**: REST API - Enterprise Configuration integration contract.
- **FRs**: [FR-1: Expose structured query boundaries for REST API fetching without executing Runner logic, FR-2: Flush real-time progress events to DB]
- **Inputs**: HTTP GET requests from the UI.
- **Outputs**: Read-only JSON serialization of `ArtifactEvent` and `ValidationResult` states.
- **Depends on**: SF-01
- **Impl Plan**: ⬜

> **Retired 2026-08-13 by `ADR-003`.** Never designed, and its requirements above are
> `D-UI-05`'s (REST API - Enterprise Configuration) — recording token usage, halting on budget,
> persisting suspension state, summarising history, serving read-only state are things that
> capability does, not observations a third document makes about it. **The FR text above is
> kept, not deleted**: it is the intake for `D-UI-05`'s design, where each becomes an FR that
> `check_fr_coverage.py` enforces. Any seam it needs is an FR on the consumer; any
> user-visible journey is a journey proof. Nothing is lost — the owner changed.

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
