# Design: Topology Graph

- **Feature ID**: D-SENS-01
- **Epic**: Topic 02 (Sensors)
- **Status**: ✅ Delivered — this document is a **record**, not a plan.
- **Legacy**: Step 7
- **Created**: 2026-08-17 under `INT-US-08-MIG`. The capability shipped with **no design document and
  no feature directory at all**, so its four-line topic entry was the only record of it.

## What shipped

An in-memory directed graph of a project's modules, built from the `context.yaml` files it declares
and — for directories that declare nothing — from analysing the source. `TopologyGraph` in
`assurance/graph/topology.py`, over a pluggable `TopologyEngineProtocol` (NetworkX in practice).

It answers three kinds of question:

- **structural** — what does this module depend on, who consumes it, what cycles exist;
- **contextual** — render this module's neighbourhood as a prompt block, within a character budget;
- **operational** — do the SLA claims of a module and its dependencies contradict each other.

It is the substrate for impact analysis and for context-enriched prompts, which is why the topic
entry calls it a foundation rather than a feature.

## Functional Requirements

Written 2026-08-17 under `specweaver-dev` §3.2c, on contact from `INT-US-08-MIG`. This capability is
`✅` and declared **no requirements at all** — one of the four in this migration with no design
document, and therefore invisible to `check_fr_sweep.py` by construction: a design that does not
exist has no uncited FR.

Written from **why the capability exists** — a prompt should carry the modules that actually bear on
the one being changed, and a change's blast radius should be knowable without reading the tree — not
from an inventory of its methods. Each is behind a killed mutant; none was believed before that.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Declared topology becomes a graph | System | Reads every `context.yaml` beneath the project root | The modules a project documents, and the edges between them, exist as a queryable graph |
| FR-2 | Blast radius, not dependency list | Engine | Asks what a change to a module affects | The **reverse**-transitive set — who breaks — rather than what the module itself needs |
| FR-3 | Undeclared directories are inferred | System | Analyses a source directory carrying no `context.yaml` | A node is generated for it, so the graph covers the project rather than only its documented part |
| FR-4 | Circular dependencies are surfaced | System | Detects cycles | Chains are reported, so a cycle is a finding instead of a traversal that never settles |
| FR-5 | Prompt context is bounded | Engine | Renders a module's topology block under a character limit | Content is cut and marked `[truncated]`, so a large neighbourhood cannot crowd out the prompt it was meant to inform |
| FR-6 | A consumer's constraints reach the module | Engine | Aggregates the constraints that apply to a module | Constraints imposed by its consumers are included, not only the ones it declares itself |
| FR-7 | Contradictory SLAs are flagged | System | Compares a module's operational metadata against its dependencies' | A latency-critical module consuming a batch-freshness source is warned, rather than reading as consistent |

**FR-1's mutant fails 50 test files across all three tiers** — replacing the `context.yaml` walk with
an empty iterable. That number is the honest measure of "foundation": selectors, staleness, the graph
CLI and the tach sync journey all rest on it.

**FR-2's mutant is the sharp one.** `impact_of` traverses `forward=False`; flipping it to `forward=True`
returns the module's *dependencies* instead of its *consumers*. Both are non-empty sets of real module
names, both look plausible in a prompt, and the direction is the entire point of the query — an impact
analysis pointing the wrong way is worse than none, because it reads as reassurance. Five tests catch
it.

**That mutant is shared with `A-SENS-01` FR-3**, which claims changes recursively invalidate upward
consumers, and whose citation already sat on the same test file. One line, two claims at different
altitudes, so **one mutant kills both** — the two citations are not independent evidence and the test
file says so. Worth recording because a reader tallying killed mutants across the ledger would otherwise
count this one twice.

Not declared, deliberately: staleness. `stale_nodes` and the merkle-boundary comparison live in this
class but belong to `A-SENS-01` (Incremental Semantics), which owns the cache and is separately cited.
Claiming them here would double-count one behaviour across two capabilities.

## Non-Functional Requirements

None declared. The capability has no measured threshold in the repository — its performance envelope is
whatever `rglob` plus the engine costs — and inventing one now would add a row nothing checks. Stated
rather than left blank, per §3.2c.
