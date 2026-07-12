---
description: "Phase 4: Run the full test suite — all tests must pass. Report exact counts."
---

# Phase 4: Run Full Test Suite

> [!CAUTION]
> You MUST run the tests in the exact order below.
> Do NOT proceed to the next test level if there are ANY failures in the current level.
> Fix all failures before advancing to the next command. All commands must be run autonomously.
> 
> **STRICT ANTI-CACHING RULE:** You MUST physically execute every single one of these `run_command` tools right now. NEVER assume tests pass because you ran `pytest` five minutes ago. You are in a strict pre-commit gate, and the laws of the gate require a fresh run.

4.1. Run **Unit** Tests:
     ```
     python -m pytest tests/unit/
     ```

4.2. Run **Integration** Tests:
     ```
     python -m pytest tests/integration/
     ```

4.3. Run **End-to-End (E2E)** Tests:
     ```
     python -m pytest tests/e2e/
     ```

4.4. **MANDATORY REPORTING**: After all test suites pass, report the **exact numbers**:
     - Total unit tests passed: X
     - Total integration tests passed: X
     - Total e2e tests passed: X
     - **Grand total: X tests passed**
     These numbers MUST be extracted from the actual pytest output, not estimated.

> [!IMPORTANT]
> **NO HITL GATE HERE:** If the entire test sequence passes successfully, update `task.md` and PROCEED IMMEDIATELY to Phase 5. Do NOT stop to ask the user for permission to continue.
