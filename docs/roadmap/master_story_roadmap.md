# Master User Story Roadmap

This is the unified, single-numbering format (US-1 to US-18) covering the entire lifespan of the platform.

Each story's own paths and seams are in `stories/US-NN.md`. `ADR-005`: integration is implicit
there — a path a story cannot walk with one feature is a seam FR of the story, its test written red
first. There is no separate integration entry, and no `INT-US` identifier is ever minted again.

### Story Status Flags
*   🟢 **Completed** (For Base: Core MVS is 100% delivered. For Sub-Story: Feature is 100% delivered)
*   🟡 **In Progress** (Some requirements are checked, but not all)
*   🔴 **Pending** (Zero requirements have been checked)
*   🔵 **On Hold** (Visionary, blocked, or parked)

Following the **"Good Enough" principle**, every User Story is strictly divided into:
1. **Core Required (MVS):** The absolute minimum required to achieve the user benefit.
1. **Sub-Story Add-Ons:** Optional, self-contained enhancements that group technical features into deliverable improvements.

---

## 🎯 Active Routing Queue
> **Markers.** `✅` delivered and approved · `🔧` built and proven, **approval outstanding**
> · `[ ]` not started. `🔧` is not a softer `✅`: it means the code and its evidence exist
> and the `specweaver-design` Phase 6 gate has not been run.

*The engineering team must select ONE of the following candidates as the next primary objective. Do not start a new candidate until the current one is `🟢 Completed`.*

> [!CAUTION]
> **Nothing in this queue is the next thing to do.** Six capabilities are `🔧` — built, proven, and
> never approved — and two of them are known wrong. Finish those first. They are listed in
> `.agents/STATE.md`, which is the file to read before this one.
>
> This queue ranks what to start **after** that. `C-FLOW-11` used to head it and has since been
> built; it is not a candidate any more.

1. **Kernel-Enforced Resource Bounds (`B-EXEC-04`)** ← SECURITY MANDATE
   * **Features:** `B-EXEC-04` — cgroups v2 `pids.max` scoped to a process subtree. Prereqs: none.
     Details: [topic_06](topics/topic_06_sandbox.md).
   * **Pros:** `C-EXEC-02` FR-11 promises a fork-bombing script is capped, and today that promise
     rests on a best-effort `RLIMIT_NPROC` backstop which is per-real-UID and therefore bounds the
     machine's user rather than the sandbox. Two sampling-based repairs were tried and measured to
     fail. This is the mechanism that can hold, and it **removes** the backstop.
   * **Cons:** Linux-only, needs a real cgroups v2 delegation story, no epic unlock.
   * **ROI:** **Risk-driven** — an unmet FR on the untrusted-execution path, with the replacement
     already named in the design and in `CLAUDE.md`.
2. **DAL-Escalated Isolation for Pipeline Runs (`C-EXEC-07`)** ← DAL PARITY
   * **Features:** `C-EXEC-07` (pipeline-aware allow-list derivation + dual-fan-out-in-worktree +
     `sw run`/`sw resume` escalation wiring), integration implicit per `ADR-005`. Prereqs: `C-EXEC-06` ✅.
     Details: [topic_06](topics/topic_06_sandbox.md) / [US-09.md](stories/US-09.md).
   * **Pros:** Closes the asymmetry the PO question exposed: the tool's most untrusted execution
     surface (LLM-derived scenario tests over LLM-generated code, now LIVE via
     `sw run scenario_integration`) has the weakest default.
   * **Cons:** Engine work; no epic unlock; allow-list derivation for arbitrary pipelines is the hard part.
   * **ROI:** **Medium** — security parity plus workspace hygiene; cheapest while the run-journey
     context from `INT-US-24` is still fresh, and it batches with the same high-criticality modules.
3. **Multi-Stage Reviews (`E-VAL-04`)** ← CHEAPEST BITE
   * **Features:** `E-VAL-04` — configurable multi-stage review pipeline, designed rubric-first on
     `C-VAL-05` 🔧. Prereqs: `E-VAL-02` ✅, `B-VAL-02` ✅, and `C-VAL-05` **approved**.
     Details: [topic_05](topics/topic_05_validation.md).
   * **Pros:** A stage becomes a rubric file plus a `load_rubric` call rather than a rule class.
   * **Cons:** Blocked until `C-VAL-05` is approved, which is a set-back item. Smallest strategic payoff.
   * **ROI:** **Medium-high** — least effort per unit of capability, and it is the test of whether
     `C-VAL-05`'s substrate actually pays out before `B-VAL-03` and `B-INTL-08` bet on it.

### 🔭 Focus Points

*Two standing lenses, orthogonal to the queue above. The queue ranks by strategic unlock; these
rank by proximity to a closed story. A capability can appear in both.*

**Focus 1 — `US-11` (GraphRAG for Brownfield Scale) and its add-ons.**

Core MVS is **one capability from 🟢**: `B-SENS-03` 🔧 shipped the chunking half, and `A-SENS-02`
(Postgres Apache AGE + pgvector sidecar) is all that remains. It is the highest-leverage single
item on the board — it also closes `US-12`'s *Massive Scale Context Retrieval* and `US-19`'s
*Distributed Topology Scaling*, so **one capability moves three stories**. It has no design
document yet, and it is infrastructure work rather than a pure-logic module, so it is high value
and *not* cheap; it belongs to this focus rather than to Focus 2.

The add-on groups behind it, nearest first:

| Group | Open | Note |
|---|---|---|
| 🟡 Infinite Scale Management | `A-FLOW-02`, `A-INTL-04` | `A-SENS-01` ✅ already landed; two items from 🟢 |
| 🔴 Cross-Language Dependency Resolution | `B-SENS-07` | single item |
| 🔴 Microservice Federation | `A-SENS-04` | single item |
| 🔴 Dynamic Knowledge Relevance | `B-FLOW-04`, `A-SENS-03` | retrieval scoring; wants `A-SENS-02` first |
| 🔴 Static Code Flow Analysis | `B-SENS-04`, `B-SENS-05` | statically-typed languages only, by design |

**Focus 2 — the 🟡 harvest: stories one capability from green.**

Measured against the ledger, **thirteen 🟡 stories have exactly one open item in their Core MVS**.
Each is a whole user story that turns 🟢 for one capability, which is the cheapest kind of progress
this roadmap can buy.

