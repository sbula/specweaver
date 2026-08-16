---
name: specweaver-dev
description: "TDD development skill for implementing features. Load context → read spec → break down
→ red/green/refactor → pre-commit → commit (per commit boundary). Use when the user asks to
implement, develop, code, or build a sub-feature from its implementation plan."
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
> 4. **Pre-commit gate before EVERY commit.** Run the pre-commit skill — no shortcuts.
> 5. **Always re-read a file before editing it.** Never rely on memory.
> 6. **NEVER skip a commit boundary.** When `task.md` calls for a commit, you MUST STOP and wait for the user (HITL). Do NOT proceed to the next phase.

> [!IMPORTANT]
> **AGENT DIRECTIVE FOR TDD:**
> DO NOT prompt or inform the user every time you transition between Red, Green, or Refactor phases.
> Execute the phases silently and continuously.
> STOP only at the defined HITL gates: red-flag check (Phase 1), task list review (Phase 2),
> and the per-commit cycle gates (Phase 5).

## MCP Tool Guidance

When available, prefer these MCP tools over grep/file-reading:

- **Before modifying code:** Use `codebase-memory` → `search_graph` to find the exact definition and all references of the symbol you're changing.
- **Before adding imports:** Use `codebase-memory` → `trace_path` to verify the import respects layer boundaries (tools→atoms→commons).
- **When using library APIs:** Use `context7` → `get-library-docs` for correct Pydantic v2, SQLAlchemy async, pytest, or Typer syntax.
- **Fall back to grep/file-reading** if MCP tools are unavailable.

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
     Document state lies: INT-US-21's three prerequisites were all marked `✅` and all three were
     materially broken (handlers never registered; a field documented as hook-populated with zero
     writes in `src/`; a required enum that cannot be YAML-serialized). This checks the evidence,
     not the checkbox.
   - Design Document `Status: APPROVED`? If not → trigger the design skill first.
   - This sub-feature's `Impl Plan` is `✅` in the tracker? If not → trigger the implementation-plan skill first.
   - All sub-features in `depends_on` have `Committed ✅`? If not → tell the user which dep is incomplete.

> [!CAUTION]
> **TEST TIER MUST MATCH THE CLAIM (`TECH-017`, `ADR-003`).** Tier is chosen per requirement, not
> per story type: behaviour of this module alone → **unit**; a **seam** (calling, reading or
> persisting through another module) → **integration**; a user-visible journey across capabilities →
> **e2e**.
>
> `ADR-003` folded integration into the story that creates the seam, so if your commit boundary
> touches another module's surface, **this boundary owns that integration test** — no later story
> will write it. Where step *n*'s interface depends on step *n−1*'s output, write the seam test
> BETWEEN the two: that is the only moment it can fail for the right reason. Note the red and its
> reason in the walkthrough.
>
> **This binds the e2e too.** A journey test written once the journey already works cannot fail for
> the right reason either, so the e2e is authored in **3.1 Red like any other test** — before the
> wiring it exercises — and turned green inside the same boundary. The tier profile in
> `scripts/tests.py` decides which tiers **run** at this commit state; it never decides when a test
> is **written**, and "the profile runs e2e later" is not a reason to author it later.
>
> `ADR-003`'s worked example is `C-EXEC-06` FR-8: an e2e whose **pipeline** step 1 generates a file
> a later **pipeline** step consumes. Note which "steps" those are — they are steps inside the test,
> not commit boundaries. Multi-step is what makes the journey falsifiable; it does not license a
> test that stays red past its own commit.
>
> **If the journey genuinely cannot go green inside one boundary**, that is a finding about the
> boundaries, not a red to carry: the plan drew them so a user-visible journey spans several. Raise
> it — redraw the boundary, or descope the e2e to the journey that IS complete here. Do not commit
> a red, and do not `skip`/`xfail` it to green: a silent skip is the failure mode
> `check_proof_tier.py` and `_silent_skips.py` exist to catch.
>
> Writing many unit tests where a seam was expected is a **diagnostic**: the capability you build on
> shipped incomplete, and that is a finding against *it*, not tests to adopt under your own name.
> Before Phase 2, check whether a CLI surface already works well enough for an e2e: an explicit spec
> path often works long before bare-name resolution does.

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

