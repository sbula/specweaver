---
description: "Phase 7: Write the walkthrough documenting changes, tests, the combined analysis and every stop."
---

# Phase 7: Walkthrough

7.1. Write or update the walkthrough — `<ID>_<boundary>_walkthrough.md` beside the design, or the
     commit message when the work has no design — documenting:
     - What was changed and why
     - All test results (exact counts: unit, integration, e2e, grand total)
     - All lint, mypy, complexity, and architecture check results
     - **The combined analysis** from §2.8 and the edge cases from §3.1b
     - **Decisions:** for every point where the gate stopped for the user (§1.9, §2.8, §7.5.2),
       what was found, the reasoning presented, and the user's decision. Where a finding was
       fixed or accepted without a stop, say so, so the user can review it afterwards.

> [!WARNING]
> The walkthrough MUST transparently document every decision the gate took.
> If a finding was accepted without the user, explain why and what the user should review.
