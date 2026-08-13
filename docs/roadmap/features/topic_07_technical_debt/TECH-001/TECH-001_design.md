# Design: Domain-Driven Design Unification

- **Feature ID**: TECH-001
- **Phase**: 6
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-001/TECH-001_design.md

## Feature Overview

Feature TECH-001 adds Domain-Driven Design (DDD) compliance to the SpecWeaver core system by
dismantling legacy monolithic layers (`core/config/`, `interfaces/cli/`, and `core/loom/`). It
solves the "Package by Layer" anti-pattern by extracting and relocating database mixins, CLI
commands, and Sandbox executors into their respective feature-bounded contexts (e.g., `llm_store/`,
`sandbox/git/`, `graph/cli.py`). It interacts with the Typer CLI root, the LLM telemetry database,
and the execution engine, but does NOT touch actual business logic. Key constraints: Zero Regression
Guarantee (the entire E2E test suite must pass with zero modifications to test assertions) and
strict DAL Context Enforcement via `context.yaml` files.

## Research Findings

### Codebase Patterns
Currently, `core/config/` houses a monolithic SQLite connection pool and multiple mixins
(`_db_llm_mixin.py`, `_db_telemetry_mixin.py`) serving disparate features. This must be
decentralized into specific data access layers per domain.
The `interfaces/cli/` directory contains commands for every system feature (e.g., `lineage.py`,
`graph.py`, `review.py`). These will be moved into domain-specific subdirectories (e.g.,
`src/specweaver/graph/cli.py`) and dynamically loaded.
The `core/loom/` Sandbox groups files by layer (`atoms/`, `tools/`, `commons/`) rather than by
domain (`sandbox/git/`, `sandbox/qa/`). We will refactor this to align with the 4-layer Agentic
Architecture pattern (Executor → Tool → Interface → Atom) and physically colocate these layers
inside feature-specific packages.

**ROI Analysis & Beneficiaries:**
1. **Microservice Readiness (High ROI):** Features like the Knowledge Graph (`graph/`) or Telemetry
   will profit immensely because their API, Database, and CLI layers will be strictly decoupled,
   making extraction into a standalone microservice trivial.
2. **Security & RBAC (High ROI):** Organizing `loom/` into bounded domains (`sandbox/git/`) ensures
   that security executors and role-based interfaces are isolated, severely reducing the blast
   radius of any Sandbox escape.
3. **Developer Experience (Medium ROI):** Future engineers will no longer have to jump between 4 different root directories to add a single feature.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Typer | ^0.12.0 | `Typer.add_typer()` | CLI Sub-command Registration |
| SQLAlchemy | ^2.0.0 | Engine, Session, DeclarativeBase | SQLite Persistence |

