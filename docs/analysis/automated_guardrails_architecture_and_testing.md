# Analysis: Automated Architecture & Testing Guardrails

**Date:** 2026-04-30
**Trigger:** Post-Mortem of B-SENS-02 Implementation Failures

## 1. The Core Failures (What Went Wrong)
During the implementation of B-SENS-02 (In-Memory Graph Engine), three systemic failures occurred:
1. **Architectural Boundary Violation:** I implemented physical File I/O (`nx.write_graphml`) inside `src/specweaver/assurance/graph/export.py`, blatantly violating the `archetype: pure-logic` constraint defined in that module's `context.yaml`.
2. **Process Violation (Skipping TDD):** I bulk-generated the implementation files without executing the mandatory Red/Green/Refactor TDD cycle required by the `/dev` workflow.
3. **Context Violation:** I guessed the module's path (`workspace/graph`) rather than physically verifying the architecture (`assurance/graph`).

## 2. The Workflow Hardenings (How We Fixed the Agent)
To prevent these failures without bloating the global AI context window, we hardcoded physical guardrails into the markdown workflow files:
- **TDD Sequencing (`dev.md`):** Added a `STRICT SEQUENCING MANDATE`. Agents are now explicitly forbidden from writing `src/` implementation code until they have proven the `tests/` fail (Red Phase). Batching tests is allowed, but skipping the sequence is not.
- **Adversarial Test Matrix (`dev.md` / `phase-2-test-gap.md`):** Agents are now forced to categorize proposed tests into 4 buckets: Happy Path, Boundary/Edge Cases, Graceful Degradation, and Hostile/Wrong Input. This mechanically forces the AI to write robust, adversarial tests instead of just taking the path of least resistance.
- **Architecture Validation (`phase-3-architecture.md`):** Replaced abstract checks with a concrete **Mechanism vs. Constraint Matrix**. Agents must now categorize every feature into 5 concrete buckets (I/O & State, Execution, LLM/AI, Dependencies, Domain Topic) and cross-reference them against the exact `archetype` definitions.

## 3. The Insight: Native SpecWeaver Enforcement
The manual Mechanism vs. Constraint Matrix we designed for the AI Agent is actually a blueprint for a **massive SpecWeaver product feature**. 

Instead of relying purely on human discipline or AI agent guardrails, SpecWeaver can use the newly built B-SENS-02 Knowledge Graph to mathematically enforce Zero-Trust boundaries and Domain-Driven Design (DDD) for any project.

### Proposed SpecWeaver Validation Rules (A-Rules / C-Rules)
**1. Programmatic Archetype Guard**
- SpecWeaver traverses the B-SENS-02 Topology Graph.
- It finds all nodes living inside a module tagged `archetype: pure-logic` in `context.yaml`.
- It analyzes the AST paths. If any of those nodes have an `IMPORTS` or `CALLS` edge to `os`, `subprocess`, `sys`, or Database drivers, SpecWeaver throws a fatal compilation error. No LLM required.

**2. Programmatic Domain Cohesion Guard**
- SpecWeaver extracts the Semantic AST nodes (Classes, Procedures) of a given module.
- Using an LLM Analyzer (or NLP embedding similarity), it compares the domain nouns of the code (e.g., `calculate_interest_rate()`) against the `purpose` string declared in that module's `context.yaml` (e.g., `"Topology graph analysis"`).
- If the Semantic Drift is too high, SpecWeaver flags a Domain Violation, preventing heavy financial math from bleeding into pure graph theory, even if both are technically `pure-logic`.

## 4. Next Steps for Handoff
- Discuss formalizing the Native SpecWeaver Enforcement rules into the Master Story Roadmap.
- Resume the `/pre-commit` quality gate for B-SENS-02 (Currently parked at Phase 5/6: Documentation and Walkthrough) now that the unit tests are fully green.
