---
description: "Phase 4: Implement missing tests identified in Phase 3."
---
// turbo-all

> [!IMPORTANT]
> **All test, lint, mypy, architecture, complexity, file size, e2e, and integration commands MUST be executed autonomously.**
> Set \SafeToAutoRun: true\ for ALL of these commands.
> NEVER prompt the user for confirmation to run checks. Just run them.



# Phase 4: Implement Missing Tests

// turbo-all

4.1. Implement ALL missing tests identified in Phase 3 (after HITL confirmation).
     Follow existing test patterns (fixtures, helpers, naming conventions)
     already established in the test files.
4.2. Run ruff on any new or modified test files to ensure lint-clean:
     ```
     python -m ruff check tests/
     ```
     Fix any errors immediately!

> [!IMPORTANT]
> **NO HITL GATE HERE:** Once tests are implemented and lint-clean, update `task.md` and PROCEED IMMEDIATELY to Phase 5. Do NOT stop to ask the user for permission to continue.
