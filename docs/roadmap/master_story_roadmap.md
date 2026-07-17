# Master User Story Roadmap

This is the unified, single-numbering format (US-1 to US-18) covering the entire lifespan of the platform.

### Story Status Flags
*   🟢 **Completed** (For Base: Core MVS is 100% delivered. For Sub-Story: Feature is 100% delivered)
*   🟡 **In Progress** (Some requirements are checked, but not all)
*   🔴 **Pending** (Zero requirements have been checked)
*   🔵 **On Hold** (Visionary, blocked, or parked)

Following the **"Good Enough" principle**, every User Story is strictly divided into:
1. **Core Required (MVS):** The absolute minimum required to achieve the user benefit.
2. **Sub-Story Add-Ons:** Optional, self-contained enhancements that group technical features into deliverable improvements.

---

## 🎯 Active Routing Queue
*The engineering team must select ONE of the following candidates as the next primary objective. Do not start a new candidate until the current one is `🟢 Completed`.*

1. **Candidate A: US-9 Core Execution — Standard Local Execution** ← ACTIVE FOCUS, both listed features now `✅` complete
   * **Features:** `E-EXEC-01` Standard Local Execution ✅ + `C-EXEC-02` Native CLI Action Nodes ✅
   * **Pros:** Closes `US-9` Core (Zero-Trust Sandbox), directly unblocking `US-3` (Autonomous Implementation) and all safe code execution workflows.
   * **Cons:** None. **Update (2026-07-17)**: `INT-US-09` (Base Integration Contract) is now `✅`, so US-9's **Core MVS is 100% delivered** (INT-US-09 + US-5 Core + E-EXEC-01 + C-EXEC-02) → US-9 Core is `🟢`. Only the *optional* Sub-Story Add-Ons (`INT-US-09-SF01..SF04`: Containerized Isolation, Security Defenses, Extreme Paranoia, Rust) remain open. Needs a team decision on the next Active Routing Queue focus.
2. **Candidate B: Configurable Prompt Render Profiles** ← UNBLOCKED
   * **Features:** `C-INTL-05` Configurable Prompt Render Profiles + `INT-US-04-SF08`
   * **Pros:** Enhances US-4 Orchestration by allowing dynamic, context-aware templating of prompts.
   * **Cons:** Sub-story level enhancement; does not unlock new epics directly.
3. **Candidate C: US-2 Completion — Project Metadata Injection** ← UNBLOCKED
   * **Features:** `D-INTL-05` Project Metadata Injection
   * **Pros:** Single remaining blocker for `US-2` Core. Closes the Interactive Drafter and unlocks `US-21` (Autonomous Decomposition).
   * **Cons:** Moderate effort.
4. **Candidate D: Token-Burn Circuit Breakers (EDoS Prevention)** ← UNBLOCKED
   * **Features:** `B-FLOW-05` Token-Burn Circuit Breakers + `INT-US-04-SF02`
   * **Pros:** High financial security ROI. Prevents massive LLM cost overruns natively within the Flow Engine.
   * **Cons:** Hardening measure; does not unblock downstream epics.
5. **Candidate E: AST Prompt Injection Sanitization** ← UNBLOCKED
   * **Features:** `E-VAL-03` AST Prompt Injection Sanitization
   * **Pros:** High security ROI. Protects the Validation Engine from prompt injection attacks embedded in source code.
   * **Cons:** Purely a hardening measure.

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
    *   `✅` **INT-US-01:** Base Integration Contract defined in [US-01_integration.md](topics/topic_08_integration/US-01_integration.md) (Complete)
    *   `✅` **US-5 Core** *(provides AST extraction for C13 drift rules)*
    *   `✅` **E-UI-01:** CLI Scaffold
    *   `✅` **E-SENS-01:** Loom Filesystem Tools
    *   `✅` **E-VAL-01:** Validation Engine (Foundation)
    *   `✅` **E-INTL-01:** LLM Adapter (Gemini)
*   **Sub-Story Add-Ons:**
    *   🔴 **Security Defenses:**
        *   `[ ]` **INT-US-01-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **E-VAL-03:** AST Prompt Injection Sanitization
    *   🟡 **Enforce Internal Architecture:**
        *   `[ ]` **INT-US-01-SF02:** Sub-Story Integration (Pending Design)
        *   `✅` **C-EXEC-01:** Internal Layer Enforcement
        *   `✅` **C-EXEC-03:** Domain-Driven Module Consolidation
        *   `[ ]` **E-UI-04:** CLI Command Arch Separation (Discovery vs Validation)
    *   🟡 **Configurable Multi-Stage Reviews:**
        *   `[ ]` **INT-US-01-SF03:** Sub-Story Integration (Pending Design)
        *   `✅` **E-VAL-02:** Auto-discover Standards
        *   `[ ]` **E-VAL-04:** Multi-stage Reviews
        *   `[ ]` **B-VAL-02:** Spec Rot Interceptor
    *   🔴 **Mathematical Speed & Security (Rust):**
        *   `[ ]` **INT-US-01-SF04:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-VAL-04:** High-Performance Rust Validation Core

### 🟡 US-2: The Interactive Drafter
*   **User Benefit:** I can have the LLM co-author a spec with me section-by-section.
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-02:** Base Integration Contract defined in [US-02_integration.md](topics/topic_08_integration/US-02_integration.md)
    *   `✅` **E-UI-01:** CLI Scaffold
    *   `✅` **E-SENS-01:** Loom Filesystem Tools
    *   `✅` **E-INTL-01:** LLM Adapter (Gemini)
    *   `✅` **E-INTL-02:** Spec Drafting (`sw draft`) & HITL Provider
    *   `✅` **E-INTL-03:** Spec Review Engine
    *   `[ ]` **D-INTL-05:** Project Metadata Injection
