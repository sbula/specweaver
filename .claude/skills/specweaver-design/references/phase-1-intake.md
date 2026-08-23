---
description: "Phase 1: Intake — read the feature entry and clarify scope with HITL if needed."
---

# Phase 1: Intake

1.1. Read the feature entry. If referenced by ID, read:
     `docs/roadmap/capability_matrix.md and the relevant docs/roadmap/topics/topic_*.md`
     and locate the row for this feature. Also read any linked proposal documents.

1.2. Determine whether all of the following are answerable without guessing:

     - **What** does the feature do? (user-facing behavior — what changes for the user)
     - **Why** does it exist? (the problem it solves — what currently doesn't work or is missing)
     - **Boundaries**: what does it touch? What explicitly does it NOT touch?
     - **Constraints**: performance targets, compatibility requirements, scope limits,
       technology mandates, security requirements.

1.3. If ALL of the above are answerable:
     Write a 3–5 sentence working definition using this format:
     ```
     Feature <ID> adds <capability> to <system component>.
     It solves <problem> by <approach>.
     It interacts with <modules/systems> and does NOT touch <out-of-scope areas>.
     Key constraints: <list constraints or "none stated">.
     ```
     Proceed autonomously to Phase 2.

1.4. If ANY of the above is unclear or missing:
     **STOP — HITL gate.**
     Present a numbered list of targeted questions, one per gap.
     Do NOT guess. Do NOT make assumptions.
     **Wait for answers before proceeding.**

> [!CAUTION]
> **HARD GATE:** If the feature description has gaps, you MUST stop and ask.
> Never start research on a poorly defined feature — the entire design will be wrong.
> A vague working definition produces vague requirements, which produce wrong code.

> [!CAUTION]
> **Phase 1 does not end with a working definition. It ends with `/grill-me`.**
>
> Answering the four intake questions from a registry entry proves the entry is readable, not that
> the scope is agreed. Everything a design does not ask, it decides. Measured 2026-08-19 across six
> capabilities built in one session: **twenty-five product-visible decisions were taken by the
> agent with no input** — a `$25` default spend cap that bills real money, the DAL level at which
> an agent is allowed to improvise, an agent turn ceiling, a chunk size, which prompt surfaces
> count as untrusted, and a detection strategy that **did not conform to the capability's own
> specification**. Every one was documented in the design. Not one was agreed. Documenting a guess
> does not stop it being a guess.
>
> So: **run `/grill-me <ID>` yourself** as soon as a trigger appears, and put every question to the
> user. Their answers are the only ones that close it — a question you answer on their behalf is the
> guess this rule exists to stop. Wait.
>
> Take the grilling to an **empty frontier** before Phase 2. Its output is what Phase 3 binds
> requirements to, and what Phase 6 reviews against. A design that reaches Phase 6 with decisions
> the user is seeing for the first time has turned the approval gate into a rubber stamp.
>
> **Some decisions are never the agent's**, whatever else the grilling settles. **Open
> `.agents/PRINCIPLES.md` §2 and read the table** — the names are listed there with the *fires on*
> column beside each, and a name without that column tells you nothing about when it applies.
>
> The names are deliberately not repeated here. This paragraph used to carry its own copy, which
> drifted: it said *"the twelve triggers"* while listing thirteen. §5 — one fact, one place.
>
> Read it before Phase 2 and name every trigger this capability touches. Each one goes to the user
> unsettled — no default, no placeholder, no reasonable-looking assumption.
>
> **Record each settled decision beside the fact it governs**, marked `` `[agreed <date>]` `` with an
> ISO date — in the sentence that states the number, names the surface, or draws the boundary. Not
> in a section of its own: `PRINCIPLES.md` §5 forbids the second copy, and a list at the foot of the
> document drifts the moment somebody edits the body without scrolling down.
>
> A trigger that did not fire is recorded **nowhere**. It has no fact to sit beside, and the
> thirteen are a detector, not a checklist to transcribe. The gate that demanded the transcription
> was `TECH-069`, retired 2026-08-23 for measuring vocabulary instead of truth.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 1 complete. Working definition written **and the grilling closed**.
> Proceed to Phase 2 (Research).