2.3. Write the task list to `task.md`. Each task should have:
     - A clear, one-line description
     - The source file(s) to create/modify
     - The test file(s) to create/modify

2.4. **Red/Blue Team Analysis**: Execute the `specweaver-red-blue-review` skill against the task list to look for missing edge cases, architectural gaps, or implementation flaws.

2.5. Present the task list and the Red/Blue review findings to the user for review (HITL).
     Wait for approval before proceeding.

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
> **Two shared test helpers exist because their absence caused real, cited-proof defects. Use them
> rather than re-implementing either.**
>
> **`tests/rendering.py` — `shows(output, needle)` for any assertion on CLI output.** Rich
> soft-wraps to the terminal width, so `result.output` can contain `orp\nhan.py`. A raw `in` check
> then passes or fails on `COLUMNS`, which nothing in the test declares and CI does not hold
> constant. `TECH-017` found this **twice, both times in the cited proof of a delivered contract**,
> and both were invisible until the file was run on its own — the full suite stayed green because
> xdist sets a different width. `shows()` squashes whitespace on **both** sides. Presence checks
> only: never assert layout or ordering with it.
>
> **Setting `COLUMNS` at invoke time does not widen anything.** Rich TRUNCATES table cells to the
> terminal width (`fake-journey-model` renders as `fake-j…`), and the CLI's `Console` is built at
> module **import** (`interfaces/cli/_core.py:37`) — so `runner.invoke(..., env={"COLUMNS": ...})`
> is already too late. `INT-US-16` asserted a model name that way: green run alone, red under
> `-n auto`, where xdist's import-time width is narrower. **Assert something width cannot change** —
> a parsed number, a row count — rather than a string that might be truncated. And note the mirror
> image: asserting a truncated string is ABSENT passes for free, which is how the same commit's
> isolation test was vacuous until it counted rows instead.
>
> **`tests/scripted_llm.py` — `ScriptedLLM` / `scripted_world()` when a test needs a doubled LLM.**
> `scripted_world` patches **two** things and both are load-bearing: patching only
> `create_llm_adapter` leaves `ModelRouter.get_for_task` free to build a **real provider** from the
> registry, bypassing the patch — a live API call inside a test that reads as mocked. That was found
> for real in `INT-US-02`'s e2e. Anything that copies or re-implements this must carry both patches.
> Import it explicitly rather than hiding it in a fixture: the import line is the only place a
> reader sees that a test doubles the model.

### 3.2 Green — Implement the Minimum Code

- **Re-read the target file** before editing (mandatory).
- Write the simplest code that makes the tests pass.
- Do NOT add code that isn't needed by a test. YAGNI.
- Run the tests — they MUST pass (green).
```
python -m pytest tests/unit/<relevant_test_file>.py -v --tb=short
```

### 3.2a Debugging — When Tests Fail Unexpectedly

> [!NOTE]
> **Interpreter + parallelism.** Every command in this skill uses a bare `python` for brevity, but
> run them with the project venv (`.venv/Scripts/python.exe` on Windows, `.venv/bin/python` on
> Linux): the system interpreter imports `specweaver` fine but has **no `pytest-xdist`**, so
> `-n auto` silently does nothing there and the suite runs serial.
>
> The single-file commands below are deliberately serial — measured on 16 cores, one module is
> 12.5s serial vs 15.2s with `-n auto`, because worker startup costs more than it saves. Add
> `-n auto` only once you are running a whole tier or the full suite (`tests/unit` 5m02 -> 1m37;
> full suite ~13m -> 4m26). `scripts/tests.py` already passes `-n auto`, so the commit-boundary
> gate in Phase 4/5 needs nothing extra.


When a test fails and you need to debug, run targeted tests autonomously.
All these commands auto-run — no human interaction needed:
```
# Single test by node ID
python -m pytest tests/unit/test_foo.py::TestClass::test_method -v --tb=long

# Keyword filter
python -m pytest tests/unit/test_foo.py -k "test_specific_case" -v --tb=long

# All tests in a specific file with full traceback
python -m pytest tests/unit/test_foo.py -v --tb=long

# Re-run only previously failed tests
python -m pytest --lf -v --tb=long

# Run test with debug logging enabled
python -m pytest tests/unit/test_foo.py -s --log-cli-level=DEBUG

# Run arbitrary python debug scripts via file (must be safe)
# write your script to .tmp/debug.py then run:
python .tmp/debug.py
```

