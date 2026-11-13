# Implementation Plan: Postgres pgvector Sidecar [SF-01: No fixed traversal depth]
- **Feature ID**: A-SENS-02
- **Sub-Feature**: SF-01 — No fixed traversal depth
- **Design Document**: docs/roadmap/features/topic_02_sensors/A-SENS-02/A-SENS-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/A-SENS-02/A-SENS-02_sf01_implementation_plan.md
- **Status**: APPROVED

## Scope

`MAX_NEIGHBOURHOOD_DEPTH` is deleted. Both in-memory engines take `depth: int | None`, and `None`
reaches everything `[agreed 2026-11-11]` (Q23 A). FRs: FR-1, FR-2, FR-3, FR-4. All four claim
behaviour of `graph` alone, so every proof is **unit** tier. No seam: nothing outside `graph` calls
either method today (`extract_subgraph` has no production caller; `neighbors_within` is called only
by the three selectors in `graph/topology/selectors.py`).

**FR-3 also builds the supersede marker** `[agreed 2026-11-13]` (Decision 1 A). A closed story's FR
row stays as written; a later design marks it superseded, with the user's approval tag, and the FR
gates count it as superseded instead of uncited. This is FR gate tooling under `scripts/`; its
tests are unit tier (`tests/unit/scripts/`).

**Output for SF-06:** the traversal cases as plain data in `tests/traversal_cases.py`, so the DB
traversal (FR-23) runs the same cases and compares node sets and depths.

## Research Notes

- **The engines.**
  - `InMemoryGraphEngine.extract_subgraph(self, start_hash: str, depth: int) -> nx.DiGraph`
    (`graph/core/engine/core.py:81`): `max_depth = min(depth, MAX_NEIGHBOURHOOD_DEPTH)` (:89), then
    `nx.ego_graph(..., radius=max_depth, undirected=True)`. Raises `NodeNotFoundError` for a missing
    hash and `ValueError` for a non-string hash.
  - `TopologyEngine.neighbors_within(self, module: str, depth: int = 1) -> set[str]`
    (`graph/topology/engine.py:93`): `depth < 1` → empty set; a missing module → empty set;
    `radius = min(depth, MAX_NEIGHBOURHOOD_DEPTH)` (:100); the start is removed from the result.
- **Signatures that change with them:** `GraphEngineProtocol.extract_subgraph`
  (`graph/core/engine/protocol.py:27`), `TopologyEngineProtocol.neighbors_within`
  (`graph/topology/topology.py:40`), `TopologyGraph.neighbors_within` (`topology.py:419`).
- **networkx, measured 2026-11-13 (3.14 venv):** `ego_graph(radius=None)` has no cutoff; a
  10,000-node chain, undirected, takes 0.065 s. `radius=-1` and `radius=0` both give the start alone.
- **Tests that assert the cap today, and must change:**
  - `tests/unit/graph/test_one_depth_limit.py` (TECH-088 FR-9) — deleted (FR-3).
  - `tests/unit/graph/topology/test_topology_engine.py:132` (`test_rt27_max_depth_enforced`).
  - `tests/unit/graph/topology/test_topology_engine_answers.py:88` (`test_a_deep_request_is_cut_at_the_limit`).
  - `tests/unit/graph/core/engine/test_graph_engine_core.py:49` (`test_extract_subgraph_max_depth`).
  - `tests/unit/graph/topology/test_topology_engine_answers.py:80` (`test_no_depth_is_no_neighbourhood`,
    parametrized `[0, -1]`): `-1` now raises `ValueError` (Q4); `0` keeps the empty set.
- **The protocol guard:** `tests/unit/graph/topology/test_engine_protocol.py` compares names, kinds
  and DEFAULTS of engine and protocol, so `= None` must land in both at once (T2).
- **Selectors (FR-4):** `DirectNeighborSelector` depth 1 (:73), `NHopConstraintSelector` its own
  depth, default 2, clamped to ≥ 1 (:98), `ImpactWeightedSelector` depth 2 (:136). All already pass
  a depth. Covered by `tests/unit/graph/topology/test_selectors.py` (D-VAL-04 FR-4).
