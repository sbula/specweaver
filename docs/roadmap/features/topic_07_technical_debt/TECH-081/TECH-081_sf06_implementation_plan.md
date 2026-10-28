# Implementation Plan: The Layer Check Reports Clean While the Layers Are Broken [SF-06: Graph and assurance in one direction]
- **Feature ID**: TECH-081
- **Sub-Feature**: SF-06 — Graph and assurance in one direction
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-06
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf06_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-17: `graph` imports nothing from `assurance/graph`; `graph/interfaces` passes the service name in;
`TopologyContext` moves to `commons` (AD-5). No command, option or output changes (NFR-1). Four
`deprecated` edges and their ledger rows go (NFR-2 — none added):
`graph → assurance.graph`, `infrastructure.llm → assurance.graph`,
`workflows.drafting → assurance.graph`, `workflows.planning → assurance.graph`.

## Research Notes

Read 2026-10-28.

- **The loop**: `graph/core/builder/orchestrator.py:255` (`GraphOrchestrator.build_target`) lazily
  imports `load_topology`, `resolve_service_name` from `assurance.graph.loader` only to compute
  `service_name`; `assurance/graph/loader.py:52` imports `graph.topology.engine`. No other `graph/**`
  file names `assurance` (grep, lazy and type-only included).
- **`build_target(target_path, project_path) -> int`**, static. One `src` caller:
  `graph/interfaces/cli.py:58` (`sw graph build`). No API door builds a graph. Tests: 8 calls —
  `test_orchestrator.py:205,234` (patch `assurance.graph.loader.load_topology`),
  `test_real_extraction_to_graph.py` (5), `test_graph_service_name.py:57`.
- **`TECH-004` FR-6** (service name from the root `context.yaml`) is proven today by
  `tests/integration/graph/test_graph_service_name.py` through `build_target`, and by corpus mutant
  `build-ignores-name` anchored in `build_target`. When the name is computed in the CLI, both move
  there: the test drives `sw graph build` (`CliRunner` on the app, as
  `tests/e2e/capabilities/graph/test_graph_build_persists_edges_e2e.py:72` does).
- **`TopologyContext`** (`assurance/graph/topology.py:68`): frozen dataclass, stdlib only, pure
  (`get_prompt_content`, `get_prompt_label`). Built only in `topology.py:454`. Type-only users:
  `infrastructure/llm/prompt/adders.py:14`, `workflows/drafting/_base.py:26`,
  `workflows/planning/decomposer.py:20`, `assurance/graph/loader.py:18`. Tests import it from the
  old path in 11 files (18 lines). `docs/dev_guides/pluggable_contexts.md:38` cites the old path.
- **tach**: `commons` is `utility = true`, `depends_on = []`, no `[[interfaces]]` on
  `assurance.graph`. `graph.interfaces` depends on `core.config`, `graph`, `graph.lineage`, and
  `interfaces.cli` (deprecated, SF-05). `assurance.graph` depends on `graph`, `workspace.analyzers`,
  `workspace.context` — none reaches `graph.interfaces`, so `graph.interfaces → assurance.graph` makes
  no loop.
- **Manifests**: `commons` exposes a list (FR-6 checks each name exists) — gains `TopologyContext`.
  `graph/interfaces` consumes `core/config`, `graph`, `graph/lineage` — gains `assurance/graph`.
  `graph`, `llm`, `drafting`, `planning` manifests do not name `assurance/graph` (nothing to remove).
- **Ledger**: rows `:16` (orchestrator, owed FR-17) and `:27-30` (the four deprecated edges).
  `TECH-081` corpus mutant `ledger-cites-moved-file` anchors on row `:16`, so it re-anchors on the
  `topology.py` row (`:12`), which stays (non-goal).
- `tests/unit/graph/core/builder/test_declared_imports.py` docstring names the inline crossing as
  open; it goes when the crossing goes.
- **Corpora on moved code**: `TECH-004` `build-ignores-name` (re-pointed to the CLI), `TECH-068`
  (7) and `TECH-075` (1) on `orchestrator.py` (re-pinned where the symbol changes; `.tmp/stale.py`).

## Approach (pseudocode, ordered)

**CB-1 — `TopologyContext` to `commons` (AD-5)** — kind `refactor`
1. Red: drop the three type-only `deprecated` edges (`infrastructure.llm`, `workflows.drafting`,
   `workflows.planning` → `assurance.graph`) and ledger rows `:28-30`. Tach red.
2. Green: `git mv`-style move of the class to `commons/topology_context.py` (the whole class, no
   shim); `topology.py` imports it for its own use; the four `src` users and the 11 test files import
   the new path (path-only); `commons` manifest exposes it; the guide cites the new path.

