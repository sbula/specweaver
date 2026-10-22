# Design: QA Runners Are Split, Copied, and Can Report a Skipped Tool as Clean

- **Feature ID**: TECH-087
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 14 below.

## Problem Statement

The runner contract and the runners live in two packages; Java and Kotlin are ~70% copies; dead
parsers are kept by a test; a complexity timeout or stub reads as clean; git commit and executor
choice are done several ways.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **SB-1** — The runner contract and factory live in `qa_runner`, the five runners in `language`;
  they import each other, held apart only by lazy imports. Where: `qa_runner/core/factory.py:49` ↔
  `language/core/*/runner.py`.
- **SB-3** — Three dead JUnit parsers kept alive only by a test. Where: `java/runner.py:49`,
  `kotlin/runner.py:141`, `rust/runner.py:43`.
- **Real defect 3** — Old JUnit parsers are called only by a test, which checks code no runner runs.
  Where: `java/runner.py:49`, `kotlin/runner.py:141`, `rust/runner.py:43`.
- **SB-5** — Java and Kotlin runners ~70% the same and drifting (Kotlin parses SARIF inline, returns
  raw compile errors). Where: `java/runner.py:95-422` vs `kotlin/runner.py:51-292`.
- **SB-6** — Byte-identical apart from names. Where: `java/stack_trace_filter.py`,
  `kotlin/stack_trace_filter.py`.
- **SB-8** — The Python runner hand-builds "tool did not run" results with a different marker; a
  complexity timeout and the TS complexity stub read as clean. Where: `python/runner.py:68,236,329`,
  `typescript/runner.py:152`.
- **SB-9** — Two identical SARIF walkers; tool-report parsers split between sandbox and the AST
  package. Where: `language/core/sarif.py:31` vs `workspace/ast/parsers/_sarif_complexity.py:35`.
- **AG-12** — QA tool-report parsers in the tree-sitter package; the clippy one has no caller.
  Where: `workspace/ast/parsers/{java,kotlin,rust,typescript}/parsers.py`.
- **SB-22** — Single-user modules in the wrong folder. Where: `language/core/evaluator.py`,
  `maven_output.py`, `rule_atom.py`.
- **SB-24** — Signs of cloning: "Jest timed out", odd `getattr(__builtins__, ...)`. Where:
  `typescript/runner.py:175,380`.
- **Real defect 7** — A TypeScript architecture timeout reports "Jest timed out". Where:
  `typescript/runner.py:380`.
- **SB-23** — MCP uses raw `Popen` (unrecorded exception); container vs host depends on whether a
  caller injected an executor. Where: `mcp/core/executor.py:16`; `or SubprocessExecutor(cwd)` in 9
  places.
- **SB-11** — "Stage all, commit" three times; "nothing to commit" means three things; one ignores
  `add` failures. Where: `git/core/atom.py:112`, `git/interfaces/tool.py:151`,
  `worktree_ops.py:105`.
- **X-13** — Git called through raw subprocess outside the governed git executor. Where:
  `standards/discovery.py:31,80`, `cli_drift.py:8,160`.

## Goal

Runners beside their factory, one JVM base, one executor, and a tool that did not run never reads as
clean.

## Open Decisions (for the grilling, not answered here)

- None found at minting. The grilling in `specweaver-design` asks again.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-087`. Write each fix's test
red
first.