*   **Sub-Story Add-Ons:**
    *   🔴 **Surgical Spec Refactoring:**
        *   `[ ]` **INT-US-02-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-SENS-05:** Markdown AST Mutators
    *   🔴 **Remote UI Integration:**
        *   `[ ]` **INT-US-02-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-UI-04:** REST API - Interactive Authoring

### 🟡 US-3: Autonomous Implementation
*   **User Benefit:** I can hand an approved spec to the engine, and it will generate the code, write the tests, run them, and auto-fix linting errors.
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-03:** Base Integration Contract defined in [US-03_integration.md](topics/topic_08_integration/US-03_integration.md)
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **US-9 Core** *(provides Zero-Trust Sandbox)*
    *   `✅` **US-28 Core** *(provides Agent State Ledger)*
    *   `✅` **D-INTL-01:** Implementation Generator
    *   `✅` **D-VAL-05:** Code Validation Rules (C01-C08, Type hints, Coverage)
    *   `✅` **D-VAL-01:** QA Runner Tool & Lint-Fix Reflection Loop
*   **Sub-Story Add-Ons:**
    *   🔴 **Multi-Language Test Support:**
        *   `[ ]` **INT-US-03-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-VAL-03:** Polyglot QA Runner
    *   🔴 **Visual UI Drift Detection:**
        *   `[ ]` **INT-US-03-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-VAL-05:** Multi-Modal Visual Quality Gates

### 🟢 US-4: Context-Aware Flow Orchestration
*   **User Benefit:** I can define complex multi-step workflows (draft → review → code → test) and run them autonomously with the agent aware of cross-file dependencies.
*   **Core Required (MVS):**
    *   `✅` **INT-US-04:** Base Integration Contract defined in [INT-US-04_design.md](features/topic_08_integration/INT-US-04/INT-US-04_design.md) (Complete)
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
    *   🔴 **Security Defenses:**
        *   `[ ]` **INT-US-04-SF02:** Sub-Story Integration defined in [SF-02: Security Defenses](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-02-security-defenses-integration-pending-design)
        *   `[ ]` **B-FLOW-05:** Token-Burn Circuit Breakers (EDoS Prevention)
    *   🟢 **Parallel Multi-Spec Execution:**
        *   `✅` **INT-US-04-SF03:** Sub-Story Integration defined in [SF-03: Parallel Multi-Spec Execution](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-03-parallel-multi-spec-execution-integration-pending-design)
        *   `✅` **C-FLOW-03:** Multi-Spec Pipeline Fan-Out
    *   🟢 **Context Mention Highlighting:**
        *   `✅` **INT-US-04-SF04:** Sub-Story Integration defined in [SF-04: Context Mention Highlighting](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-04-context-mention-highlighting-integration-pending-design)
        *   `✅` **C-SENS-01:** Auto Spec-Mention Detection
    *   🟡 **Advanced Routing & Conditional Flows:**
        *   `[ ]` **INT-US-04-SF05:** Sub-Story Integration defined in [SF-05: Advanced Routing & Conditional Flows](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-05-advanced-routing--conditional-flows-integration-pending-design)
        *   `[ ]` **C-FLOW-02:** Deferred Router Mapping Capabilities
        *   `✅` **C-FLOW-05:** Interactive Gate Variables (HITL)
    *   🔴 **Infinite Memory Management:**
        *   `[ ]` **INT-US-04-SF06:** Sub-Story Integration defined in [SF-06: Infinite Memory Management](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-06-infinite-memory-management-integration-pending-design)
        *   `[ ]` **C-INTL-04:** Conversation Summarization (Token compression)
    *   🔴 **Remote UI Integration:**
        *   `[ ]` **INT-US-04-SF07:** Sub-Story Integration defined in [SF-07: Remote UI Integration](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-07-remote-ui-integration-pending-design)
        *   `[ ]` **D-UI-05:** REST API - Enterprise Configuration
    *   🟢 **Configurable Prompt Render Profiles:**
        *   `✅` **INT-US-04-SF08:** Sub-Story Integration defined in [SF-08: Configurable Prompt Render Profiles Integration](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-08-configurable-prompt-render-profiles-integration)
        *   `✅` **C-INTL-05:** Configurable Prompt Render Profiles
    *   🔴 **Declarative Dynamic Prompt Routing:**
        *   `[ ]` **INT-US-04-SF09:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-INTL-10:** Declarative Prompt Optimization (DSPy-style routing)

### 🟢 US-5: Polyglot Code Understanding
*   **User Benefit:** SpecWeaver natively understands the deep syntax of my codebase across multiple languages, allowing it to extract symbols securely instead of guessing at raw text.
*   **Core Required (MVS):**
    *   `✅` **INT-US-05:** Base Integration Contract defined in [US-05_integration.md](topics/topic_08_integration/US-05_integration.md) (Complete)
    *   `✅` **US-4 Core** *(provides Config & Flow Engine)*
    *   `✅` **E-SENS-03:** Context Ledgers & Workspace Boundaries
    *   `✅` **D-SENS-02:** Base Tree-Sitter AST Skeleton Extractor
    *   `✅` **C-FLOW-02:** Router-based flow control
    *   `✅` **D-EXEC-02:** Git Worktree Bouncer (Safe diff striping)
    *   `✅` **D-SENS-03:** Enterprise Polyglot Extraction (Go, Kotlin, C/C++, Rust, Java)
