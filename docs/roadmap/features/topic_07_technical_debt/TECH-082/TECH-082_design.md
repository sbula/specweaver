# Design: Domain Logic Lives in the Flow Engine

- **Feature ID**: TECH-082
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `refactor`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 9 below.

## Problem Statement

Language layouts, framework detection, contract rendering and whole LLM workflows (arbitration, lint
repair, drift) sit in `core/flow`, and the runner's parts reach into each other's privates.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **Fix first #10** — Language layouts, framework detection, contract rendering and whole LLM
  workflows sit in `core/flow` instead of `workflows/`, `sandbox/language` or
  `assurance/validation`. Where: `core/flow/engine/task_files.py`, `frameworks.py`,
  `handlers/contract_renderers.py`, `arbiter.py`, `lint_fix.py`, `drift.py`.
- **FL-3** — Language layouts, framework detection and contract rendering live in the engine. Where:
  `engine/task_files.py`, `engine/frameworks.py`, `handlers/contract_renderers.py` (533 lines),
  `agentic_coder.py:63`, `acceptance.py:28`.
- **FL-5** — Validation policy sits in flow handlers and is imported by validation's own CLI and the
  API. Where: `handlers/validation_hydrator.py`, `archetype_pipelines.py`, `qa_targets.py:50`.
- **WV-7** — Whole LLM workflows in flow handlers, with hand-written f-string prompts. Where:
  `handlers/arbiter.py`, `lint_fix.py:231`, `drift.py:146`, `contract_renderers.py`,
  `validation_hydrator.py`.
- **FL-17** — Oversized handlers mixing domain logic and orchestration. Where: `arbiter.py:300-461`,
  `validation.py:384-535`, `lint_fix.py:67-296`.
- **FL-16** — Runner split into free functions taking `runner: Any` and reading its privates; engine
  branches on specific handlers' output keys. Where: `step_execution.py:186-578`, `approval.py`,
  `session.py`, `hydration.py:83`.
- **FL-9** — "What a step is" in four tables plus literals; the dual pipeline is reached by a
  `params.mode` switch. Where: `models.py:106,391`, `registry.py:97`, `_llm.py:25`, roles hard-coded
  in 10 handlers.
- **FL-10** — `context.feedback` is an untyped grab-bag; two pop functions; the arbiter hard-codes
  YAML step names. Where: `gates.py:155`, `arbiter.py:236,425`, `generation.py:50`, `draft.py:29`.
- **FL-21** — Two modules titled "Context Assembler"; private modules used by five outside packages;
  dead `FILENAME_PREFIX`. Where: `mcp_assembler.py`, `context_assembler.py`, `base.py`, `_llm.py`,
  `_profiles.py`.

## Goal

The engine orchestrates; domain work lives in `workflows/`, `sandbox/language` and
`assurance/validation`.

## Open Decisions (for the grilling, not answered here)

- `T-ARCH`: the home of each moved workflow.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-082`. Write each fix's test
red
first.
