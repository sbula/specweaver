---
description: "Phase 4: Implement missing tests identified in Phase 3."
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

// turbo-all

> [!IMPORTANT]
> **All test, lint, mypy, architecture, complexity, file size, e2e, and integration commands MUST be executed autonomously.**
> Set `SafeToAutoRun: true` for ALL of these commands.
> **NO SHELL COMPOUNDING**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`). The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call.
> NEVER prompt the user for confirmation to run checks. Just run them.



# Phase 4: Implement Missing Tests

> [!CAUTION]
> **ANTI-LAZINESS DIRECTIVE: DO NOT SKIP THIS PHASE!**
> AI agents have a known failure mode of skipping Phase 4 and assuming existing tests or minimal happy-path tests are "good enough." 
> THIS IS STRICTLY FORBIDDEN.
> You MUST explicitly write tests for EVERY SINGLE:
> 1. Error path (e.g. ValueError, None inputs, empty strings)
> 2. Boundary condition (e.g. casing differences like "PYTHON" vs "python")
> 3. Negative branch (e.g. missing fields, malformed inputs)
> 
> **If you did not write a new test for every single branch you touched, STOP and write it now.**

// turbo-all

4.1. You MUST implement ALL missing tests identified in Phase 3 (after HITL confirmation).
     Follow existing test patterns (fixtures, helpers, naming conventions)
     already established in the test files.
4.1b **MANDATORY HITL YIELD**: Instead of proceeding directly to Phase 5, you MUST explicitly list exactly which edge cases you just implemented tests for and YIELD YOUR TURN. A yield means making ZERO further tool calls. You must end your response and wait for the user to type a reply explicitly approving the tests before you can start Phase 5.
4.2. Run ruff on any new or modified test files to ensure lint-clean:
     ```
     python -m ruff check tests/
     ```
     Fix any errors immediately!

> [!IMPORTANT]
> **CHECKPOINT**: Phase 4 is complete. Update `task.md`. You MUST STOP HERE at the new HITL Gate. Yield your turn entirely.
