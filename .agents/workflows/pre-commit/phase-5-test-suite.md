---
description: "Phase 5: Run the full test suite — all tests must pass."
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

// turbo-all

> [!IMPORTANT]
> **All test, lint, mypy, architecture, complexity, file size, e2e, and integration commands MUST be executed autonomously.**
> Set `SafeToAutoRun: true` for ALL of these commands.
> **NO SHELL COMPOUNDING**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`). The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call.
> NEVER prompt the user for confirmation to run checks. Just run them.



# Phase 5: Run Full Test Suite

// turbo-all

> [!CAUTION]
> You MUST run the tests in the exact order below.
> Do NOT proceed to the next test level if there are ANY failures in the current level.
> Fix all failures before advancing to the next command. All commands must be run autonomously.

5.1. Run **Unit** Tests:
     ```
     python run_unit_tests.py
     ```

5.2. Run **Integration** Tests:
     ```
     python run_integ_tests.py
     ```

5.3. Run **End-to-End (E2E)** Tests:
     ```
     python run_e2e_tests.py
     ```

> [!IMPORTANT]
> **NO HITL GATE HERE:** If the entire test sequence passes successfully, update `task.md` and PROCEED IMMEDIATELY to Phase 6. Do NOT stop to ask the user for permission to continue.
