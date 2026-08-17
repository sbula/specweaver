# Contract: INT-US-10 — The Monolith Dependency Visualizer

- **Feature ID**: INT-US-10
- **Phase**: 8 (Integration)
- **Status**: DRAFT — the migration entry `INT-US-10-MIG` is open
- **Authority**: `ADR-004`; method and gates in [`TECH-060`](../../topic_07_technical_debt/TECH-060/TECH-060_design.md)

## What this contract is

The (sub)story contract for US-10: its **path inventory** and the **cross-feature (N)FRs** the
inventory generates. Nothing here restates what a single capability does — that belongs to the
capability's own design (`ADR-003` Type A).

US-10 holds one closed capability, `B-SENS-02` (Persistent Knowledge Graph Builder), and one unbuilt
one, `C-UI-01` (Pipeline Visualizer / `sw graph` HTML export). Its add-on group holds `B-VAL-01` ✅
under `INT-US-10-SF01`.

## Path Inventory

| # | Path | Span | Owner | Runnable today | Blocker |
|---|---|---|---|---|---|
| P-1 | AST dicts → NetworkX nodes; dedup; SQLite persist; subgraph query; GraphML export | single feature | `B-SENS-02` | yes | — |
| P-2 | Real polyglot extraction (`D-SENS-02`/`D-SENS-03`) → graph nodes | **cross-feature** | **this contract** (FR-1) | **yes** | — |
| P-3 | Persisted graph → `sw graph` HTML export | cross-feature | this contract, deferred | no | `C-UI-01` |
| P-4 | Journey: a user sees a visual map of a monolith's God Nodes | cross-feature | this contract, deferred | no | `C-UI-01` |
| P-5 | AST drift detection (`B-VAL-01`) over the persisted graph | cross-feature | `INT-US-10-SF01` | yes | — |

**P-1 is not a row this contract owns.** Every path through `B-SENS-02` alone is that capability's
own requirement, and its FR table already declares all five. What is missing is citation: measured
2026-08-17, `check_fr_coverage.py B-SENS-02` reports **0 of 5 FRs cited by any test**, while covering
tests exist for each. The dedup claim (FR-2) was probed by dropping the `semantic_hash TEXT UNIQUE`
constraint — **18 tests failed**, so the behaviour is genuinely protected and only the tag is absent.
That backfill happens under `specweaver-dev` §3.2c as first contact, from `INT-US-10-MIG`, and it is
shared: five other base contracts list `B-SENS-02` as their only closed capability, and none of them
repeats this work.

**P-2 is the finding, and it is a composition gap rather than a missing test.** Each part is
covered on its own:

| Part | Proof today |
|---|---|
| `graph_adapter.extract_ast_dict` | `tests/unit/workspace/ast/adapters/test_graph_adapter.py` — 6 cases, real parser, real file |
| `GraphBuilder.ingest_ast` | `tests/integration/graph/test_builder_integration.py` — but with `fake_java_parser`, a stub whose docstring says it *"Simulates a Tree-Sitter AST extractor purely for integration testing delta logic"* |
| `SqliteGraphRepository` | seven test files, dedup mutant-probed |
| `GraphOrchestrator.build_target` — the only place the three meet | `test_orchestrator.py:149`, which `MagicMock`s the repository, topology and engine and asserts `persist_semantic_digraph.assert_called_once()` |

So nothing anywhere drives the **real** adapter into the **real** mapper into **real** SQLite. The one
test that names the composition asserts that calls happened, not that nodes came out. An initial draft
of this row called the seam "mocked at the boundary", which overstated it — the adapter is tested; the
*pair* is not, which is the rule the 2026-08-16 handover recorded: **if two things are only ever used
together, test the pair.**

Both sides shipped, so neither can accept the requirement (`finished-stories-immutable`), which is why
it lands here.

## Cross-feature Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Real extraction feeds the graph | integration test | Build a graph from a real fixture project using the **shipped** polyglot extractor — no `fake_java_parser` — for at least Python and one non-Python language | Nodes and edges are created from the real AST shape; the extractor's output and `GraphBuilder`'s expected input are proven to agree |

Deferred rows generate no FR yet: `C-UI-01`'s interface is not defined, so a test written against it
could not fail for the right reason. `check_xfail_blockers.py` holds the obligation once it is.

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | AST dict shape | `D-SENS-02` · the extractor's returned mapping (`type`, `children`, `name`) | read `tests/integration/graph/test_builder_integration.py:11-31`, which hand-rolls that shape |
| FR-1 | graph construction | `B-SENS-02` · `GraphBuilder(engine, parser=...)` | read `graph/core/builder/orchestrator.py:14` |
| FR-1 | dedup on persist | `B-SENS-02` · `semantic_hash TEXT UNIQUE` + `ON CONFLICT(semantic_hash)` | read `graph/core/store/repository.py:69,142`; mutant-probed, 18 tests killed it |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | No skip on a repo-controlled dependency | The non-Python half of FR-1 must NOT skip on grammar availability: `tree-sitter-java` is a hard dependency in `pyproject.toml`, so absence is a defect rather than an environment gap. R8 in `check_conventions.py` enforces this, and rejected the first draft |

## Migration disposition

`INT-US-10-MIG` closes when: P-1's citations are backfilled onto `B-SENS-02` and mutant-verified,
FR-1 is written and green, and P-3/P-4 are recorded as deferred against `C-UI-01`. It does **not**
wait for `C-UI-01` — the contract keeps the deferred rows and stays open.

`INT-US-10-SF01` (P-5) is its own contract and its own migration entry.
