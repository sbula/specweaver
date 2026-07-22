# Design: Agentic Interview Drafting (Grill-Style)

- **Feature ID**: D-INTL-07
- **Epic**: Topic 04 (Intelligence)
- **Status**: STUB — not yet run through the `specweaver-design` skill. **BLOCKED on `C-FLOW-11`.**
- **Origin**: Investigation of the grill-me skill family vs. US-2 (2026-07-22, Steve Bula + Claude):
  aihero.dev's `grilling → /to-spec` chain demonstrates that an **adaptive interview** (one question at a
  time, recommended answers, facts self-served from the repo, decision-tree walked branch by branch)
  followed by a **separate synthesis step** produces materially better specs than a fixed questionnaire.
- **DAL**: D (Internal Tooling)

## Problem Statement

`E-INTL-02`'s `Drafter` is a **fixed `SPEC_SECTIONS` questionnaire**: for each section, ask one canned
question, have the LLM write the section. This is the hardcoded-question-tree antipattern (same class
flagged on `D-INTL-04`): non-adaptive, cannot follow up, cannot resolve decision dependencies, asks the
user for facts the repo already contains, and its interview quality is frozen in Python instead of
improving with the model. The 2026-07-22 timeline decision (Option A): close `INT-US-02` on this engine
now — its gates are engine-agnostic — and replace the engine later under this capability. **Investment in
the old engine's interview quality is frozen as of that decision.**

## Goal

A grill-style **agentic drafting engine** for the draft step:

1. **Interview** — an agentic work unit (a `C-FLOW-11` work unit with a mounted interview rubric) conducts
   an adaptive grilling: one question at a time with a recommended answer, facts looked up in the
   workspace instead of asked, decisions resolved dependency-first, stop at shared understanding.
2. **Synthesis** — a separate `/to-spec`-style synthesis pass (no re-interviewing) renders the
   conversation into **SpecWeaver's spec contract** (the format S01–S12 validates; seams-first testing
   decisions; out-of-scope section).
3. **Same gates** — output flows through the exact `INT-US-02` chain (S-battery → semantic review →
   bounded loop). The engine changes; the assurance harness does not.
4. Interview + synthesis guidance are **rubric content** (`C-VAL-05`-class artifacts), not code — they
   version, override per-project, and improve without releases.

## Relationship & Dependencies
- **DEPENDS ON (hard):** `C-FLOW-11` — Graduated Autonomy work units are the execution substrate; building
  this without it would hand-roll another agent loop in the orchestration layer (explicitly rejected by the
  middle-way direction). **Do not design before `C-FLOW-11` is committed.**
- **Depends on (soft):** `C-VAL-05` — the rubric-artifact substrate the interview/synthesis content should
  ship as (versioned, DAL-gated, per-project overridable).
- **Supersession target:** `E-INTL-02` (fixed-questionnaire Drafter). Replace outright vs. keep as a
  deterministic/headless fallback mode — **decided on engineering merit at design intake**, not preordained.
- **MANDATORY DECOMMISSION DUTIES (if the design decides "replace")** — this story is NOT done until:
  1. The superseded code is **deleted** (`Drafter` questionnaire path, dead `SPEC_SECTIONS` machinery,
     anything no longer reachable) — no dead engines left in the tree.
  2. `E-INTL-02` is **removed from the living registry** — capability-matrix cell, topic_04 DAL-E entry,
     and every roadmap dep line — replaced by pointers to `D-INTL-07` (tombstone precedent: `C-EXEC-05`,
     "retired: absorbed into B-INTL-09"). The living docs MUST describe the current code, not history.
  3. `E-INTL-02`'s spec **text** is never edited — the finished document remains, unchanged, in
     `features/topic_04_intelligence/E-INTL-02/` + git history as the archival record of what was true.
  4. The supersession is narrated HERE (this doc's as-built notes): what was removed, what replaced it, why.
  (Registry removals touch ✅-marked lines → done deliberately via the guard hatch at this story's
  commit boundary, with HITL sign-off — that is the designed legitimate use of the hatch.)
- **Consumed by:** `INT-US-02-SF03` (the US-2 sub-story wiring this engine into `sw draft` /
  `new_feature`). The `INT-US-02` base contract's gates (validate→review chain, bounded loop, provider
  wiring, proof) are reused verbatim — they gate whatever engine produced the spec.
- **Sibling:** `D-INTL-04` (Design Questionnaire — greenfield bootstrap → `context.yaml`), already
  annotated grill-me-pattern; shares the interview-rhythm rubric approach but targets a different artifact.

## Candidate Approaches (not yet designed)
1. Work-unit role "drafter": interview rubric + synthesis rubric mounted; tools = read-only workspace
   access + user-question channel; output = spec file matching the contract — recommended shape.
2. Interview rhythm as harness-side turn protocol vs. fully rubric-driven — decide at intake.
3. Fallback question: keep `E-INTL-02` oneshot mode for non-agentic runtimes/headless, or replace fully —
   decide at intake with usage data.

## Non-Goals (proposed, pending design)
- Changing the spec contract or the S-battery (the gates are the fixed point).
- Greenfield bootstrap interviews (`D-INTL-04`'s scope).
- Building any interview loop outside a `C-FLOW-11` work unit.

## Next Step
After `C-FLOW-11` is committed: run `specweaver-design D-INTL-07` (jointly minted `INT-US-02-SF03` follows
as the integration contract).
