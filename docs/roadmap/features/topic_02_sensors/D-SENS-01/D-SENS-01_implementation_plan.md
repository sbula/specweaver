# D-SENS-01 — Topology Graph

**FRs owned: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7.** Recorded 2026-08-17 under
`specweaver-dev` §3.2c, from `INT-US-08-MIG`.

> This file is a **record**, not a plan. The capability shipped before the FR ledger existed and had
> no feature directory at all, so there was never a plan to state ownership on. It exists because
> `check_fr_coverage.py` requires every FR to be carried somewhere, and inventing a retrospective
> multi-sub-feature breakdown would be fiction. One capability, one owner.

## Where it lives

| Surface | Site |
|---|---|
| Graph, queries, prompt rendering | `assurance/graph/topology.py` — `TopologyGraph`, `TopologyNode`, `TopologyContext` |
| Engine behind it | `graph/topology/engine.py`, via `TopologyEngineProtocol` (add_node/add_edge/traverse/cycles/neighbors_within) |
| Inference for undeclared directories | `workspace/context/inferrer.py` + `workspace/analyzers/factory.py`, called from `_auto_infer_missing` |

## Proof and mutants

| FR | Test file | Mutant |
|---|---|---|
| FR-1 | `tests/unit/assurance/graph/test_topology.py` | the `context.yaml` walk replaced by an empty iterable — **50 files fail** |
| FR-2 | `tests/unit/assurance/graph/test_topology.py` | `impact_of` flipped to `forward=True`, returning dependencies as though they were consumers — 5 fail |
| FR-3 | `tests/unit/assurance/graph/test_topology.py` | inferred nodes discarded instead of added |
| FR-4 | `tests/unit/assurance/graph/test_topology.py` | `cycles()` returns `[]` |
| FR-5 | `tests/unit/assurance/graph/test_topology_prompt.py` | the `char_limit` branch never taken |
| FR-6 | `tests/unit/assurance/graph/test_topology.py` | the consumer loop in `constraints_for` emptied |
| FR-7 | `tests/unit/assurance/graph/test_topology.py` | the batch-freshness condition forced false |
