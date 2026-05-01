# TECH-01: Domain-Driven Design Unification

**Status:** Backlog  
**Type:** Technical Debt / Architecture Epic  

## Background

As SpecWeaver has evolved, the architecture has drifted into a hybrid state. Some modules (e.g., `drafting/`, `review/`, `planning/`) successfully follow Domain-Driven Design (Package by Feature) principles, encapsulating their models, orchestrators, and logic within a single Bounded Context.

However, other modules have fallen into the "Package by Layer" trap, specifically:
1. **The `config/` Dumping Ground:** `config/` is currently acting as a global database bucket for all SQLite storage (e.g., `config/database.py`, `llm_telemetry_mixin`, profile storage). This violates DDD, as feature-specific persistence logic is physically ripped away from its feature.
2. **The `cli/` Monolith:** All CLI presentation code is stuffed into `cli/` rather than being nested within the respective domain folders (e.g., `cli/lineage.py` instead of `lineage/cli/`).
3. **The `loom/` Hybrid:** The Sandbox is split by layer (`commons/`, `tools/`, `atoms/`) but sub-split by feature (`git/`, `qa_runner/`), leading to "High Scatter" where modifying a single tool requires traversing three separate directories.

With the introduction of the B-SENS-02 Graph Triad (`graph/`, `graph_store/`, `graph_builder/`), we established the first truly pure DDD implementation that enforces Semantic Boundary Compliance. 

## Scope & Objective

The objective of this Epic is to execute a massive refactoring effort to align the legacy codebase with the B-SENS-02 DDD principles, preparing SpecWeaver for extraction into independent microservices.

### FR-1: Deconstruct the `config/` Database Monolith
*   Extract LLM telemetry DB logic into an `llm_store/` adapter.
*   Extract pipeline state DB logic into a `flow_store/` adapter.
*   Extract domain profile DB logic into a `profile_store/` adapter.
*   Reduce `config/database.py` to handle *only* core environment configurations.

### FR-2: Decentralize the `cli/` Presentation Layer
*   Move `cli/lineage.py` into a domain-specific folder (`lineage/cli/` or `graph_builder/cli/`).
*   Move `cli/constitution_commands.py` into `constitution/cli/`.
*   Ensure each CLI segment is dynamically registered to the root Typer app without hardcoded monolithic imports.

### FR-3: Consolidate the `loom/` Sandbox
*   Reorganize the Sandbox into true Bounded Contexts: `sandbox_git/`, `sandbox_qa/`, `sandbox_fs/`.
*   Inside each bounded context, establish the `atom/`, `tool/`, and `executor/` layers natively.

## Security & Architectural Gates
*   **Zero Regression Guarantee:** This is a purely structural refactor. No business logic may be altered. The entire E2E test suite must pass with 0 modifications to test assertions.
*   **DAL Context Enforcement:** All newly created Bounded Context folders must contain strict `context.yaml` files ensuring that Domain A never directly imports Domain B's logic or storage layers.
