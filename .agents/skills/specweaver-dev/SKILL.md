---
name: specweaver-dev
description: >-
  Implements one sub-feature test-first from its approved implementation plan: load context, break
  into tasks, red → green → refactor, mutate, then pre-commit and commit at each commit boundary.
  Use when the user says 'dev <impl_plan_path>', 'implement <feature_id> SF-<N>', 'develop
  <feature_id>', 'start coding <feature_id>' or 'build <impl_plan_path>'.
argument-hint: "<impl_plan_path> | <feature_id> SF-<N>"
---

# Development Skill (TDD)

```
Trigger: "dev <impl_plan_path>", "implement <feature_id> SF-<N>",
         "develop <feature_id>", "start coding <feature_id>",
         "build <impl_plan_path>"
```

> [!CAUTION]
> **STRICT RULES — NO EXCEPTIONS:**
> 1. **NO guessing or assuming.** If anything is unclear, STOP and ask the user (HITL).
> 2. **NO single-shot implementations.** Break work into small, manageable tasks.
> 3. **TDD: red tests first.** Every task starts with a failing test.
> 4. **Pre-commit gate before EVERY commit.** Invoke the `specweaver-pre-commit` skill — no shortcuts.
> 5. **Always re-read a file before editing it.** Never rely on memory.
> 6. **NEVER skip a commit boundary.** When `.tmp/task.md` calls for a commit, run the full gate and
>    commit before the next batch. Commit on your own; stop for the user only at the boundary that
>    closes the sub-feature `[agreed 2026-08-15]`.

> [!IMPORTANT]
> **AGENT DIRECTIVE FOR TDD:**
> DO NOT prompt or inform the user every time you transition between Red, Green, or Refactor phases.
> Execute the phases silently and continuously.
> STOP only at: the red-flag check (Phase 1) when it finds a gap, a §2 trigger
> (`PRINCIPLES.md`), and the commit boundary that closes the sub-feature (Phase 4–6). Raise
> anything that changes a decision at once; do not bank findings until the end.

> [!CAUTION]
> **Integration is implicit in the (sub)story (`ADR-005`). Never mint or reference an `INT-US`.**
> A test that cannot go RED proves nothing, so the test comes first. The (sub)story owns every test
> it needs, spanning ones included. A related (sub)story unbuilt → write the test now as
> `pytest.mark.xfail(strict=True, reason="blocked on <CAPABILITY-ID> ...")`; the blocker must be
> named, and `check_xfail_blockers.py` fails a marker whose blocker has shipped or is unnamed.
> A **seam FR** is proven at integration or
> e2e tier, never by a unit test with the other side mocked. A missing spanning test under a
> finished (sub)story → a `TECH` ticket. Full rules: [references/integration.md](references/integration.md).

Why each rule exists: [references/lessons.md](references/lessons.md).

## Phase 1: Load Context & Read the Spec

**1.0. Load context (mandatory — before anything else):**

a. Read the Implementation Plan at `<impl_plan_path>` in full.
b. From its header block, extract the Design Document path.
c. Read the Design Document in full. Focus on:
   - Feature Overview (understand the intent and rationale)
   - The sub-feature section for this plan (scope, FRs subset, inputs, outputs)
   - Progress Tracker (verify all pre-conditions are met)
d. **Pre-condition checks — HARD STOP if any fail:**
   - **Prerequisites green IN CODE:** run `python scripts/check_story_preconditions.py <STORY-ID>`.
     A non-zero exit is a hard block — do not implement, do not waive it, do not ask for a waiver.
     Document state lies; this checks the evidence, not the checkbox.
   - Design Document `Status: APPROVED`? If not → trigger the design skill first.
   - This sub-feature's `Impl Plan` is `✅` in the tracker? If not → trigger the implementation-plan skill first.
   - All sub-features in `depends_on` have `Committed ✅`? If not → tell the user which dep is incomplete.

