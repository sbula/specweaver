# Master User Story Roadmap

This is the unified, single-numbering format (US-1 to US-18) covering the entire lifespan of the platform.

### Story Status Flags
*   🟢 **Completed** (All Core MVS and Sub-Story Add-Ons are 100% delivered)
*   🟡 **In Progress** (Active development, or Core is done but Add-Ons remain)
*   🔴 **Pending** (Core MVS is not yet delivered)
*   🔵 **On Hold** (Visionary, blocked by extreme complexity, or parked for re-evaluation)

Following the **"Good Enough" principle**, every User Story is strictly divided into:
1. **Core Required (MVS):** The absolute minimum required to achieve the user benefit.
2. **Sub-Story Add-Ons:** Optional, self-contained enhancements that group technical features into deliverable improvements.

---

## 🎯 Active Routing Queue
*The engineering team must select ONE of the following candidates as the next primary objective. Do not start a new candidate until the current one is `🟢 Completed`.*

1. **Candidate A: US-9 The Zero-Trust Sandbox (Security)**
   * **Pros:** Unblocks safe, autonomous code execution (`US-3`). Prevents host-machine compromise.
   * **Cons:** High infrastructure complexity (Podman/Docker orchestration).
2. **Candidate B: US-5 Baseline Code Understanding (Capability)**
   * **Pros:** Allows the agent to read existing repositories securely via AST, unblocking legacy refactoring.
   * **Cons:** Deep dependency on Tree-Sitter C-bindings.
3. **Candidate C: US-6 Pipeline Observability (Trust)**
   * **Pros:** Developers can actually see what the autonomous fleet is doing, reducing anxiety.
   * **Cons:** UI/UX heavy; does not expand core mathematical capabilities.

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

### 🟡 US-1: The Validation Engine
*   **User Benefit:** I can write a spec in Markdown and mathematically prove its structural quality before writing any code.
*   **Integration Contract:** The CLI (`E-UI-01`) must parse the file using Loom (`E-SENS-01`) and pass it to the Validation Engine (`E-VAL-01`), ensuring no unvalidated LLM generation occurs.
*   **Verifiable Proof:** `tests/e2e/capabilities/assurance/test_standards_e2e.py`
*   **Core Required (MVS):**
    *   `✅` **E-UI-01:** CLI Scaffold
    *   `✅` **E-SENS-01:** Loom Filesystem Tools
    *   `✅` **E-VAL-01:** Validation Engine (Foundation)
    *   `✅` **E-INTL-01:** LLM Adapter (Gemini)
*   **Sub-Story Add-Ons:**
    *   **Security Defenses:**
        *   `[ ]` **E-VAL-03:** AST Prompt Injection Sanitization
        *       *User Benefit:* Malicious instructions hidden in specs cannot hijack the implementation agent.
        *       *Integration Contract:* The Validation Engine must strip adversarial syntax before the prompt enters the LLM Adapter context.
        *       *Verifiable Proof:* `[Pending]`
    *   **Enforce Internal Architecture:**
        *   `✅` **C-EXEC-01:** Internal Layer Enforcement
        *   `✅` **C-EXEC-03:** Domain-Driven Module Consolidation
        *   `[ ]` **E-UI-04:** CLI Command Arch Separation (Discovery vs Validation)
    *   **Configurable Multi-Stage Reviews:**
        *   `✅` **E-VAL-02:** Auto-discover Standards
        *   `[ ]` E-VAL-02 Multi-stage Reviews
        *   `[ ]` **B-VAL-02:** Spec Rot Interceptor
    *   **Mathematical Speed & Security (Rust):**
        *   `[ ]` Static Validation Rule Pipelines (Rust PyO3)

### 🟡 US-2: The Interactive Drafter
*   **User Benefit:** I can have the LLM co-author a spec with me section-by-section.
*   **Integration Contract:** The interactive loop (`E-INTL-02`) must seamlessly hand off the generated context to the Review Engine, ensuring no manual copy-pasting is required.
*   **Verifiable Proof:** `[Pending e2e draft test]`
*   **Core Required (MVS):**
    *   `✅` **E-UI-01:** CLI Scaffold
    *   `✅` **E-SENS-01:** Loom Filesystem Tools
    *   `✅` **E-INTL-01:** LLM Adapter (Gemini)
    *   `✅` **E-INTL-02:** Spec Drafting (`sw draft`) & HITL Provider
    *   `✅` **E-INTL-02:** Spec Review Engine
    *   `[ ]` **D-INTL-05:** Project Metadata Injection
