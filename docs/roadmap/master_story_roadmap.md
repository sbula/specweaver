# Master User Story Roadmap

This is the unified, single-numbering format (US-1 to US-18) covering the entire lifespan of the platform.

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
*The engineering team must select ONE of the following candidates as the next primary objective. Do not start a new candidate until the current one is `🟢 Completed`.*

> **Refreshed 2026-07-28** (US-21 delivered → left the queue; `C-FLOW-12` minted for the
> `INT-US-21-SF02` add-on, sequenced behind `C-EXEC-07`, and no longer gated on `TECH-014`).
> **This queue does not route technical debt.** The backlog pass this note used to call for is
> done: **10 of 41 TECH tickets are open**, and only one still asserts a claim against a candidate
> below — see **Debt Sequencing**.
> *The queue is the decision surface: unlike story entries, each candidate carries the full routing
> case (pros / cons / ROI). Deep detail still lives in the linked topic/integration docs.*

1. **Rubrics-as-Content (`C-VAL-05`)** ← MIDDLE-WAY FIRST BITE
   * **Features:** `C-VAL-05` — battery engine stays code; semantic judgment content → versioned, DAL-gated rubric files. Prereqs: none. Details: [topic_05](topics/topic_05_validation.md).
   * **Pros:** Low-risk (no execution-path change); establishes the "engine hard / content soft" precedent the approved middle-way direction rests on; substrate for `B-VAL-03`, `E-VAL-04`, `B-INTL-08`.
   * **Cons:** No epic unlock; payoff is architectural, invisible to the CLI user on day 1.
   * **ROI:** **Medium-high** — small, well-bounded effort that de-risks and sequences the two larger middle-way builds (`C-FLOW-11`, `C-INTL-06` deliberately queue AFTER this proves the pattern).