| Story | Sole open item | Why it is close |
|---|---|---|
| `US-6` | `D-UI-01` | **Already in progress** — TDD phases 1–3 done, 57 API tests. Nearest thing on the board to finished, and it is also half of `US-7` |
| `US-20` | `B-VAL-05` | A battery rule over DAL boundaries; both the battery and the DAL machinery already exist |
| `US-14` | `A-INTL-01` | Adversarial spec review — a rubric plus a review stage now that `C-VAL-05` 🔧 ships the substrate |
| `US-10` | `C-UI-01` | Pipeline visualiser on the delivered dashboard; also closes `US-20`'s *DAG Visualization* |
| `US-15` | `C-UI-02` | Traceability matrix UX over `C-VAL-04` ✅ |
| `US-8` | `D-INTL-04` | Design questionnaire; has an architecture document already |
| `US-11` | `A-SENS-02` | See Focus 1 — highest leverage, lowest cheapness |
| `US-12` | `C-INTL-03` | Reverse-weaving (`sw capture`) |
| `US-13` | `A-VAL-02` | Symbolic maths validation; needs a solver, so cheap it is not |
| `US-17` | `B-VAL-04` | SWE-Bench QA gates |
| `US-19` | `C-FLOW-04` | Work packet bundling |
| `US-26` | `B-SENS-06` | OSV vulnerability feed ingestion |
| `US-27` | `A-SENS-05` | APM telemetry ingestion (Sentry/Datadog) |

`US-7` is the near miss: two items (`D-UI-01`, `D-UI-03`), and `D-UI-01` is the same in-progress
capability that closes `US-6`.

**If the aim is stories closed per unit of effort, `D-UI-01` first, then `B-VAL-05` and
`A-INTL-01`.** If the aim is capability reach, `A-SENS-02`.

### 🔧 Debt Sequencing

