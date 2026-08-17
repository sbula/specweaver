# Implementation Plan: INT-US-10 — Migration

- **Feature ID**: INT-US-10
- **Contract**: [INT-US-10_design.md](INT-US-10_design.md)
- **Migration entry**: `INT-US-10-MIG`
- **Authority**: `ADR-004`; method in [`TECH-060`](../../topic_07_technical_debt/TECH-060/TECH-060_design.md)

**FRs owned: FR-1.** One cross-feature requirement, because the inventory's other runnable row (P-1)
belongs to `B-SENS-02` and its deferred rows (P-3, P-4) generate none yet.

## Commit boundaries

| CB | Owns | Delivers | State |
|---|---|---|---|
| CB-1 | FR-1 | `tests/integration/graph/test_real_extraction_to_graph.py` — real adapter → real mapper → real SQLite, nothing mocked | done |
| CB-2 | P-1 | `B-SENS-02`'s five FRs cited and mutant-verified, under `specweaver-dev` §3.2c | open |

CB-2 is the shared half. Five other base contracts list `B-SENS-02` as their only closed capability,
and this is where that work happens once — the reason `TECH-060` orders the batch by capability
cluster rather than by story number.

## What CB-1 proved, and what it found

Four tests. Three pass; the fourth is `xfail(strict=True)` against **`TECH-061`**, minted from it.

**The composition was never driven.** Each part had proof and the seam had none:
`test_graph_adapter.py` covers the adapter with a real parser, `test_builder_integration.py` covers
the builder with `fake_java_parser`, and `test_orchestrator.py:149` names `build_target` then
`MagicMock`s the repository, topology and engine to assert `persist_semantic_digraph` was *called*.
Three green suites, no proof the shapes meet.

**`TECH-061`: the graph is Python-only.** `collect_files` filters `.py` and nothing else
(`orchestrator.py:85-97`) while `D-SENS-03` ships five other extractors and both the adapter and the
mapper are language-agnostic. A real Java file whose symbols the extractor *does* report persists
**zero** nodes — not even the FILE node, because collection drops it before the mapper is reached.
Per `ADR-004` clause 6 that is a new ticket, not an edit to `B-SENS-02`, and `INT-US-10` stays open
until it lands.

## Three gates corrected the work as it was written

Worth recording, because each was a rule already in force that this commit would otherwise have
broken:

- **`check_xfail_blockers.py` did not understand TECH blockers.** It resolved only capability ids
  against the matrix, so the first real marker it had to judge — blocked on a *ticket*, which
  `ADR-004` clause 6 makes the normal case — was unjudgeable. Widened to read ticket status from the
  TECH ledger. The gate was two commits old and its first live use exposed the gap.
- **R8 rejected a `pytest.skip` on grammar availability.** `tree-sitter-java` is a hard dependency in
  `pyproject.toml`, so the grammar is repo-controlled and skipping on it converts a defect into a
  green run. The branch was dead anyway: the extractor reports the class and the run still persists
  nothing. NFR-1 in the contract was rewritten from "honest skips" to "no skip on a repo-controlled
  dependency".
- **R6 and TC003** caught a test class naming no function under test, and an annotation-only import.

## Verification

| FR | Proof | Tier |
|---|---|---|
| FR-1 | `test_real_extraction_to_graph.py` — shape agreement, real persistence, dedup across the real composition, and the polyglot case xfailed against `TECH-061` | integration |

`B-SENS-02` FR-2's dedup was probed rather than assumed: dropping `semantic_hash TEXT UNIQUE` killed
18 tests, so the constraint is genuinely protected and CB-2 is citation work, not new tests.