**CB-2 — the CLI hands the builder its service name (FR-17)** — kind `tooling` (Q1 `[agreed 2026-10-28]`) — closes SF-06
3. Red: drop `graph → assurance.graph` from `tach.toml` and ledger rows `:16`, `:27`; add the plain
   edge `graph.interfaces → assurance.graph`. Rewrite `test_graph_service_name.py` to run
   `sw graph build` through the CLI app (same four cases). Tach red; the test passes still (the
   builder computes the name today) — its red is the mutant in step 5.
4. Green: `build_target(target_path, project_path, *, service_name: str)`, no default; the CLI
   `build` computes `resolve_service_name(load_topology(project_path), project_path)` and passes it.
   The other test calls pass `service_name=`; `test_orchestrator.py` drops its loader patches and
   asserts the name it passed reaches the repository. `graph/interfaces` manifest consumes
   `assurance/graph`. `test_declared_imports.py` docstring loses the open-crossing paragraph.
5. Corpus: `build-ignores-name` moves to `graph/interfaces/cli.py` `build` (name → `"default"`;
   the CLI test goes red). `ledger-cites-moved-file` re-anchors on row `:12`.

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| arch | `test_tach_architectural_boundaries`, `test_tach_sees_every_module` | FR-17 | edges and ledger rows go before the code moves |
| integration | `test_graph_service_name.py` via `sw graph build` | `TECH-004` FR-6 (seam CLI → loader → builder → store) | mutant `build-ignores-name` in the CLI |
| unit | `test_orchestrator.py`: the passed name reaches the repository | FR-17 | `service_name` is not a parameter today |
| all | the suite | NFR-1 | — |

Mutants: `graph-imports-assurance` (`build_target` imports `assurance.graph.loader` again → tach
red); `llm-imports-topology` (`adders.py` imports `TopologyContext` from `assurance.graph` → tach
red); `build-ignores-name` re-pointed (above).

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–2 | suite green; `llm-imports-topology` killed; commit |
| CB-2 | steps 3–5 | suite green; `graph-imports-assurance`, `build-ignores-name` killed; stage and stop (closes SF-06) |

## Documentation

`docs/dev_guides/pluggable_contexts.md:38` — the new path. No user-facing change.

## Architecture Verification (Phase 3)

- `commons/topology_context.py`: a frozen dataclass and two string methods — no I/O, no imports
  from `specweaver`; fits `pure-logic`, `forbids: specweaver/*`, and the purpose ("cross-layer data
  models"). Precedent: `commons/scenario_models.py` (SF-03).
- `graph.interfaces → assurance.graph`: `orchestrator` CLI; `assurance.graph` reaches `graph`,
  `workspace.*` only. No loop. `graph` then depends only on `workspace.ast.adapters`.
- Four `deprecated` edges removed, none added (NFR-2).

## Audit (Phase 2) — settled

❓ **Q1 — test calls that change in CB-2.** `service_name` becomes a required parameter, so 8 test
calls change and one test is rewritten to go through the CLI. The `refactor` gate refuses any test
edit that is not a path change.
- **A:** CB-2 runs `--kind tooling`; CB-1 stays `refactor`; the design's kind line says so.
- **B:** `service_name` optional, default `"default"`; a forgotten caller silently stores every graph
  as `default` — the bug `TECH-004` FR-6 fixed.

The user chose A `[agreed 2026-10-28]`: CB-2 runs `--kind tooling`.

## Consistency (Phase 5)

- Red/Blue, 2 cycles:
  - R1 (MEDIUM) the CLI's `build` catches every exception and prints "Failed to build graph". If the
    name is computed outside that `try`, a bad `context.yaml` crashes instead (NFR-1). Blue: step 4
    computes the name inside the existing `try`.
  - R2 (MEDIUM) `topology.py` imports `TopologyContext` for its own use, so the old path still
    resolves and a test could keep using it (NFR-3). Blue: CB-1 is done only when
    `grep -rn "graph.topology import.*TopologyContext" src tests` finds nothing.
  - R3 (MEDIUM) `test_declared_imports.py` reads module-level imports only, so a lazy import of
    `assurance.graph` could come back. Blue: tach counts lazy imports; mutant
    `graph-imports-assurance` proves it.
  - R4 (LOW) `TECH-068` (7) and `TECH-075` (1) mutants sit in `orchestrator.py`; `build_target`'s
    hash changes. Blue: step 5 re-pins them; `scripts/stale_mutants.py` reports 0.
  - R5 (LOW) `loader.py:18` names `TopologyContext` type-only. Blue: it is one of the four `src`
    users re-pointed in step 2.
  - Cycle 2: no new finding.