*Nothing open. All 64 `TECH` tickets are delivered, each with its FRs cited and behind a killed
mutant. Full record: [topic_07](topics/topic_07_technical_debt.md) and the [TECH ledger](#-technical-debt-tech).*

*This table ranked open debt by what it invalidated. It stays, empty, because the next ticket needs
somewhere to go — and because an empty ranking is a fact worth being able to read, where a deleted
section would only be an absence.*

### 📋 Routing Selection Matrix
A story only enters the Active Routing Queue if it satisfies one of these rules:
1. **The Prove It Rule:** Directly contributes to achieving Success Criteria #1 through #6.
2. **The Hard Blocker Rule:** If a feature requires a dependency, the dependency evicts it from the queue.
3. **The Security Mandate:** Mitigating critical threats (e.g. Sandbox Escape) preempts UX work.
4. **The DAL Batching Rule:** Batching features that touch the same high-criticality modules to prevent paying the integration cost twice.

---

## Success Criteria

**The platform is PROVEN when you can:**
1. ✅ sw init my-app --path . registers and scaffolds the project
2. ✅ sw check some_spec.md reports PASS/FAIL with findings
3. ✅ sw draft greet_service produces a real spec via HITL interaction
4. ✅ sw implement greet_service_spec.md generates code + tests
5. ✅ sw check --level code greet_service.py checks syntax, tests, coverage
6. ✅ sw review code greet_service.py provides LLM semantic judgment

**The platform is ENTERPRISE-READY when additionally:**
7. ✅ You've used it on SpecWeaver itself (dogfooding)
8. 🔜 You've used it to build an external proprietary trading system (US-18)
9. ✅ Features can be added without restructuring (interface extensibility confirmed)
10. 🔜 Topology-aware spec authoring catches cross-service issues before code generation (US-19)
11. ✅ Multi-project management: sw projects, sw use, sw remove, sw update, sw scan

---

### 🟢 US-1: The Validation Engine
*   **User Benefit:** I can write a spec in Markdown and mathematically prove its structural quality before writing any code.
*   **Core Required (MVS):**
    *   `✅` **US-5 Core** *(provides AST extraction for C13 drift rules)*
    *   `✅` **E-UI-01:** CLI Scaffold
    *   `✅` **E-SENS-01:** Loom Filesystem Tools
    *   `✅` **E-VAL-01:** Validation Engine (Foundation)
    *   `✅` **E-INTL-01:** LLM Adapter (Gemini)
*   **Sub-Story Add-Ons:**
    *   🟡 **Security Defenses:**
        *   `🔧` **E-VAL-03:** AST Prompt Injection Sanitization
    *   🟡 **Enforce Internal Architecture:**
        *   `✅` **C-EXEC-01:** Internal Layer Enforcement
        *   `✅` **C-EXEC-03:** Domain-Driven Module Consolidation
        *   `[ ]` **E-UI-04:** CLI Command Arch Separation (Discovery vs Validation)
    *   🟡 **Configurable Multi-Stage Reviews:**
        *   `✅` **E-VAL-02:** Auto-discover Standards
        *   `[ ]` **E-VAL-04:** Multi-stage Reviews
        *   `✅` **B-VAL-02:** Spec Rot Interceptor
    *   🟡 **Rubrics-as-Content:**
        *   `🔧` **C-VAL-05:** Rubrics-as-Content Validation
    *   🔴 **Mathematical Speed & Security (Rust):**
        *   `[ ]` **A-VAL-04:** High-Performance Rust Validation Core

### 🟢 US-2: The Interactive Drafter
*   **User Benefit:** I can have the LLM co-author a spec with me section-by-section.
*   **Core Required (MVS):**
    *   `✅` **E-UI-01:** CLI Scaffold
    *   `✅` **E-SENS-01:** Loom Filesystem Tools
    *   `✅` **E-INTL-01:** LLM Adapter (Gemini)
    *   `✅` **E-INTL-02:** Spec Drafting (`sw draft`) & HITL Provider
    *   `✅` **E-INTL-03:** Spec Review Engine
    *   `✅` **D-INTL-05:** Project Metadata Injection
*   **Sub-Story Add-Ons:**
    *   🔴 **Surgical Spec Refactoring:**
        *   `[ ]` **D-SENS-05:** Markdown AST Mutators
    *   🔴 **Remote UI Integration:**
        *   `[ ]` **D-UI-04:** REST API - Interactive Authoring
    *   🔴 **Grill-Style Agentic Drafting** *(blocked on `C-FLOW-11`)*:
        *   `[ ]` **D-INTL-07:** Agentic Interview Drafting (Grill-Style) — needs `C-FLOW-11` (hard), `C-VAL-05` (soft)

### 🟢 US-3: Autonomous Implementation
*   **User Benefit:** I can hand an approved spec to the engine, and it will generate the code, write the tests, run them, and auto-fix linting errors.
*   **Core Required (MVS):**
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **US-9 Core** *(provides Zero-Trust Sandbox)*
    *   `✅` **US-28 Core** *(provides Agent State Ledger)*
    *   `✅` **D-INTL-01:** Implementation Generator
    *   `✅` **D-VAL-05:** Code Validation Rules (C01-C08, Type hints, Coverage)
    *   `✅` **D-VAL-01:** QA Runner Tool & Lint-Fix Reflection Loop
*   **Sub-Story Add-Ons:**
    *   🟡 **Multi-Language Test Support:**
        *   `[ ]` **D-INTL-08:** Polyglot Implementation Loop
        *   `✅` **D-VAL-03:** Polyglot QA Runner
    *   🔴 **Visual UI Drift Detection:**
        *   `[ ]` **A-VAL-05:** Multi-Modal Visual Quality Gates
    *   🟡 **Graduated Autonomy:**
        *   `🔧` **C-FLOW-11:** Graduated Autonomy (DAL-Driven Execution-Mode Dial)

### 🟢 US-4: Context-Aware Flow Orchestration
*   **User Benefit:** I can define complex multi-step workflows (draft → review → code → test) and run them autonomously with the agent aware of cross-file dependencies.
*   **Core Required (MVS):**
    *   `✅` **US-28 Core** *(provides Agent State Ledger)*
    *   `✅` **E-VAL-01:** Validation Engine
    *   `✅` **D-SENS-01:** Topology Graph (`context.yaml`)
    *   `✅` **E-FLOW-01:** SQLite Config DB & Overrides
    *   `✅` **Step 9:** Context-Enriched Prompts (Token Budgeting, Injection Selectors)
    *   `✅` **E-FLOW-02:** YAML Pipeline Models
    *   `✅` **D-FLOW-01:** SQLite Pipeline Runner & State Persistence
    *   `✅` **D-FLOW-02:** `sw run` CLI & Enterprise Logging
    *   `✅` **D-FLOW-04:** Unified Runner Architecture
    *   `✅` **E-FLOW-03:** Multi-Provider Registry
*   **Sub-Story Add-Ons:**
    *   🟡 **Security Defenses:**
        *   `🔧` **B-FLOW-05:** Token-Burn Circuit Breakers (EDoS Prevention)
    *   🟢 **Parallel Multi-Spec Execution:**
        *   `✅` **C-FLOW-03:** Multi-Spec Pipeline Fan-Out
    *   🟢 **Context Mention Highlighting:**
        *   `✅` **C-SENS-01:** Auto Spec-Mention Detection
    *   🟡 **Advanced Routing & Conditional Flows:**
        *   `[ ]` **C-FLOW-10:** Deferred Router Mapping Capabilities
        *   `✅` **C-FLOW-05:** Interactive Gate Variables (HITL)
    *   🔴 **Infinite Memory Management:**
        *   `[ ]` **C-INTL-04:** Conversation Summarization (Token compression)
    *   🔴 **Remote UI Integration:**
        *   `[ ]` **D-UI-05:** REST API - Enterprise Configuration
    *   🟢 **Configurable Prompt Render Profiles:**
        *   `✅` **C-INTL-05:** Configurable Prompt Render Profiles
    *   🔴 **Envelope-vs-Content Prompt Externalization:**
        *   `[ ]` **C-INTL-06:** Envelope-vs-Content Prompt Externalization — sequenced behind `C-VAL-05`
    *   🔴 **Declarative Dynamic Prompt Routing:**
        *   `[ ]` **B-INTL-10:** Declarative Prompt Optimization

### 🟢 US-5: Polyglot Code Understanding
*   **User Benefit:** SpecWeaver natively understands the deep syntax of my codebase across multiple languages, allowing it to extract symbols securely instead of guessing at raw text.
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Config & Flow Engine)*
    *   `✅` **E-SENS-03:** Context Ledgers & Workspace Boundaries
    *   `✅` **D-SENS-02:** Base Tree-Sitter AST Skeleton Extractor
    *   `✅` **C-FLOW-02:** Router-based flow control
    *   `✅` **D-EXEC-02:** Git Worktree Bouncer (Safe diff striping)
    *   `✅` **D-SENS-03:** Enterprise Polyglot Extraction (Go, Kotlin, C/C++, Rust, Java)
*   **Sub-Story Add-Ons:**
    *   🔴 **Infrastructure Understanding:**
        *   `[ ]` **C-SENS-04:** Infrastructure-as-Code Extraction (HCL2)
    *   🔴 **API Contract Understanding:**
        *   `[ ]` **C-SENS-07:** Polyglot Expansion (TypeSpec)
    *   🟢 **Intelligent Code Exclusions:**
        *   `✅` **C-SENS-02:** Smart Scan Exclusions (.specweaverignore)
    *   🟢 **Framework Native Understanding:**
        *   `✅` **B-INTL-02:** Macro Evaluator (Rust/Kotlin plugin expansion)
    *   🔴 **Mathematical Speed & Security (Rust):**
        *   `[ ]` **D-SENS-04:** Parallel AST Extraction Engine

---

### 🟡 US-6: The Remote Dashboard (Tablet on a Train)
**Benefit:** *I can review specs and control SpecWeaver pipelines from my browser on a tablet, without needing to run the heavy AI engine locally.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Flow Engine)*
    *   `✅` **C-FLOW-02:** Router-based flow control
    *   `🔧` **D-UI-01:** `sw serve` Core Orchestration API
    *   `✅` **E-UI-02:** Web dashboard
*   **Sub-Story Add-Ons:**
    *   🔴 **Strict UI Data Contracts:**
        *   `[ ]` **D-UI-02:** Structured output schemas
    *   🔴 **Live Pipeline Streaming:**
        *   `[ ]` **B-UI-01:** Real-Time Feedback Sensor Dashboard
    *   🔴 **Remote Systems Integration:**
        *   `[ ]` **D-UI-07:** REST API - Systems Integration


