# Master User Story Roadmap

This is the unified, single-numbering format (US-1 to US-18) covering the entire lifespan of the platform.

### Story Status Flags
*   🟢 **Completed** (All Core MVS and Sub-Story Add-Ons are 100% delivered)
*   🟡 **In Progress** (Active development, or Core is done but Add-Ons remain)
*   🔴 **Pending** (Core MVS is not yet delivered)

Following the **"Good Enough" principle**, every User Story is strictly divided into:
1. **Core Required (MVS):** The absolute minimum required to achieve the user benefit.
2. **Sub-Story Add-Ons:** Optional, self-contained enhancements that group technical features into deliverable improvements.

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
**Benefit:** *I can write a spec in Markdown and mathematically prove its structural quality before writing any code.*
*   **Core Required (MVS):**
    *   `✅` **E-UI-01:** CLI Scaffold
    *   `✅` **E-SENS-01:** Loom Filesystem Tools
    *   `✅` **E-VAL-01:** Validation Engine (Foundation)
    *   `✅` **E-INTL-01:** LLM Adapter (Gemini)
*   **Sub-Story Add-Ons:**
    *   **Enforce Internal Architecture:**
        *   `✅` **C-EXEC-01:** Internal Layer Enforcement
        *   `[ ]` CLI Command Architecture Separation (Discovery vs Validation)
    *   **Configurable Multi-Stage Reviews:**
        *   `✅` **E-VAL-02:** Auto-discover Standards
        *   `[ ]` E-VAL-02 Multi-stage Reviews
    *   **Mathematical Speed & Security (Rust):**
        *   `[ ]` Static Validation Rule Pipelines (Rust PyO3)

### 🟡 US-2: The Interactive Drafter
**Benefit:** *I can have the LLM co-author a spec with me section-by-section, interactively prompting me for missing context.*
*   **Core Required (MVS):**
    *   `✅` **E-UI-01:** CLI Scaffold
    *   `✅` **E-SENS-01:** Loom Filesystem Tools
    *   `✅` **E-INTL-01:** LLM Adapter (Gemini)
    *   `✅` **E-INTL-02:** Spec Drafting (`sw draft`) & HITL Provider
    *   `✅` **E-INTL-02:** Spec Review Engine
*   **Sub-Story Add-Ons:**
    *   **Surgical Spec Refactoring:**
        *   `[ ]` B-INTL-01 Markdown AST Mutators

### 🟡 US-3: Autonomous Implementation
**Benefit:** *I can hand an approved spec to the engine, and it will generate the code, write the tests, run them, and auto-fix linting errors.*
*   **Core Required (MVS):**
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **D-INTL-01:** Implementation Generator
    *   `✅` **D-INTL-01:** Code Validation Rules (C01-C08, Type hints, Coverage)
    *   `✅` **D-VAL-01:** QA Runner Tool & Lint-Fix Reflection Loop
*   **Sub-Story Add-Ons:**
    *   **Multi-Language Test Support:**
        *   `[ ]` D-VAL-03 Polyglot QA Runner
    *   **Visual UI Drift Detection:**
        *   `[ ]` 4.11 Multi-Modal Visual Quality Gates / V-Series <!-- TODO: investigate orphaned legacy ID today in the evening -->

### 🟡 US-4: Context-Aware Flow Orchestration
**Benefit:** *I can define complex multi-step workflows (draft → review → code → test) and run them autonomously with the agent aware of cross-file dependencies.*
*   **Core Required (MVS):**
    *   `✅` **E-VAL-01:** Validation Engine
    *   `✅` **D-SENS-01:** Topology Graph (`context.yaml`)
    *   `✅` **E-FLOW-01:** SQLite Config DB & Overrides
    *   `✅` **Step 9:** Context-Enriched Prompts (Token Budgeting, Injection Selectors)
    *   `✅` **E-FLOW-02:** YAML Pipeline Models
    *   `✅` **D-FLOW-01:** SQLite Pipeline Runner & State Persistence
    *   `✅` **D-FLOW-02:** `sw run` CLI & Enterprise Logging
*   **Sub-Story Add-Ons:**
    *   **Parallel Multi-Spec Execution:**
        *   `✅` **C-FLOW-03:** Multi-Spec Pipeline Fan-Out
    *   **Context Mention Highlighting:**
        *   `✅` **C-SENS-01:** Auto Spec-Mention Detection
    *   **Advanced Routing & Conditional Flows:**
        *   `[ ]` C-FLOW-02 Deferred Router Mapping Capabilities
    *   **Infinite Memory Management:**
        *   `[ ]` C-INTL-04 Conversation Summarization (Token compression)

### 🟡 US-5: Polyglot Code Understanding
**Benefit:** *SpecWeaver natively understands the deep syntax of my codebase across multiple languages, allowing it to extract symbols securely instead of guessing at raw text.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Config & Flow Engine)*
    *   `✅` **E-SENS-02 / D-SENS-02:** Context Ledgers & Workspace Boundaries
    *   `✅` **D-SENS-02:** Base Tree-Sitter AST Skeleton Extractor
    *   `✅` **C-FLOW-02:** Router-based flow control
    *   `✅` **D-EXEC-02:** Git Worktree Bouncer (Safe diff striping)
    *   `✅` **D-SENS-03:** Enterprise Polyglot Extraction (Go, Kotlin, C/C++, Rust, Java)
