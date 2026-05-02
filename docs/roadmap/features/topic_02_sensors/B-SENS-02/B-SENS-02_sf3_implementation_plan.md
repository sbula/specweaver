# [Workflow: /implementation-plan] Phase 4: HITL Gate - SF-3 (Revised)

- **Feature ID**: B-SENS-02
- **Sub-Feature**: SF-3 — Graph Builder Orchestration & Harmonization
- **Design Document**: docs/roadmap/features/topic_02_sensors/B-SENS-02/B-SENS-02_design.md
- **Status**: DRAFT (Awaiting HITL Approval)

Based on our discussion regarding KISS, Single Point of Responsibility, strict boundary adherence, and **ID Prefixing**, please formally review and approve the following architectural proposals.

---

### #1. Architecture: AST Parser Injection & Boundary Adherence (CRITICAL)

**Background:** 
The orchestrator (`GraphBuilder`) in SF-1 expects a raw AST Dictionary to feed its `OntologyMapper`. If `graph.builder` directly imports the parser from the `workspace` module to get this dictionary, it creates a boundary violation.

**Options:**
1. Update `specweaver.graph.core.builder.context.yaml` to explicitly allow importing `workspace.parsers` and hardcode the parser inside the builder.
2. Utilize **Dependency Injection**. The top-level CLI command (`sw graph build`) imports the parser and passes it into `GraphBuilder(parser=...)`. `graph.builder` never imports the workspace layer.

**Analysis:**
- **Option 1**: Pros: None. Cons: Massive boundary violation. Tightly couples the Graph Domain to the physical workspace.
- **Option 2**: Pros: Perfect decoupling. The Graph Domain remains pure and testable. The CLI (Application Root) handles the dirty work of wiring dependencies together.

**Proposal:** **Option 2.** We will strictly use Dependency Injection. The top-level CLI will instantiate the AST-to-Dictionary adapter and inject it into the Graph Orchestrator. No `context.yaml` allowed_import changes are required.
> Comment: 

---

### #2. Architecture: Feature-Specific Graph Sub-Modules (CRITICAL)

**Background:**
We need to migrate the Topology Graph logic and the Lineage Graph logic into the Graph Domain. However, dumping feature-specific business logic directly into the generic `graph.engine` violates Single Point of Responsibility.

**Options:**
1. Dump all tree-traversal and cycle-detection math directly into `graph.engine.core`.
2. Create dedicated, highly-visible feature sub-modules: `specweaver.graph.topology` and `specweaver.graph.lineage`. Move the generic graph algorithms/schemas into these sub-modules. Leave the operational SLA logic in `assurance` and the Typer command routing in `cli`.

**Analysis:**
- **Option 1**: Pros: Less folders. Cons: Bloats the core engine with feature-specific concepts like "Lineage" and "Assurance".
- **Option 2**: Pros: Perfect encapsulation. Graph logic stays in the graph folder, neatly compartmentalized by feature. `assurance` and `cli` modules remain pure and delegate the heavy graph lifting to these dedicated sub-modules.

**Proposal:** **Option 2.** We will create `specweaver.graph.topology` and `specweaver.graph.lineage` sub-modules. Only the raw graph math and SQLite data operations move here. Feature-specific UX and operational validation remain in their original modules.
> Comment: 

---

### #3. Architecture: Enforcing ID Prefixing Rules (HIGH)

**Background:**
The Design Document mandates that all IDs must be prefixed (e.g., `monolith:billing:ast:123`) to ensure global uniqueness when integrating with other microservices. Currently, SF-1 generates raw SHA-256 hashes without prefixes.

**Options:**
1. Let the SQLite DB handle prefixing on insert.
2. Update `SemanticHasher` to accept a prefix schema (`system`, `service`, `domain`) upon instantiation. The Graph Orchestrator will feed the prefixed hashes (e.g., `monolith:billing:ast:<hash>`) directly into the `InMemoryGraphEngine` so they are consistent across memory, GraphML exports, and SQLite.

**Analysis:**
- **Option 1**: Pros: Less code in the engine. Cons: The in-memory NetworkX graph would have different IDs than the SQLite database, causing massive synchronization bugs.
- **Option 2**: Pros: Unified IDs across memory, disk, and exports. Perfect alignment with the design spec.

**Proposal:** **Option 2.** We will update `SemanticHasher` and `GraphBuilder` to enforce the ID prefix rule while feeding in the data. The CLI command will read the project's context and inject the correct prefixes.
> Comment: 

---

### #4. Design Document: Correcting Hallucinations & Incoherencies (HIGH)

**Background:**
The existing Design Document for B-SENS-02 contains incorrect paths and vague directives (e.g., referencing `loom/commons/language/ast_parser.py` which does not exist, and vaguely stating "Refactors cli/lineage.py").

**Options:**
1. Proceed with implementation and ignore the incorrect design doc.
2. Update `B-SENS-02_design.md` as the very first execution step to correct the AST parser location, explicitly document the Dependency Injection boundary, define the new `topology` and `lineage` sub-modules, and reaffirm the ID Prefixing implementation.

**Analysis:**
- **Option 1**: Pros: Saves 5 minutes. Cons: The Design Document (the source of truth) remains inaccurate and misleading for future agents.
- **Option 2**: Pros: Enforces "Documentation as Code" and ensures future agents understand the exact architecture.

**Proposal:** **Option 2.** Update the Design Document to reflect reality before writing any code.
> Comment: Approved.

## Execution Notes
*   **Commit Boundary 1 (AST Adapter & ID Prefixing)**: Completed on 2026-05-01. ID Prefixing was implemented in `SemanticHasher` and `OntologyMapper`. The AST Parser adapter was successfully implemented using Dependency Injection and safely housed in `specweaver.workspace.ast.adapters` (pure logic) to avoid CLI context boundary violations. Tech Debt issue `TECH-02` was created to formally restructure all AST parsers in the future.
*   **Commit Boundary 2 (Topology Harmonization)**: Completed. Extracted graph math from `assurance.graph.topology` into the generic `graph.topology.engine`.
*   **Commit Boundary 3 (Lineage Harmonization)**: Completed. Migrated legacy `context.db.log_artifact_event` logic to `graph_store.lineage_repository.LineageRepository`. Re-wired all E2E tests to check the local `.specweaver/graph.db` per AD-1 boundaries. E2E pipeline and CI gates are passing securely.
*   **Commit Boundary 4 (CLI Wiring)**: Completed. Implemented the `sw graph build` Typer command inside `specweaver.interfaces.cli.graph`. Instantiated and wired together `InMemoryGraphEngine`, `SqliteGraphRepository`, the parser adapter, and the `GraphBuilder` orchestrator using strict Dependency Injection to prevent Context Layer bleed.