> [!CAUTION]
> **TEST TIER MUST MATCH THE CLAIM (`TECH-017`, `ADR-003`).** Behaviour of this module alone →
> **unit**; a **seam** (calling, reading or persisting through another module) → **integration**;
> a user-visible journey across capabilities → **e2e**. This boundary owns the integration test for
> any surface it touches, and the e2e is written in 3.1 Red like any other test. Never commit a red,
> and never `skip`/`xfail` one to green. Read [references/test-tier.md](references/test-tier.md)
> before Phase 2.

**1.0e. MANDATORY**: Read ALL relevant files in `docs/dev_guides/` and `docs/user_guides/`.
       These contain established patterns, conventions, and extension points.

**1.0f. MANDATORY**: Read ALL `context.yaml` files for every module that will be
       created or modified. Verify no violations before writing code.

**1.1. Read the implementation plan** in full again with fresh understanding of the design context.
     Understand the full scope, interfaces, and dependencies.

**1.1a. MANDATORY**: Verify you understand ALL FRs, NFRs, Architectural Decisions (ADs),
       and Risk Tables (RTs) from the design doc. List them to yourself. If any are unclear, STOP and ask.

**1.1b. Architecture principles reminder**: Keep these in mind throughout development:
       KISS, DDD, TDD, DRY, hexagonal architecture, separation of concerns.
       Implement corner cases, FRs, NFRs, RTs, and ADs.

1.2. **Red flag check**: Can you implement this without guessing?
     - Are all interfaces defined?
     - Are all data models clear?
     - Are all edge cases specified?
     - Are dependencies on other modules clear?

     If ANY answer is "no" → **STOP. Call the HITL. Ask the user.**
     Do NOT proceed with assumptions.

## Phase 2: Task Breakdown

2.1. Break the feature into small, independently testable tasks.
     Each task should be completable in one TDD cycle (red → green → refactor).

2.2. Order tasks by dependency — implement foundations first, consumers last.

2.3. Write the task list to `.tmp/task.md`. Each task should have:
     - A clear, one-line description
     - The source file(s) to create/modify
     - The test file(s) to create/modify

2.4. **Red/Blue Team Analysis**: Execute the `specweaver-red-blue-review` skill against the task list to look for missing edge cases, architectural gaps, or implementation flaws.

2.5. Fix what the review finds. Report the task list and the findings to the user in a few lines
     and continue: the approved plan already covers it. Stop only if a finding changes a decision.

## Phase 3: TDD Cycle (repeat for each task)

For each task in the breakdown:

### 3.1 Red — Write Failing Tests First

> [!CAUTION]
> **STRICT SEQUENCING MANDATE:** You MUST write the test file(s) in `tests/` and run `pytest` to
> verify they fail (Red) **BEFORE** you are allowed to write or modify ANY implementation code in
> `src/`.
> You are permitted to batch this: you may write 20 failing test cases at once. But you MUST run
> them and confirm they fail before moving to Phase 3.2. Generating `src/` implementation code
> before proving the tests fail is a severe process violation.

> [!CAUTION]
> **ADVERSARIAL TEST MATRIX MANDATE:** Before generating any tests, you MUST explicitly output a test matrix classifying your proposed tests into exactly 4 buckets:
> 1. **Happy Path:** Expected Input -> Expected Output.
> 2. **Boundary/Edge Cases:** Empty arrays, massive files, max constraints, cyclic graphs.
> 3. **Graceful Degradation:** Dependencies failing, network timeouts, unparseable ASTs.
> 4. **Hostile/Wrong Input:** Path traversal strings, completely wrong types, `None` injections.
>
> You MUST write at least one test story for EACH of these 4 buckets. If a bucket is mathematically impossible for the current feature, explicitly justify why.

> [!CAUTION]
> **THE MATRIX VARIES INPUTS. IT NEVER ASKS WHETHER THE UNIT IS USED ALONE.** So ask two more
> questions before you stop writing tests:
>
> 1. **Is this only ever used in sequence with something else?** Then a test of each end is not a
>    test of the pair: each unit test builds the state it wants instead of letting the other half
>    build it.
> 2. **Does anything else in the repo do this same job?** Then assert that they **agree**.
>
> Neither question is answered by a bucket, because each half genuinely satisfies its own bucket.
> Where the answer to either is yes, that test is **integration** even when both sides are pure —
> the seam is the claim.

