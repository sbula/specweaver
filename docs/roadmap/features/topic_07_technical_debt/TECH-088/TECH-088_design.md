# Design: Two Graph Engines in Two Homes

- **Feature ID**: TECH-088
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `refactor`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 7 below.

## Problem Statement

Two graph engines with different depth caps; the graph that review, drafting and planning use lives
under `assurance`, while `graph/` holds a knowledge graph nothing reads; lineage is spread over
three packages.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **AG-1** — Two graph engines (hand-written Tarjan and networkx), each with its own depth cap; the
  protocol does not match its implementation. Where: `graph/topology/engine.py:24`,
  `graph/core/engine/core.py:14`, `assurance/graph/topology.py:26`.
- **AG-2** — The graph used by review, drafting and planning sits under `assurance`; `graph/` holds
  a write-only knowledge graph. Where: `assurance/graph/topology.py:119` vs
  `graph/core/builder/orchestrator.py:205`.
- **AG-14** — Lineage spread over three packages; `repository.py` holds the protocol,
  `lineage_repository.py` the repository. Where: `graph/lineage/repository.py`,
  `store/lineage_repository.py`, `scanner.py`, `commons/lineage.py`.
- **AG-17** — One word, unrelated meanings; an `Any` slot probed with `hasattr`. Where:
  `run_context.py:120` (`topology: Any`), two `changes.py`, two `detect_language`.
- **AG-18** — Prompt rendering in the assurance graph; LLM and workflows import it. Where:
  `assurance/graph/selectors.py`, `topology.py:83`.
- **AG-13** — Retrieval chunker in the analyzers package, no product caller. Where:
  `workspace/analyzers/chunking.py`.
- **CW-22** — A retrieval chunker with no product caller, in the tree-sitter adapter package. Where:
  `workspace/analyzers/chunking.py` (528 lines).

## Goal

One graph domain with one engine.

## Open Decisions (for the grilling, not answered here)

- `T-SCOPE`: the future of the write-only knowledge graph, and of the unused retrieval chunker (move, park or drop).

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-088`. Write each fix's test
red
first.