### 🟡 US-7: The IDE Copilot (VS Code)
**Benefit:** *I can interact with the engine and approve/reject generated code seamlessly inside VS Code without switching to the terminal.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Flow Engine)*
    *   `✅` **C-FLOW-02:** Router-based flow control
    *   `🔧` **D-UI-01:** `sw serve` Core Orchestration API
    *   `[ ]` **D-UI-03:** VS Code Extension
*   **Sub-Story Add-Ons:**
    *   🔴 **Strict UI Data Contracts:**
        *   `[ ]` **D-UI-02:** Structured output schemas
    *   🔴 **Real-time File Tracking:**
        *   `[ ]` **E-UI-03:** File watcher (Auto-re-validate specs on save)

### 🟡 US-8: The Greenfield Bootstrap Wizard
**Benefit:** *When starting a new project, an interactive wizard bounds the LLM's architecture choices so it doesn't hallucinate invalid tech stacks.*
*   **Core Required (MVS):**
    *   `✅` **US-2 Core** *(provides Interactive Drafter)*
    *   `✅` **D-SENS-01:** Topology Graph
    *   `[ ]` **D-INTL-04:** Interactive Design Questionnaire — *(2026-07-21) design as rhythm-harness + rubric content (grill-me pattern), not hardcoded question trees*
*   **Sub-Story Add-Ons:**
    *   🔴 **Socratic Context Gathering:**
        *   `[ ]` **A-INTL-03:** Socratic drafting flow
    *   🔴 **Architectural De-duplication:**
        *   `[ ]` **B-INTL-03:** Synthetic Commons Extraction

### 🟢 US-9: The Zero-Trust Sandbox
*   **User Benefit:** The agent is physically incapable of destroying my host machine, and its execution memory is perfectly deterministic.
*   **Core Required (MVS):**
    *   `✅` **US-5 Core** *(provides Git Worktree Bouncer)*
    *   `✅` **E-EXEC-01:** [Standard Local Execution](features/topic_06_sandbox/E-EXEC-01/E-EXEC-01_design.md)
    *   `✅` **C-EXEC-02:** Native CLI Action Nodes
*   **Sub-Story Add-Ons:**
    *   🟢 **Containerized Isolation:**
        *   `✅` **D-EXEC-01:** Podman/Docker Integration
        *   `✅` **B-EXEC-01:** Ephemeral Podman Sub-Containers
    *   🔴 **Security Defenses:**
        *   `[ ]` **E-EXEC-02:** Air-Gapped Network Egress Control
        *   `[ ]` **B-EXEC-04:** [Kernel-Enforced Resource Bounds (cgroups v2)](features/topic_06_sandbox/B-EXEC-04/B-EXEC-04_design.md)
    *   🔴 **Extreme Execution Paranoia:**
        *   `[ ]` **A-EXEC-01:** Functional Agent Sandboxing (Black Box Ledgers)
    *   🔴 **Mathematical Speed & Security (Rust):**
        *   `[ ]` **A-EXEC-03:** Git Worktree Bouncer C-Bindings (Rust PyO3)
    *   🟢 **Per-Run (Session) Worktree Isolation:**
        *   `✅` **C-EXEC-06:** Per-Run (Session) Worktree Isolation
    *   🔴 **DAL-Escalated Isolation for Pipeline Runs:**
        *   `[ ]` **C-EXEC-07:** DAL-Escalated Isolation for Pipeline Runs — needs `C-EXEC-06` ✅

### 🟡 US-10: The Monolith Dependency Visualizer
**Benefit:** *I can instantly see a visual map of my entire 20-year-old C++ monolith's God Nodes and dependencies.*
*   **Core Required (MVS):**
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **C-UI-01:** Pipeline visualization (`sw graph` HTML export)
*   **Sub-Story Add-Ons:**
    *   🟢 **Code-to-Spec Drift Checking:**
        *   `✅` **B-VAL-01:** AST Drift Detection

### 🟡 US-11: GraphRAG for Brownfield Scale
**Benefit:** *The agent can instantly recall exact context from 20 interacting microservices without blowing up the context window.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Context Prompts)*
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **A-SENS-02:** Postgres (Apache AGE + pgvector) sidecar
    *   `🔧` **B-SENS-03:** AST-based semantic chunking
*   **Sub-Story Add-Ons:**
    *   🔴 **Dynamic Knowledge Relevance:**
        *   `[ ]` **B-FLOW-04:** Hybrid RAG orchestration (composite scoring)
        *   `[ ]` **A-SENS-03:** Event-driven knowledge graph updates
    *   🔴 **Static Code Flow Analysis:**
        *   `[ ]` **B-SENS-04:** Static Control Flow Graph (CFG)
        *   `[ ]` **B-SENS-05:** Static Dataflow Solver
    *   🔴 **Cross-Language Dependency Resolution:**
        *   `[ ]` **B-SENS-07:** Language-Agnostic Dependency Resolution
    *   🟡 **Infinite Scale Management:**
        *   `✅` **A-SENS-01:** Deep Semantic Hashing (Rocket Mode streaming)
        *   `[ ]` **A-FLOW-02:** Hash-based garbage collection
        *   `[ ]` **A-INTL-04:** Memory consolidation
    *   🔴 **Microservice Federation:**
        *   `[ ]` **A-SENS-04:** Federated Microservice Linkage (Cross-Repo API Graphing via strict ID prefixes)

### 🟡 US-12: Legacy Spec Extraction (Reverse-Weaving)
**Benefit:** *SpecWeaver automatically reverse-engineers and drafts Spec.md contracts by reading my old undocumented Java/C++ code.*
*   **Core Required (MVS):**
    *   `✅` **US-2 Core** *(provides Spec Drafting)*
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **C-INTL-03:** Reverse-Weaving (`sw capture`)
*   **Sub-Story Add-Ons:**
    *   🔴 **Massive Scale Context Retrieval:**
        *   `[ ]` **A-SENS-02:** Postgres (Apache AGE + pgvector) sidecar
    *   🔴 **Automated Code Purging:**
        *   `[ ]` **A-FLOW-03:** Dead Code Detection & Analysis (finding unreachable functions using the graph for human review)

