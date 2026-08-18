---
name: specweaver-design
description: "Feature design skill. Intake → Research → Feature Detail → Decompose → Document →
Consistency Check. Produces a self-contained Design Document with Progress Tracker. Use when the
user asks to design a feature, create a design document, or analyze requirements for a feature."
---

# Design Skill

```
Trigger: "design <feature_id>", "create design for <feature_id>",
         "design document for <feature_id>", "analyze requirements for <feature_id>"
```

Output: `docs/roadmap/features/[Topic]/[ID]/[ID]_design.md`

> [!CAUTION]
> **MANDATORY SEQUENCING — DO NOT SKIP OR REORDER PHASES.**
>
> This skill has 6 phases that MUST be executed in strict order.
> Every phase MUST be completed before moving to the next one.
>
> **Before starting each phase:**
> 1. Read the phase file from the `references/` directory listed below.
> 2. Complete every step in that phase before moving on.
> 3. Never skip a phase, even if the feature seems simple.
>
> **Phases 1, 3, and 6 have HITL gates** — you MUST stop and wait for the user.
> Phase 1 gate fires only if the feature description is ambiguous.
> Phase 3 gates fire on gaps, API conflicts, or architectural switches.
> Phase 6 gate fires always — the design MUST be approved before planning begins.

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Execute all research and analysis autonomously.
> STOP only at the defined HITL gates. Never add extra stops.

> [!CAUTION]
> **The integration and e2e proof belongs to the capability, never to an `INT-US` story.**
> A test that cannot go RED proves nothing, and RED is only available while the feature is
> unimplemented. Collecting the seam into an integration story that runs *after* the capability
> ships means its first run is green against code that already exists — it asserts the present,
> not the contract.
>
> **Every capability not yet `✅` is responsible for its own integration and e2e testing.** No
> exceptions, nothing deferred to a later story: it declares its seam FRs and proves them at
> integration/e2e tier inside its own TDD cycle, red before the code they judge. This has not
> been the practice historically — the delivered corpus carries the debt — so it binds the work
> in front of you, not a backfill programme.
>
> It follows that you **never mint or reference an `INT-US-NN` / `INT-US-NN-SFxx` for work that is
> not built yet** — not as a dependency, not as a retirement tombstone. There is nothing left for
> such a story to own.
>
> An `INT-US` entry is legitimate in exactly one place: a (sub)story that **already holds a
> finished feature**, where `finished-stories-immutable` bars the closed capability from taking
> the FR and the proof has nowhere else to live.
>
> **What integration actually is.** A feature's (N)FRs are not all local. Any FR whose
> satisfaction needs something from outside — a call into another module, data handed across a
> boundary, a format or schema both sides must agree on, an ordering, a shared file — is a
> **seam FR**: a hidden contract with another feature. Those, and only those, are what an
> integration test proves. Name them as seams when you write the FR table, because a seam FR
> proven by a unit test with the other side mocked proves the mock, not the contract. `TECH-041`
> is one instance: `C-VAL-03` is `✅` and its DAL override is proven link by link, never as a
> chain.
>
> **There, an OPEN `INT-US` is load-bearing — never delete it.** It is the only record that a
> feature which is already implemented has not been integration-tested. Removing it does not
> retire the debt; it hides it, and the story then reads as proven. An `INT-US` line closes by
> the integration being written and passing. It never closes by being tidied away.

> [!CAUTION]
> **Before Phase 3 can bind requirements to surfaces, the (sub)story contract must exist.**
> `ADR-004`: every (sub)story holds a contract — its `INT-US` entry — carrying the path inventory
> and the cross-feature (N)FRs. Starting a design inside a (sub)story is what creates it.
>
> If the contract is absent, **stop and create it** (`specweaver-feature` Phase 0b) before
> continuing. A design that binds FRs to surfaces without one has nowhere to put the requirements
> that cross a feature boundary, and they end up restated on this capability — which is the defect
> `ADR-003` measured and `ADR-004` re-scoped.
>
> Only the paths that cross a feature boundary go there. A path this one feature can walk alone is
> this feature's own FR.

> [!IMPORTANT]
> **When you stop at a HITL gate, the decision is now invisible to everyone but this conversation.**
> Phase 6's gate always fires; Phases 1 and 3 fire on ambiguity. Before you stop, record in
> `.tmp/HANDOVER.md`: which gate, what question is open, and the document that must be read before
> answering it. One line each.
>
> This is what a handover is for and what `git log` cannot give you. `E-VAL-03` sat at its Phase 1 gate
> across sessions and was only picked up correctly because the handover named the analysis document and
> said *do not restart the research* — without that line the next session re-derives it.

## MCP Tool Guidance

When available, prefer these MCP tools over grep/file-reading for code discovery:

| Tool | When to use | Instead of |
|------|------------|------------|
| `codebase-memory` → `search_graph` | Find functions, classes, routes by name | `grep` across source files |
| `codebase-memory` → `trace_path` | Trace call chains and dependencies | Reading files one-by-one |
| `codebase-memory` → `get_architecture` | Understand module structure | Reading every context.yaml |
| `context7` → `resolve-library-id` + `get-library-docs` | Get correct API syntax for libraries (Pydantic, SQLAlchemy, Typer, etc.) | Guessing from training data |

> If these tools are unavailable (e.g., MCP not configured), fall back to grep/file-reading normally.

## Phases


| Phase | File | Description | HITL Gate? |
|-------|------|-------------|------------|
| **1** | `.agents/skills/specweaver-design/references/phase-1-intake.md` | Read feature entry + clarify scope | ⚠️ If unclear |
| **2** | `.agents/skills/specweaver-design/references/phase-2-research.md` | Parallel: codebase + internet research + ROI | No |
| **3** | `.agents/skills/specweaver-design/references/phase-3-detail.md` | FR/NFR ⇄ surface fixpoint, bindings, API validation, arch alignment | ⚠️ On gap, missing surface, or arch switch |
| **4** | `.agents/skills/specweaver-design/references/phase-4-decompose.md` | Sub-feature breakdown + dependency graph | No |
| **5** | `.agents/skills/specweaver-design/references/phase-5-document.md` | Write design.md | No |
| **6** | `.agents/skills/specweaver-design/references/phase-6-consistency.md` | Final checks + Red/Blue + HITL approval | ⚠️ Always |

Execute each phase by reading its file and following the instructions exactly.