*   **Sub-Story Add-Ons:**
    *   **Surgical Spec Refactoring:**
        *   `[ ]` B-INTL-01 Markdown AST Mutators
    *   **Remote UI Integration:**
        *   `[ ]` D-UI-04 REST API - Interactive Authoring

### 🟡 US-3: Autonomous Implementation [Execution Blocker: Requires US-9]
*   **User Benefit:** I can hand an approved spec to the engine, and it will generate the code, write the tests, run them, and auto-fix linting errors.
*   **Integration Contract:** The Implementation Generator (`D-INTL-01`) must pipe natively into the QA Runner (`D-VAL-01`). The QA Runner MUST execute exclusively inside the Zero-Trust Podman Sandbox (`D-EXEC-01`).
*   **Verifiable Proof:** `[Pending e2e sandbox loop test]`
*   **Core Required (MVS):**
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **D-INTL-01:** Implementation Generator
    *   `✅` **D-INTL-01:** Code Validation Rules (C01-C08, Type hints, Coverage)
    *   `✅` **D-VAL-01:** QA Runner Tool & Lint-Fix Reflection Loop
*   **Sub-Story Add-Ons:**
    *   **Multi-Language Test Support:**
        *   `[ ]` D-VAL-03 Polyglot QA Runner
    *   **Visual UI Drift Detection:**
        *   `[ ]` A-VAL-05 Multi-Modal Visual Quality Gates

### 🟡 US-4: Context-Aware Flow Orchestration
*   **User Benefit:** I can define complex multi-step workflows (draft → review → code → test) and run them autonomously with the agent aware of cross-file dependencies.
*   **Integration Contract:** The SQLite Config DB (`E-FLOW-01`) must statefully persist outputs from the Validation Engine (`E-VAL-01`), allowing the Pipeline Runner (`D-FLOW-01`) to pass sanitized, verified context into subsequent prompt steps.
*   **Verifiable Proof:** `tests/e2e/capabilities/assurance/test_mcp_flow_e2e.py`
*   **Core Required (MVS):**
    *   `✅` **E-VAL-01:** Validation Engine
    *   `✅` **D-SENS-01:** Topology Graph (`context.yaml`)
    *   `✅` **E-FLOW-01:** SQLite Config DB & Overrides
    *   `✅` **Step 9:** Context-Enriched Prompts (Token Budgeting, Injection Selectors)
    *   `✅` **E-FLOW-02:** YAML Pipeline Models
    *   `✅` **D-FLOW-01:** SQLite Pipeline Runner & State Persistence
    *   `✅` **D-FLOW-02:** `sw run` CLI & Enterprise Logging
    *   `[ ]` **D-FLOW-04:** Unified Runner Architecture
    *   `[ ]` **E-FLOW-03:** Multi-Provider Registry
*   **Sub-Story Add-Ons:**
    *   **Security Defenses:**
        *   `[ ]` **B-FLOW-03:** Token-Burn Circuit Breakers (EDoS Prevention)
        *       *User Benefit:* The agent cannot burn my API budget if it gets stuck in an infinite Lint-Fix loop.
        *       *Integration Contract:* The Pipeline Runner must count prompt attempts and mechanically pause the execution thread, triggering a HITL gate before retry 4.
        *       *Verifiable Proof:* `[Pending]`
    *   **Parallel Multi-Spec Execution:**
        *   `✅` **C-FLOW-03:** Multi-Spec Pipeline Fan-Out
    *   **Context Mention Highlighting:**
        *   `✅` **C-SENS-01:** Auto Spec-Mention Detection
    *   **Advanced Routing & Conditional Flows:**
        *   `[ ]` C-FLOW-02 Deferred Router Mapping Capabilities
        *   `✅` **C-FLOW-05:** Interactive Gate Variables (HITL)
    *   **Infinite Memory Management:**
        *   `[ ]` C-INTL-04 Conversation Summarization (Token compression)
    *   **Remote UI Integration:**
        *   `[ ]` D-UI-05 REST API - Enterprise Configuration