### 🟡 US-13: Financial-Grade Math Proofs
**Benefit:** *The agent mathematically proves its algorithms are secure before I deploy them to production, discovering 0-days natively.*
*   **Core Required (MVS):**
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `[ ]` **A-VAL-02:** Symbolic Math Validation
*   **Sub-Story Add-Ons:**
    *   🔴 **Symbolic Tree Traversal:**
        *   `[ ]` **A-INTL-02:** LLM-Guided Symbolic Execution
        *   `[ ]` **C-SENS-03:** Symbol index + anti-hallucination gate
    *   🔴 **Dynamic Memory Attacks:**
        *   `[ ]` **A-EXEC-02:** Tool-Augmented Security Fuzzing Harnesses

### 🟡 US-14: Adversarial Red-Teaming
**Benefit:** *An adversarial AI attacks my spec to find logic holes and edge-cases before I waste money generating bad code.*
*   **Core Required (MVS):**
    *   `✅` **US-2 Core** *(provides Spec Review Engine)*
    *   `✅` **US-3 Core** *(provides QA Runner)*
    *   `[ ]` **A-INTL-01:** Pre-Generation Adversarial Spec Review
*   **Sub-Story Add-Ons:**
    *   🔴 **Mathematical Mutation Checks:**
        *   `[ ]` **B-VAL-03:** Semantic Test Completeness — *(2026-07-21) design rubric-first on the `C-VAL-05` substrate*
        *   `[ ]` **A-VAL-03:** Mutation testing
    *   🔴 **Architectural Sandboxing:**
        *   `[ ]` **B-EXEC-03:** Blast radius / locality enforcement
    *   🔴 **Agent Independence Protocols:**
        *   `[ ]` **B-INTL-06:** Multi-Agent Isolation Patterns — needs `C-FLOW-11` + `C-EXEC-06` ✅

### 🟡 US-15: Enterprise Audit & Traceability
**Benefit:** *I can hand a compliance auditor a ledger that proves exactly which LLM generated which line of code based on which business requirement.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Pipeline Runner)*
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **C-UI-02:** Traceability Matrix UX
*   **Sub-Story Add-Ons:**
    *   🟡 **Enterprise Compliance Protocols:**
        *   `✅` **B-SENS-01:** Artifact lineage graph
        *   `[ ]` **A-UI-01:** 'Dark Factory' Compliance Logging
    *   🔴 **Zero-Trust ACL:**
        *   `[ ]` **B-EXEC-02:** Tiered access rights & Provenance tracking

### 🟢 US-16: AI Operations & Cost Routing
**Benefit:** *I can see exactly how much money each agent is spending, detect LLM friction, and dynamically route tasks to cheaper models.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Config DB)*
    *   `✅` **Step 9a:** Token Tracking
    *   `✅` **C-FLOW-01:** Telemetry DB
    *   `✅` **D-FLOW-03:** Static Routing
*   **Sub-Story Add-Ons:**
    *   🔴 **Centralized Model Table:**
        *   `[ ]` **C-FLOW-13:** Model Catalogue — per-model pricing, serving adapter and capabilities as data, not source
        *   `[ ]` **D-FLOW-05:** Model Catalogue Adoption — move every consumer onto `C-FLOW-13`, delete the per-adapter cost dicts
    *   🔴 **Dynamic Data-Driven Routing:**
        *   `[ ]` **A-FLOW-01:** Data-driven routing recommendations — needs `C-FLOW-13`
        *   `[ ]` **B-INTL-04:** Dynamic AI Arbiter — needs `C-FLOW-13`
    *   🔴 **Friction Analytics Dashboard:**
        *   `[ ]` **C-UI-03:** Task-type cost analytics dashboard
        *   `[ ]` **B-FLOW-03:** Deterministic friction detection (git diff math)
        *   `[ ]` **C-FLOW-07:** HITL Root-Cause Tagging
    *   🔴 **Enterprise Thought Observability:**
        *   `[ ]` **B-FLOW-02:** OpenTelemetry Agent Tracing
    *   🔴 **Remote UI Integration:**
        *   `[ ]` **D-UI-06:** REST API - Telemetry & Auditing

### 🟡 US-17: The SWE-Bench Guarantee
**Benefit:** *SpecWeaver proves it hasn't degraded by autonomously solving standardized SWE-Bench tickets before every release.*
*   **Core Required (MVS):**
    *   `✅` **US-3 Core** *(provides QA Runner)*
    *   `✅` **US-4 Core** *(provides CLI & Flow Engine)*
    *   `[ ]` **B-VAL-04:** Agent Platform Benchmarking (`sw eval`)
*   **Sub-Story Add-Ons:**
    *   🔴 **Continuous Integration:**
        *   `[ ]` **A-UI-02:** Standardized Benchmarking CI

### 🟡 US-18: Productionizing External Targets
**Benefit:** *We prove the entire platform works by using it to build and manage an external proprietary trading system.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides CLI & Flow Engine)*
    *   `✅` **US-5 Core** *(provides Worktree Bouncer & AST extractors)*
    *   `✅` **C-FLOW-03:** Multi-Spec Pipeline Fan-Out
    *   `✅` **US-9 Core** *(provides Containerized deployment)*
    *   `[ ]` **US-13 Core** *(provides Math Validation)*
    *   `[ ]` **US-14 Core** *(provides Adversarial Review)*
    *   `[ ]` **B-UI-02:** External Proprietary Validation
*   **Sub-Story Add-Ons:**
    *   🔴 **Secure Sandboxed Operations:**
        *   `[ ]` **D-INTL-04:** Interactive Design Questionnaire — *(2026-07-21) design as rhythm-harness + rubric content (grill-me pattern), not hardcoded question trees*
    *   🔴 **CI/CD Pipeline Integration:**
        *   `[ ]` **C-FLOW-08:** Pluggable Webhook & CI Invocation

