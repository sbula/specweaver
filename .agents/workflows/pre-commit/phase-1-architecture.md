---
description: "Phase 1: Architecture verification — verify layer placement, dependency direction, and archetype compliance."
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

// turbo-all

> [!IMPORTANT]
> **Autonomy vs. HITL:**
> Execute the architecture verifications autonomously, but you MUST STOP and present any findings to the user. NEVER bypass the user review of violations.


# Phase 1: Architecture Verification

1.1. Read the architecture reference in full:
     ```
     docs/architecture/architecture_reference.md
     ```

1.2. Identify ALL source files that were created or modified for this feature.

1.3. For EACH changed/new file, verify:
     - **Layer placement**: Does the file live in the correct module per the
       architecture? Check the module's `context.yaml` for `purpose` and `archetype`.
     - **Dependency direction**: Do its imports respect `consumes` and `forbids`
       rules declared in the nearest `context.yaml`?
     - **Archetype compliance**: Does the code follow the structural constraints
       of its archetype (e.g., `pure-logic` has no I/O, `adapter` wraps externals,
       `orchestrator` delegates)?
     - **No parallel mechanisms**: Does the change duplicate existing
       infrastructure (e.g., creating a new security layer when FolderGrant exists)?

1.4. **Zoom-out test** — for EACH new module, file, or capability added:
     - Does a similar capability already exist elsewhere in the codebase?
       (e.g., a "research search" function vs the existing `filesystem/` grep)
     - Would extending an existing module be a better fit than creating a new one?
     - Is the new code named by what the *agent does* ("research") rather than
       what the *code is* ("filesystem search")? If so, it likely belongs in an
       existing module.
     - Check the Feature Map in the architecture reference for precedent.

     > A feature may look correct in isolation, but the whole picture may reveal
     > a better home already exists. Always verify against the full architecture
     > before accepting new module placement.

1.5. **Acyclic Dependencies** — verify the change does NOT introduce circular
     imports between modules. Dependencies must form a DAG (directed acyclic
     graph) pointing downward. If module A imports from B, B must NEVER import
     from A (directly or transitively). Check with:
     - Follow the import chain of every new `import`/`from` statement
     - If a cycle exists, break it with an interface in a lower-level module

1.6. **Common Closure** — things that change together should live together.
     If the feature required modifying files in 3+ different modules, ask:
     - Are those changes tightly coupled? If so, should they be co-located?
     - Conversely, if one module has mixed concerns (some parts change with
       feature A, others with feature B), it may need splitting.

1.7. **Stability Direction** — depend toward stable modules, not away from them.
     - Stable modules: `config/`, `context/`, `validation/` (pure-logic, rarely change)
     - Volatile modules: `drafting/`, `review/`, `implementation/` (orchestrators, change often)
     - A stable module must NEVER depend on a volatile one
     - New code in a stable module must not introduce volatile dependencies

1.8. For EACH violation found (whether pre-existing or newly introduced):
     - **Fix it** if possible within the scope of this feature.
     - If the fix requires a separate task, **document the violation** in the
       architecture reference (`docs/architecture/architecture_reference.md`)
       under "Known Boundary Violations" with: what, where, which rule is broken.
     - **No violation may be silently skipped.** Every issue must be either
       fixed or documented — this is non-negotiable.

1.9. **DEFERRED HITL GATE:**
     - Do NOT stop immediately if architecture violations are found.
     - Instead, document the architecture findings and PROCEED to Phase 2 (Test Gap Analysis).
     - At the end of Phase 2, present a COMBINED analysis containing both the Architecture Violations and the Test Gap Analysis.
     - > [!CAUTION]
       > **FORMAT EXCEPTION:** You MUST NOT write this combined analysis into a file or system Artifact! You MUST print the full Background, Architecture Findings, Coverage Matrix, Options, Analysis, and Proposal DIRECTLY into your conversational chat response.

> [!CAUTION]
> **HARD GATE RELOCATED:** The hard stop has been moved to the end of Phase 2. You may proceed directly to Phase 2.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 1 is complete. Update `task.md`.
> The NEXT phase is Phase 2 (Code Quality Checks / Test Gap). Proceed to it immediately to gather the test gap analysis.