### 🟡 US-5: Polyglot Code Understanding
*   **User Benefit:** SpecWeaver natively understands the deep syntax of my codebase across multiple languages, allowing it to extract symbols securely instead of guessing at raw text.
*   **Integration Contract:** The AST Skeleton Extractor (`D-SENS-02`) must natively resolve edges against the Git Worktree Bouncer (`D-EXEC-02`) to ensure extracted context accurately reflects the current filesystem state without hallucinatory paths.
*   **Verifiable Proof:** `tests/e2e/capabilities/core/test_lineage_e2e.py`
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Config & Flow Engine)*
    *   `✅` **E-SENS-02:** Context Ledgers & Workspace Boundaries
    *   `✅` **D-SENS-02:** Base Tree-Sitter AST Skeleton Extractor
    *   `✅` **C-FLOW-02:** Router-based flow control
    *   `✅` **D-EXEC-02:** Git Worktree Bouncer (Safe diff striping)
    *   `✅` **D-SENS-03:** Enterprise Polyglot Extraction (Go, Kotlin, C/C++, Rust, Java)
*   **Sub-Story Add-Ons:**
    *   **Infrastructure Understanding:**
        *   `[ ]` **C-SENS-04:** Infrastructure-as-Code Extraction (HCL2)
    *   **API Contract Understanding:**
        *   `[ ]` **C-SENS-07:** Polyglot Expansion (TypeSpec)
    *   **Intelligent Code Exclusions:**
        *   `✅` **C-SENS-02:** Smart Scan Exclusions (.specweaverignore)
    *   **Framework Native Understanding:**
        *   `✅` **B-INTL-02:** Macro Evaluator (Rust/Kotlin plugin expansion)
    *   **Mathematical Speed & Security (Rust):**
        *   `[ ]` Polyglot AST Extractor via Rayon (Rust PyO3)

---

### 🔴 US-6: The Remote Dashboard (Tablet on a Train)
**Benefit:** *I can review specs and control SpecWeaver pipelines from my browser on a tablet, without needing to run the heavy AI engine locally.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Flow Engine)*
    *   `✅` **C-FLOW-02:** Router-based flow control
    *   `[ ]` **D-UI-01:** `sw serve` Core Orchestration API
    *   `[ ]` **E-UI-02:** Web dashboard
*   **Sub-Story Add-Ons:**
    *   **Strict UI Data Contracts:**
        *   `[ ]` D-UI-02 Structured output schemas
    *   **Live Pipeline Streaming:**
        *   `[ ]` B-UI-01 Real-Time Feedback Sensor Dashboard
    *   **Remote Systems Integration:**
        *   `[ ]` D-UI-07 REST API - Systems Integration


### 🔴 US-7: The IDE Copilot (VS Code)
**Benefit:** *I can interact with the engine and approve/reject generated code seamlessly inside VS Code without switching to the terminal.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Flow Engine)*
    *   `✅` **C-FLOW-02:** Router-based flow control
    *   `[ ]` **D-UI-01:** `sw serve` Core Orchestration API
    *   `[ ]` **D-UI-03:** VS Code Extension
*   **Sub-Story Add-Ons:**
    *   **Strict UI Data Contracts:**
        *   `[ ]` D-UI-02 Structured output schemas
    *   **Real-time File Tracking:**
        *   `[ ]` E-UI-03 File watcher (Auto-re-validate specs on save)

### 🔴 US-8: The Greenfield Bootstrap Wizard
**Benefit:** *When starting a new project, an interactive wizard bounds the LLM's architecture choices so it doesn't hallucinate invalid tech stacks.*
*   **Core Required (MVS):**
    *   `✅` **US-2 Core** *(provides Interactive Drafter)*
    *   `✅` **D-SENS-01:** Topology Graph
    *   `[ ]` **D-INTL-04:** Interactive Design Questionnaire
*   **Sub-Story Add-Ons:**
    *   **Socratic Context Gathering:**
        *   `[ ]` A-INTL-03 Socratic drafting flow
    *   **Architectural De-duplication:**
        *   `[ ]` B-INTL-03 Synthetic Commons Extraction