### 🟡 US-19: Microservice Fleet Orchestration
**Benefit:** *I can design, generate, and orchestrate an entire fleet of 20+ microservices, automatically keeping their API contracts and topology synchronized across independent repositories.*
*   **Core Required (MVS):**
    *   `✅` **US-28 Core** *(provides Agent State Ledger)*
    *   `✅` **US-4 Core**
    *   `✅` **US-5 Core**
    *   `✅` **C-FLOW-03:** Multi-Spec Pipeline Fan-Out
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **C-FLOW-04:** Work Packet Bundling (Coordinated multi-agent dispatch)
*   **Sub-Story Add-Ons:**
    *   🔴 **Cross-Service Contract Validation:**
        *   `[ ]` **A-VAL-06:** Industry Standard Bridges
    *   🔴 **Parallel Execution Safety:**
        *   `[ ]` **C-EXEC-04:** Concurrent Git Merge Orchestration
    *   🟡 **Distributed Topology Scaling:**
        *   `[ ]` **A-SENS-02:** Postgres (Apache AGE + pgvector) sidecar (For massive scale context)
        *   `✅` **A-SENS-01:** Deep Semantic Hashing (Rocket Mode streaming)

### 🟡 US-20: Enterprise Architecture Enforcement
**Benefit:** *My project cannot degrade — test intensity is enforced per DAL and forbidden dependencies are blocked across the DAG.*
*   **Core Required (MVS):**
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **D-SENS-01:** Topology Graph (Dependency mapping)
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `✅` **C-EXEC-01:** Internal Layer Enforcement (Validating dependency direction)
    *   `[ ]` **B-VAL-05:** DAL Architecture Gate (Dependency tier validation)
*   **Sub-Story Add-Ons:**
    *   🔴 **Test Intensity Gating:**
        *   `[ ]` **B-VAL-03:** Semantic Test Completeness (Required for DAL-B) — *(2026-07-21) design rubric-first on the `C-VAL-05` substrate*
        *   `[ ]` **A-VAL-03:** Mutation Testing Gates (Required for DAL-A)
    *   🔴 **Automated Degradation Prevention:**
        *   `[ ]` **C-FLOW-09:** DAL CI/CD Risk Evaluation (Auto-rejects PRs on degradation)
    *   🔴 **DAG Visualization:**
        *   `[ ]` **C-UI-01:** Pipeline visualizer (Color-codes DAG by DAL risk)


### 🟢 US-21: Autonomous Feature Decomposition
**Benefit:** *I can give the agent a massive, epic-level Spec, and it will automatically break it down into a DAG of small, testable sub-components before writing any code.*
*   **Core Required (MVS):**
    *   `✅` **US-2 Core** *(provides Interactive Drafter)*
    *   `✅` **D-INTL-02:** Feature Decomposition
    *   `✅` **D-INTL-03:** Explicit Plan Phase
*   **Sub-Story Add-Ons:**
    *   🟢 **Recursive Planning:**
        *   `✅` **C-INTL-01:** Iterative Decomposition
    *   🔴 **Multi-Level Recursive Decomposition** *(the `AD-2` half `C-INTL-01` never built)*:
        *   `[ ]` **C-INTL-07:** Multi-Level Recursive Decomposition
    *   🔴 **Autonomous DAG Execution** *(blocked on `C-EXEC-07`; `TECH-014` cleared 2026-08-12)*:
        *   `[ ]` **C-FLOW-12:** Autonomous DAG Execution

### 🟢 US-22: Polyglot Contract Enforcement
**Benefit:** *SpecWeaver mathematically proves that my Python microservice didn't break the REST/gRPC contract of my Rust worker.*
*   **Core Required (MVS):**
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **A-VAL-01:** Protocol/Schema Analyzers (.proto, openapi)
    *   `✅` **C-VAL-04:** Traceability Matrix Check
*   **Sub-Story Add-Ons:**
    *   🔴 **Mathematical Speed & Security:**
        *   `[ ]` **A-VAL-04:** Rust PyO3 Validations (Massive performance scale for deep contract checking)

### 🟢 US-23: Enterprise Tool Extension (MCP)
**Benefit:** *I can instantly plug SpecWeaver into my company's internal tools (Jira, Confluence) using the Model Context Protocol without writing custom Python adapters.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Flow Engine for E2E execution)*
    *   `✅` **C-INTL-02:** MCP Client Architecture
*   **Sub-Story Add-Ons:**
    *   🔴 **Strict Security Gating:**
        *   `[ ]` **B-INTL-05:** Dynamic Tool Gating via Archetypes — design jointly with `C-FLOW-11`

### 🟢 US-24: Behavioral Scenario Verification
**Benefit:** *SpecWeaver runs parallel behavioral verification pipelines to prove the generated code actually solves the business scenario, not just syntax tests.*
*   **Core Required (MVS):**
    *   `✅` **US-3 Core** *(provides QA Runner)*
    *   `✅` **B-FLOW-01:** Scenario Testing Pipeline
    *   `✅` **D-VAL-01:** QA Runner Tool
*   **Sub-Story Add-Ons:**
    *   🔴 **Intelligent Resolution:**
        *   `[ ]` **B-INTL-07:** Error Attribution Arbiter

### 🟢 US-25: Compliance & Constitution Governance
**Benefit:** *I can enforce project-wide rules (Constitutions) and domain-specific profiles (e.g., 'Web App' vs 'ML Model') that dynamically override agent behavior.*
*   **Core Required (MVS):**
    *   `✅` **C-VAL-01:** Constitution Artifact
    *   `✅` **C-VAL-02:** Domain Profiles
*   **Sub-Story Add-Ons:**
    *   🟢 **Dynamic Risk Controls:**
        *   `✅` **D-VAL-02:** Custom Rule Paths
        *   `✅` **D-VAL-04:** Adaptive Assurance Standards
        *   `✅` **C-VAL-03:** Dynamic Risk Rulesets

---

### 🟡 US-26: Fleet-Wide CVE Remediation
**Benefit:** *When a zero-day drops, every usage of the vulnerable function is found across all repositories and refactored fleet-wide.*
*   **Core Required (MVS):**
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **B-SENS-06:** OSV Vulnerability Feed Ingestion
*   **Sub-Story Add-Ons:**
    *   🔴 **Massive Scale Orchestration:**
        *   `[ ]` **A-INTL-05:** Multi-Repo Refactoring Orchestration

