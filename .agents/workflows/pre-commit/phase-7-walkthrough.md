---
description: "Phase 7: Write a walkthrough artifact documenting changes, tests, and HITL gate decisions."
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

// turbo-all

> [!IMPORTANT]
> **All test, lint, mypy, architecture, complexity, file size, e2e, and integration commands MUST be executed autonomously.**
> Set `SafeToAutoRun: true` for ALL of these commands.
> **NO SHELL COMPOUNDING**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`). The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call.
> NEVER prompt the user for confirmation to run checks. Just run them.



# Phase 7: Walkthrough

7.1. Write or update the walkthrough artifact documenting:
     - What was changed and why
     - All test results
     - **HITL gate decisions**: For EVERY HITL gate (steps 1.8 and 3.9),
       document what was found, the reasoning presented to the user,
       and the user's decision. If a gate was skipped or auto-approved,
       document the justification and flag it so the user can
       retroactively review the decision.

> [!WARNING]
> The walkthrough MUST transparently document all HITL gate interactions.
> If a gate was bypassed, explain why and what the user should review.