### 🔴 US-9: The Zero-Trust Sandbox
*   **User Benefit:** The agent is physically incapable of destroying my host machine, and its execution memory is perfectly deterministic.
*   **Integration Contract:** The QA Runner (`US-3 Core`) must be forcefully injected into the Podman/Docker Integration (`D-EXEC-01`), with host filesystem mounts set strictly to read-only for source files, and write-only for designated temporary test artifacts.
*   **Verifiable Proof:** `[Pending e2e sandbox test]`
*   **Core Required (MVS):**
    *   `✅` **US-3 Core** *(provides QA Runner)*
    *   `✅` **US-5 Core** *(provides Git Worktree Bouncer)*
    *   `[ ]` **E-EXEC-01:** Standard Local Execution
    *   `✅` **D-EXEC-01:** Podman/Docker Integration
    *   `[ ]` **B-EXEC-01:** Containerized deployment (Podman/Docker)
    *   `[ ]` **C-EXEC-02:** Native CLI Action Nodes
*   **Sub-Story Add-Ons:**
    *   **Security Defenses:**
        *   `[ ]` **E-EXEC-02:** Air-Gapped Network Egress Control
        *       *User Benefit:* Prevents the agent from downloading unvetted malicious dependencies via hallucination.
        *       *Integration Contract:* The Docker daemon must physically disable external networking during the QA execution phase, allowing only pre-cached dependencies.
        *       *Verifiable Proof:* `[Pending]`
    *   **Extreme Execution Paranoia:**
        *   `[ ]` A-EXEC-01 Functional Agent Sandboxing (Black Box Ledgers)
    *   **Mathematical Speed & Security (Rust):**
        *   `[ ]` **A-EXEC-03:** Git Worktree Bouncer C-Bindings (Rust PyO3)

### 🔴 US-10: The Monolith Dependency Visualizer
**Benefit:** *I can instantly see a visual map of my entire 20-year-old C++ monolith's God Nodes and dependencies.*
*   **Core Required (MVS):**
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `[ ]` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **C-UI-01:** Pipeline visualization (`sw graph` HTML export)
*   **Sub-Story Add-Ons:**
    *   **Code-to-Spec Drift Checking:**
        *   `[ ]` B-VAL-01 AST Drift Detection

### 🔴 US-11: GraphRAG for Brownfield Scale
**Benefit:** *The agent can instantly recall exact context from 20 interacting microservices without blowing up the context window.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Context Prompts)*
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `[ ]` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **A-SENS-02:** Postgres (Apache AGE + pgvector) sidecar
    *   `[ ]` **B-SENS-03:** AST-based semantic chunking
*   **Sub-Story Add-Ons:**
    *   **Dynamic Knowledge Relevance:**
        *   `[ ]` B-FLOW-04 Hybrid RAG orchestration (composite scoring)
        *   `[ ]` A-SENS-03 Event-driven knowledge graph updates
    *   **Static Code Flow Analysis:**
        *   `[ ]` **B-SENS-04:** Static Control Flow Graph (CFG)
        *   `[ ]` **B-SENS-05:** Static Dataflow Solver
    *   **Infinite Scale Management:**
        *   `[ ]` A-SENS-01 Deep Semantic Hashing (Rocket Mode streaming)
        *   `[ ]` A-FLOW-02 Hash-based garbage collection
        *   `[ ]` A-INTL-04 Memory consolidation
    *   **Microservice Federation:**
        *   `[ ]` **A-SENS-04:** Federated Microservice Linkage (Cross-Repo API Graphing via strict ID prefixes)

### 🔴 US-12: Legacy Spec Extraction (Reverse-Weaving)
**Benefit:** *SpecWeaver automatically reverse-engineers and drafts Spec.md contracts by reading my old undocumented Java/C++ code.*
*   **Core Required (MVS):**
    *   `✅` **US-2 Core** *(provides Spec Drafting)*
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `[ ]` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **C-INTL-03:** Reverse-Weaving (`sw capture`)
*   **Sub-Story Add-Ons:**
    *   **Massive Scale Context Retrieval:**
        *   `[ ]` **A-SENS-02:** Postgres (Apache AGE + pgvector) sidecar
    *   **Automated Code Purging:**
        *   `[ ]` A-FLOW-03 Repository Entropy & Garbage Collection (finding dead code)