### 🟡 US-27: Autonomous Production Self-Healing
**Benefit:** *A production exception becomes a Hotfix Spec and PR on its own — the stack trace resolves to an AST node through the Knowledge Graph.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Flow Engine)*
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **A-SENS-05:** APM Telemetry Ingestion (Sentry/Datadog)
*   **Sub-Story Add-Ons:**
    *   🔴 **Infinite Loop Protection:**
        *   `[ ]` **A-FLOW-04:** Blast-Radius Circuit Breaker (Prevents bad hotfixes from cascading)

### 🟢 US-28: Agent-Native Issue & State Tracker
**Benefit:** *Agents hand complex tasks to one another without context degrading — session state, tasks and blockers live in a local Memory Bank.*
*   **Core Required (MVS):**
    *   `✅` **B-INTL-09:** Agent Memory Bank (Schema + CRUD + Resilience) — [Design](features/topic_04_intelligence/B-INTL-09/B-INTL-09_design.md) (Complete)
    *   `✅` **D-INTL-06:** Context Hydration & Handover (Retrieval + Prompt Injection + Handover Protocols) — [Design](features/topic_04_intelligence/D-INTL-06/D-INTL-06_design.md) (Complete)
*   **Sub-Story Add-Ons:**
    *   🔴 **Advanced Multi-Agent Concurrency:**
        *   `[ ]` **A-EXEC-04:** Advanced Row-Level Task Locking (Pessimistic Locks, WAL2, Deadlock Detection)

---

## Technical Debt & Architecture Stories (TECH)

These stories do not add new user-facing features, but are critical epics required to ensure the platform remains stable, secure, and mathematically sound as it scales to enterprise levels.

