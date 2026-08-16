---
name: specweaver-implementation-plan
description: "Create or audit an implementation plan for a sub-feature. Deep research, audit across
16 categories, architecture verification, Red/Blue team analysis, consistency check. Use when the
user asks to create an implementation plan, plan a sub-feature, or prepare for development."
---

# Implementation Plan Skill

```
Trigger: "implementation plan for <feature_id> <sf_id>",
         "plan <feature_id> SF-<N>", "prepare implementation for <feature_id>"
```

**Pre-conditions — HARD STOP if any fail:**

1. **Prerequisites are green IN CODE, not just in documents:**
   ```
   python scripts/check_story_preconditions.py <STORY-ID>
   ```
   A non-zero exit is a **hard block** — do not plan, do not "note it and continue", and do not
   ask the user to waive it. Fix the reported facts first, or file the finding as its own ticket
   (`specweaver-ticket`) and stop.

   > [!CAUTION]
   > This exists because document state lies. INT-US-21's design recorded its prerequisites as
   > "all ✅: US-2 Core, D-INTL-02, D-INTL-03" — and **all three were materially broken**:
   > handlers never registered so the shipped pipeline could not run a single step;
   > `RunContext.plan` documented as "(set by runner hook)" with zero writes in `src/`; a required
   > enum that cannot be serialized to YAML at all. Every checkbox was true as written and false
   > in fact. The script verifies the *evidence* behind the checkbox: the declared proof exists,
   > passes, and does not skip; every bundled pipeline step resolves to a real handler; no field
   > documented as "set by X" is unwritten.

2. The Design Document at `<design_doc_path>` exists and `Status: APPROVED`.
3. If `<sf_id>` is given: all sub-features in its `depends_on` list have `Impl Plan ✅`
   in the Progress Tracker.
4. If `<sf_id>` is omitted and the design has sub-features: ask the user which sub-feature
   to plan. Do NOT plan all sub-features at once.

> [!IMPORTANT]
> **TEST TIER MUST MATCH THE CLAIM, NOT THE STORY TYPE (`TECH-017`, `ADR-003`).** Decide the tier
> per requirement when drawing the commit boundaries:
>
> | The requirement claims | Proof tier |
> |---|---|
> | behaviour of this module alone | unit |
> | **a seam** — this module calling, reading or persisting through another | **integration** |
> | a user-visible journey across capabilities | **e2e** |
>
> `ADR-003` folded integration into the story that creates the seam, so a plan that touches another
> module's surface **owns** the integration test for it — there is no later story that will do it.
> Never defer all integration work to one final boundary; that is how SF-02 CB-1 came to ship 16
> unit tests and zero others.
>
> **Write the seam test at the boundary where the interface first exists and the behaviour does
> not.** Where step *n*'s interface depends on step *n−1*'s output, the test goes **between** them —
> that is the only moment a red means anything. Record the red and its reason in the plan: it is the
> one piece of evidence a `Proves:` tag can never supply, that the test CAN fail.
>
> **The same sequencing binds the e2e** — the half most easily lost, because nothing about a
> journey test *looks* like it belongs early. A journey test written once the journey already works
> has never failed for the right reason, exactly as a seam test written after the seam has not. So
> the e2e is authored **before the wiring it exercises**, inside the boundary that owns it, and
> turned green there.
>
> **Name the boundary that owns each journey claim, and do not park it at the last one because the
> tier profile runs it there.** `scripts/tests.py` decides when a tier is *executed* at a given
> commit state; it says nothing about when the test is *written*.
>
> `ADR-003`'s worked example is `C-EXEC-06` FR-8, a *"multi-step, freshly-generated-file e2e"*
> where step 1 generates a file a later step consumes — and those are **pipeline** steps inside the
> test, not commit boundaries. Multi-step is what makes the journey falsifiable; it is not licence
> to plan a test that stays red past its own commit.
>
> **If a journey cannot go green inside any single boundary, the boundaries are wrong** — that is a
> Phase 4 finding, not a red to schedule. Redraw them so the journey completes in one, or narrow
> the e2e to the journey that IS complete there and state which part is deferred and to which
> boundary. An e2e planned as red-at-commit will be turned green by a skip, and that is the exact
> shape `check_proof_tier.py` was built to catch.
>
> Unit-test-heaviness where a seam was expected is a **diagnostic**: the capability you are building
> on shipped incomplete, and that is a finding against *it* (`TECH-017` FR-6), not a reason to
> write its tests here under your own story's name.
>
> **A boundary whose Done-when says "write the missing test" is done when that test KILLS A MUTANT,
> not when it passes.** Neutralise the line the test claims to cover and check it goes red:
> `python scripts/_mutate.py --file … --old … --new …`. State the expected mutant in the plan, so
> the boundary has a falsifiable exit condition rather than a green tick.
>
> This is not ceremony. `TECH-017` wrote a containment test that passed immediately and proved
> nothing — the function it covered returned `{}` for every caller, so the assertion could not fail.
> The mutant was what said so, and chasing it found a key mismatch that had kept skeleton context
> out of every generation and review prompt since the feature shipped.

