---
description: "Phase 3: Architecture Verification — verify layer placement, dependency direction, and archetype compliance for every proposed change. No HITL. Feeds Phase 4."
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

> [!IMPORTANT]
> **This phase is fully autonomous. No HITL.**
> All violations discovered here are appended to the Phase 2 audit list
> as CRITICAL items and presented together in Phase 4.

// turbo-all

# Phase 3: Architecture Verification

3.1. For EACH new or modified module proposed in the plan, verify:
     - **Layer placement**: Does the proposed file live in the correct module per the
       architecture? Check the target module's `context.yaml` for `purpose` and `archetype`.
     - **Dependency direction**: Do the proposed imports respect `consumes` and `forbids`
       rules declared in the nearest `context.yaml`?
     - **Archetype compliance**: Does the proposed code follow the structural constraints
       of its archetype (e.g., `pure-logic` has no I/O, `adapter` wraps externals,
       `orchestrator` delegates)?
     - **No parallel mechanisms**: Does the plan duplicate existing infrastructure
       (e.g., creating a new security layer when FolderGrant exists)?

3.2. **Zoom-out test** — for EACH new module, file, or capability proposed:
     - Does a similar capability already exist elsewhere in the codebase?
     - Would extending an existing module be a better fit than creating a new one?
     - Is the proposed code named by what the *agent does* rather than what the
       *code is*? If so, flag it — it likely belongs in an existing module.
     - Check the Feature Map in the architecture reference for precedent.

3.3. **Acyclic Dependencies** — verify the proposed changes do NOT introduce
     circular imports. Dependencies must form a DAG pointing downward.
     Trace the full import chain for any cross-module references,
     distinguishing module-level imports from lazy (in-function) imports.

3.4. **Common Closure** — if the plan modifies 3+ different modules for a single
     feature, ask: are those changes tightly coupled and should they be co-located?

3.5. **Stability Direction** — verify the plan does not add volatile dependencies
     to stable modules (`config/`, `context/`, `validation/`).

3.6. Flag every architectural violation as a **CRITICAL** audit question.
     Append to the list from Phase 2. Each entry MUST include:
     - What rule is broken
     - Which file/module is affected
     - A concrete fix recommendation

> [!IMPORTANT]
> **CHECKPOINT:** Phase 3 complete. All violations appended to audit list as CRITICAL items.
> Proceed to Phase 4 (Merge Findings — HITL).