- **Mutant anchors this SF breaks** (`stale_mutants.py` runs at `cb`):
  - `TECH-088_mutants.json` FR-9: `limit-plus-one` (engine.py), `own-limit` (core.py) — the
    requirement goes away.
  - `TECH-088_mutants.json` `protocol-renames-depth` (topology.py, the protocol line).
  - `TECH-004_mutants.json` `engine-drifts-from-protocol` (core.py, the `extract_subgraph` line).
- **Gates that see TECH-088 FR-9:** `fr_sweep` (doc gate) ratchets the count of uncited FRs. Deleting
  FR-9's only test leaves it uncited unless the TECH-088 FR table changes too.
- **The FR gates, read 2026-11-13.**
  - `check_fr_sweep.py` counts uncited FRs of DELIVERED stories only (`_DELIVERED` on
    `master_story_roadmap.md`), with `census()` → `uncited(story)`. `TECH-088` is delivered, so
    deleting FR-9's only test raises the count by 1 and the ratchet blocks the commit.
  - `check_fr_coverage.py <ID>` is the per-story closure gate; `print_ledger` prints one line per FR
    (`NO TEST` for an uncited one). Run on `TECH-088`, it would fail after the deletion.
  - Both read declared FRs with `declared_frs_from_text` and citations with `cited_frs_in_tests`.
  - No supersede mechanism exists today. The only "retired" mechanism is the mutant corpus
    tombstone (`_corpus.py --retire FR-n --reason`), which `stale_mutants.py` skips.
- **Docs that state the cap:** `src/specweaver/graph/CLAUDE.md:22`,
  `docs/dev_guides/knowledge_graph_querying.md:31,82`, `B-SENS-02_design.md:208` (RT-27, history).

## The supersede marker (FR-3, Decision 1 A)

**Grammar.** Inside one FR row of the superseding design:
`` supersedes `<STORY>` FR-<n> with FR-<m> `` plus an `` `[agreed <YYYY-MM-DD>]` `` in the same row.
`FR-<m>` is an FR of the superseding design. The A-SENS-02 FR-3 row gains "with FR-1".

**One parser, two gates.** `check_fr_coverage.py` gets `supersede_markers(features_root)` →
`{(story, fr): Marker(by_story, by_fr, agreed, row_ok)}` over every design. The sweep imports it, as
it imports `declared_frs_from_text` today.

**Order of checks, per marker** (each failure exits 1 and names the marker):
1. the row has an `[agreed <date>]` tag — else "supersede marker without the user's approval tag";
2. `<STORY>` has a design and declares `FR-<n>` — else "supersedes an FR that does not exist";
3. `<STORY>` is not the superseding story — a design cannot supersede itself;
4. `FR-<m>` is declared by the superseding design and cited by a test (`cited_frs_in_tests`) — else
   "the superseding FR has no test".

5. no other marker supersedes the same `<STORY> FR-<n>` — else "superseded twice".

Only a marker that passes all five discharges `<STORY> FR-<n>`. The tag is text: the gate proves a
tag is present, not who wrote it, like every other `[agreed]` tag in the repo.

**What the reports show.** The superseded FR stays visible:
- `check_fr_coverage.py TECH-088`: `FR-9  plan  superseded by A-SENS-02 FR-1 [agreed 2026-11-13]`,
  and it does not count as `NO TEST`.
- `check_fr_sweep.py`: not counted as uncited; the pass line adds "N superseded", and `--list` prints
  each as `TECH-088 FR-9 superseded by A-SENS-02 FR-1`.
- A superseded FR that is still cited by a test is not an error (the old test may stay).

## Decisions (Phase 4, the user, 2026-11-13)

- **Q1 A** — fan-out shape: see "Traversal cases" below `[agreed 2026-11-13]`.
- **Q2 → Decision 1 A** — the supersede marker above; `TECH-088` keeps its FR-9 row `[agreed 2026-11-13]`.
- **Q3** — depth is optional: `depth: int | None = None` in both engines, both protocols and
  `TopologyGraph`; `None` is unbounded (the time limit applies where it exists). The selectors keep
  the depths they pass today `[agreed 2026-11-13]`.
