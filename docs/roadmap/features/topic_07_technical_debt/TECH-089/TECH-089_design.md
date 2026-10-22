# Design: Parser Helpers Are Copied Outside the Parser Layer

- **Feature ID**: TECH-089
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 4 below.

## Problem Statement

Standards analyzers and the Python parser keep private copies of the shared tree helpers; one copy
still has a doc-comment bug the parsers fixed.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **AG-9** — Standards re-implement parser helpers, including a doc-comment bug the parsers already
  fixed. Where: `standards/languages/python/analyzer.py:15`, `javascript/analyzer.py:35-83`.
- **AG-10** — Python keeps private copies of the shared tree helpers. Where:
  `parsers/python/_references.py:32` vs `_ref_tools.py:17`.
- **AG-11** — Python imports extracted three ways. Where: `python/codestructure.py:176`,
  `python/_references.py:286`, standards Python analyzer.
- **AG-21** — Parallel JVM helpers remain. Where: `java`/`kotlin` `_references.py` beyond `_jvm.py`.

## Goal

One helper set in the parser layer, used everywhere.

## Open Decisions (for the grilling, not answered here)

- None found at minting. The grilling in `specweaver-design` asks again.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-089`. Write each fix's test
red
first.