*   **Sub-Story Add-Ons:**
    *   🔴 **Infrastructure Understanding:**
        *   `[ ]` **INT-US-05-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-SENS-04:** Infrastructure-as-Code Extraction (HCL2)
    *   🔴 **API Contract Understanding:**
        *   `[ ]` **INT-US-05-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-SENS-07:** Polyglot Expansion (TypeSpec)
    *   🟢 **Intelligent Code Exclusions:**
        *   `✅` **INT-US-05-SF03:** Sub-Story Integration (Complete)
        *   `✅` **C-SENS-02:** Smart Scan Exclusions (.specweaverignore)
    *   🟢 **Framework Native Understanding:**
        *   `✅` **INT-US-05-SF04:** Sub-Story Integration (Complete)
        *   `✅` **B-INTL-02:** Macro Evaluator (Rust/Kotlin plugin expansion)
    *   🔴 **Mathematical Speed & Security (Rust):**
        *   `[ ]` **INT-US-05-SF05:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-SENS-04:** Parallel AST Extraction Engine

---

### 🟡 US-6: The Remote Dashboard (Tablet on a Train)
**Benefit:** *I can review specs and control SpecWeaver pipelines from my browser on a tablet, without needing to run the heavy AI engine locally.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-06:** Base Integration Contract defined in [US-06_integration.md](topics/topic_08_integration/US-06_integration.md)
    *   `✅` **US-4 Core** *(provides Flow Engine)*
    *   `✅` **C-FLOW-02:** Router-based flow control
    *   `[ ]` **D-UI-01:** `sw serve` Core Orchestration API
    *   `[ ]` **E-UI-02:** Web dashboard
*   **Sub-Story Add-Ons:**
    *   🔴 **Strict UI Data Contracts:**
        *   `[ ]` **INT-US-06-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-UI-02:** Structured output schemas
    *   🔴 **Live Pipeline Streaming:**
        *   `[ ]` **INT-US-06-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-UI-01:** Real-Time Feedback Sensor Dashboard
    *   🔴 **Remote Systems Integration:**
        *   `[ ]` **INT-US-06-SF03:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-UI-07:** REST API - Systems Integration


### 🟡 US-7: The IDE Copilot (VS Code)
**Benefit:** *I can interact with the engine and approve/reject generated code seamlessly inside VS Code without switching to the terminal.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-07:** Base Integration Contract defined in [US-07_integration.md](topics/topic_08_integration/US-07_integration.md)
    *   `✅` **US-4 Core** *(provides Flow Engine)*
    *   `✅` **C-FLOW-02:** Router-based flow control
    *   `[ ]` **D-UI-01:** `sw serve` Core Orchestration API
    *   `[ ]` **D-UI-03:** VS Code Extension
*   **Sub-Story Add-Ons:**
    *   🔴 **Strict UI Data Contracts:**
        *   `[ ]` **INT-US-07-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-UI-02:** Structured output schemas
    *   🔴 **Real-time File Tracking:**
        *   `[ ]` **INT-US-07-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **E-UI-03:** File watcher (Auto-re-validate specs on save)

### 🟡 US-8: The Greenfield Bootstrap Wizard
**Benefit:** *When starting a new project, an interactive wizard bounds the LLM's architecture choices so it doesn't hallucinate invalid tech stacks.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-08:** Base Integration Contract defined in [US-08_integration.md](topics/topic_08_integration/US-08_integration.md)
    *   `[ ]` **US-2 Core** *(provides Interactive Drafter)*
    *   `✅` **D-SENS-01:** Topology Graph
    *   `[ ]` **D-INTL-04:** Interactive Design Questionnaire
*   **Sub-Story Add-Ons:**
    *   🔴 **Socratic Context Gathering:**
        *   `[ ]` **INT-US-08-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-INTL-03:** Socratic drafting flow
    *   🔴 **Architectural De-duplication:**
        *   `[ ]` **INT-US-08-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-INTL-03:** Synthetic Commons Extraction