### Blueprint References
- `knowledge/secure_ai_agent_workflows/artifacts/best_practices/tool_refactoring_guide.md`
- `knowledge/secure_ai_agent_workflows/artifacts/architecture/atoms_and_tools.md`

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Extract LLM Telemetry DB | System | Separates LLM database mixins from `core/config/database.py` | A standalone `llm_store` layer handles LLM storage. |
| FR-2 | Extract Flow State DB | System | Separates pipeline state DB mixins | A standalone `flow_store` layer handles pipeline execution state. |
| FR-3 | Extract Profile DB | System | Separates profile DB mixins | A standalone `profile_store` layer handles domain profiles. |
| FR-4 | Decentralize CLI Commands | System | Relocates Typer CLI modules to their respective domains | Domain-specific `cli.py` files exist in `graph/`, `llm/`, `workflows/`, etc. |
| FR-5 | Re-register CLI Root | System | Modifies `interfaces/cli/main.py` | All decentralized commands are discovered and mounted. |
| FR-6 | Refactor Loom Sandbox Domains | System | Groups `atoms/`, `tools/`, and `commons/` into feature directories | Directories like `sandbox/git/` and `sandbox/qa/` exist with native layer files. |
| FR-7 | Config Control Flow Decoupling | System | Strips `database.py` and `settings.py` of all domain orchestration logic and inline imports. | Configuration modules contain zero control flow, shifting DB schema initialization and settings loading to Orchestrator layers (CLI). |
| FR-8 | LLM Factory Dependency Injection | System | Removes `Database` coupling from `llm/router.py` and `llm/factory.py`. | The LLM domain strictly accepts pure Pydantic `SpecWeaverSettings` via DI, severing it from active project state logic. |
| FR-9 | Eliminate `core.config` Circular Dependencies | System | Removes the mutual `tach.toml` dependency between `core.config` and `infrastructure.llm`, and between `core.config` and `core.flow`. | `core.config` is a pure leaf module with no outbound dependency on higher-level bounded contexts; both cycles are gone from `tach.toml`. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Zero Regression | 100% of the existing E2E and Unit test suite MUST pass without changing test assertions. **[proof: meta — rule about tests, docs or the diff]** |
| NFR-2 | Boundary Enforcement | All new bounded contexts MUST include a `context.yaml` enforcing `consumes`/`forbids` rules, and MUST be registered in `tach.toml` (including the new `workspace` boundary). **[proof: arch — tach/lint gate, not pytest]** |
| NFR-3 | CQRS & SQLite WAL | Decentralized `store/` layers MUST use SQLite WAL mode. Concurrent Atoms MUST use read-only sessions. **True CQRS:** Repositories MUST pass pure DTOs to the Write Queue. The CQRS worker MUST own its own isolated write session to prevent `DetachedInstanceError`s. |
| NFR-4 | Native Healer Isolation | `interfaces/cli/main.py` MUST hardcode the core agent commands AND the base File System tool. Plugin crashes must fail loudly but allow the core to boot so the agent can heal the broken plugin. |
| NFR-5 | Safe Bootstrapping | Runtime DB bootstrapping MUST use safe, idempotent `run_sync(Base.metadata.create_all)` separated from the `Database` constructor. Programmatic Alembic execution at runtime is forbidden (Alembic is CLI-only). |
| NFR-6 | Meta-Class Registry | The Sandbox MUST eradicate string-based dispatching and pre-commit generators. Tools MUST inherit from `BaseTool`, utilizing `__init_subclass__` to automatically and safely populate the in-memory registry. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Typer | 0.12.0 | `add_typer()` | Yes | Required for dynamic CLI loading. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Retain `interfaces/cli/main.py` as root | A single entrypoint is required for the `sw` binary, acting strictly as a router to domain CLIs. | No |
| AD-2 | Rename `loom` to domain prefixes | Nest Sandbox Domains under a `sandbox/` namespace (e.g. `sandbox/git`) to prevent naming collisions with pure logic domains while keeping the root directory clean. | No |

## Architecture Visualization

### 1. New Bounded Contexts
```mermaid
graph TD
    subgraph Core_Infrastructure [Core Infrastructure / Shared]
        A[interfaces/cli/main.py<br>The Rescue Core]
        B[core/config/database.py<br>CQRS Queue & session_scope]
        C[(specweaver.db<br>SQLite WAL)]
        D[BaseTool Meta-Class<br>Auto-Registry]
    end

    subgraph Domain_Graph [Domain: Knowledge Graph]
        G_CLI(graph/cli.py)
        G_API(graph/api.py)
        G_Core(graph/engine.py)
    end

    subgraph Domain_LLM [Domain: LLM & Telemetry]
        L_CLI(llm/cli.py)
        L_Store(llm/store.py<br>Models & Repo)
        L_Core(llm/adapter.py)
    end

    A -.->|Dynamically Loads| G_CLI
    A -.->|Dynamically Loads| L_CLI
    
    B ===|Write Queue & DI| L_Store
    L_Store -.->|Commits to| C
```

### 2. CQRS Database Flow
```mermaid
sequenceDiagram
    participant T1 as Task 1 (Atom)
    participant T2 as Task 2 (Atom)
    participant SQ as core/config/database<br>Async Write Queue
    participant DB as specweaver.db (WAL)

    T1->>DB: Read Query (session_scope)
    T2->>DB: Read Query (session_scope)
    Note over T1,DB: Unlimited parallel reads (WAL Mode)
    
    T1->>SQ: Emit WriteCommand(Telemetry)
    T2->>SQ: Emit WriteCommand(FlowState)
    Note over SQ,DB: Single Write Worker processes queue sequentially
    
    SQ->>DB: Execute Write (Telemetry)
    SQ->>DB: Execute Write (FlowState)
```

## Developer Guides Required

Evaluate if this feature introduces a new sub-system, paradigm, or extension layer that requires a Developer Guide for onboarding engineers.

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Domain-Driven CLI Creation | How to add a new CLI command to a bounded context and register it. | ✅ Done |

## Sub-Feature Breakdown

### SF-01: Deconstruct `core/config/` Database Monolith
- **Scope**: Extracts LLM telemetry, Flow state, and Profile database logic into independent domain stores.
- **FRs**: [FR-1, FR-2, FR-3, FR-7, FR-8]

