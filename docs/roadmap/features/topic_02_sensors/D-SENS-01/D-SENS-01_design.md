# D-SENS-01 — Topology Graph

**Status**: ✅ Delivered — this document is a **record**, not a plan. · **Epic**: Topic 02 (Sensors) ·
**Legacy**: Step 7 · **Feature ID**: D-SENS-01

| | |
|---|---|
| Used by | selectors, staleness (`A-SENS-01`), the graph CLI, the tach sync journey; impact analysis; context-enriched prompts |
| Not owned | staleness — `stale_nodes` and the merkle-boundary comparison live in this class but belong to `A-SENS-01` |
| Record | created 2026-08-17 under `INT-US-08-MIG`; the capability shipped with **no design document and no feature directory**, only a four-line topic entry |

## What it does

An in-memory directed graph of a project's modules, built from the `context.yaml` files it declares
and — for directories that declare nothing — from analysing the source. `TopologyGraph` in
`assurance/graph/topology.py`, over a pluggable `TopologyEngineProtocol` (NetworkX in practice).

It answers three kinds of question:

- **structural** — what does this module depend on, who consumes it, what cycles exist;
- **contextual** — render this module's neighbourhood as a prompt block, within a character budget;
- **operational** — do the SLA claims of a module and its dependencies contradict each other.

It is a foundation, not a feature: impact analysis and context-enriched prompts sit on it.

## Architecture

| Surface | Site |
|---|---|
| Graph, queries, prompt rendering | `assurance/graph/topology.py` — `TopologyGraph`, `TopologyNode`, `TopologyContext` |
| Engine | `graph/topology/engine.py`, via `TopologyEngineProtocol` |
| Inference for undeclared directories | `workspace/context/inferrer.py` + `workspace/analyzers/factory.py`, via `_auto_infer_missing` |

## Functional Requirements

Written 2026-08-17 under `specweaver-dev` §3.2c, on contact from `INT-US-08-MIG`. The capability was
`✅` with **no requirements at all** — one of the four in this migration with no design document, so
invisible to `check_fr_sweep.py` (a design that does not exist has no uncited FR).

The FRs state **why the capability exists** — a prompt should carry the modules that bear on the one
being changed, and a change's blast radius should be knowable without reading the tree — not an
inventory of methods. Each is behind a killed mutant.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Declared topology becomes a graph | System | Reads every `context.yaml` beneath the project root | The modules a project documents, and the edges between them, exist as a queryable graph |
| FR-2 | Blast radius, not dependency list | Engine | Asks what a change to a module affects | The **reverse**-transitive set — who breaks — rather than what the module itself needs |
| FR-3 | Undeclared directories are inferred | System | Analyses a source directory carrying no `context.yaml` | A node is generated for it, so the graph covers the project rather than only its documented part |
| FR-4 | Circular dependencies are surfaced | System | Detects cycles | Chains are reported, so a cycle is a finding instead of a traversal that never settles |
| FR-5 | Prompt context is bounded | Engine | Renders a module's topology block under a character limit | Content is cut and marked `[truncated]`, so a large neighbourhood cannot crowd out the prompt it was meant to inform |
| FR-6 | A consumer's constraints reach the module | Engine | Aggregates the constraints that apply to a module | Constraints imposed by its consumers are included, not only the ones it declares itself |
| FR-7 | Contradictory SLAs are flagged | System | Compares a module's operational metadata against its dependencies' | A latency-critical module consuming a batch-freshness source is warned, rather than reading as consistent |

- **FR-1's mutant fails 50 test files across all three tiers** (the `context.yaml` walk replaced by an
  empty iterable) — the measure of "foundation".
- **FR-2's mutant**: `impact_of` traverses `forward=False`; `forward=True` returns the module's
  *dependencies* instead of its *consumers*. Both are plausible non-empty sets, and a wrong-way impact
  analysis reads as reassurance — worse than none. Five tests catch it.
- **One mutant, two claims**: the FR-2 mutant also kills `A-SENS-01` FR-3 (changes invalidate upward
  consumers), cited on the same test file. The two citations are not independent evidence — do not
  count this mutant twice.
- **Staleness is not declared here**: `A-SENS-01` (Incremental Semantics) owns the cache and is cited
  separately; claiming it here would double-count one behaviour.

## Non-Functional Requirements

None declared. No measured threshold exists — its performance envelope is whatever `rglob` plus the
engine costs — and an invented one would be a row nothing checks. Stated rather than left blank, per
§3.2c.
