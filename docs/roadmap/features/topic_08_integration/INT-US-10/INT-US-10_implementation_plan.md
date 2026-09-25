# INT-US-10 — Migration Plan

**Migration entry**: `INT-US-10-MIG` · **FRs owned**: FR-1 · Contract:
[INT-US-10_design.md](INT-US-10_design.md) · Authority: `ADR-004`; method in
[`TECH-060`](../../topic_07_technical_debt/TECH-060/TECH-060_design.md)

## Goal

Prove FR-1: real extraction feeds the real graph. P-1 belongs to `B-SENS-02`; P-3/P-4 generate no FR
yet.

## Commit boundaries

| CB | Owns | Delivers | State |
|---|---|---|---|
| CB-1 | FR-1 | `tests/integration/graph/test_real_extraction_to_graph.py` — real adapter → real mapper → real SQLite, nothing mocked | done |
| CB-2 | P-1 | `B-SENS-02`'s five FRs cited and mutant-verified, under `specweaver-dev` §3.2c | done (see contract §Migration disposition) |

CB-2 is the shared half: five other base contracts list `B-SENS-02` as their only closed capability,
and the work happens here once — why `TECH-060` orders the batch by capability cluster, not story
number.

## Tests

| FR | Proof | Tier |
|---|---|---|
| FR-1 | `test_real_extraction_to_graph.py` — shape agreement, real persistence, dedup across the real composition, and the polyglot case xfailed against `TECH-061` | integration |

Four tests: three pass; the fourth is `xfail(strict=True)` against **`TECH-061`**, minted from it.

`B-SENS-02` FR-2's dedup was probed: dropping `semantic_hash TEXT UNIQUE` killed 18 tests, so CB-2 is
citation work, not new tests.

## As built

**Found — `TECH-061`: the graph is Python-only.** `collect_files` filters `.py` and nothing else
(`orchestrator.py:85-97`), while `D-SENS-03` ships five other extractors and both the adapter and the
mapper are language-agnostic. A real Java file whose symbols the extractor reports persists **zero**
nodes — not even the FILE node, since collection drops it before the mapper. Per `ADR-004` clause 6
that is a new ticket, not an edit to `B-SENS-02`; `INT-US-10` stays open until it lands.

Gate rules this work had to meet:

- **`check_xfail_blockers.py` reads TECH blockers.** It resolved only capability ids against the
  matrix; widened to read ticket status from the TECH ledger, since `ADR-004` clause 6 makes a ticket
  blocker the normal case.
- **R8: no `pytest.skip` on grammar availability.** `tree-sitter-java` is a hard dependency in
  `pyproject.toml`; skipping on it turns a defect into a green run. Hence NFR-1: "no skip on a
  repo-controlled dependency" (replaced "honest skips").
- **R6 and TC003**: a test class must name its function under test; no annotation-only import.
