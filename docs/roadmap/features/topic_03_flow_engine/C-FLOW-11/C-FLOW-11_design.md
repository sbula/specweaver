# Design: Graduated Autonomy — DAL-Driven Execution-Mode Dial

- **Feature ID**: C-FLOW-11
- **Epic**: Topic 03 (Flow Orchestration)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Architecture-direction review (2026-07-21, Steve Bula + Claude): SpecWeaver fuses two products —
  an **assurance harness** (specs, gates, validation battery, DAL policy, zero-trust sandbox — the durable
  moat) and an **LLM orchestration engine** (one-shot handlers, prompt-slot assembly, hand-rolled reflection
  loops — commoditizing against the agentic-runtime/skills paradigm). Resolution: neither "all hardcoded" nor
  "all skills" — a **policy dial**. Rigidity becomes a graduated, DAL-driven run property.
- **DAL**: C (Enterprise Standard) — the dial is itself assurance policy.

## Problem Statement

Work execution is frozen at one point on the rigidity spectrum: every generation step is a **one-shot LLM
call** (`generation.py`: build prompt → single `generate()` → write file) and every fix loop is hand-rolled
(`lint_fix.py`, "inspired by Aider's max_reflections"). This under-delivers vs. an agent iterating with tools
in a sandbox, and over-delivers ceremony for small/low-risk projects. Meanwhile the zero-trust machinery
(C-EXEC-06 session isolation + authorized `strip_merge` + the gate battery) already guarantees results at the
boundary — **the gates make the middle free**, so the middle's rigidity should be a policy choice, not an
architectural constant.

## Goal

Make execution mode a **DAL-driven dial**, mirroring the approved AD-8 pattern from `INT-US-03 SF-03`
(DAL-driven isolation escalation — the same graduated-policy shape):

1. **Dual-mode work steps**: pipeline steps gain `mode: oneshot | agentic` (default `oneshot` — zero
   regression). `oneshot` = today's handlers, untouched. `agentic` = a **work unit**: a sandboxed agent with
   tools + mounted skills iterating inside a C-EXEC-06 session worktree until its inner loop converges,
   then gated/verified/authorized exactly like any step output.
2. **Mode policy at the composition root**: resolved from `SandboxSettings`/DAL (e.g. low-DAL → agentic
   with light gates; DAL-A/B → oneshot-deterministic or agentic with full battery + strict gates + HITL) —
   configurable, ADR-002-frozen onto the context.
3. **Bounded cost**: token/turn budgets per work unit (NFR — no unbounded agent loops).

## Relationship
- **Consumes**: `C-EXEC-06` (session isolation = the work-unit sandbox), `INT-US-03` (the implement loop is
  the pilot), DAL machinery (`DALLevel.rank`, `DALResolver`, AD-8 precedent).
- **Supersedes in agentic mode (without reopening the ✅ stories)**: the `D-VAL-01` lint-fix reflection loop
  (the agent fixes lint natively inside its work unit; the lint *gate* remains in both modes) and the
  one-shot internals of `D-INTL-01` (which becomes the dial's `oneshot` position, unchanged).
- **Context mounting**: work units read constitution/standards/rubrics as files and pull memory — the
  externalization contract is `C-INTL-06`.
- **Complements**: `C-VAL-05` (rubrics-as-content — softens validation *content* while this softens
  execution *mode*; together they are the "middle way").
- **Future**: role = tool allowlist + mounted skill set + DAL-scoped gates ("assurance-graded skill
  mounting") — likely its own follow-up capability once work units exist.

## Candidate Approaches (not yet designed)
1. New `work_unit` step action beside existing handlers (additive; handlers untouched) — recommended.
2. Agent runtime binding: own loop via Agent SDK vs. driving an external CLI headless vs. runtime-pluggable
   adapter (mirroring the LLM-adapter pattern one level up). **Open strategic decision.**
3. Pilot: `sw implement` generate→fix inner loop as ONE agentic work unit, gated by the existing
   run_tests/validate_code/strip_merge chain.

## Non-Goals (proposed, pending design)
- Removing/rewriting the one-shot handlers (they are the deterministic mode of the dial).
- Multi-agent orchestration (that's `B-INTL-06` territory).
- Softening any guarantee: sandbox, authorization, mechanical rules, gates stay hardcoded at every dial position.

## Next Step
Run `specweaver-design C-FLOW-11`. Decide the runtime-binding question (Candidate 2) at intake.
