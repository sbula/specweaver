# INT-US-10 — The Monolith Dependency Visualizer (Contract)

**Status**: DRAFT — the migration entry `INT-US-10-MIG` is open · **Phase**: 8 (Integration) ·
**Feature ID**: INT-US-10

| | |
|---|---|
| Authority | `ADR-004`; method and gates in [`TECH-060`](../../topic_07_technical_debt/TECH-060/TECH-060_design.md) |
| Closed capability | `B-SENS-02` (Persistent Knowledge Graph Builder) |
| Unbuilt capability | `C-UI-01` (Pipeline Visualizer / `sw graph` HTML export) |
| Add-on group | `B-VAL-01` ✅ under `INT-US-10-SF01` |
| Open on | `TECH-061` (FR-1's polyglot case) · `C-UI-01` (P-3, P-4) |

## What this contract is

The (sub)story contract for US-10: its **path inventory** and the **cross-feature (N)FRs** the
inventory generates. What a single capability does belongs to that capability's own design
(`ADR-003` Type A).

## Path Inventory

| # | Path | Span | Owner | Runnable today | Blocker |
|---|---|---|---|---|---|
| P-1 | AST dicts → NetworkX nodes; dedup; SQLite persist; subgraph query; GraphML export | single feature | `B-SENS-02` | yes | — |
| P-2 | Real polyglot extraction (`D-SENS-02`/`D-SENS-03`) → graph nodes | **cross-feature** | **this contract** (FR-1) | **yes** | — |
| P-3 | Persisted graph → `sw graph` HTML export | cross-feature | this contract, deferred | no | `C-UI-01` |
| P-4 | Journey: a user sees a visual map of a monolith's God Nodes | cross-feature | this contract, deferred | no | `C-UI-01` |
| P-5 | AST drift detection (`B-VAL-01`) over the persisted graph | cross-feature | `INT-US-10-SF01` | yes | — |

**P-1 is not owned here.** Every path through `B-SENS-02` alone is that capability's requirement; its
FR table declares all five. Only the citations were missing: on 2026-08-17 `check_fr_coverage.py
B-SENS-02` reported **0 of 5 FRs cited by any test**, though covering tests existed. Dedup (FR-2) was
probed by dropping the `semantic_hash TEXT UNIQUE` constraint — **18 tests failed**, so the behaviour
is protected and only the tag was absent. The backfill runs under `specweaver-dev` §3.2c as first
contact, from `INT-US-10-MIG`.

**P-2 is a composition gap, not a missing test.** Each part is covered on its own:

| Part | Proof |
|---|---|
| `graph_adapter.extract_ast_dict` | `tests/unit/workspace/ast/adapters/test_graph_adapter.py` — 6 cases, real parser, real file |
| `GraphBuilder.ingest_ast` | `tests/integration/graph/test_builder_integration.py` — with `fake_java_parser`, a stub that *"Simulates a Tree-Sitter AST extractor purely for integration testing delta logic"* |
| `SqliteGraphRepository` | seven test files, dedup mutant-probed |
| `GraphOrchestrator.build_target` — the only place the three meet | `test_orchestrator.py:149` `MagicMock`s the repository, topology and engine and asserts `persist_semantic_digraph.assert_called_once()` |

Nothing drove the **real** adapter into the **real** mapper into **real** SQLite; the one test naming
the composition asserted calls, not nodes. Rule (2026-08-16 handover): **if two things are only ever
used together, test the pair.** Both sides shipped, so neither can take the requirement
(`finished-stories-immutable`); it lands here.

## Cross-feature Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Real extraction feeds the graph | integration test | Build a graph from a real fixture project using the **shipped** polyglot extractor — no `fake_java_parser` — for at least Python and one non-Python language | Nodes and edges are created from the real AST shape; the extractor's output and `GraphBuilder`'s expected input are proven to agree |

Deferred rows generate no FR yet: `C-UI-01`'s interface is undefined, so a test against it could not
fail for the right reason. `check_xfail_blockers.py` holds the obligation once it is.

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | AST dict shape | `D-SENS-02` · the extractor's returned mapping (`type`, `children`, `name`) | read `tests/integration/graph/test_builder_integration.py:11-31`, which hand-rolls that shape |
| FR-1 | graph construction | `B-SENS-02` · `GraphBuilder(engine, parser=...)` | read `graph/core/builder/orchestrator.py:14` |
| FR-1 | dedup on persist | `B-SENS-02` · `semantic_hash TEXT UNIQUE` + `ON CONFLICT(semantic_hash)` | read `graph/core/store/repository.py:69,142`; mutant-probed, 18 tests killed it |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | No skip on a repo-controlled dependency | The non-Python half of FR-1 must NOT skip on grammar availability: `tree-sitter-java` is a hard dependency in `pyproject.toml`, so absence is a defect, not an environment gap. Enforced by R8 in `check_conventions.py` |

## Migration disposition

**`INT-US-10-MIG` is discharged (2026-08-17).** P-1's citations are backfilled and mutant-verified,
FR-1 is written and green, P-3/P-4 are deferred against `C-UI-01`. The migration finishes; the
contract keeps those rows and stays open — the split `ADR-004` draws.

**`B-SENS-02` passes its own FR ledger** — 5 of 5 cited, each behind a killed mutant,
`check_fr_coverage.py` exit 0. First of the 62 delivered capabilities the migration brought there;
the repo-wide FR sweep fell 233 → 229.

The backfill is **shared**: `INT-US-11`, `-12`, `-15`, `-26` and `-27` list `B-SENS-02` as their only
closed capability and cite this work instead of repeating it — the payoff of ordering the batch by
capability cluster.

`INT-US-10-SF01` (P-5) is its own contract and its own migration entry.
