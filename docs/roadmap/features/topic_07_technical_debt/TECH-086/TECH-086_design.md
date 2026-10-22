# Design: Tool Roles and Scaffolding Are Copied per Area

- **Feature ID**: TECH-086
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `refactor`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 9 below.

## Problem Statement

Role access is spelled in about ten tables (a permission surface); tool scaffolding is copied per
area; the dispatcher is also the composition root and the grant policy.

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **SB-12** — The tool re-implements the atom's change path and parser lookup. Where:
  `code_structure/interfaces/tool.py:419,498` vs `core/atom.py:263,107`.
- **SB-13** — Tool scaffolding copied per area. Where: `_require_intent` ×5, `ToolResult` ×5, grant
  checks ×2, `ExecutorResult` ×2.
- **SB-14** — Role access control in up to three tables per area; facades uneven. Where:
  `base.py:74`, `ROLE_INTENTS` per tool, `dispatcher.py:179`.
- **X-12** — Role names spelled in about 10 tables; a permission surface. Where: `ROLE_INTENTS` ×6,
  role maps ×4.
- **SB-15** — The dispatcher is also the composition root and the grant policy. Where:
  `dispatcher.py:116-301`.
- **SB-19** — One concept, several names; "interface" means an ABC and a tool layer; protocol uses
  `action`, all others `intent`. Where: `PythonQARunner` vs `<Lang>Runner`; `interface.py` vs
  `interfaces/`.
- **SB-21** — Grants, boundary, doc access, manifests and git merge verdict in one file. Where:
  `security.py` (360 lines).
- **EP-8** — `interfaces/` means the user CLI in domains and the LLM tool layer in sandbox. Where:
  `sandbox/*/interfaces/` vs `*/interfaces/cli.py`; three manifest schemas.
- **FL-11** — Tool dispatcher and workspace boundary built three ways; generation borrows review's
  private builder. Where: `review.py:37`, `scenario.py:25`, `agentic_coder.py:44`.

## Goal

One role list, shared tool parts, and a dispatcher that only routes.

## Open Decisions (for the grilling, not answered here)

- None found at minting. The grilling in `specweaver-design` asks again.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-086`. Write each fix's test
red
first.