**Output header block** — write this at the top of every impl plan produced:
```markdown
# Implementation Plan: <Feature Name> [SF-<N>: <Sub-Feature Name>]
- **Feature ID**: <feature_id>
- **Sub-Feature**: SF-<N> — <name>   (omit line if not decomposed)
- **Design Document**: <design_doc_path>
- **Design Section**: §Sub-Feature Breakdown → SF-<N>  (omit line if not decomposed)
- **Implementation Plan**: <this_file_path>
- **Status**: DRAFT | APPROVED
```

> [!CAUTION]
> **MANDATORY SEQUENCING — DO NOT SKIP OR REORDER PHASES.**
>
> This skill has 6 phases that MUST be executed in strict order.
> Every phase MUST be completed before moving to the next one.
>
> **Before starting each phase:**
> 1. Read the phase file from the `references/` directory listed below.
> 2. Complete every step in that phase before moving on.
>
> **Phases 4 and 5 have HITL gates** — you MUST stop and wait for the user.
> Phase 4: present all audit + arch findings (always fires).
> Phase 5: final consistency approval (always fires).

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Execute research, audit, and architecture verification autonomously.
> STOP only at the defined HITL gates (Phases 4 and 5). Never bypass them.

> [!CAUTION]
> **CODE DETAIL LIMIT: pseudocode and short snippets only — NEVER a full-fledged class or algorithm.**
>
> An implementation plan may include:
> - Short illustrative snippets (a few lines) showing a signature, a call shape, or one
>   tricky bit of logic worth pinning down (e.g. "reject PATH case-insensitively: `key.upper() == \"PATH\"`").
> - Pseudocode describing the sequence of steps/checks an implementation must perform,
>   and in what order, with the reasoning for that order.
> - Exact signatures pulled from *existing* code being called or subclassed (these are
>   research findings, not authored code — quoting `SubprocessExecutor.execute()`'s real
>   signature is fine; writing out `BashActionAtom`'s entire `run()` body is not).
>
> An implementation plan must NEVER include a complete, ready-to-paste class body,
> a fully worked algorithm, or anything a developer could copy verbatim into the
> source file without doing any of their own implementation work. Writing the real
> code is the **`dev` skill's** job — driven test-first (red → green → refactor) from
> the FRs and test plan this document specifies. A plan that pre-writes the
> implementation defeats TDD (tests get written to match code that already exists in
> the plan, not the other way around) and produces two competing sources of truth that
> drift the moment the `dev` skill's tests force a different shape.
>
> If you catch yourself writing a full method body with every branch fleshed out,
> STOP — collapse it back down to an ordered list of checks/steps (pseudocode) and
> move any signature-level detail into the Research Notes as a cited fact, not
> authored code.

> [!CAUTION]
> **The integration and e2e proof belongs to the capability, never to an `INT-US` story.**
> A test that cannot go RED proves nothing, and RED is only available while the feature is
> unimplemented. Collecting the seam into an integration story that runs *after* the capability
> ships means its first run is green against code that already exists — it asserts the present,
> not the contract.
>
> **Never mint or reference an `INT-US-NN` / `INT-US-NN-SFxx` for work that is not built yet** —
> not as a dependency, not as a retirement tombstone. The seam and journey proofs are FRs of the
> capability, authored red inside its own TDD cycle, before the code they judge.
>
> An `INT-US` entry is legitimate in exactly one place: a (sub)story that **already holds a
> finished feature**, where `finished-stories-immutable` bars the closed capability from taking
> the FR and the proof has nowhere else to live.
>
> **There, an OPEN `INT-US` is load-bearing — never delete it.** It is the only record that a
> feature which is already implemented has not been integration-tested. Removing it does not
> retire the debt; it hides it, and the story then reads as proven. An `INT-US` line closes by
> the integration being written and passing. It never closes by being tidied away.

## MCP Tool Guidance

When available, prefer these MCP tools over grep/file-reading:

- **Architecture verification (Phase 3):** Use `codebase-memory` → `get_architecture` and `trace_path` to verify dependency chains and layer boundaries.
- **Identifying existing patterns (Phase 0-1):** Use `codebase-memory` → `search_graph` to find similar implementations in the codebase.
- **API surface validation:** Use `context7` → `get-library-docs` to verify library APIs referenced in the plan are correct.
- **Fall back to grep/file-reading** if MCP tools are unavailable.

## Phases


| Phase | File | Description | HITL Gate? |
|-------|------|-------------|------------|
| **0** | `.agents/skills/specweaver-implementation-plan/references/phase-0-research.md` | Deep codebase + external API + guides research | No |
| **1** | `.agents/skills/specweaver-implementation-plan/references/phase-1-preparation.md` | Read design doc + architecture + cross-ref codebase | No |
| **2** | `.agents/skills/specweaver-implementation-plan/references/phase-2-audit.md` | Identify all open questions across 16 categories | No |
| **3** | `.agents/skills/specweaver-implementation-plan/references/phase-3-architecture.md` | Architecture verification — feeds Phase 4 | No |
| **4** | `.agents/skills/specweaver-implementation-plan/references/phase-4-merge.md` | Present combined findings → HITL → merge into plan | ⚠️ Always |
| **5** | `.agents/skills/specweaver-implementation-plan/references/phase-5-consistency.md` | Consistency + Red/Blue + HITL approval | ⚠️ Always |

**After Phase 5 approval:**
- Mark `Impl Plan ✅` for this SF in the Progress Tracker in the Design Document.
- Update the `Session Handoff` paragraph in the Design Document.
