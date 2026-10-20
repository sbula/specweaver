# Design: A Task's Target Files Are Named for Python Only

- **Feature ID**: TECH-073
- **Epic**: Topic 07 (Technical Debt)
- **Status**: ABSORBED by `D-INTL-08` `[agreed 2026-10-20]` — its stem rule and its one
  derivation of a task's files are `D-INTL-08` FR-1 and FR-3
  ([design](../../topic_04_intelligence/D-INTL-08/D-INTL-08_design.md)); it closes with SF-01
- **Origin**: 2026-10-16, `E-SENS-03` design, grilling Q5 — the user asked for this ticket directly. A
  defect in delivered work (`D-EXEC-02` ✅, `C-EXEC-06` ✅), so it is not an edit to either.

## Problem Statement

A task's target files are named in three places, and each writes the Python convention into code:

| Where | What it names |
|---|---|
| `core/flow/handlers/generation.py:135-136`, `:439` | the files the generator writes: `src/<stem>.py`, `tests/test_<stem>.py` |
| `core/flow/engine/isolation.py:40-58` `derive_allowed_paths` | the worktree merge allow-list (`D-EXEC-02`), the same two paths |
| `E-SENS-03` (designed 2026-10-16) | the task's write grant, from that same allow-list `[agreed 2026-10-16]` |

The stem is `spec_path.stem.replace("_spec", "")` in both, while the topology selector uses
`.removesuffix("_spec")` (`core/flow/interfaces/cli.py:416-425`): a spec named `my_spec_tool_spec.md`
gets two different module names. A Java, Kotlin, TypeScript or Rust project gets `.py` targets unless
`[sandbox] session_allowed_paths` lists its files by hand.

## Candidate Approaches (not yet designed)

- One derivation of a task's target files, from the project's language (the polyglot runners already
  know it), used by generation, the merge allow-list and the write grant alike.
- The same stem rule everywhere, `removesuffix` or `replace` — a decision, since it renames modules.

## Non-Goals (proposed, pending design)

- What an agent may read (`B-FLOW-04` owes it). Which agent gets write tools (`C-FLOW-11`).

## Next Step

Run `specweaver-design TECH-073`. Sequencing: it can land before or after `E-SENS-03`; both read the
one allow-list.
