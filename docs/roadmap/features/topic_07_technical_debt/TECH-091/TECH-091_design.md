# Design: CLI Errors Print as Markup, and Commands Live Anywhere

- **Feature ID**: TECH-091
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 5 below.

## Problem Statement

55 error prints pass exception text as Rich markup, so an error containing `[/...]` crashes the
print; there is no rule for where a command lives.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **EP-11** — TTY check twice; HITL seam bypassed in review; error text printed as markup. Where:
  `cli/main.py:127` vs `_core.py:188`; 55 markup error prints.
- **Real defect 8** — 55 error prints use Rich markup on exception text; an error containing
  `[/...]` raises while the real error is shown. Where: CLI-wide.
- **EP-7** — No single rule for where a command lives. Where: `interfaces/cli/routers/`,
  `review/interfaces/cli.py:148`, `config` split over 4 files.
- **CW-13** — The "config" CLI edits workspace-owned project columns; its manifest names a path that
  does not exist. Where: `core/config/interfaces/cli.py:49-300`.
- **CW-23** — Scaffold templates split across two files; lazy imports with no cycle to break. Where:
  `scaffold.py:45-200`, `_templates.py`.

## Goal

One error printer; one rule for where a command lives.

## Open Decisions (for the grilling, not answered here)

- None found at minting. The grilling in `specweaver-design` asks again.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-091`. Write each fix's test
red
first.
