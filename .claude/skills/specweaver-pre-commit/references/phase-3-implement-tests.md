---
description: "Phase 3: Implement missing tests identified in Phase 2."
---

# Phase 3: Implement Missing Tests

> [!CAUTION]
> **ANTI-LAZINESS DIRECTIVE: DO NOT SKIP THIS PHASE!**
> AI agents have a known failure mode of skipping Phase 3 and assuming existing tests or minimal happy-path tests are "good enough." 
> THIS IS STRICTLY FORBIDDEN.
> You MUST explicitly write tests for EVERY SINGLE:
> 1. Error path (e.g. ValueError, None inputs, empty strings)
> 2. Boundary condition (e.g. casing differences like "PYTHON" vs "python")
> 3. Negative branch (e.g. missing fields, malformed inputs)
> 
> **If you did not write a new test for every single branch you touched, STOP and write it now.**

3.1. You MUST implement ALL missing tests identified in Phase 2 (after HITL confirmation).
     Follow existing test patterns (fixtures, helpers, naming conventions)
     already established in the test files.
3.1b **MANDATORY HITL YIELD**: Instead of proceeding directly to Phase 4, you MUST explicitly list
exactly which edge cases you just implemented tests for and YIELD YOUR TURN. A yield means making
ZERO further tool calls. You must end your response and wait for the user to type a reply explicitly
approving the tests before you can start Phase 4.
3.2. Run lint on any new or modified test files to ensure lint-clean:
     ```
     python scripts/quality.py quick --only ruff
     ```
     Fix any errors immediately!

     This covers `src/`, `tests/` and `scripts/` in one pass — a test file that lints clean while
     the module it exercises does not is not a state worth reporting. The full gate runs in
     Phase 5; this is the fast subset for the loop you are in.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 3 ends at the §3.1b yield, not here. Update `task.md`, present exactly which
> edge cases you covered — or state plainly that no branch was touched and none were needed — and
> wait. Phase 4 begins on the user's reply.
>
> This note used to read *"NO HITL GATE HERE, proceed immediately"*, contradicting §3.1b four lines
> above it and `SKILL.md`, which names Phases 1, 2 and 3 as gated. An instruction that argues with
> itself is obeyed selectively, which is the same as not existing.
