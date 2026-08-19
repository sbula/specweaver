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
> **Integration is implicit in the (sub)story. There is no integration story.** `ADR-005` retires
> the `INT-US` family outright — `INT-US-NN`, `INT-US-NN-SFxx` and `-MIG` alike. Never mint one,
> never reference one, not as a dependency and not as a tombstone.
>
> **A test that cannot go RED proves nothing, and RED is only available before the code exists.**
> A test written after the code is green on its first run: it asserts the present state instead of
> a contract the code must satisfy. So the test comes first, and it gets the chance to fail.
>
> **A (sub)story owns every test it needs, including the ones that span features.** If one feature
> alone cannot prove it, the spanning test is still part of this (sub)story. It is not deferred, and
> it is not handed to a separate entry.
>
> **When a related (sub)story is unbuilt, write the test now anyway** and commit it as
> `pytest.mark.xfail(strict=True)` naming the blocker. It fails today for the right reason.
> `strict=True` makes an unexpected pass a failure, so the suite says so out loud the moment the
> last related (sub)story lands. `check_xfail_blockers.py` fails any such marker whose named
> blocker has become `✅`, so it cannot rot into a permanent exemption.
>
> **The (sub)story is finished when those tests are green** — not when its own feature compiles.
>
> **What integration actually is.** A feature's (N)FRs are not all local. Any FR whose satisfaction
> needs something from outside — a call into another module, data handed across a boundary, a format
> or schema both sides must agree on, an ordering, a shared file — is a **seam FR**: a hidden
> contract with another feature. Those, and only those, are what a spanning test proves. Name them
> as seams when you write the FR table, because a seam FR proven by a unit test with the other side
> mocked proves the mock, not the contract. `TECH-041` is one instance: `C-VAL-03` is `✅` and its
> DAL override is proven link by link, never as a chain.
>
> **A missing spanning test under an already-finished (sub)story is a defect in delivered work**, so
> it becomes a `TECH` ticket that owns the test and writes it red first. That is the rule for every
> other defect in closed code. Integration used to be the one carve-out, and the carve-out is what
> grew a second registry: measured 2026-08-19, 31 of 36 open contract rows were tracking work that
> another ticket already owned.

> [!CAUTION]
> **Before Phase 3 can bind requirements to surfaces, the (sub)story must list its paths.**
> `ADR-005`: every (sub)story holds a **path list** — every path a user walks through it, one row
> each, with the span that decides who proves it. The list lives in the (sub)story, not in a separate
> entry. Starting a design inside a (sub)story is what creates it.
>
> If the list is absent, **stop and create it** (`specweaver-feature` Phase 0b) before continuing. A
> design that binds FRs to surfaces without one has nowhere to record the requirements that cross a
> feature boundary, and they end up restated on this capability.
>
> A path this one feature can walk alone is this feature's own FR. A path that crosses features is a
> seam FR, and its test is written red first — `xfail(strict=True)` naming the blocker while a
> related (sub)story is unbuilt.

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