Debug loop: read error → re-read source → fix → re-run failing test → repeat until green.

### 3.2b Mutate — prove the test can still fail

Green means the test passes. It does **not** mean the test would notice the behaviour going away,
and a test written after the code has never failed for the right reason.

For each FR this boundary claims to prove, neutralise the line that carries it and check the suite
objects:

```
python scripts/_mutate.py --file src/... --old '<exact anchor>' --new '<neutralised>'
```

It runs in a detached worktree, so your tree is untouched and you can keep working; a targeted run
is seconds, the whole suite about a minute. Three answers matter:

| Result | Meaning |
|---|---|
| `KILLED`, several | protected |
| `KILLED`, **exactly one** | a single point of protection — worth a note in the walkthrough |
| `SURVIVED` | the test does not test this. Fix it now, while you still have the context |

> [!CAUTION]
> **Run it on the claims you are about to call proven, not on the ones you already doubt.**
> `TECH-017` ran six of these by hand and **four caught vacuous assertions** — a guard that passed
> with a bypass planted, a credential check that passed un-isolated, a repo root that globbed a
> directory which does not exist. Every one was written by someone who believed the claim.
>
> A *surviving* mutant is not automatically a gap: an **equivalent** mutant, one that does not change
> observable behaviour, survives for a reason that is not missing coverage. Confirm the edit changes
> something before acting on it.

For several claims at once — an audit, or a boundary with many FRs — use
`scripts/_mutate_campaign.py --campaign <json>`, which reuses one sandbox and writes a report to
`.tmp/` (gitignored). Nothing it produces is committed: a report is an input to your decision, never
a record of one.

> [!IMPORTANT]
> **A probe answers today's question; a CAMPAIGN keeps answering it.** The two above are
> throwaway — they tell you whether a claim holds right now and leave no record. When the claim is
> one you are about to call **proven**, write it into the durable corpus instead:
> `docs/roadmap/features/<topic>/<ID>/<ID>_mutants.json`, one campaign per (N)FR, scoped to the
> tests that cover it.
>
> The nightly session then re-asks it forever, and `symbol_sha` drift reports `STALE` when the code
> a claim rested on moves. That is the difference between knowing a test was strong in August and
> knowing it is strong today.
>
> `python scripts/mutation.py --corpus <path> --no-baseline` runs one file while you write it.
> Authoring, dispositions and the morning gate: `docs/dev_guides/writing_mutation_campaigns.md`.

### 3.2c Backfill on contact — a capability you touch gains the FRs it never had

**Measured 2026-08-16 (`TECH-053`): of 62 capabilities marked `✅`, exactly ONE passes its own FR
ledger.** Nineteen have no design document at all — eight from the "Step N" bootstrap, eleven from
the "Feature 3.x" era whose implementation plans carry real design reasoning and **zero FRs between
them**. They are invisible to `check_fr_sweep.py` by construction: no design means no FRs to be
uncited, so they score zero and read as perfect.

**So when a commit boundary touches one of them, it gives it FRs.** Not as a project — writing
nineteen designs at once manufactures nineteen claims nobody can falsify, which is worse than the
silence it replaces. On contact, you already have the context and a change to test against, which
is the whole reason it is cheap here and expensive as an audit.

Two rules make the difference between a requirement and a paraphrase:

1. **Write it from why the capability exists, not from what the code does.** An FR read off the
   implementation restates it, and a restatement can never fail.
2. **Kill a mutant with it before believing it.** Neutralise the line the new FR claims to cover
   (3.2b). If nothing dies, you transcribed rather than constrained — delete the FR and write a
   different one. This is the only mechanical way to tell the two apart, and it caught two vacuous
   tests in `TECH-051`/`TECH-053` written by someone who believed them.

**Where the code predates any recorded intent, a journey proof beats a reconstructed design.**
`D-FLOW-01`'s entire written record is *"SQLite Pipeline Runner & State Persistence."* There is
nothing to backfill *from* except the code, so a spec would describe the implementation with a
straight face. One falsifiable e2e — *a pipeline runs and its state survives a resume* — declares no
FRs, invents no history, and can fail. Prefer it.

### 3.3 Refactor (if needed)

