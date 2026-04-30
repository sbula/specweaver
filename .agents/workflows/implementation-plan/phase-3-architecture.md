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

3.1. **Mechanism vs. Constraint Matrix (MANDATORY)**:
     For every new feature or module proposed in the plan, you MUST explicitly extract the technical mechanisms it requires, and map them against the target module's `context.yaml` constraints (`archetype` and `forbids`). 
     
     You MUST analyze every mechanism across these 5 categories:
     - **I/O & State**: Reading/writing files, SQLite access, network requests, environment variables, global state.
     - **Execution**: Running shell commands, using git, invoking subprocesses.
     - **LLM/AI**: API calls to LLMs, prompt generation, parsing LLM output.
     - **Dependencies**: Importing from other modules (e.g., `loom/`, `cli/`).
     - **Domain Topic (Semantic Cohesion)**: The core subject matter of the computation (e.g., Graph Topology vs. Financial Math).
     
     For every mechanism identified, check the `context.yaml` and `architecture_reference.md` definitions for the target module:
     - If the module is `pure-logic`, it strictly forbids ALL I/O, Execution, and State mechanisms.
     - If the module `forbids: [specweaver/loom/*]`, it strictly forbids Execution.
     - If the module `forbids: [specweaver/llm]`, it strictly forbids LLM/AI.
     - **Domain Check**: Verify the feature's domain topic strictly matches the `purpose` declared in `context.yaml`. Do NOT mix distinct domains (e.g., financial math inside a graph topology module), even if both are `pure-logic`.
     
     If a mechanism conflicts with the constraints, it is a CRITICAL violation. The proposed location MUST be rejected, or the design refactored (e.g. by extracting the violating I/O mechanism into an `adapter` and returning pure payloads).

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