### 🔵 US-13: Financial-Grade Math Proofs
**Benefit:** *The agent mathematically proves its algorithms are secure before I deploy them to production, discovering 0-days natively.*
*   **Core Required (MVS):**
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `[ ]` **A-VAL-02:** Symbolic Math Validation
*   **Sub-Story Add-Ons:**
    *   **Symbolic Tree Traversal:**
        *   `[ ]` A-INTL-02 LLM-Guided Symbolic Execution
        *   `[ ]` C-SENS-03 Symbol index + anti-hallucination gate
    *   **Dynamic Memory Attacks:**
        *   `[ ]` A-EXEC-02 Tool-Augmented Security Fuzzing Harnesses

### 🔴 US-14: Adversarial Red-Teaming
**Benefit:** *An adversarial AI attacks my spec to find logic holes and edge-cases before I waste money generating bad code.*
*   **Core Required (MVS):**
    *   `✅` **US-2 Core** *(provides Spec Review Engine)*
    *   `✅` **US-3 Core** *(provides QA Runner)*
    *   `[ ]` **A-INTL-01:** Pre-Generation Adversarial Spec Review
*   **Sub-Story Add-Ons:**
    *   **Mathematical Mutation Checks:**
        *   `[ ]` B-VAL-03 Semantic Test Completeness
        *   `[ ]` A-VAL-03 Mutation testing
    *   **Architectural Sandboxing:**
        *   `[ ]` B-EXEC-03 Blast radius / locality enforcement
    *   **Agent Independence Protocols:**
        *   `[ ]` B-INTL-06 Multi-Agent Isolation Patterns

### 🔴 US-15: Enterprise Audit & Traceability
**Benefit:** *I can hand a compliance auditor a ledger that proves exactly which LLM generated which line of code based on which business requirement.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Pipeline Runner)*
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `[ ]` **B-SENS-02:** Persistent Knowledge Graph Builder
    *   `[ ]` **C-UI-02:** Traceability Matrix UX
*   **Sub-Story Add-Ons:**
    *   **Enterprise Compliance Protocols:**
        *   `[ ]` **B-SENS-01:** Artifact lineage graph
        *   `[ ]` A-UI-01 'Dark Factory' Compliance Logging
    *   **Zero-Trust ACL:**
        *   `[ ]` **B-EXEC-02:** Tiered access rights & Provenance tracking

### 🔴 US-16: AI Operations & Cost Routing
**Benefit:** *I can see exactly how much money each agent is spending, detect LLM friction, and dynamically route tasks to cheaper models.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Config DB)*
    *   `✅` **Step 9a:** Token Tracking
    *   `[ ]` **C-FLOW-01:** Telemetry DB
    *   `[ ]` **D-FLOW-03:** Static Routing
*   **Sub-Story Add-Ons:**
    *   **Dynamic Data-Driven Routing:**
        *   `[ ]` A-FLOW-01 Data-driven routing recommendations
        *   `[ ]` B-INTL-04 Dynamic AI Arbiter
    *   **Friction Analytics Dashboard:**
        *   `[ ]` C-UI-03 Task-type cost analytics dashboard
        *   `[ ]` B-FLOW-03 Deterministic friction detection (git diff math)
        *   `[ ]` C-FLOW-07 HITL Root-Cause Tagging
    *   **Enterprise Thought Observability:**
        *   `[ ]` B-FLOW-02 OpenTelemetry Agent Tracing
    *   **Remote UI Integration:**
        *   `[ ]` D-UI-06 REST API - Telemetry & Auditing

### 🔴 US-17: The SWE-Bench Guarantee
**Benefit:** *SpecWeaver proves it hasn't degraded by autonomously solving standardized SWE-Bench tickets before every release.*
*   **Core Required (MVS):**
    *   `✅` **US-3 Core** *(provides QA Runner)*
    *   `✅` **US-4 Core** *(provides CLI & Flow Engine)*
    *   `[ ]` **B-VAL-04:** Agent Platform Benchmarking (`sw eval`)
*   **Sub-Story Add-Ons:**
    *   **Continuous Integration:**
        *   `[ ]` A-UI-02 Standardized Benchmarking CI