### 🟢 US-9: The Zero-Trust Sandbox
*   **User Benefit:** The agent is physically incapable of destroying my host machine, and its execution memory is perfectly deterministic.
*   **Core Required (MVS):**
    *   `✅` **INT-US-09:** Base Integration Contract defined in [US-09_integration.md](topics/topic_08_integration/US-09_integration.md) — **Verifiable Proof:** `tests/e2e/sandbox/test_int_us_09_isolation_e2e.py` (real git worktree, unmocked: `action: bash` + `run_tests`/pytest run worktree-bounded under the opt-in US-9 policy, source root unmutated). Container-free (US-5 + E-EXEC-01 + C-EXEC-02). **Backlog:** API-run policy wiring (`pipelines.py`) and `run_tests`-in-worktree dep-resolution robustness deferred; containerization is the separate `INT-US-09-SF01` add-on.
    *   `✅` **US-5 Core** *(provides Git Worktree Bouncer)*
    *   `✅` **E-EXEC-01:** [Standard Local Execution](features/topic_06_sandbox/E-EXEC-01/E-EXEC-01_design.md)
    *   `✅` **C-EXEC-02:** [Native CLI Action Nodes](features/topic_06_sandbox/C-EXEC-02/C-EXEC-02_design.md) — SF-1/SF-2/SF-3 all complete. **Verifiable Proof:** `tests/integration/core/flow/handlers/test_bash_action_integration.py` (real `PipelineRunner` + `StepHandlerRegistry` executing a real script, end-to-end + router branching + `step_records` propagation; no e2e test — justified in the design doc's ROI section as an internal engine capability, not yet wired into a user-facing CLI pipeline)
*   **Sub-Story Add-Ons:**
    *   🟡 **Containerized Isolation:**
        *   `[ ]` **INT-US-09-SF01:** Sub-Story Integration (Pending Design)
        *   `✅` **D-EXEC-01:** Podman/Docker Integration
        *   `✅` **B-EXEC-01:** [Ephemeral Podman Sub-Containers](features/topic_06_sandbox/B-EXEC-01/B-EXEC-01_design.md) — **Verifiable Proof:** `tests/integration/sandbox/execution/test_container_executor_integration.py` + `tests/integration/sandbox/atoms/qa_runner/python/test_container_atom_integration.py` (real Podman engine: RO-mount write-blocking, RW-scratch write-allowance, `--network none` egress-blocking, guaranteed cleanup, full `factory→atom→executor` chain). Integration-tier, not literal e2e-tier (CLI-invocation) — noted transparently, not silently resolved; see the design doc's Session Handoff.
    *   🔴 **Security Defenses:**
        *   `[ ]` **INT-US-09-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **E-EXEC-02:** Air-Gapped Network Egress Control
    *   🔴 **Extreme Execution Paranoia:**
        *   `[ ]` **INT-US-09-SF03:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-EXEC-01:** Functional Agent Sandboxing (Black Box Ledgers)
    *   🔴 **Mathematical Speed & Security (Rust):**
        *   `[ ]` **INT-US-09-SF04:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-EXEC-03:** Git Worktree Bouncer C-Bindings (Rust PyO3)

### 🟡 US-10: The Monolith Dependency Visualizer
**Benefit:** *I can instantly see a visual map of my entire 20-year-old C++ monolith's God Nodes and dependencies.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-10:** Base Integration Contract defined in [US-10_integration.md](topics/topic_08_integration/US-10_integration.md)
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **C-UI-01:** Pipeline visualization (`sw graph` HTML export)
*   **Sub-Story Add-Ons:**
    *   🔴 **Code-to-Spec Drift Checking:**
        *   `[ ]` **INT-US-10-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-VAL-01:** AST Drift Detection

### 🟡 US-11: GraphRAG for Brownfield Scale
**Benefit:** *The agent can instantly recall exact context from 20 interacting microservices without blowing up the context window.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-11:** Base Integration Contract defined in [US-11_integration.md](topics/topic_08_integration/US-11_integration.md)
    *   `✅` **US-4 Core** *(provides Context Prompts)*
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **A-SENS-02:** Postgres (Apache AGE + pgvector) sidecar
    *   `[ ]` **B-SENS-03:** AST-based semantic chunking
*   **Sub-Story Add-Ons:**
    *   🔴 **Dynamic Knowledge Relevance:**
        *   `[ ]` **INT-US-11-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-FLOW-04:** Hybrid RAG orchestration (composite scoring)
        *   `[ ]` **A-SENS-03:** Event-driven knowledge graph updates
    *   🔴 **Static Code Flow Analysis:**
        *   `[ ]` **INT-US-11-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-SENS-04:** Static Control Flow Graph (CFG)
        *   `[ ]` **B-SENS-05:** Static Dataflow Solver
    *   🔴 **Infinite Scale Management:**
        *   `[ ]` **INT-US-11-SF03:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-SENS-01:** Deep Semantic Hashing (Rocket Mode streaming)
        *   `[ ]` **A-FLOW-02:** Hash-based garbage collection
        *   `[ ]` **A-INTL-04:** Memory consolidation
    *   🔴 **Microservice Federation:**
        *   `[ ]` **INT-US-11-SF04:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-SENS-04:** Federated Microservice Linkage (Cross-Repo API Graphing via strict ID prefixes)

### 🟡 US-12: Legacy Spec Extraction (Reverse-Weaving)
**Benefit:** *SpecWeaver automatically reverse-engineers and drafts Spec.md contracts by reading my old undocumented Java/C++ code.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-12:** Base Integration Contract defined in [US-12_integration.md](topics/topic_08_integration/US-12_integration.md)
    *   `[ ]` **US-2 Core** *(provides Spec Drafting)*
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **C-INTL-03:** Reverse-Weaving (`sw capture`)
*   **Sub-Story Add-Ons:**
    *   🔴 **Massive Scale Context Retrieval:**
        *   `[ ]` **INT-US-12-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-SENS-02:** Postgres (Apache AGE + pgvector) sidecar
    *   🔴 **Automated Code Purging:**
        *   `[ ]` **INT-US-12-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-FLOW-03:** Dead Code Detection & Analysis (finding unreachable functions using the graph for human review)

### 🟡 US-13: Financial-Grade Math Proofs
**Benefit:** *The agent mathematically proves its algorithms are secure before I deploy them to production, discovering 0-days natively.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-13:** Base Integration Contract defined in [US-13_integration.md](topics/topic_08_integration/US-13_integration.md)
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `[ ]` **A-VAL-02:** Symbolic Math Validation
*   **Sub-Story Add-Ons:**
    *   🔴 **Symbolic Tree Traversal:**
        *   `[ ]` **INT-US-13-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-INTL-02:** LLM-Guided Symbolic Execution
        *   `[ ]` **C-SENS-03:** Symbol index + anti-hallucination gate
    *   🔴 **Dynamic Memory Attacks:**
        *   `[ ]` **INT-US-13-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-EXEC-02:** Tool-Augmented Security Fuzzing Harnesses

### 🟡 US-14: Adversarial Red-Teaming
**Benefit:** *An adversarial AI attacks my spec to find logic holes and edge-cases before I waste money generating bad code.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-14:** Base Integration Contract defined in [US-14_integration.md](topics/topic_08_integration/US-14_integration.md)
    *   `[ ]` **US-2 Core** *(provides Spec Review Engine)*
    *   `[ ]` **US-3 Core** *(provides QA Runner)*
    *   `[ ]` **A-INTL-01:** Pre-Generation Adversarial Spec Review
*   **Sub-Story Add-Ons:**
    *   🔴 **Mathematical Mutation Checks:**
        *   `[ ]` **INT-US-14-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-VAL-03:** Semantic Test Completeness
        *   `[ ]` **A-VAL-03:** Mutation testing
    *   🔴 **Architectural Sandboxing:**
        *   `[ ]` **INT-US-14-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-EXEC-03:** Blast radius / locality enforcement
    *   🔴 **Agent Independence Protocols:**
        *   `[ ]` **INT-US-14-SF03:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-INTL-06:** Multi-Agent Isolation Patterns

### 🟡 US-15: Enterprise Audit & Traceability
**Benefit:** *I can hand a compliance auditor a ledger that proves exactly which LLM generated which line of code based on which business requirement.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-15:** Base Integration Contract defined in [US-15_integration.md](topics/topic_08_integration/US-15_integration.md)
    *   `✅` **US-4 Core** *(provides Pipeline Runner)*
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **C-UI-02:** Traceability Matrix UX
*   **Sub-Story Add-Ons:**
    *   🔴 **Enterprise Compliance Protocols:**
        *   `[ ]` **INT-US-15-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-SENS-01:** Artifact lineage graph
        *   `[ ]` **A-UI-01:** 'Dark Factory' Compliance Logging
    *   🔴 **Zero-Trust ACL:**
        *   `[ ]` **INT-US-15-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-EXEC-02:** Tiered access rights & Provenance tracking

### 🟡 US-16: AI Operations & Cost Routing
**Benefit:** *I can see exactly how much money each agent is spending, detect LLM friction, and dynamically route tasks to cheaper models.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-16:** Base Integration Contract defined in [US-16_integration.md](topics/topic_08_integration/US-16_integration.md)
    *   `✅` **US-4 Core** *(provides Config DB)*
    *   `✅` **Step 9a:** Token Tracking
    *   `[ ]` **C-FLOW-01:** Telemetry DB
    *   `[ ]` **D-FLOW-03:** Static Routing
*   **Sub-Story Add-Ons:**
    *   🔴 **Dynamic Data-Driven Routing:**
        *   `[ ]` **INT-US-16-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-FLOW-01:** Data-driven routing recommendations
        *   `[ ]` **B-INTL-04:** Dynamic AI Arbiter
    *   🔴 **Friction Analytics Dashboard:**
        *   `[ ]` **INT-US-16-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-UI-03:** Task-type cost analytics dashboard
        *   `[ ]` **B-FLOW-03:** Deterministic friction detection (git diff math)
        *   `[ ]` **C-FLOW-07:** HITL Root-Cause Tagging
    *   🔴 **Enterprise Thought Observability:**
        *   `[ ]` **INT-US-16-SF03:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-FLOW-02:** OpenTelemetry Agent Tracing
    *   🔴 **Remote UI Integration:**
        *   `[ ]` **INT-US-16-SF04:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-UI-06:** REST API - Telemetry & Auditing

### 🟡 US-17: The SWE-Bench Guarantee
**Benefit:** *SpecWeaver proves it hasn't degraded by autonomously solving standardized SWE-Bench tickets before every release.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-17:** Base Integration Contract defined in [US-17_integration.md](topics/topic_08_integration/US-17_integration.md)
    *   `[ ]` **US-3 Core** *(provides QA Runner)*
    *   `✅` **US-4 Core** *(provides CLI & Flow Engine)*
    *   `[ ]` **B-VAL-04:** Agent Platform Benchmarking (`sw eval`)
*   **Sub-Story Add-Ons:**
    *   🔴 **Continuous Integration:**
        *   `[ ]` **INT-US-17-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-UI-02:** Standardized Benchmarking CI

### 🟡 US-18: Productionizing External Targets
**Benefit:** *We prove the entire platform works by using it to build and manage an external proprietary trading system.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-18:** Base Integration Contract defined in [US-18_integration.md](topics/topic_08_integration/US-18_integration.md)
    *   `✅` **US-4 Core** *(provides CLI & Flow Engine)*
    *   `✅` **US-5 Core** *(provides Worktree Bouncer & AST extractors)*
    *   `✅` **C-FLOW-03:** Multi-Spec Pipeline Fan-Out
    *   `[ ]` **US-9 Core** *(provides Containerized deployment)*
    *   `[ ]` **US-13 Core** *(provides Math Validation)*
    *   `[ ]` **US-14 Core** *(provides Adversarial Review)*
    *   `[ ]` **B-UI-02:** External Proprietary Validation
*   **Sub-Story Add-Ons:**
    *   🔴 **Secure Sandboxed Operations:**
        *   `[ ]` **INT-US-18-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-INTL-04:** Interactive Design Questionnaire
    *   🔴 **CI/CD Pipeline Integration:**
        *   `[ ]` **INT-US-18-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-FLOW-08:** Pluggable Webhook & CI Invocation

### 🟡 US-19: Microservice Fleet Orchestration
**Benefit:** *I can design, generate, and orchestrate an entire fleet of 20+ microservices, automatically keeping their API contracts and topology synchronized across independent repositories.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-19:** Base Integration Contract defined in [US-19_integration.md](topics/topic_08_integration/US-19_integration.md)
    *   `✅` **US-28 Core** *(provides Agent State Ledger)*
    *   `✅` **US-4 Core**
    *   `✅` **US-5 Core**
    *   `✅` **C-FLOW-03:** Multi-Spec Pipeline Fan-Out
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **C-FLOW-04:** Work Packet Bundling (Coordinated multi-agent dispatch)
*   **Sub-Story Add-Ons:**
    *   🔴 **Cross-Service Contract Validation:**
        *   `[ ]` **INT-US-19-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-VAL-06:** Industry Standard Bridges
    *   🔴 **Parallel Execution Safety:**
        *   `[ ]` **INT-US-19-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-EXEC-04:** Concurrent Git Merge Orchestration
    *   🔴 **Distributed Topology Scaling:**
        *   `[ ]` **INT-US-19-SF03:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-SENS-02:** Postgres (Apache AGE + pgvector) sidecar (For massive scale context)
        *   `[ ]` **A-SENS-01:** Deep Semantic Hashing (Rocket Mode streaming)

### 🟡 US-20: Enterprise Architecture Enforcement
**Benefit:** *SpecWeaver mathematically prevents my project from degrading by enforcing strict test intensities (e.g., DAL-A requires mutation tests) and blocking forbidden dependencies across the DAG.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-20:** Base Integration Contract defined in [US-20_integration.md](topics/topic_08_integration/US-20_integration.md)
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **D-SENS-01:** Topology Graph (Dependency mapping)
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **C-EXEC-01:** Internal Layer Enforcement (Validating dependency direction)
    *   `[ ]` **B-VAL-05:** DAL Architecture Gate (Dependency tier validation)
*   **Sub-Story Add-Ons:**
    *   🔴 **Test Intensity Gating:**
        *   `[ ]` **INT-US-20-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-VAL-03:** Semantic Test Completeness (Required for DAL-B)
        *   `[ ]` **A-VAL-03:** Mutation Testing Gates (Required for DAL-A)
    *   🔴 **Automated Degradation Prevention:**
        *   `[ ]` **INT-US-20-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-FLOW-09:** DAL CI/CD Risk Evaluation (Auto-rejects PRs on degradation)
    *   🔴 **DAG Visualization:**
        *   `[ ]` **INT-US-20-SF03:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-UI-01:** Pipeline visualizer (Color-codes DAG by DAL risk)


### 🟡 US-21: Autonomous Feature Decomposition
**Benefit:** *I can give the agent a massive, epic-level Spec, and it will automatically break it down into a DAG of small, testable sub-components before writing any code.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-21:** Base Integration Contract defined in [US-21_integration.md](topics/topic_08_integration/US-21_integration.md)
    *   `[ ]` **US-2 Core** *(provides Interactive Drafter)*
    *   `✅` **D-INTL-02:** Feature Decomposition
    *   `✅` **D-INTL-03:** Explicit Plan Phase
*   **Sub-Story Add-Ons:**
    *   🟢 **Recursive Planning:**
        *   `✅` **INT-US-21-SF01:** Sub-Story Integration (Complete)
        *   `✅` **C-INTL-01:** Iterative Decomposition

### 🟡 US-22: Polyglot Contract Enforcement
**Benefit:** *SpecWeaver mathematically proves that my Python microservice didn't break the REST/gRPC contract of my Rust worker.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-22:** Base Integration Contract defined in [US-22_integration.md](topics/topic_08_integration/US-22_integration.md)
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **A-VAL-01:** Protocol/Schema Analyzers (.proto, openapi)
    *   `[ ]` **C-VAL-04:** Traceability Matrix Check
*   **Sub-Story Add-Ons:**
    *   🔴 **Mathematical Speed & Security:**
        *   `[ ]` **INT-US-22-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-VAL-04:** Rust PyO3 Validations (Massive performance scale for deep contract checking)

### 🟡 US-23: Enterprise Tool Extension (MCP)
**Benefit:** *I can instantly plug SpecWeaver into my company's internal tools (Jira, Confluence) using the Model Context Protocol without writing custom Python adapters.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-23:** Base Integration Contract defined in [US-23_integration.md](topics/topic_08_integration/US-23_integration.md)
    *   `✅` **US-4 Core** *(provides Flow Engine for E2E execution)*
    *   `✅` **C-INTL-02:** MCP Client Architecture
*   **Sub-Story Add-Ons:**
    *   🔴 **Strict Security Gating:**
        *   `[ ]` **INT-US-23-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-INTL-05:** Dynamic Tool Gating via Archetypes

### 🟡 US-24: Behavioral Scenario Verification
**Benefit:** *SpecWeaver runs parallel behavioral verification pipelines to prove the generated code actually solves the business scenario, not just syntax tests.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-24:** Base Integration Contract defined in [US-24_integration.md](topics/topic_08_integration/US-24_integration.md)
    *   `[ ]` **US-3 Core** *(provides QA Runner)*
    *   `✅` **B-FLOW-01:** Scenario Testing Pipeline
    *   `[ ]` **D-VAL-01:** QA Runner Tool
*   **Sub-Story Add-Ons:**
    *   🔴 **Intelligent Resolution:**
        *   `[ ]` **INT-US-24-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-INTL-07:** Error Attribution Arbiter

### 🟢 US-25: Compliance & Constitution Governance
**Benefit:** *I can enforce project-wide rules (Constitutions) and domain-specific profiles (e.g., 'Web App' vs 'ML Model') that dynamically override agent behavior.*
*   **Core Required (MVS):**
    *   `✅` **INT-US-25:** Base Integration Contract defined in [US-25_integration.md](topics/topic_08_integration/US-25_integration.md)
    *   `✅` **C-VAL-01:** Constitution Artifact
    *   `✅` **C-VAL-02:** Domain Profiles
*   **Sub-Story Add-Ons:**
    *   🔴 **Dynamic Risk Controls:**
        *   `[ ]` **INT-US-25-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-VAL-02:** Custom Rule Paths
        *   `[ ]` **D-VAL-04:** Adaptive Assurance Standards
        *   `[ ]` **C-VAL-03:** Dynamic Risk Rulesets

---

### 🟡 US-26: Fleet-Wide CVE Remediation
**Benefit:** *When a zero-day vulnerability drops, SpecWeaver instantly scans the polyglot AST across all repositories to find every usage of the vulnerable function, and safely refactors the implementation across the entire fleet.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-26:** Base Integration Contract defined in [US-26_integration.md](topics/topic_08_integration/US-26_integration.md)
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **B-SENS-06:** OSV Vulnerability Feed Ingestion
*   **Sub-Story Add-Ons:**
    *   🔴 **Massive Scale Orchestration:**
        *   `[ ]` **INT-US-26-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-INTL-05:** Multi-Repo Refactoring Orchestration

### 🟡 US-27: Autonomous Production Self-Healing
**Benefit:** *SpecWeaver hooks directly into Datadog/Sentry. When a production exception fires, it reads the stack trace, uses the Knowledge Graph to pinpoint the failing AST node, and autonomously drafts a Hotfix Spec and PR to resolve the crash.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-27:** Base Integration Contract defined in [US-27_integration.md](topics/topic_08_integration/US-27_integration.md)
    *   `✅` **US-4 Core** *(provides Flow Engine)*
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **A-SENS-05:** APM Telemetry Ingestion (Sentry/Datadog)
*   **Sub-Story Add-Ons:**
    *   🔴 **Infinite Loop Protection:**
        *   `[ ]` **INT-US-27-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-FLOW-04:** Blast-Radius Circuit Breaker (Prevents bad hotfixes from cascading)

### 🟢 US-28: Agent-Native Issue & State Tracker
**Benefit:** *AI Agents can seamlessly hand over complex tasks to one another and prevent context degradation by storing session state, active tasks, and blockers in a structured, local SQLite Memory Bank.*
*   **Core Required (MVS):**
    *   `✅` **INT-US-28:** Base Integration Contract defined in [US-28_integration.md](topics/topic_08_integration/US-28_integration.md) (Complete)
    *   `✅` **B-INTL-09:** Agent Memory Bank (Schema + CRUD + Resilience) — [Design](features/topic_04_intelligence/B-INTL-09/B-INTL-09_design.md) (Complete)
    *   `✅` **D-INTL-06:** Context Hydration & Handover (Retrieval + Prompt Injection + Handover Protocols) — [Design](features/topic_04_intelligence/D-INTL-06/D-INTL-06_design.md) (Complete)
*   **Sub-Story Add-Ons:**
    *   🔴 **Advanced Multi-Agent Concurrency:**
        *   `[ ]` **INT-US-28-SF01:** Sub-Story Integration
        *   `[ ]` **A-EXEC-04:** Advanced Row-Level Task Locking (Pessimistic Locks, WAL2, Deadlock Detection)

---

## Technical Debt & Architecture Stories (TECH)

These stories do not add new user-facing features, but are critical epics required to ensure the platform remains stable, secure, and mathematically sound as it scales to enterprise levels.

### 🟢 TECH-001: Domain-Driven Design Unification
**Benefit:** *SpecWeaver's internal architecture is perfectly cohesive and microservice-ready, preventing "Dumping Ground" anti-patterns and circular dependencies as the team scales.*
*   **Core Required (MVS):**
    *   `✅` **TECH-001:** [Domain-Driven Design Unification](features/topic_07_technical_debt/TECH-001/TECH-001_design.md)
        *   `✅` SF-01: Deconstruct Config Monolith
        *   `✅` SF-02: Decentralize CLI Layer
        *   `✅` SF-03: Consolidate Sandbox
*   **Verifiable Proof:**
    *   `tests/e2e/capabilities/infrastructure/test_cqrs_e2e.py`

### 🟢 TECH-002: BaseTool Meta-Class Registry
**Benefit:** *Eliminates manual tool registration and automates dependency injection bindings for all sandbox tools by utilizing `__init_subclass__`.*
*   **Core Required (MVS):**
    *   `✅` **TECH-002:** [BaseTool Meta-Class Registry](features/topic_07_technical_debt/TECH-002/TECH-002_design.md)
*   **Verifiable Proof:**
    *   `tests/integration/sandbox/test_dispatcher_sf3_integration.py`

### 🟢 TECH-003: Structural Refactoring of Workspace AST Module
**Benefit:** *Crystal clear boundary separation between mechanical Tree-Sitter extraction and semantic ontology mapping.*
*   **Core Required (MVS):**
    *   `✅` **TECH-003:** [Structural Refactoring of Workspace AST Module](features/topic_07_technical_debt/TECH-003/TECH-003_design.md)

### 🟢 TECH-004: Architectural Analysis & Refactoring of `sw graph build` CLI
**Benefit:** *Strips hardcoded logic from the CLI, enabling pure headless execution of the Graph Builder from any background Atom.*
*   **Core Required (MVS):**
    *   `✅` **TECH-004:** [Architectural Analysis & Refactoring of `sw graph build` CLI](features/topic_07_technical_debt/TECH-004/TECH-004_design.md)

### 🟢 TECH-005: Database Table Prefix Harmonization
**Benefit:** *All database tables use a consistent domain-prefix naming convention, preventing naming collisions and making schema ownership crystal clear as domain count grows.*
*   **Core Required (MVS):**
    *   `✅` **TECH-005:** [Database Table Prefix Harmonization](features/topic_07_technical_debt/TECH-005/TECH-005_design.md)
        *   `✅` SF-1: Model Refactoring
        *   `✅` SF-2: Alembic Migration
*   **Verifiable Proof:**
    *   `tests/unit/alembic/test_af60fd3509a2_tech_005_rename_tables.py`

### 🟢 TECH-006: Context Loading Pipeline Refactoring
**Benefit:** *Eliminates business logic from CLI layers, kills the cross-interface spider web of private helper imports, and reduces RunContext from a 23-field God Object to a lean execution context.*
*   **Core Required (MVS):**
    *   `✅` **TECH-006:** [Context Loading Pipeline Refactoring](features/topic_07_technical_debt/TECH-006/TECH-006_design.md)
*   **Dependency:** D-INTL-06 SF-02 (Prompt Factory) — the highest-ROI refactoring (moving constitution/standards loading inside the factory) requires the factory to exist first.
*   **Discovered during:** D-INTL-06 Red Team Cycle 4 pattern analysis.

### 🟢 TECH-007: PromptBuilder Input Escaping
**Benefit:** *Hardens the prompt assembly layer against prompt injection by ensuring all string rendering uses proper escaping.*
*   **Core Required (MVS):**
    *   `✅` **TECH-007:** [PromptBuilder Input Escaping](features/topic_07_technical_debt/TECH-007/TECH-007_design.md) (Tracked as cross-cutting tech debt)
*   **Discovered during:** D-INTL-06 Red Team Cycle 1 pattern analysis.

### 🟢 TECH-008: Architectural Documentation Modularization
**Benefit:** *Transforms the impenetrable 46KB `architecture_reference.md` monolith into a visually-rich, GitHub-publishable static site structure perfectly aligned with Domain-Driven Design.*
*   **Core Required (MVS):**
    *   `✅` **TECH-008:** [Architectural Documentation Modularization](features/topic_07_technical_debt/TECH-008/TECH-008_design.md)

### 🟢 TECH-009: Git & Filesystem Subprocess Migration
**Benefit:** *Eliminates the last raw `subprocess.run()` calls from the sandbox by migrating GitExecutor and ripgrep search to SubprocessExecutor, gaining env isolation, credential stripping, telemetry, and timeout escalation for free.*
*   **Core Required (MVS):**
    *   `✅` **TECH-009:** [Git & Filesystem Subprocess Migration](features/topic_07_technical_debt/TECH-009/TECH-009_design.md)
        *   `✅` SF-01: GitExecutor Subprocess Migration (constructor-injected `SubprocessExecutor`, backward-compatible default)
        *   `✅` SF-02: Filesystem Search (ripgrep) Subprocess Migration (`grep_content`/`_grep_ripgrep` gain an optional `executor` param)
*   **Origin:** E-EXEC-01 backlog (follow-up ticket)
*   **Deferred future scope (found during C-EXEC-02 SF-1 pre-commit, not yet a numbered SF):**
    *   `assurance/validation/interfaces/cli_drift.py`'s `git diff --cached` query — kept on raw `subprocess` with a documented `noqa: TID251`. Routing it through `sandbox.git`'s `GitExecutor` would be the architecturally-correct fix (narrower coupling than a direct `SubprocessExecutor` import), but requires opening a new `assurance.validation` → `sandbox` dependency in `tach.toml` that doesn't exist today — a real architecture decision, not a lint fix.
    *   `assurance/standards/discovery.py`'s `git ls-files` query — same treatment, `noqa: TID251` with a documented reason. This module's `context.yaml` **explicitly forbids** `specweaver/sandbox/*` ("High-level orchestrators must never bypass the flow engine to natively execute raw processes") — the correct long-term fix is routing through the flow engine (e.g. a `GitAtom`-based pipeline step), not a direct sandbox import at all.

### 🔴 TECH-010: MCP Persistent-Process Executor Migration
**Benefit:** *Closes the last raw `subprocess.Popen()` call in the sandbox (`mcp/core/executor.py`) by giving `SubprocessExecutor` — or a sibling class — a long-lived, bidirectional streaming-process mode, so `MCPExecutor`'s JSON-RPC-over-stdio bridge gains the same env isolation, credential stripping, and telemetry the rest of the sandbox already has.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-010:** MCP Persistent-Process Executor Migration (design doc not yet written)
*   **Origin:** Found during C-EXEC-02 SF-1 pre-commit gate (2026-07-13) while auditing repo-wide TID251 violations. `MCPExecutor` keeps a subprocess alive across many `call_rpc()` calls (background reader thread, persistent stdin/stdout pipes) — architecturally incompatible with `SubprocessExecutor.execute()`, which is a one-shot blocking call (`proc.communicate()`, waits for process exit). Migrating it onto the existing one-shot executor would break the MCP bridge, not just risk a regression — this needs its own design for a persistent/streaming-process abstraction. Currently exempted via a documented `noqa: TID251` in `mcp/core/executor.py`.

### 🔴 TECH-011: Load-Time Params Validation for All Pipeline Step Types
**Benefit:** *Gives every pipeline step type fast, load-time feedback on malformed/missing `params` — consistent with how `PipelineDefinition.validate_flow()` already fails fast on invalid `(action, target)` combinations — instead of a mistyped param (e.g. a step-level key that should be nested under `params:`) silently surfacing as a confusing runtime handler error, potentially much later in a long, HITL-gated pipeline.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-011:** [Load-Time Params Validation for All Pipeline Step Types](features/topic_07_technical_debt/TECH-011/TECH-011_design.md) (design doc not yet written)
*   **Origin:** Found during C-EXEC-02 SF-2's implementation-plan Phase 4 (2026-07-14). SF-2 deliberately did NOT special-case load-time validation for `action: bash` steps' `params.script` (would have introduced the first action-specific exception to the engine's otherwise-uniform "params are opaque until a handler runs at execution time" behavior) — this ticket tracks doing it properly, for all step types uniformly, as its own design.