*   **Sub-Story Add-Ons:**
    *   **Mathematical Speed & Security (Rust):**
        *   `[ ]` Polyglot AST Extractor via Rayon (Rust PyO3)

---

### 🔴 US-6: The Remote Dashboard (Tablet on a Train)
**Benefit:** *I can review specs and control SpecWeaver pipelines from my browser on a tablet, without needing to run the heavy AI engine locally.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Flow Engine)*
    *   `✅` **C-FLOW-02:** Router-based flow control
    *   `[ ]` **D-UI-01:** `sw serve` REST API Server
    *   `[ ]` **E-UI-02:** Web dashboard
*   **Sub-Story Add-Ons:**
    *   **Strict UI Data Contracts:**
        *   `[ ]` D-UI-02 Structured output schemas
        *   `[ ]` 3.34b REST API Sync <!-- TODO: investigate orphaned legacy ID today in the evening -->
    *   **Live Pipeline Streaming:**
        *   `[ ]` B-UI-01 Real-Time Feedback Sensor Dashboard

### 🔴 US-7: The IDE Copilot (VS Code)
**Benefit:** *I can interact with the engine and approve/reject generated code seamlessly inside VS Code without switching to the terminal.*
*   **Core Required (MVS):**
    *   `✅` **US-4 Core** *(provides Flow Engine)*
    *   `✅` **C-FLOW-02:** Router-based flow control
    *   `[ ]` **D-UI-01:** `sw serve` REST API Server
    *   `[ ]` **D-UI-03:** VS Code Extension
*   **Sub-Story Add-Ons:**
    *   **Strict UI Data Contracts:**
        *   `[ ]` D-UI-02 Structured output schemas
        *   `[ ]` 3.34b REST API Synchronization <!-- TODO: investigate orphaned legacy ID today in the evening -->
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
**Benefit:** *The agent is physically incapable of destroying my host machine, and its execution memory is perfectly deterministic.*
*   **Core Required (MVS):**
    *   `✅` **US-3 Core** *(provides QA Runner)*
    *   `✅` **US-5 Core** *(provides Git Worktree Bouncer)*
    *   `[ ]` **B-EXEC-01 / 4.9:** Containerized deployment (Podman/Docker)
    *   `[ ]` **C-EXEC-02:** Native CLI Action Nodes
*   **Sub-Story Add-Ons:**
    *   **Extreme Execution Paranoia:**
        *   `[ ]` A-EXEC-01 Functional Agent Sandboxing (Black Box Ledgers)
        *   `[ ]` 4.5 Agent isolation patterns <!-- TODO: investigate orphaned legacy ID today in the evening -->
    *   **Mathematical Speed & Security (Rust):**
        *   `[ ]` Git Worktree Bouncer C-Bindings (Rust PyO3)

### 🔴 US-10: The Monolith Dependency Visualizer
**Benefit:** *I can instantly see a visual map of my entire 20-year-old C++ monolith's God Nodes and dependencies.*
*   **Core Required (MVS):**
    *   `✅` **US-5 Core** *(provides Polyglot Extraction)*
    *   `[ ]` **B-SENS-02 / A-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
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
    *   **Infinite Scale Management:**
        *   `[ ]` A-SENS-01 Deep Semantic Hashing (Rocket Mode streaming)
        *   `[ ]` A-FLOW-02 Hash-based garbage collection
        *   `[ ]` A-INTL-04 Memory consolidation

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

### 🔴 US-13: Financial-Grade Math Proofs
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
        *   `[ ]` B-VAL-03 / A-VAL-03 Semantic Test Completeness & Mutation testing
    *   **Architectural Sandboxing:**
        *   `[ ]` B-EXEC-03 Blast radius / locality enforcement

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
    *   `[ ]` **C-FLOW-01 / D-FLOW-03:** Telemetry DB & Static Routing
*   **Sub-Story Add-Ons:**
    *   **Dynamic Data-Driven Routing:**
        *   `[ ]` A-FLOW-01 / B-INTL-04 Data-driven routing recommendations & Dynamic AI Arbiter
    *   **Friction Analytics Dashboard:**
        *   `[ ]` C-UI-03 Task-type cost analytics dashboard
        *   `[ ]` B-FLOW-03 Deterministic friction detection (git diff math)
        *   `[ ]` 5.5a HITL root-cause tagging <!-- TODO: investigate orphaned legacy ID today in the evening -->
    *   **Enterprise Thought Observability:**
        *   `[ ]` B-FLOW-02 OpenTelemetry Agent Tracing

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
        *   `[ ]` 3.41 Industry Standard Bridges (Pact.io for consumer-driven contracts) <!-- TODO: investigate orphaned legacy ID today in the evening -->
    *   **Distributed Topology Scaling:**
        *   `[ ]` **A-SENS-02:** Postgres (Apache AGE + pgvector) sidecar (For massive scale context)
        *   `[ ]` **A-SENS-01:** Deep Semantic Hashing (Rocket Mode streaming)
