---
description: "Phase 4: Decompose — split the feature into self-contained, agent-sized sub-features and build a dependency graph. Fully autonomous, no HITL."
---

> [!CAUTION]
> **NO SHELL COMPOUNDING & NO PIPES**: You are strictly forbidden from combining commands using shell operators (`&&`, `||`, `;`, `|`, `>`) or using inline scripts like `python -c`. The secure sandbox blocks these and demands HITL approval. Execute EACH command as a SEPARATE `run_command` tool call or write a `.py` script and run it.

> [!IMPORTANT]
> **This phase is fully autonomous. No HITL.**
> Apply the rules consistently. Document your reasoning.

// turbo-all

# Phase 4: Decompose

---

## Step 1 — Decomposition Decision

4.1. Assess the total scope using the FRs from Phase 3.
     Decompose if ANY of the following are true:
     - More than 5 Functional Requirements
     - Changes touch more than 3 distinct modules
     - More than 1 external integration (library, API, service)
     - Two or more independent capability areas that could be developed separately

     If NONE are true → mark as a **single self-contained feature** (no sub-feature split).
     Skip to Step 4 to produce single-SF documentation and proceed to Phase 5.

---

## Step 2 — Sub-Feature Rules

Each sub-feature MUST satisfy ALL of the following:

4.2. **Distinct scope**: a named capability area with its own FR subset.
     No FR is shared between two sub-features. Every FR belongs to exactly one SF.

4.3. **Self-contained**: can be implemented and tested independently.
     It does not require a sibling SF to be fully complete in order to build or test it,
     unless that dependency is explicitly declared.

4.4. **Defined interface**: has explicit inputs and outputs.
     - Inputs: what it receives from prior SFs, the CLI, the DB, files, or the environment.
     - Outputs: what it produces for later SFs, the system, or the user.

4.5. **Agent-sized**: can be handled by one agent in one session.
     Heuristic: ≤ 5 FRs, ≤ 3 modules, ≤ 1 external integration.
     If a candidate SF exceeds this — split it further and re-apply this rule.

---

## Step 3 — Dependency Graph

4.6. For each sub-feature, declare one of:
     - `depends_on: none` — can start as soon as design is approved
     - `depends_on: [SF-N]` — requires SF-N to be fully committed first
     - `depends_on: [SF-N, SF-M]` — requires multiple SFs committed first

4.7. Verify the dependency graph is acyclic (a DAG).
     If a cycle exists: restructure the SFs to break it.
     A dependency cycle means the decomposition is wrong — the SFs are too tightly coupled.

4.8. Derive the topological execution order (a valid build order).
     Identify which SFs have no shared or transitive dependencies — these can run
     in parallel sessions.

---

## Step 4 — Coverage Check

4.9. Verify: union of all sub-feature FR subsets = 100% of top-level FRs.
     Every FR must appear in exactly one sub-feature.
     If an FR is uncovered: assign it to the most logical SF and justify why.

> [!IMPORTANT]
> **CHECKPOINT:** Phase 4 complete.
> Sub-feature breakdown, dependency graph, and execution order are ready.
> Proceed to Phase 5 (Document).
