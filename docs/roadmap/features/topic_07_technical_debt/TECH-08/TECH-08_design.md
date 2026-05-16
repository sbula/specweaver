# Design: TECH-08 CLI ApplicationService Layer Extraction

- **Feature ID**: TECH-08
- **Phase**: 5
- **Status**: DRAFT
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-08/TECH-08_design.md

## Feature Overview

Feature TECH-08 adds an explicit `ApplicationService` (or `UseCase`) layer between the CLI Typer routers and the Flow Engine. It solves the problem of CLI routers acting as the "Composition Root" and handling complex context hydration (e.g., loading the Constitution, Standards, and LLM Adapter). By extracting this logic into `specweaver.core.application`, the Delivery Mechanism (`interfaces/cli` and `interfaces/api`) strictly handles only argument parsing and HTTP/CLI error formatting. It interacts with the `core.flow` engine and the public APIs of the bounded contexts (`workspace`, `assurance`), and it strictly does NOT touch the internal execution logic of the domains themselves. Key constraints: Must adhere perfectly to Hexagonal Architecture principles and resolve the cross-interface "spider web" identified in ADR 002.

## Research Findings

### Codebase Patterns
- **Current State**: The `RunContext` initialization (loading constitution, standards, binding DB, wiring the LLM Router and Adapter) is heavily duplicated across 6 entry points: `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`, `interfaces/api/v1/implement.py`, `interfaces/api/v1/review.py`, and `assurance/validation/interfaces/cli_drift.py`.
- **Cross-Interface Spider Web**: To hydrate the context, the CLI and API modules are currently importing private helper functions (`_load_constitution_content`, `_load_standards_content`, `_require_llm_adapter`) directly from *other* interface modules. This is a severe architectural anti-pattern.
- **Architectural Boundary**: By creating `src/specweaver/core/application`, we establish a valid Hexagonal Application layer that orchestrates the Domain (`core.flow`, `workspace`) and Infrastructure (`llm`).

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Typer | 0.12+ | CLI Routing | pyproject.toml |
| FastAPI | 0.111+ | REST API Routing | pyproject.toml |

### Blueprint References
- `docs/architecture/07_architectural_decision_records/adr_002_composition_root_vs_factories.md` (Formalizes the decision to keep hydration in the Composition Root, not the Engine).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | **Create Service** | Developer | Instantiate `FlowOrchestrator` | A reusable Application Service exists that accepts standard execution parameters (`project_path`, `spec_path`) and either a `pipeline_name` string or a dynamic `PipelineDefinition` object. |
| FR-2 | **Encapsulate Hydration** | `FlowOrchestrator` | Construct `RunContext` | The service successfully loads the `Constitution`, `Standards`, and DB session, and binds them to the context, replacing the CLI's logic. |
| FR-3 | **Encapsulate Infrastructure** | `FlowOrchestrator` | Initialize LLM | The service accepts a `require_llm` flag. If True, it successfully resolves and binds the `ModelRouter` and `LLM Adapter` to the context before invoking the `PipelineRunner`. If False, it bypasses LLM loading to prevent crashes in CI environments. |
| FR-4 | **Refactor CLI** | CLI Routers | Invoke `FlowOrchestrator` | `core.flow.interfaces.cli`, `workflows.review.interfaces.cli`, and `workflows.implementation.interfaces.cli` no longer contain `RunContext` initialization or cross-interface imports. |
| FR-5 | **Refactor API** | REST API Routers | Invoke `FlowOrchestrator` | `api/v1/implement.py` and `api/v1/review.py` no longer contain `RunContext` initialization or cross-interface imports. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | **Architecture Strictness** | The `core.application` module MUST be sealed in `tach.toml` and ONLY depend on `workspace`, `assurance`, `infrastructure.llm`, and `core.flow`. No domain module may depend on `core.application`. |
| NFR-2 | **Decoupled Error Handling** | The `core.application` module MUST NOT import `typer`, `fastapi`, or `rich`. All errors must be pure Domain Exceptions (e.g., `MissingConstitutionError`) that the Delivery Mechanism catches and translates. |
| NFR-3 | **Interface Stability** | The external CLI commands (`sw run`, `sw review`) and HTTP endpoints MUST NOT change their external signatures, arguments, or behavior. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Typer | 0.12.3 | `typer.Typer()` | Y | Pure Python refactor. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Create `src/specweaver/core/application` | Establishes a true Hexagonal Application Service layer that orchestrates the Domain. | No |
| AD-2 | Cut `interfaces/cli` cross-imports | Removing `_load_*` imports from other Typer routers eliminates the spider web and enforces isolation. | No |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Hexagonal Application Services | Documentation on where to place orchestration logic (Application Services) vs CLI routing. | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: FlowOrchestrator Extraction
- **Scope**: Create the `core.application` boundary, implement pure Domain Exceptions, build the `FlowOrchestrator` service, and centralize the `RunContext` hydration logic with lazy LLM loading.
- **FRs**: [FR-1, FR-2, FR-3]
- **Inputs**: `project_path`, `spec_path`, `pipeline_name`, `target_path` from any Delivery Mechanism.
- **Outputs**: Returns a fully executed `PipelineRunState`.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-08/TECH-08_sf1_implementation_plan.md

### SF-2: Delivery Mechanism Refactoring
- **Scope**: Refactor all 4 CLI Typer routers and all 2 FastAPI routers to instantiate and invoke the `FlowOrchestrator`, cutting all cross-interface imports and updating `tach.toml`.
- **FRs**: [FR-4, FR-5]
- **Inputs**: Incoming CLI/API commands.
- **Outputs**: Output mapped to Typer console or FastAPI JSON response.
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-08/TECH-08_sf2_implementation_plan.md

## Execution Order

1. SF-1: Extract the logic into `core.application.FlowOrchestrator`. (Starts immediately).
2. SF-2: Strip the duplication from the CLI/API layers and enforce `tach.toml` boundaries. (Depends on SF-1).

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | FlowOrchestrator Extraction | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-2 | Delivery Mechanism Refactoring | SF-1 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design DRAFT — awaiting HITL approval.
**Next step**: After approval, run:
`/implementation-plan docs/roadmap/features/topic_07_technical_debt/TECH-08/TECH-08_design.md SF-1`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
