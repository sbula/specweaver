---
description: "Phase 4: Run the test tiers this story requires at this commit point. Report exact counts."
---

# Phase 4: Run the Test Gate

> [!CAUTION]
> **STRICT ANTI-CACHING RULE:** You MUST physically execute the command below right now. NEVER
> assume tests pass because you ran `pytest` five minutes ago. You are in a strict pre-commit
> gate, and the laws of the gate require a fresh run.

4.1. Run the test gate for the commit point you are at and the story you are on:

     ```
     python scripts/tests.py cb <STORY-ID>        # a commit boundary (CB-N)
     python scripts/tests.py sf <STORY-ID>        # the sub-feature (SF-N) is complete
     python scripts/tests.py feature <STORY-ID>   # the feature / story is closing
     ```

     A **TECH ticket must also declare its kind**, because the four kinds need different proof:

     ```
     python scripts/tests.py cb TECH-020 --kind refactor
     ```

     `refactor` · `bugfix` · `tooling` · `audit`.

     This replaces the three unconditional `pytest tests/unit|integration|e2e` invocations that
     used to be this phase. **Which tiers run, and over how much code, is not your choice** — it
     is decided by the story's type and DAL:

     - **Capability stories** (`C-FLOW-12`) are unit-led; integration and e2e arrive at `sf` and
       `feature`.
     - **A (sub)story's spanning tests** run at integration and e2e tier only, from the first
       commit. `ADR-005` puts them in the (sub)story itself, so they arrive with its work rather
       than in a separate entry. If you find yourself wanting a unit test to stand in for one,
       that is not a coverage gap to fill here: it is the signal that the capability underneath
       shipped incomplete, and it belongs upstream as its own story.
     - **DAL shifts the whole profile.** DAL-A runs every tier at full scope from `cb`; DAL-B one
       state earlier than baseline; DAL-D/E later. A spanning test inherits the **most critical**
       DAL among the capabilities it crosses — and note the direction: DAL-A is Mission-Critical,
       DAL-E is Prototyping, so "most critical" is the *lowest* letter.

     `python scripts/tests.py matrix` prints every profile.

> [!IMPORTANT]
> **Widening is allowed; narrowing never is.** `--also integration` or `--all` may add tiers when
> you have reason to want more. There is no flag that removes one. If a run feels too slow, that
> is the profile telling you what this story costs — not a setting to turn down.

4.2. **A tier that selects ZERO tests is a FAILURE, not a pass.** If the gate reports
     `selected NO tests`, you changed source that nothing mirrors. That is missing coverage: go
     back to Phase 2/3 and write the test, do not work around the scope.

4.3. **For `--kind refactor`, the gate also asserts that you did not modify any test file.** A
     refactor's entire claim is that behaviour did not change, and the proof is that the existing
     tests pass *unmodified*. If it blocks, either the behaviour genuinely moved — in which case
     it is not a refactor and must be reclassified — or the tests were bent to fit, which is worse.

4.4. **MANDATORY REPORTING**: After the gate passes, report the **exact numbers** per tier that
     ran, taken from the actual pytest output and never estimated:
     - Tier, scope, and tests passed for each tier the gate selected
     - **Grand total: X tests passed**
     - The story's resolved DAL and where it came from (the gate prints this)

> [!IMPORTANT]
> **NO HITL GATE HERE:** If the test gate passes, update `task.md` and PROCEED IMMEDIATELY to Phase 5. Do NOT stop to ask the user for permission to continue.
