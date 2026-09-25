# B-SENS-02 SF-03 — Graph Builder Orchestration & Harmonization

**Status**: DRAFT (Awaiting HITL Approval) · **FRs owned**: FR-1, FR-6, FR-7 · **Depends on**:
SF-01, SF-02 · Design: [B-SENS-02_design.md](B-SENS-02_design.md) §Sub-features → SF-03

FR-1 is AST-to-node mapping, FR-6 bounded subgraph extraction, FR-7 GraphML export. Ownership recorded
2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-10-MIG`. Proof and mutants:
`tests/unit/graph/core/builder/test_mapper.py`, `.../engine/test_graph_engine_core.py`,
`.../builder/test_orchestrator.py`.

**Not covered here:** this plan proves the composition of mapper, adapter and repository with mocks
only. `INT-US-10` FR-1 drives the real thing; `TECH-061` owns the Python-only file collection it
exposed.

## Goal

Wire the AST parser, engine and store into one `sw graph build` pipeline with ID prefixing, and move
the legacy Topology and Lineage graphs onto the same triad.

## Decisions (audit)

Each proposed option (2) at the HITL gate, and the build followed it. Only #4 carries a recorded
"Approved" comment.

1. **AST parser injection** (CRITICAL). `GraphBuilder` (SF-01) needs a raw AST dict for its
   `OntologyMapper`; importing the parser from `workspace` into `graph.builder` is a boundary
   violation.
   - Rejected (1): allow `workspace.parsers` in `specweaver.graph.core.builder.context.yaml` and
     hardcode the parser — tightly couples the Graph Domain to the physical workspace.
   - Chosen (2), Dependency Injection: the top-level CLI command (`sw graph build`) imports the
     parser, instantiates the AST-to-Dictionary adapter and passes it into `GraphBuilder(parser=...)`.
     `graph.builder` never imports the workspace layer; no `context.yaml` allowed_import changes.
2. **Feature-specific graph sub-modules** (CRITICAL). Where do Topology and Lineage graph logic go?
   - Rejected (1): all tree-traversal and cycle-detection math into `graph.engine.core` — bloats the
     core engine with feature concepts like "Lineage" and "Assurance".
   - Chosen (2): sub-modules `specweaver.graph.topology` and `specweaver.graph.lineage`. Only the raw
     graph math and SQLite data operations move there. Operational SLA logic stays in `assurance`,
     Typer command routing in `cli`; both delegate the graph work.
3. **ID prefixing** (HIGH). The design mandates prefixed IDs (e.g., `monolith:billing:ast:123`);
   SF-01 generated raw SHA-256 hashes.
   - Rejected (1): the SQLite DB prefixes on insert — the in-memory graph would carry different IDs
     than the database, a synchronization bug source.
   - Chosen (2): `SemanticHasher` accepts a prefix schema (`system`, `service`, `domain`) at
     instantiation; `GraphBuilder` feeds the prefixed hashes (e.g., `monolith:billing:ast:<hash>`)
     into the `InMemoryGraphEngine`, so IDs match across memory, GraphML exports, and SQLite. The CLI
     reads the project's context and injects the prefixes.
4. **Fix the design first** (HIGH) — Approved. Before any code, `B-SENS-02_design.md` is corrected:
   the AST parser location (it referenced `loom/commons/language/ast_parser.py`, which does not
   exist, and vaguely said "Refactors cli/lineage.py"), the DI boundary, the `topology` and `lineage`
   sub-modules, and ID Prefixing. The design doc is the source of truth for future agents. Rejected
   (1): implement and ignore it.

## As built

- **CB-1 — AST Adapter & ID Prefixing** (2026-05-01). ID Prefixing in `SemanticHasher` and
  `OntologyMapper`. The AST parser adapter uses DI and lives in `specweaver.workspace.ast.adapters`
  (pure logic), avoiding CLI context boundary violations. `TECH-003` created to restructure all AST
  parsers.
- **CB-2 — Topology Harmonization.** Graph math extracted from `assurance.graph.topology` into the
  generic `graph.topology.engine`.
- **CB-3 — Lineage Harmonization.** Legacy `context.db.log_artifact_event` logic migrated to
  `graph_store.lineage_repository.LineageRepository`. E2E tests re-wired to check the local
  `.specweaver/specweaver.db` (AD-1). E2E pipeline and CI gates pass.
- **CB-4 — CLI Wiring.** `sw graph build` Typer command in `specweaver.interfaces.cli.graph`. Wires
  `InMemoryGraphEngine`, `SqliteGraphRepository`, the parser adapter and the `GraphBuilder`
  orchestrator with DI, preventing Context Layer bleed.

**Since moved** (noted 2026-09-25): `LineageRepository` →
`src/specweaver/graph/lineage/store/lineage_repository.py`; the `sw graph build` command →
`src/specweaver/graph/interfaces/cli.py`.