### 🔴 US-18: Productionizing External Targets
**Benefit:** *We prove the entire platform works by using it to build and manage an external proprietary trading system.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides CLI & Flow Engine)*
    *   `✅` **US-5 Core** *(provides Worktree Bouncer & AST extractors)*
    *   `✅` **C-FLOW-03:** Multi-Spec Pipeline Fan-Out
    *   `[ ]` **US-9 Core** *(provides Containerized deployment)*
    *   `[ ]` **US-13 Core** *(provides Math Validation)*
    *   `[ ]` **US-14 Core** *(provides Adversarial Review)*
    *   `[ ]` **B-UI-02:** External Proprietary Validation
*   **Sub-Story Add-Ons:**
    *   **Secure Sandboxed Operations:**
        *   `[ ]` **D-INTL-04:** Interactive Design Questionnaire
    *   **CI/CD Pipeline Integration:**
        *   `[ ]` Custom deployment hooks

### 🔴 US-19: Microservice Fleet Orchestration
**Benefit:** *I can design, generate, and orchestrate an entire fleet of 20+ microservices, automatically keeping their API contracts and topology synchronized across independent repositories.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core**
    *   `✅` **US-5 Core**
    *   `✅` **C-FLOW-03:** Multi-Spec Pipeline Fan-Out
    *   `[ ]` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `[ ]` **C-FLOW-04:** Work Packet Bundling (Coordinated multi-agent dispatch)
*   **Sub-Story Add-Ons:**
    *   **Cross-Service Contract Validation:**
        *   `[ ]` A-VAL-06 Industry Standard Bridges
    *   **Parallel Execution Safety:**
        *   `[ ]` **C-EXEC-04:** Concurrent Git Merge Orchestration
    *   **Distributed Topology Scaling:**
        *   `[ ]` **A-SENS-02:** Postgres (Apache AGE + pgvector) sidecar (For massive scale context)
        *   `[ ]` **A-SENS-01:** Deep Semantic Hashing (Rocket Mode streaming)

### 🔴 US-20: Enterprise Architecture Enforcement
**Benefit:** *SpecWeaver mathematically prevents my project from degrading by enforcing strict test intensities (e.g., DAL-A requires mutation tests) and blocking forbidden dependencies across the DAG.*
*   **Core Required (MVS):**
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **D-SENS-01:** Topology Graph (Dependency mapping)
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (Provides deep DAG traversal)
    *   `[ ]` **C-EXEC-01:** Internal Layer Enforcement (Validating dependency direction)
    *   `[ ]` **B-VAL-05:** DAL Architecture Gate (Dependency tier validation)
*   **Sub-Story Add-Ons:**
    *   **Test Intensity Gating:**
        *   `[ ]` **B-VAL-03:** Semantic Test Completeness (Required for DAL-B)
        *   `[ ]` **A-VAL-03:** Mutation Testing Gates (Required for DAL-A)
    *   **Automated Degradation Prevention:**
        *   `[ ]` **C-FLOW-06:** DAL CI/CD Risk Evaluation (Auto-rejects PRs on degradation)
    *   **DAG Visualization:**
        *   `[ ]` **C-UI-01:** Pipeline visualizer (Color-codes DAG by DAL risk)


### 🟡 US-21: Autonomous Feature Decomposition
**Benefit:** *I can give the agent a massive, epic-level Spec, and it will automatically break it down into a DAG of small, testable sub-components before writing any code.*
*   **Core Required (MVS):**
    *   `✅` **US-2 Core** *(provides Interactive Drafter)*
    *   `✅` **D-INTL-02:** Feature Decomposition
    *   `✅` **D-INTL-03:** Explicit Plan Phase
*   **Sub-Story Add-Ons:**
    *   **Recursive Planning:**
        *   `✅` **C-INTL-01:** Iterative Decomposition

### 🔵 US-22: Polyglot Contract Enforcement
**Benefit:** *SpecWeaver mathematically proves that my Python microservice didn't break the REST/gRPC contract of my Rust worker.*
*   **Core Required (MVS):**
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **A-VAL-01:** Protocol/Schema Analyzers (.proto, openapi)
    *   `[ ]` **C-VAL-04:** Traceability Matrix Check
