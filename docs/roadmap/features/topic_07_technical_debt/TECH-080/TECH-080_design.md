# Design: Module Manifests Are Read Five Ways

- **Feature ID**: TECH-080
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 4 below.

## Problem Statement

The walk up to the nearest `context.yaml` and its parse exist at least five times, with different
start rules and two YAML libraries; `dal_resolver` crashes on a list-shaped file.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **CW-17** — Walk-up and parse of `context.yaml` at least five times; `dal_resolver` crashes on a
  list-shaped file; two YAML libraries. Where: `_context_walk.py`, `archetype_resolver.py:47,79`,
  `dal_resolver.py:51`, `directory_walk.py:20` + 3 runners.
- **SB-4** — "Nearest `context.yaml` forbids" three times in sandbox, with different start rules.
  Where: `java/runner.py:70`, `typescript/runner.py:318`, `python/forbids_checker.py:27`,
  `assurance/graph/topology.py:259`.
- **AG-19** — A full topology load and hash just to read a service name; three ways to build a
  topology. Where: `orchestrator.py:258`.
- **AG-15** — A different manifest schema; SpecWeaver's own topology loader skips these modules.
  Where: `graph/**/context.yaml`.

## Goal

One manifest reader with a typed model.

## Open Decisions (for the grilling, not answered here)

- None found at minting. The grilling in `specweaver-design` asks again.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-080`. Write each fix's test
red
first.