> [!IMPORTANT]
> **The matrix says WHAT to test; `specweaver-pre-commit/references/test-quality.md` says whether a
> passing test proves anything.** Read it before writing assertions — the eight vacuous-proof
> patterns are cheaper to avoid than to find later, and pattern 7 (deriving your expected value
> from the thing under test) is invisible in review.
>
> Two workflow rules from that file apply here directly: **a targeted green is not evidence, only
> the full suite is**, and **the tree is frozen while a full suite runs** — a run whose source
> changed underneath it proves nothing.

- Write the test(s) for the task according to your matrix. Include:
  - Happy path
  - Boundary/Edge cases
  - Graceful Degradation error paths
  - Hostile input handling
- Run the test(s) — they MUST fail (red). If they pass, the test is wrong.
```
python -m pytest tests/unit/<relevant_test_file>.py -v --tb=short
```

> [!IMPORTANT]
> **Two shared test helpers exist; use them rather than re-implementing either.**
> `tests/rendering.py` — `shows(output, needle)` for any assertion on CLI output.
> `tests/scripted_llm.py` — `doubled_llm()` / `scripted_world()` when a test needs a doubled LLM.
> Read [references/test-helpers.md](references/test-helpers.md) before using either.

### 3.2 Green — Implement the Minimum Code

- **Re-read the target file** before editing (mandatory).
- Write the simplest code that makes the tests pass.
- Do NOT add code that isn't needed by a test. YAGNI.
- Run the tests — they MUST pass (green).
```
python -m pytest tests/unit/<relevant_test_file>.py -v --tb=short
```

### 3.2a Debugging — When Tests Fail Unexpectedly

Run targeted tests autonomously; the commands are in
[references/test-helpers.md](references/test-helpers.md).
Debug loop: read error → re-read source → fix → re-run failing test → repeat until green.

### 3.2b Mutate — prove the test can still fail

Green means the test passes. It does **not** mean the test would notice the behaviour going away.
For each FR this boundary claims to prove, neutralise the line that carries it and check the suite
objects:

```
python scripts/_mutate.py --file src/... --old '<exact anchor>' --new '<neutralised>'
```

`SURVIVED` means the test does not test this: fix it now, while you still have the context. Run it
on the claims you are about to call proven, not on the ones you already doubt. When the claim is
one you are about to call **proven**, write it into the durable corpus
`docs/roadmap/features/<topic>/<ID>/<ID>_mutants.json`. Results, campaigns and the corpus:
[references/proving.md](references/proving.md).

### 3.2c Backfill on contact — a capability you touch gains the FRs it never had

When a commit boundary touches a delivered capability with no design or no FRs, it gives it FRs.
Not as a project. Write each FR from why the capability exists, and kill a mutant with it before
believing it. Rules and the journey-proof alternative: [references/proving.md](references/proving.md).

### 3.3 Refactor (if needed)

- Clean up duplication, naming, structure.
- Run tests again — still green.
- Run the fast quality gate — fix any issues immediately.
```
python -m pytest tests/unit/<relevant_test_file>.py -v --tb=short
python scripts/quality.py quick
```

A green `quick` is never permission to commit: [references/gates.md](references/gates.md).

### 3.4 Update task.md

- Mark the completed task as `[x]` in `.tmp/task.md`.

## Phase 4 + 5 + 6: Per-Commit Quality Gate (repeat for each commit boundary)

The implementation plan defines one or more commit boundaries in `.tmp/task.md`
(e.g., "commit after tasks 1–3", "commit after tasks 4–6").
**Each boundary triggers a full quality + commit cycle before the next task batch begins.**

> [!CAUTION]
> **HARD RULE:** There is NO single pre-commit run at the end of the dev skill.
> Every commit boundary gets its own pre-commit run and its own commit.
> 3 commit boundaries = 3 pre-commit runs = 3 commits.
> Do NOT batch commits. Do NOT skip the pre-commit for intermediate commits.