> **FR-7 and FR-8 assigned here by `TECH-025` SF-04 on 2026-08-09, not by this story.** Every other
> row of the FR table above belonged to a sub-feature; these two belonged to none, so the table and
> this breakdown disagreed and nothing owned them. SF-01 is the right owner on the evidence rather
> than by elimination: its plan §4b ("Dependency Inversion — The Monolith Fix") describes exactly
> their work — stripping `settings.py` and `database.py` of control flow, adding
> `interfaces/cli/settings_loader.py` and `interfaces/cli/_db_utils.py`, and modifying
> `llm/router.py` and `llm/factory.py`. No scope is added to a delivered sub-feature; the
> assignment records what SF-01 already shipped. Editing a delivered story's design is authorised
> for this ticket only, by TECH-025 AD-4, and is noted here rather than made silently.
- **Inputs**: Legacy `_db_mixin` classes and SQLAlchemy models.
- **Outputs**: Decentralized `store/` packages inside their respective domains.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-001/TECH-001_sf01_implementation_plan.md

### SF-02: Decentralize `interfaces/cli/` Layer
- **Scope**: Moves CLI commands into domain folders and sets up dynamic Typer registration.
- **FRs**: [FR-4, FR-5]
- **Inputs**: Existing Typer modules in `interfaces/cli/`.
- **Outputs**: Domain-specific `cli.py` modules mounted to `main.py`.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-001/TECH-001_sf02_implementation_plan.md

### SF-03: Consolidate `core/loom/` Sandbox
- **Scope**: Reorganizes the execution engine into pure `sandbox/` bounded contexts honoring the 4-layer architecture.
- **FRs**: [FR-6]
- **Inputs**: `core/loom/atoms`, `core/loom/tools`, `core/loom/commons`.
- **Outputs**: Feature-packaged sandbox directories (`sandbox/git`, etc.).
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-001/TECH-001_sf03_implementation_plan.md

### SF-04: Eliminate `core.config` Circular Dependencies
- **Scope**: `tach.toml` currently declares `core.config` ⇄ `infrastructure.llm` and `core.config` ⇄
  `core.flow` as live mutual dependencies. A declared cycle is still a cycle, and it directly
  contradicts this feature's own "preventing circular dependencies" claim — `core.config` must
  become a pure leaf module with no outbound dependency on higher-level bounded contexts.
- **FRs**: [FR-9]
- **Inputs**: `tach.toml` dependency declarations (`core.config` at line 34 depends on `core.flow`
  and `infrastructure.llm`; `core.flow` at line 42 and `infrastructure.llm` at line 54 depend back
  on `core.config`) and the concrete imports each declares.
- **Outputs**: Both cycles removed from `tach.toml`; `core.config` has no outbound dependency on `infrastructure.llm` or `core.flow`.
- **Depends on**: none
- **Impl Plan**: not yet written
- **Note (2026-08-01)**: this scope was briefly split into a standalone `TECH-022` ticket (minted
  2026-07-31 under the finished-stories-immutable rule, since TECH-001 was — incorrectly —
  considered fully delivered at the time). Once TECH-001 itself was corrected to reflect that it was
  never actually finished, `TECH-022` was retired and its scope folded back in here as SF-04, rather
  than left to live on as a permanently "tracked" gap next to a story marked done.

## Execution Order

1. SF-01, SF-02, and SF-03 can run in parallel (no shared dependencies). SF-04 is independent and can start any time.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Deconstruct Config Monolith | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Decentralize CLI Layer | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | Consolidate Sandbox | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-04 | Eliminate `core.config` Circular Dependencies | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: SF-01–04 all fully implemented, tested, and committed (SF-04: commit
`346f64c3`, 2026-08-02). `core.config` now has `depends_on = []` in `tach.toml` — a true pure
leaf, matching its own `context.yaml`'s `consumes: []` claim for the first time. All three live
circular dependencies are gone (`core.config ⇄ infrastructure.llm`, `core.config ⇄ core.flow`,
and the previously-unnamed `core.config ⇄ workspace` found during SF-04's own Red/Blue review).
Every sub-feature's Progress Tracker row is now fully `✅` — this is the last one.
**Next step**: Run the closure gate (`specweaver-feature` Phase 4: `check_fr_coverage.py` + full
suite) before writing `Status: COMPLETE`, per the `dev` skill's own instruction for a story whose
last sub-feature just landed. If it passes, TECH-001's roadmap status can move back to 🟢.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate workflow.