### 🔧 Technical Debt (TECH)
*Capability-level, like `C-FLOW-02` or `E-INTL-02`: one line each — ID, short name, link, status.*
*Benefit, sequencing, proof and full rationale live in [topic_07](topics/topic_07_technical_debt.md) and each design doc.*

    *   `✅` **TECH-001:** [Domain-Driven Design Unification](features/topic_07_technical_debt/TECH-001/TECH-001_design.md)
    *   `✅` **TECH-002:** [BaseTool Registry](features/topic_07_technical_debt/TECH-002/TECH-002_design.md)
    *   `✅` **TECH-003:** [Structural Refactoring of Workspace AST Module](features/topic_07_technical_debt/TECH-003/TECH-003_design.md)
    *   `✅` **TECH-004:** [Architectural Analysis & Refactoring of `sw graph build` CLI](features/topic_07_technical_debt/TECH-004/TECH-004_design.md)
    *   `✅` **TECH-005:** [Database Table Prefix Harmonization](features/topic_07_technical_debt/TECH-005/TECH-005_design.md)
    *   `✅` **TECH-006:** [Context Loading Pipeline Refactoring](features/topic_07_technical_debt/TECH-006/TECH-006_design.md)
    *   `✅` **TECH-007:** [PromptBuilder Input Escaping](features/topic_07_technical_debt/TECH-007/TECH-007_design.md)
    *   `✅` **TECH-008:** [Architectural Documentation Modularization](features/topic_07_technical_debt/TECH-008/TECH-008_design.md)
    *   `✅` **TECH-009:** [Git & Filesystem Subprocess Migration](features/topic_07_technical_debt/TECH-009/TECH-009_design.md)
    *   `✅` **TECH-010:** [MCP Persistent-Process Executor Migration](features/topic_07_technical_debt/TECH-010/TECH-010_design.md)
    *   `✅` **TECH-011:** [Load-Time Params Validation for All Pipeline Step Types](features/topic_07_technical_debt/TECH-011/TECH-011_design.md)
    *   `✅` **TECH-012:** [Multi-Step Git-Worktree Isolation is Broken (Reconcile Never Commits; Crashes on Step 2)](features/topic_07_technical_debt/TECH-012/TECH-012_design.md)
    *   `✅` **TECH-013:** [API Composition Roots Do Not Resolve Worktree-Isolation Policy](features/topic_07_technical_debt/TECH-013/TECH-013_design.md)
    *   `✅` **TECH-014:** [Fan-Out RunContext Isolation (Concurrent Sub-Run State Corruption)](features/topic_07_technical_debt/TECH-014/TECH-014_design.md)
    *   `✅` **TECH-015:** [Retire Grab-Bag Modules (Name-Says-Nothing Refactor)](features/topic_07_technical_debt/TECH-015/TECH-015_design.md)
    *   `✅` **TECH-016:** [Unified Artifact Writer & Serialization Format Enforcement](features/topic_07_technical_debt/TECH-016/TECH-016_design.md)
    *   `✅` **TECH-017:** [Integration-Contract Proof Audit (Test Tier Must Match Story Tier)](features/topic_07_technical_debt/TECH-017/TECH-017_design.md)
    *   `✅` **TECH-018:** [Delivered Add-On Re-Validation Against an Integrated Base](features/topic_07_technical_debt/TECH-018/TECH-018_design.md)
    *   `✅` **TECH-019:** [Skill Instruction Integrity — Dangling Doc References and Contradictory Gate Orders](features/topic_07_technical_debt/TECH-019/TECH-019_design.md)
    *   `✅` **TECH-020:** [Extract the Step-Execution Loop from PipelineRunner](features/topic_07_technical_debt/TECH-020/TECH-020_design.md)
    *   `✅` **TECH-021:** [`loop_back` Discards the Failing Step's Result](features/topic_07_technical_debt/TECH-021/TECH-021_design.md)
    *   `✅` **TECH-023:** [Repo-Wide Cyclomatic Complexity Violations](features/topic_07_technical_debt/TECH-023/TECH-023_design.md)
    *   `✅` **TECH-024:** [Repo-Wide Dependency Cycles](features/topic_07_technical_debt/TECH-024/TECH-024_design.md)
    *   `✅` **TECH-025:** [Registry IDs Leaking Into Proofs](features/topic_07_technical_debt/TECH-025/TECH-025_design.md)
    *   `✅` **TECH-026:** [Roadmap Placement Contract](features/topic_07_technical_debt/TECH-026/TECH-026_design.md)
    *   `✅` **TECH-027:** [Sub-Feature Identifier Contract](features/topic_07_technical_debt/TECH-027/TECH-027_design.md)
    *   `✅` **TECH-028:** [Split `dev` Dependency Definitions](features/topic_07_technical_debt/TECH-028/TECH-028_design.md)
    *   `✅` **TECH-029:** [Sandbox Process Cap Uses `RLIMIT_NPROC`](features/topic_07_technical_debt/TECH-029/TECH-029_design.md)
    *   `✅` **TECH-030:** [An Empty `FolderGrant` Path Diverges by Platform](features/topic_07_technical_debt/TECH-030/TECH-030_design.md)
    *   `✅` **TECH-031:** [Container Prepare Phase Has Never Installed a Toolchain](features/topic_07_technical_debt/TECH-031/TECH-031_design.md)
    *   `✅` **TECH-032:** [Non-Python QA Runners Report an Absent Toolchain as Success](features/topic_07_technical_debt/TECH-032/TECH-032_design.md)
    *   `✅` **TECH-033:** [A Step's Retry Budget Resets on Every `sw resume`](features/topic_07_technical_debt/TECH-033/TECH-033_design.md)
    *   `✅` **TECH-034:** [Split the AST Parser Hierarchy by Language Paradigm](features/topic_07_technical_debt/TECH-034/TECH-034_design.md)
    *   `✅` **TECH-035:** [Chronically Failing Class-Health Gate](features/topic_07_technical_debt/TECH-035/TECH-035_design.md)
    *   `✅` **TECH-036:** [Lineage Telemetry Takes Down a Lint Fix That Already Succeeded](features/topic_07_technical_debt/TECH-036/TECH-036_design.md)
    *   `✅` **TECH-037:** [Duplicated Code Is Found Only By Accident](features/topic_07_technical_debt/TECH-037/TECH-037_design.md)
    *   `✅` **TECH-038:** [Registry Claims Recursive Decomposition the Capability Does Not Implement](features/topic_07_technical_debt/TECH-038/TECH-038_design.md)
    *   `✅` **TECH-039:** [One Identifier Named Two Delivered Add-Ons (`INT-US-05-SUB` Collision)](features/topic_07_technical_debt/TECH-039/TECH-039_design.md)
    *   `✅` **TECH-040:** [`sw run --verbose` Showed No Handler Output](features/topic_07_technical_debt/TECH-040/TECH-040_design.md)
    *   `✅` **TECH-041:** [The Code-Level DAL Override Is Unproven End to End](features/topic_07_technical_debt/TECH-041/TECH-041_design.md)
    *   `✅` **TECH-044:** [Registry Entries Carry Content Belonging Four Layers Down](features/topic_07_technical_debt/TECH-044/TECH-044_design.md)
    *   `✅` **TECH-045:** [Nothing Bounds a Document's Size](features/topic_07_technical_debt/TECH-045/TECH-045_design.md)
    *   `✅` **TECH-046:** [`C-INTL-01` Shipped Without the Recursion It Was Designed For](features/topic_07_technical_debt/TECH-046/TECH-046_design.md)
    *   `✅` **TECH-047:** [Nothing Runs the FR-Coverage Gate Across Delivered Work](features/topic_07_technical_debt/TECH-047/TECH-047_design.md)
    *   `✅` **TECH-048:** [A Design the FR Gate Cannot Parse Reports "Cannot Run", Not "Failed"](features/topic_07_technical_debt/TECH-048/TECH-048_design.md)
    *   `✅` **TECH-049:** [Mutation Campaign Corpus and Session Gate](features/topic_07_technical_debt/TECH-049/TECH-049_design.md)
    *   `✅` **TECH-050:** [28 Tests Fail Whenever an Agent Runs Them](features/topic_07_technical_debt/TECH-050/TECH-050_design.md)
    *   `✅` **TECH-051:** [24 Tests Look Like Coverage and Never Run](features/topic_07_technical_debt/TECH-051/TECH-051_design.md)
    *   `✅` **TECH-052:** [`sw usage --since` Crashes on Unparseable Input](features/topic_07_technical_debt/TECH-052/TECH-052_design.md)
    *   `✅` **TECH-053:** [A `✅` Nothing Can Verify](features/topic_07_technical_debt/TECH-053/TECH-053_design.md)
    *   `✅` **TECH-054:** [The Two Foundations Nobody Wrote Down](features/topic_07_technical_debt/TECH-054/TECH-054_design.md)
    *   `✅` **TECH-055:** [The Suite Edits the Standard It Is Measured Against](features/topic_07_technical_debt/TECH-055/TECH-055_design.md)
    *   `✅` **TECH-056:** [The Morning Gate Marks Its Own Homework](features/topic_07_technical_debt/TECH-056/TECH-056_design.md)
    *   `✅` **TECH-057:** [The Nightly Runs Its Mutants One at a Time](features/topic_07_technical_debt/TECH-057/TECH-057_design.md)
    *   `✅` **TECH-058:** [The Nightly's Baseline Forgot Its Own `-n auto`](features/topic_07_technical_debt/TECH-058/TECH-058_design.md)
    *   `✅` **TECH-059:** [Registry IDs and History in Production Comments](features/topic_07_technical_debt/TECH-059/TECH-059_design.md)
    *   `✅` **TECH-060:** [Integration Migration to (Sub)Story Path Inventories](features/topic_07_technical_debt/TECH-060/TECH-060_design.md)
    *   `✅` **TECH-061:** [The Knowledge Graph Is Python-Only](features/topic_07_technical_debt/TECH-061/TECH-061_design.md)
    *   `✅` **TECH-062:** [Parallel Fan-Out Has No Collision Guards](features/topic_07_technical_debt/TECH-062/TECH-062_design.md)
    *   `✅` **TECH-063:** [The MCP Container Boundary Checks a Name, Not a Command](features/topic_07_technical_debt/TECH-063/TECH-063_design.md)
    *   `✅` **TECH-064:** [Polyglot Architecture Checks Report Success Where They Do Nothing](features/topic_07_technical_debt/TECH-064/TECH-064_design.md)
    *   `✅` **TECH-065:** [Parameterised Annotations Never Match a Framework Schema](features/topic_07_technical_debt/TECH-065/TECH-065_design.md)
    *   `✅` **TECH-066:** [Contract Drift Analysis Can Never Find Anything](features/topic_07_technical_debt/TECH-066/TECH-066_design.md)
    *   `✅` **TECH-067:** [The Pipeline Resolves a Module's DAL and Never Applies It](features/topic_07_technical_debt/TECH-067/TECH-067_design.md)
