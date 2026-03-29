---
description: "Phase 4: Merge Findings — present the full combined audit list to HITL, then merge resolved findings into the plan."
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Presenting the findings is MANDATORY. This gate ALWAYS fires.
> Do NOT start merging until the user has responded to the findings.

// turbo-all

# Phase 4: Merge Findings

---

## HITL Gate (Mandatory — Always Fires)

4.1. Combine all findings from Phase 2 (audit questions) and Phase 3 (architectural
     violations) into a single ranked list:
     - CRITICAL items first (architectural violations belong here)
     - Then HIGH, MEDIUM, LOW
     - Within each severity: sort by impact (broadest impact first)

4.2. Present the full list to the user.
     **STOP. Wait for the user to respond.**
     Do NOT summarize, filter, or omit items. Present ALL of them.
     Do NOT answer questions on behalf of the user. Wait for their input.

---

## Merge Resolved Findings (after user response)

4.3. After the user has reviewed, answered, or accepted the findings:

     - **Findings that changed the design** → update the relevant plan sections.
     - **Findings that are implementation caveats** → add as inline `[!CAUTION]`,
       `[!WARNING]`, or `[!NOTE]` alerts next to the relevant code or section.
     - **Findings that are deferred** → add to the Backlog section at the end of the plan.
     - **Findings that are rejected or not applicable** → discard silently.

4.4. **Do NOT create a separate audit report.**
     The implementation plan is the single self-contained document.
     Another agent in a fresh session must be able to implement it without any
     other document, conversation, or external context.

4.5. Present the updated plan sections to the user for a quick review before Phase 5.

> [!CAUTION]
> **HARD GATE:** Do NOT proceed to Phase 5 until the user has explicitly
> reviewed the findings and you have merged the resolved ones.
> Skipping this gate produces an incomplete, unreviewed plan.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 4 complete. Findings merged into plan.
> Proceed to Phase 5 (Final Consistency Check).