- **Q4 A** — both engines refuse a depth that is not `int` or `None`, and refuse `bool`, with a
  `TypeError` naming the value; a negative depth raises `ValueError` naming the value; 0 keeps
  today's answer (module graph: empty set; code graph: the start alone) `[agreed 2026-11-13]`.
- **Q5 A** — `tests/traversal_cases.py`, plain data `[agreed 2026-11-13]`.
- **Q6 A** — no time limit in memory is an accepted risk **until SF-06**: SF-06's shared BFS loop
  gives both in-memory engines the time limit; SF-06 owns the fix and its test (design FR-29).
  The note lives in A-SENS-02's design only; `B-SENS-02` stays as written `[agreed 2026-11-13]`.
- **Q7** — docs: `graph/CLAUDE.md:22`, `knowledge_graph_querying.md:31,82`; no edit to `TECH-088`
  or `B-SENS-02` (both closed) `[agreed 2026-11-13]`.
- **Q8** — re-anchor `protocol-renames-depth` and `engine-drifts-from-protocol`, each still
  killed; new `A-SENS-02_mutants.json` `[agreed 2026-11-13]`.
- **Q9 A** — the marker names the superseding FR: `with FR-1` `[agreed 2026-11-13]`.

## Commit boundary

One boundary; it closes SF-01, so it stops for the user before the commit.

| Task | What | Files |
|---|---|---|
| T0 | Red, then green: the supersede marker — gate tests first (no tag, missing FR, self-supersede, uncited superseding FR, a valid marker shown as "superseded by …" in both reports); then the parser and both gates | `scripts/check_fr_coverage.py`, `scripts/check_fr_sweep.py`, `tests/unit/scripts/test_check_fr_coverage.py`, `tests/unit/scripts/test_check_fr_sweep.py`, the A-SENS-02 FR-3 row |
| T1 | Red: the shared cases and the no-cap tests for both engines | `tests/traversal_cases.py` (new), `tests/unit/graph/test_no_fixed_depth.py` (new) |
| T2 | Green: delete the constant; `depth: int \| None = None` and the Q4 checks in both engines, both protocols and `TopologyGraph` | `core.py`, `engine.py`, `protocol.py`, `topology.py`, `models.py` |
| T3 | FR-3: delete `test_one_depth_limit.py`; the three cap tests assert no cap; `-1` raises `ValueError`; retire the FR-9 campaign (`--reason "superseded by A-SENS-02 FR-1"`) | the five test files above, `TECH-088_mutants.json` |
| T4 | FR-4: selectors on a chain of 10 keep depth 1 and 2 answers | `tests/unit/graph/topology/test_selectors.py` |
| T5 | Mutants and docs | `A-SENS-02_mutants.json` (new), the two corpora above, the docs above |

**Red, and why (T0):** before the parser exists, a design with a marker and no tag passes both gates;
the test must show it fail. After T3 deletes FR-9's test, the sweep must stay at its baseline only
because the marker is valid: removing the tag must turn it red.

**Traversal cases (FR-2), Q1 A `[agreed 2026-11-13]`:** the fan-out case is levels of 1,000 nodes;
node *i* on one level links to nodes *i* and *(i+1) mod 1,000* on the next. Each node is reached
once, at its shortest depth.

**Red, and why (T1):** with the cap in place, a 10,000-node chain gives 5 nodes, not 10,000, in both
engines. The Q4 cases are red too: today `"3"` fails deep in networkx, `True` counts as 1, and `-1`
returns an answer instead of `ValueError`. That is the failure the tests must show before T2.

**Mutants (T5), each must be killed:**
- `radius = depth` → `radius = None if depth is None else min(depth, 100)`: a hidden cap at 100 (the
  10,000 chain kills it).
- `None` reaching everything → `None` treated as 1.
- the `bool` refusal removed → `depth=True` is accepted (Q4);
- the negative check removed → `depth=-1` returns an answer (Q4);
- the default `None` → `1` → a call with no depth stops at 1 (Q3).
- `ImpactWeightedSelector` depth 2 → 1 (FR-4).
- supersede: the tag check removed → the no-tag test fails;
- supersede: the citing-test check removed → the uncited-superseding-FR test fails;
- supersede: a superseded FR counted as uncited again → the sweep test fails.
- the visited set dropped is not a mutant here: networkx owns it; the cycle cases still run.