2. **AST Prompt Injection Sanitization (`E-VAL-03`)** ← SECURITY MANDATE (may preempt 1)
   * **Features:** `E-VAL-03`. Prereqs: none.
   * **Pros:** Protects the validation/LLM pipeline from instructions embedded in analyzed source. Urgency INCREASED AGAIN: `INT-US-24` put LLM-authored failure traces + verdict feedback into arbitration and regeneration prompts (flagged at every SF's Red/Blue as exactly this class), on top of the autonomous DAL-escalated US-3 flows.
   * **Cons:** Hardening only — no epic unlock, no new user-visible capability.
   * **ROI:** **Risk-driven** — medium effort vs. closing the platform's widest-known attack class while three autonomous LLM loops are already live; value grows with every new LLM-consuming feature shipped before it.
3. **Token-Burn Circuit Breakers (`B-FLOW-05` + `INT-US-04-SF02`)** ← FINANCIAL SAFETY
   * **Features:** `B-FLOW-05` + `INT-US-04-SF02`. Prereqs: none. Details: [topic_03](topics/topic_03_flow_engine.md).
   * **Pros:** Prevents runaway LLM cost (EDoS) natively in the Flow Engine — elevated relevance: the autonomous US-3 loop AND the US-24 dual-pipeline loop (which re-runs whole verification rounds on loop_back) are live; `C-FLOW-11`'s budget-cap NFR needs exactly this substrate.
   * **Cons:** Hardening; no epic unlock.
   * **ROI:** **Risk-driven** — modest effort caps the worst-case cost of every existing and future loop; currently the only guards are per-step `max_retries`, not spend.
4. **DAL-Escalated Isolation for Pipeline Runs (`C-EXEC-07` + `INT-US-09-SF06`)** ← DAL PARITY (minted 2026-07-24)
   * **Features:** `C-EXEC-07` (pipeline-aware allow-list derivation + dual-fan-out-in-worktree + `sw run`/`sw resume` escalation wiring) integrated by `INT-US-09-SF06`. Prereqs: `C-EXEC-06` ✅. Details: [topic_06](topics/topic_06_sandbox.md) / [US-09_integration.md](topics/topic_08_integration/US-09_integration.md).
   * **Pros:** Closes the asymmetry the PO question exposed: the tool's most untrusted execution surface (LLM-derived scenario tests over LLM-generated code, now LIVE via `sw run scenario_integration`) has the weakest default; also contains scenario artifact droppings + the bare-pytest collection hazard documented in the dev guide.
   * **Cons:** Engine/capability work (not integration-only); no epic unlock; allow-list derivation for arbitrary pipelines is the hard part.
   * **ROI:** **Medium** — medium-high effort for security parity + workspace hygiene; cheapest right after INT-US-24 while the run-journey context is fresh, and it batches with the same high-criticality modules (DAL Batching Rule).

> **Reserve** (integration-only epic-closers; backfill as slots free): `US-16`, `US-22`, `US-23`.
> **Not queue-eligible:** `US-17` (needs `B-VAL-04`), `US-19` (needs `C-FLOW-04`), `C-FLOW-11`/`C-INTL-06` (sequenced behind `C-VAL-05`), `TECH-013` (fold into next API-touching story).

### 🔧 Debt Sequencing

*Open debt only — **10 of 41 tickets**. A delivered ticket leaves this section; the permanent
record is the [TECH ledger](#-technical-debt-tech) at the foot of this file and each ticket's own
entry in [topic_07](topics/topic_07_technical_debt.md), which is also where status is decided.
Statuses appear below purely to rank the open set — keeping a delivered ticket here to narrate how
it was closed is what let this section drift for a month.*

**Asserts a claim on a queue candidate** — so picking a candidate without reading this is blind.

| Ticket | Claim | Against |
|---|---|---|
| `TECH-017` 🔴 | Ships a tier-ratio guardrail at **planning** time; recording it as a review check did not stop the next day's plan being unit-only. Evidence **re-measured 2026-08-13** — plan from the design doc's annotations, not its 2026-07-26 body, and take its cheapest-first phasing rather than one multi-session block. | **Any** candidate's planning phase |

**No claim on a candidate**

| Ticket | Where it fits |
|---|---|
| `TECH-031` 🟡 | Three chained container-prepare defects. **Latent, not live** — `execution_mode` defaults to `"host"`, and the vacuous-success shape that hid them is fixed. |
| `TECH-038` 🔴 | `INT-US-21-SUB` is registered as *Recursive Planning*; the decomposer is one flat LLM call returning a non-nestable plan. Registry-accuracy, not live — goes live when `C-FLOW-12` plans against it. From `TECH-018`. |
| `TECH-039` 🔴 | `INT-US-05-SUB` names two different delivered add-ons. The roadmap already has the right IDs (`SF03`/`SF04`); one document disagrees with the registry. Ambiguous by construction — tools route around it. |
| `TECH-044` 🔴 | 2341 over-long registry lines, frozen by R-DEPTH. The backlog it froze — redistribution across six layers, not a wrap. |
| `TECH-041` 🔴 | `C-VAL-03`'s code-level DAL override is proven link by link and never as a chain. Needs a scripted LLM; the lenient-DAL control is the load-bearing half. |
| `TECH-040` 🔴 | `sw run --verbose` is documented, threaded, stored — and never read. A lie in `--help`; a strict xfail already waits for the fix. |
| `TECH-010` 🔴 | Needs a long-lived-process executor abstraction, not a mechanical migration. Independent; fits anywhere. |
| `TECH-011` 🔴 | Load-time params validation, uniformly across every step type. Independent; fits anywhere. |
| `TECH-013` 🔴 | Not queue-eligible — fold into the next API-touching story. |

**Ordering.** The 2026-08-08 dependency chain — seven tickets contending for the same six files —
is **fully discharged**: `TECH-019` → `025` → `014` → `020` → `015` → `024` → `023`, all delivered
by 2026-08-13. Nothing open contends for a shared file, so the remaining four are independent and
`TECH-017` is the only one wanting the code work first.

> **Re-measure an audit ticket before planning it.** `TECH-018` was filed 2026-07-26 against
> evidence that INT-US-21 SF-03 invalidated **two days later**, by shipping the 24-test CLI journey
> that was the ticket's own second candidate approach; re-measuring closed it in one session
> instead of the "unknown size" it feared, and the same pass corrected three of `TECH-017`'s
> findings. Filing-day evidence for a ticket gated on *story X ships* is stale by construction.

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
        *   `✅` **B-VAL-02:** Spec Rot Interceptor
    *   🔴 **Rubrics-as-Content:**
        *   `[ ]` **INT-US-01-SF05:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-VAL-05:** Rubrics-as-Content Validation
    *   🔴 **Mathematical Speed & Security (Rust):**
        *   `[ ]` **INT-US-01-SF04:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-VAL-04:** High-Performance Rust Validation Core

### 🟢 US-2: The Interactive Drafter
*   **User Benefit:** I can have the LLM co-author a spec with me section-by-section.
*   **Core Required (MVS):**
    *   `✅` **INT-US-02:** Base Integration Contract defined in [US-02_integration.md](topics/topic_08_integration/US-02_integration.md) (Complete)
    *   `✅` **E-UI-01:** CLI Scaffold
    *   `✅` **E-SENS-01:** Loom Filesystem Tools
    *   `✅` **E-INTL-01:** LLM Adapter (Gemini)
    *   `✅` **E-INTL-02:** Spec Drafting (`sw draft`) & HITL Provider
    *   `✅` **E-INTL-03:** Spec Review Engine
    *   `✅` **D-INTL-05:** Project Metadata Injection
*   **Sub-Story Add-Ons:**
    *   🔴 **Surgical Spec Refactoring:**
        *   `[ ]` **INT-US-02-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-SENS-05:** Markdown AST Mutators
    *   🔴 **Remote UI Integration:**
        *   `[ ]` **INT-US-02-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-UI-04:** REST API - Interactive Authoring
    *   🔴 **Grill-Style Agentic Drafting** *(blocked on `C-FLOW-11`)*:
        *   `[ ]` **INT-US-02-SF03:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-INTL-07:** Agentic Interview Drafting (Grill-Style) — needs `C-FLOW-11` (hard), `C-VAL-05` (soft)

### 🟢 US-3: Autonomous Implementation
*   **User Benefit:** I can hand an approved spec to the engine, and it will generate the code, write the tests, run them, and auto-fix linting errors.
*   **Core Required (MVS):**
    *   `✅` **INT-US-03:** Base Integration Contract defined in [US-03_integration.md](topics/topic_08_integration/US-03_integration.md) (Complete)
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **US-9 Core** *(provides Zero-Trust Sandbox)*
    *   `✅` **US-28 Core** *(provides Agent State Ledger)*
    *   `✅` **D-INTL-01:** Implementation Generator
    *   `✅` **D-VAL-05:** Code Validation Rules (C01-C08, Type hints, Coverage)
    *   `✅` **D-VAL-01:** QA Runner Tool & Lint-Fix Reflection Loop
*   **Sub-Story Add-Ons:**
    *   🔴 **Multi-Language Test Support:**
        *   `[ ]` **INT-US-03-SF01:** Sub-Story Integration (Pending Design)
        *   `✅` **D-VAL-03:** Polyglot QA Runner
    *   🔴 **Visual UI Drift Detection:**
        *   `[ ]` **INT-US-03-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-VAL-05:** Multi-Modal Visual Quality Gates
    *   🔴 **Graduated Autonomy:**
        *   `[ ]` **INT-US-03-SF03:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-FLOW-11:** Graduated Autonomy (DAL-Driven Execution-Mode Dial) — needs `C-EXEC-06` ✅; sequenced behind `C-VAL-05`

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
        *   `[ ]` **INT-US-04-SF02:** [Security Defenses](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-02-security-defenses-integration-pending-design)
        *   `[ ]` **B-FLOW-05:** Token-Burn Circuit Breakers (EDoS Prevention)
    *   🟢 **Parallel Multi-Spec Execution:**
        *   `✅` **INT-US-04-SF03:** [Parallel Multi-Spec Execution](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-03-parallel-multi-spec-execution-integration-pending-design)
        *   `✅` **C-FLOW-03:** Multi-Spec Pipeline Fan-Out
    *   🟢 **Context Mention Highlighting:**
        *   `✅` **INT-US-04-SF04:** [Context Mention Highlighting](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-04-context-mention-highlighting-integration-pending-design)
        *   `✅` **C-SENS-01:** Auto Spec-Mention Detection
    *   🟡 **Advanced Routing & Conditional Flows:**
        *   `[ ]` **INT-US-04-SF05:** [Advanced Routing](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-05-advanced-routing--conditional-flows-integration-pending-design)
        *   `[ ]` **C-FLOW-10:** Deferred Router Mapping Capabilities
        *   `✅` **C-FLOW-05:** Interactive Gate Variables (HITL)
    *   🔴 **Infinite Memory Management:**
        *   `[ ]` **INT-US-04-SF06:** [Infinite Memory Management](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-06-infinite-memory-management-integration-pending-design)
        *   `[ ]` **C-INTL-04:** Conversation Summarization (Token compression)
    *   🔴 **Remote UI Integration:**
        *   `[ ]` **INT-US-04-SF07:** [Remote UI Integration](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-07-remote-ui-integration-pending-design)
        *   `[ ]` **D-UI-05:** REST API - Enterprise Configuration
    *   🟢 **Configurable Prompt Render Profiles:**
        *   `✅` **INT-US-04-SF08:** [Configurable Prompt Render Profiles Integration](features/topic_08_integration/INT-US-04/INT-US-04_design.md#sf-08-configurable-prompt-render-profiles-integration)
        *   `✅` **C-INTL-05:** Configurable Prompt Render Profiles
    *   🔴 **Envelope-vs-Content Prompt Externalization:**
        *   `[ ]` **INT-US-04-SF10:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-INTL-06:** Envelope-vs-Content Prompt Externalization — sequenced behind `C-VAL-05`
    *   🔴 **Declarative Dynamic Prompt Routing:**
        *   `[ ]` **INT-US-04-SF09:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-INTL-10:** Declarative Prompt Optimization

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
    *   `✅` **E-UI-02:** Web dashboard
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
    *   `✅` **US-2 Core** *(provides Interactive Drafter)*
    *   `✅` **D-SENS-01:** Topology Graph
    *   `[ ]` **D-INTL-04:** Interactive Design Questionnaire — *(2026-07-21) design as rhythm-harness + rubric content (grill-me pattern), not hardcoded question trees*
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
    *   `✅` **INT-US-09:** Base Integration Contract defined in [US-09_integration.md](topics/topic_08_integration/US-09_integration.md) (Complete)
    *   `✅` **US-5 Core** *(provides Git Worktree Bouncer)*
    *   `✅` **E-EXEC-01:** [Standard Local Execution](features/topic_06_sandbox/E-EXEC-01/E-EXEC-01_design.md)
    *   `✅` **C-EXEC-02:** Native CLI Action Nodes
*   **Sub-Story Add-Ons:**
    *   🟡 **Containerized Isolation:**
        *   `[ ]` **INT-US-09-SF01:** Sub-Story Integration (Pending Design)
        *   `✅` **D-EXEC-01:** Podman/Docker Integration
        *   `✅` **B-EXEC-01:** Ephemeral Podman Sub-Containers
    *   🔴 **Security Defenses:**
        *   `[ ]` **INT-US-09-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **E-EXEC-02:** Air-Gapped Network Egress Control
        *   `[ ]` **B-EXEC-04:** [Kernel-Enforced Resource Bounds (cgroups v2)](features/topic_06_sandbox/B-EXEC-04/B-EXEC-04_design.md)
    *   🔴 **Extreme Execution Paranoia:**
        *   `[ ]` **INT-US-09-SF03:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-EXEC-01:** Functional Agent Sandboxing (Black Box Ledgers)
    *   🔴 **Mathematical Speed & Security (Rust):**
        *   `[ ]` **INT-US-09-SF04:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-EXEC-03:** Git Worktree Bouncer C-Bindings (Rust PyO3)
    *   🟢 **Per-Run (Session) Worktree Isolation:**
        *   `✅` **INT-US-09-SF05:** Sub-Story Integration — delivered by `C-EXEC-06`; see [US-09_integration.md](topics/topic_08_integration/US-09_integration.md)
        *   `✅` **C-EXEC-06:** Per-Run (Session) Worktree Isolation
    *   🔴 **DAL-Escalated Isolation for Pipeline Runs:**
        *   `[ ]` **INT-US-09-SF06:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-EXEC-07:** DAL-Escalated Isolation for Pipeline Runs — needs `C-EXEC-06` ✅

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
        *   `✅` **B-VAL-01:** AST Drift Detection

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
        *   `✅` **A-SENS-01:** Deep Semantic Hashing (Rocket Mode streaming)
        *   `[ ]` **A-FLOW-02:** Hash-based garbage collection
        *   `[ ]` **A-INTL-04:** Memory consolidation
    *   🔴 **Microservice Federation:**
        *   `[ ]` **INT-US-11-SF04:** Sub-Story Integration (Pending Design)
        *   `[ ]` **A-SENS-04:** Federated Microservice Linkage (Cross-Repo API Graphing via strict ID prefixes)

### 🟡 US-12: Legacy Spec Extraction (Reverse-Weaving)
**Benefit:** *SpecWeaver automatically reverse-engineers and drafts Spec.md contracts by reading my old undocumented Java/C++ code.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-12:** Base Integration Contract defined in [US-12_integration.md](topics/topic_08_integration/US-12_integration.md)
    *   `✅` **US-2 Core** *(provides Spec Drafting)*
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
    *   `✅` **US-2 Core** *(provides Spec Review Engine)*
    *   `✅` **US-3 Core** *(provides QA Runner)*
    *   `[ ]` **A-INTL-01:** Pre-Generation Adversarial Spec Review
*   **Sub-Story Add-Ons:**
    *   🔴 **Mathematical Mutation Checks:**
        *   `[ ]` **INT-US-14-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-VAL-03:** Semantic Test Completeness — *(2026-07-21) design rubric-first on the `C-VAL-05` substrate*
        *   `[ ]` **A-VAL-03:** Mutation testing
    *   🔴 **Architectural Sandboxing:**
        *   `[ ]` **INT-US-14-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-EXEC-03:** Blast radius / locality enforcement
    *   🔴 **Agent Independence Protocols:**
        *   `[ ]` **INT-US-14-SF03:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-INTL-06:** Multi-Agent Isolation Patterns — needs `C-FLOW-11` + `C-EXEC-06` ✅

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
        *   `✅` **B-SENS-01:** Artifact lineage graph
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
    *   `✅` **C-FLOW-01:** Telemetry DB
    *   `✅` **D-FLOW-03:** Static Routing
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
    *   `✅` **US-3 Core** *(provides QA Runner)*
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
    *   `✅` **US-9 Core** *(provides Containerized deployment)*
    *   `[ ]` **US-13 Core** *(provides Math Validation)*
    *   `[ ]` **US-14 Core** *(provides Adversarial Review)*
    *   `[ ]` **B-UI-02:** External Proprietary Validation
*   **Sub-Story Add-Ons:**
    *   🔴 **Secure Sandboxed Operations:**
        *   `[ ]` **INT-US-18-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **D-INTL-04:** Interactive Design Questionnaire — *(2026-07-21) design as rhythm-harness + rubric content (grill-me pattern), not hardcoded question trees*
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
        *   `✅` **A-SENS-01:** Deep Semantic Hashing (Rocket Mode streaming)

### 🟡 US-20: Enterprise Architecture Enforcement
**Benefit:** *My project cannot degrade — test intensity is enforced per DAL and forbidden dependencies are blocked across the DAG.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-20:** Base Integration Contract defined in [US-20_integration.md](topics/topic_08_integration/US-20_integration.md)
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **D-SENS-01:** Topology Graph (Dependency mapping)
    *   `✅` **B-SENS-02:** Persistent Knowledge Graph Builder (SQLite)
    *   `✅` **C-EXEC-01:** Internal Layer Enforcement (Validating dependency direction)
    *   `[ ]` **B-VAL-05:** DAL Architecture Gate (Dependency tier validation)
*   **Sub-Story Add-Ons:**
    *   🔴 **Test Intensity Gating:**
        *   `[ ]` **INT-US-20-SF01:** Sub-Story Integration (Pending Design)
        *   `[ ]` **B-VAL-03:** Semantic Test Completeness (Required for DAL-B) — *(2026-07-21) design rubric-first on the `C-VAL-05` substrate*
        *   `[ ]` **A-VAL-03:** Mutation Testing Gates (Required for DAL-A)
    *   🔴 **Automated Degradation Prevention:**
        *   `[ ]` **INT-US-20-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-FLOW-09:** DAL CI/CD Risk Evaluation (Auto-rejects PRs on degradation)
    *   🔴 **DAG Visualization:**
        *   `[ ]` **INT-US-20-SF03:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-UI-01:** Pipeline visualizer (Color-codes DAG by DAL risk)


### 🟢 US-21: Autonomous Feature Decomposition
**Benefit:** *I can give the agent a massive, epic-level Spec, and it will automatically break it down into a DAG of small, testable sub-components before writing any code.*
*   **Core Required (MVS):**
    *   `✅` **INT-US-21:** Base Integration Contract defined in [US-21_integration.md](topics/topic_08_integration/US-21_integration.md)
    *   `✅` **US-2 Core** *(provides Interactive Drafter)*
    *   `✅` **D-INTL-02:** Feature Decomposition
    *   `✅` **D-INTL-03:** Explicit Plan Phase
*   **Sub-Story Add-Ons:**
    *   🟢 **Recursive Planning:**
        *   `✅` **INT-US-21-SF01:** Sub-Story Integration (Complete)
        *   `✅` **C-INTL-01:** Iterative Decomposition
    *   🔴 **Autonomous DAG Execution** *(blocked on `C-EXEC-07`; `TECH-014` cleared 2026-08-12)*:
        *   `[ ]` **INT-US-21-SF02:** Sub-Story Integration (Pending Design)
        *   `[ ]` **C-FLOW-12:** Autonomous DAG Execution

### 🟡 US-22: Polyglot Contract Enforcement
**Benefit:** *SpecWeaver mathematically proves that my Python microservice didn't break the REST/gRPC contract of my Rust worker.*
*   **Core Required (MVS):**
    *   `[ ]` **INT-US-22:** Base Integration Contract defined in [US-22_integration.md](topics/topic_08_integration/US-22_integration.md)
    *   `✅` **US-1 Core** *(provides Validation Engine)*
    *   `✅` **A-VAL-01:** Protocol/Schema Analyzers (.proto, openapi)
    *   `✅` **C-VAL-04:** Traceability Matrix Check
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
        *   `[ ]` **B-INTL-05:** Dynamic Tool Gating via Archetypes — design jointly with `C-FLOW-11`

### 🟢 US-24: Behavioral Scenario Verification
**Benefit:** *SpecWeaver runs parallel behavioral verification pipelines to prove the generated code actually solves the business scenario, not just syntax tests.*
*   **Core Required (MVS):**
    *   `✅` **INT-US-24:** Base Integration Contract defined in [US-24_integration.md](topics/topic_08_integration/US-24_integration.md) (Complete)
    *   `✅` **US-3 Core** *(provides QA Runner)*
    *   `✅` **B-FLOW-01:** Scenario Testing Pipeline
    *   `✅` **D-VAL-01:** QA Runner Tool
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
        *   `✅` **D-VAL-02:** Custom Rule Paths
        *   `✅` **D-VAL-04:** Adaptive Assurance Standards
        *   `✅` **C-VAL-03:** Dynamic Risk Rulesets

---

### 🟡 US-26: Fleet-Wide CVE Remediation
**Benefit:** *When a zero-day drops, every usage of the vulnerable function is found across all repositories and refactored fleet-wide.*
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
**Benefit:** *A production exception becomes a Hotfix Spec and PR on its own — the stack trace resolves to an AST node through the Knowledge Graph.*
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
**Benefit:** *Agents hand complex tasks to one another without context degrading — session state, tasks and blockers live in a local Memory Bank.*
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
    *   `[ ]` **TECH-010:** [MCP Persistent-Process Executor Migration](features/topic_07_technical_debt/TECH-010/TECH-010_design.md)
    *   `[ ]` **TECH-011:** [Load-Time Params Validation for All Pipeline Step Types](features/topic_07_technical_debt/TECH-011/TECH-011_design.md)
    *   `✅` **TECH-012:** [Multi-Step Git-Worktree Isolation is Broken (Reconcile Never Commits; Crashes on Step 2)](features/topic_07_technical_debt/TECH-012/TECH-012_design.md)
    *   `[ ]` **TECH-013:** [API Composition Roots Do Not Resolve Worktree-Isolation Policy](features/topic_07_technical_debt/TECH-013/TECH-013_design.md)
    *   `✅` **TECH-014:** [Fan-Out RunContext Isolation (Concurrent Sub-Run State Corruption)](features/topic_07_technical_debt/TECH-014/TECH-014_design.md)
    *   `✅` **TECH-015:** [Retire Grab-Bag Modules (Name-Says-Nothing Refactor)](features/topic_07_technical_debt/TECH-015/TECH-015_design.md)
    *   `✅` **TECH-016:** [Unified Artifact Writer & Serialization Format Enforcement](features/topic_07_technical_debt/TECH-016/TECH-016_design.md)
    *   `[ ]` **TECH-017:** [Integration-Contract Proof Audit (Test Tier Must Match Story Tier)](features/topic_07_technical_debt/TECH-017/TECH-017_design.md)
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
    *   `[ ]` **TECH-031:** [Container Prepare Phase Has Never Installed a Toolchain](features/topic_07_technical_debt/TECH-031/TECH-031_design.md)
    *   `✅` **TECH-032:** [Non-Python QA Runners Report an Absent Toolchain as Success](features/topic_07_technical_debt/TECH-032/TECH-032_design.md)
    *   `✅` **TECH-033:** [A Step's Retry Budget Resets on Every `sw resume`](features/topic_07_technical_debt/TECH-033/TECH-033_design.md)
    *   `✅` **TECH-034:** [Split the AST Parser Hierarchy by Language Paradigm](features/topic_07_technical_debt/TECH-034/TECH-034_design.md)
    *   `✅` **TECH-035:** [Chronically Failing Class-Health Gate](features/topic_07_technical_debt/TECH-035/TECH-035_design.md)
    *   `✅` **TECH-036:** [Lineage Telemetry Takes Down a Lint Fix That Already Succeeded](features/topic_07_technical_debt/TECH-036/TECH-036_design.md)
    *   `✅` **TECH-037:** [Duplicated Code Is Found Only By Accident](features/topic_07_technical_debt/TECH-037/TECH-037_design.md)
    *   `[ ]` **TECH-038:** [Registry Claims Recursive Decomposition the Capability Does Not Implement](features/topic_07_technical_debt/TECH-038/TECH-038_design.md)
    *   `[ ]` **TECH-039:** [One Identifier Names Two Delivered Add-Ons (`INT-US-05-SUB` Collision)](features/topic_07_technical_debt/TECH-039/TECH-039_design.md)
    *   `[ ]` **TECH-040:** [`sw run --verbose` Is a Dead Flag](features/topic_07_technical_debt/TECH-040/TECH-040_design.md)
    *   `[ ]` **TECH-041:** [The Code-Level DAL Override Is Unproven End to End](features/topic_07_technical_debt/TECH-041/TECH-041_design.md)
    *   `[ ]` **TECH-044:** [Registry Entries Carry Content Belonging Four Layers Down](features/topic_07_technical_debt/TECH-044/TECH-044_design.md)