For **each commit boundary** in `.tmp/task.md`, in order:

**Step A — Complete the task batch (autonomous):**
- Run all TDD tasks in this batch to completion (red → green → refactor).
- **MANDATORY TESTING**: After completing the final task in this batch, run the test gate for
  this commit boundary and story:
```
python scripts/tests.py cb <STORY-ID>
```
- A TECH ticket must add `--kind refactor|bugfix|tooling|audit`.
- **DO NOT** hand-pick which tiers or paths to run. The gate decides from the story's type and
  DAL, and `python scripts/tests.py matrix` shows every profile. `--also`/`--all` may widen the
  run; nothing narrows it.
- The `cb` scope is narrower than a full sweep on purpose; why, and how to widen it:
  [references/gates.md](references/gates.md).
- A tier reporting `selected NO tests` is a **failure**, not a pass — it means you changed source
  nothing mirrors.
- Fix any regressions before proceeding to Step B.

**Step B — Pre-Commit Quality Gate (autonomous):**
- Invoke the `specweaver-pre-commit` skill and run all its phases. This is MANDATORY, and it is
  re-invoked at every boundary: context is not execution.
- **CRITICAL**: You MUST update `.tmp/task.md` line-by-line as you execute EACH phase of the pre-commit skill.
- Every check runs; none is skipped. Implement every test the gap analysis (Phases 2–3) calls for
  before Phase 4.
- Stop for the user only if a check needs a decision you cannot take.

**Step C — Commit Boundary:**
- **Interior boundary:** commit (`<type>(<scope>): <description>`), then report in a few lines:
  the tasks it holds, the test count, what the gate found. Proceed to the next task batch (Step A).
  Never start the next batch on a red gate.
- **The boundary that closes the sub-feature (HITL — mandatory hard stop):**

> [!CAUTION]
> **HARD STOP REQUIRED:** You MUST NOT declare the sub-feature delivered autonomously.

  - Run the full gate, stage the boundary, then **STOP execution** before committing.
  - Inform the user:
    - "Commit boundary N of M is ready. Pre-commit passed."
    - Which tasks are included in this commit
    - Current test count
  - **WAIT** for the user's acceptance.
  - Do absolutely nothing else until they respond.
  - On acceptance: commit, then update `.tmp/task.md`.

**After the final commit boundary:**
- Update the Progress Tracker in the Design Document:
  `Dev ✅`, `Pre-Commit ✅`, `Committed ✅` for this sub-feature.
- Update the Session Handoff paragraph in the Design Document.
- **If this was the LAST sub-feature** (every other tracker row is `Committed ✅`), the story is
  about to be declared finished — execute **Phase 4 of `specweaver-dev`'s parent,
  `specweaver-feature`** (the closure gate: `check_fr_coverage.py` + the full suite) before writing
  `Status: COMPLETE`. Do NOT declare a story finished from inside this skill without it; running
  `dev` directly is otherwise a way to close a story having never checked the design's FR ledger.
- End every report with `Push now: YES/NO`. The user pushes, once per feature.

---

## Principles

| Principle | Rule |
|-----------|------|
| **No guessing** | If unclear → HITL. Never assume. |
| **TDD** | Red → Green → Refactor. Every task. |
| **Small tasks** | One logical unit per TDD cycle. |
| **KISS** | Keep it simple. Think of corner cases but don't over-engineer. |
| **Re-read before edit** | Always read the file immediately before modifying it. |
| **Lint early** | Run ruff after each green step. Don't accumulate debt. |
| **Architecture** | Check imports respect layer boundaries. No cross-layer violations. |
| **Coverage** | Target 70-90% test coverage. |
| **Pre-commit gate** | Mandatory before every commit. No exceptions. |
| **Commit Boundaries** | Gate and commit at every boundary. Stop for the human only at the one that closes the sub-feature. |
| **Tests run freely** | All test/lint commands run autonomously. No exceptions. |
| **Temporary Files** | Use the project's `.tmp` directory for all temporary scripts, debug files, or scratchpads. |