*   **Sub-Story Add-Ons:**
    *   **Mathematical Speed & Security:**
        *   `[ ]` **A-VAL-04:** Rust PyO3 Validations (Massive performance scale for deep contract checking)

### 🟡 US-23: Enterprise Tool Extension (MCP)
**Benefit:** *I can instantly plug SpecWeaver into my company's internal tools (Jira, Confluence) using the Model Context Protocol without writing custom Python adapters.*
*   **Core Required (MVS):**
    *   `✅` **C-INTL-02:** MCP Client Architecture
*   **Sub-Story Add-Ons:**
    *   **Strict Security Gating:**
        *   `[ ]` **B-INTL-05:** Dynamic Tool Gating via Archetypes

### 🔴 US-24: Behavioral Scenario Verification
**Benefit:** *SpecWeaver runs parallel behavioral verification pipelines to prove the generated code actually solves the business scenario, not just syntax tests.*
*   **Core Required (MVS):**
    *   `✅` **US-3 Core** *(provides QA Runner)*
    *   `✅` **B-FLOW-01:** Scenario Testing Pipeline
    *   `[ ]` **D-VAL-01:** QA Runner Tool
*   **Sub-Story Add-Ons:**
    *   **Intelligent Resolution:**
        *   `[ ]` **B-INTL-07:** Error Attribution Arbiter

### 🟡 US-25: Compliance & Constitution Governance
**Benefit:** *I can enforce project-wide rules (Constitutions) and domain-specific profiles (e.g., 'Web App' vs 'ML Model') that dynamically override agent behavior.*
*   **Core Required (MVS):**
    *   `✅` **C-VAL-01:** Constitution Artifact
    *   `✅` **C-VAL-02:** Domain Profiles
*   **Sub-Story Add-Ons:**
    *   **Dynamic Risk Controls:**
        *   `[ ]` **D-VAL-02:** Custom Rule Paths
        *   `[ ]` **D-VAL-04:** Adaptive Assurance Standards
        *   `[ ]` **C-VAL-03:** Dynamic Risk Rulesets

---

### 🔵 US-26: Fleet-Wide CVE Remediation
**Benefit:** *When a zero-day vulnerability drops, SpecWeaver instantly scans the polyglot AST across all repositories to find every usage of the vulnerable function, and safely refactors the implementation across the entire fleet.*
*   **Core Required (MVS):**
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `[ ]` **B-SENS-02:** Persistent Knowledge Graph Builder
    *   `[ ]` **B-SENS-04:** OSV Vulnerability Feed Ingestion
*   **Sub-Story Add-Ons:**
    *   **Massive Scale Orchestration:**
        *   `[ ]` **A-INTL-05:** Multi-Repo Refactoring Orchestration

### 🔵 US-27: Autonomous Production Self-Healing
**Benefit:** *SpecWeaver hooks directly into Datadog/Sentry. When a production exception fires, it reads the stack trace, uses the Knowledge Graph to pinpoint the failing AST node, and autonomously drafts a Hotfix Spec and PR to resolve the crash.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Flow Engine)*
    *   `[ ]` **B-SENS-02:** Persistent Knowledge Graph Builder
    *   `[ ]` **A-SENS-04:** APM Telemetry Ingestion (Sentry/Datadog)
*   **Sub-Story Add-Ons:**
    *   **Infinite Loop Protection:**
        *   `[ ]` **A-FLOW-04:** Blast-Radius Circuit Breaker (Prevents bad hotfixes from cascading)

---

## Technical Debt & Architecture Stories (TECH)

These stories do not add new user-facing features, but are critical epics required to ensure the platform remains stable, secure, and mathematically sound as it scales to enterprise levels.

### 🔴 TECH-01: Domain-Driven Design Unification
**Benefit:** *SpecWeaver's internal architecture is perfectly cohesive and microservice-ready, preventing "Dumping Ground" anti-patterns and circular dependencies as the team scales.*
*   **Description:** The massive refactoring effort to align the legacy `config/`, `cli/`, and `loom/` layers with the pure Domain-Driven Design (Package by Feature) principles established by the B-SENS-02 Graph Triad.
*   **Core Required (MVS):**
    *   `[ ]` **TECH-01:** [Domain-Driven Design Unification](features/topic_06_architecture/TECH-01/TECH-01_ddd_refactor.md)
