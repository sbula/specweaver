---
description: "Phase 3: Feature Detail — define FRs/NFRs, validate external APIs, and verify architectural alignment. HITL gates fire on gaps, incompatibilities, or any Architectural Switch."
---

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Derive and validate autonomously. Three categories of HITL gate:
> - Vague or missing requirements (after exhausting research)
> - API incompatibility or version conflict
> - Any Architectural Switch (hard stop, no exceptions)

// turbo-all

# Phase 3: Feature Detail

---

## Section A — Functional Requirements

A.1. Using the working definition (Phase 1) and research brief (Phase 2),
     derive every Functional Requirement for this feature.

     Each FR MUST be:
     - **Numbered**: `FR-1`, `FR-2`, ...
     - **Unambiguous**: exactly one valid interpretation
     - **Testable**: a test can pass or fail based on this FR
     - **Structured**: Actor + Action + Outcome
       Example: "The system SHALL record model_id, prompt_tokens, and completion_tokens
       for every LLM call and persist them to the telemetry DB."

A.2. Review each FR for vagueness:
     - Does it use words like "fast", "good", "some", "various", "appropriate"? → vague.
     - Does it have multiple interpretations? → vague.
     - Could you write a test for it? If no → too vague.

A.3. **HITL gate** (fires for each vague FR after exhausting research):
     Present the specific FR and the gap.
     Ask ONE targeted clarifying question.
     **STOP. Wait. Do NOT proceed with a vague requirement.**

---

## Section B — Non-Functional Requirements

B.1. List all NFRs. Each must have a concrete threshold where applicable:
     - **Performance**: latency budgets, throughput targets, memory limits
     - **Security**: authentication, authorization, input validation, data exposure
     - **Compatibility**: Python version, OS, existing DB schema, existing CLI contracts
     - **Observability**: logging requirements, error reporting, telemetry
     - **Error handling**: behavior on failure, retry policy, fallback behavior
     - **Data migration**: backward compat, migration strategy, rollback plan

B.2. **HITL gate** (fires if a critical NFR threshold is unknown):
     "Critical" means: security risk, data loss risk, or backward compatibility break.
     Ask for the specific threshold.
     **STOP. Wait.**

---

## Section C — External API & Tool Validation

C.1. For each external tool identified in Phase 2:
     a. Check `pyproject.toml` for the currently declared version.
     b. Verify the specific API surface this feature needs is stable:
        not `@experimental`, not `@deprecated`, not removed at the target version.
     c. Record: `Tool | Min Version | API Surface | Stable (Y/N) | Notes`

C.2. **HITL gate (hard stop)** — if any incompatibility is found:
     - Identify the tool, the needed API, and the conflict precisely.
     - Present at least 2 concrete options (upgrade, alternative tool, different approach).
     - **STOP. Wait for the user's decision.**
     - Do NOT proceed past a broken dependency.

---

## Section D — Architectural Alignment

D.1. For each change the feature requires (new file, modified module, new dependency,
     new DB table, new pipeline step, new CLI command):
     - Map it to the architecture reference module map.
     - Verify it fits in an existing module, or justify why a new module is needed.
     - Verify it respects `consumes`/`forbids` rules in the target module's `context.yaml`.
     - Verify it follows the archetype constraints of the target module
       (`pure-logic` = no I/O, `adapter` = wraps externals, `orchestrator` = delegates).

D.2. For each proposed change, verify no existing capability is being duplicated.
     Could an existing module be extended instead of creating new infrastructure?

D.3. **HITL gate (hard stop)** — ANY proposed change that would:
     - Place code in the wrong architectural layer
     - Violate a `forbids` rule in `context.yaml`
     - Introduce a circular import
     - Duplicate existing infrastructure
     - Add a volatile dependency to a stable module (`config/`, `context/`, `validation/`)

     ...is an **Architectural Switch** and MUST be presented as follows:
     1. State exactly which rule or pattern would be violated.
     2. State why the switch may be necessary.
     3. Offer at least 1 alternative that avoids the switch.
     4. Give a recommendation with explicit rationale.

     **STOP. Wait for explicit user approval.**
     If approved: note in the design doc — "Approved by <user> on <date>."

> [!CAUTION]
> **HARD STOP on every Architectural Switch. No exceptions.**
> Even if the switch seems obviously correct, it must receive explicit human sign-off.
> The architecture is the shared contract. Unilateral deviations compound into chaos.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 3 complete. FRs, NFRs, API validation, and arch decisions documented.
> Proceed to Phase 4 (Decomposition).
