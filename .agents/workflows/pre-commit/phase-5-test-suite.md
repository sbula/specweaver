---
description: "Phase 5: Run the full test suite — all tests must pass."
---
// turbo-all

> [!IMPORTANT]
> **All test, lint, mypy, architecture, complexity, file size, e2e, and integration commands MUST be executed autonomously.**
> Set \SafeToAutoRun: true\ for ALL of these commands.
> NEVER prompt the user for confirmation to run checks. Just run them.



# Phase 5: Run Full Test Suite

// turbo-all

5.1. Run the full test suite:
     ```
     python -m pytest --tb=short -q
     ```
     ALL tests MUST pass — no exceptions!

> [!IMPORTANT]
> **NO HITL GATE HERE:** If the entire test suite passes successfully, update `task.md` and PROCEED IMMEDIATELY to Phase 6. Do NOT stop to ask the user for permission to continue.