- Clean up duplication, naming, structure.
- Run tests again — still green.
- Run the fast quality gate — fix any issues immediately.
```
python -m pytest tests/unit/<relevant_test_file>.py -v --tb=short
python scripts/quality.py quick
```

`quick` is the sub-second subset (lint, cognitive complexity, file sizes, conventions and the
test-source guards, diff-scoped) and is meant to be run as often as you like. It is deliberately
NOT the commit gate: `python scripts/quality.py cb` runs at the commit boundary, adds mypy, tach,
the suppression ratchet, class health and cycle detection, and widens every check to the whole
source tree. Never treat a green `quick` as permission to commit.

### 3.4 Update task.md

- Mark the completed task as `[x]`.

## Phase 4 + 5 + 6: Per-Commit Quality Gate (repeat for each commit boundary)

The implementation plan defines one or more commit boundaries in `task.md`
(e.g., "commit after tasks 1–3", "commit after tasks 4–6").
**Each boundary triggers a full quality + commit cycle before the next task batch begins.**

> [!CAUTION]
> **HARD STOP RULE:** There is NO single pre-commit run at the end of the dev skill.
> Every commit boundary gets its own pre-commit + HITL gate.
> 3 commit boundaries = 3 pre-commit runs = 3 HITL commit stops.
> Do NOT batch commits. Do NOT skip the pre-commit for intermediate commits.

For **each commit boundary** in `task.md`, in order:

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
- **This is deliberately narrower than a full-suite sweep at every commit boundary.** A capability
  story runs unit tests for the packages it touched here, and the full sweep across all tiers
  happens at `sf` and `feature`. The trade is bought with the scoping, not skipped: a cross-module
  regression surfaces at the sub-feature gate rather than immediately. If a batch touched a
  widely-depended-on module and you want the sweep now, `--all` is the honest way to ask for it.
- A tier reporting `selected NO tests` is a **failure**, not a pass — it means you changed source
  nothing mirrors.
- Fix any regressions before proceeding to Step B.

**Step B — Pre-Commit Quality Gate (autonomous, gates may fire):**
- Execute the full pre-commit skill (all 7 phases). This is MANDATORY.
- Read `.agents/skills/specweaver-pre-commit/SKILL.md` and follow all phases.
- **CRITICAL**: You MUST update `task.md` line-by-line as you execute EACH phase of the pre-commit skill.
- **CRITICAL**: Do NOT act autonomously for Phase 4. Wait for user input from the Phase 3 HITL gate, and then you MUST implement the tests they approved/requested in Phase 4.
- **STOP at Phase 1 HITL gate** if architectural violations are found.
- **STOP at Phase 3 HITL gate** (test gap analysis — always fires).
- Complete Phase 4 – 7 step-by-step after the user responds, updating `task.md` at every single step.

**Step C — Commit Boundary (HITL — mandatory hard stop):**

> [!CAUTION]
> **HARD STOP REQUIRED:** You MUST NOT proceed to the next task batch autonomously.

- **STOP execution.**
- Inform the user:
  - "Commit boundary N of M is ready. Pre-commit passed."
  - Which tasks are included in this commit
  - Current test count
- **WAIT** for the user to commit or give explicit permission to proceed.
- Do absolutely nothing else until they respond.
- On commit confirmed: update `task.md`. Proceed to next task batch (Step A).

**After the final commit boundary:**
- Update the Progress Tracker in the Design Document:
  `Dev ✅`, `Pre-Commit ✅`, `Committed ✅` for this sub-feature.
- Update the Session Handoff paragraph in the Design Document.
- **If this was the LAST sub-feature** (every other tracker row is `Committed ✅`), the story is
  about to be declared finished — execute **Phase 4 of `specweaver-dev`'s parent,
  `specweaver-feature`** (the closure gate: `check_fr_coverage.py` + the full suite) before writing
  `Status: COMPLETE`. Do NOT declare a story finished from inside this skill without it; running
  `dev` directly is otherwise a way to close a story having never checked the design's FR ledger.

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
| **Commit Boundaries** | Hard stop at every commit. Wait for human. Do not bypass. |
| **Tests run freely** | All test/lint commands run autonomously. No exceptions. |
| **Temporary Files** | Use the project's `.tmp` directory for all temporary scripts, debug files, or scratchpads. |
