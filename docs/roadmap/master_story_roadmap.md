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
> `INT-US-21-SF02` add-on, sequenced behind `C-EXEC-07` and `TECH-014`, so it does NOT enter
> the queue yet). **This queue does not route technical debt, and the backlog now needs a pass —
> 14 open tickets, not the eight this note previously claimed.** The earlier count was
> `TECH-014`…`TECH-021`, i.e. only the ones INT-US-21 itself filed; `TECH-001`, `002`, `005`,
> `009`, `010`, `011` and `013` predate it and have never been ranked here at all. `TECH-021` has
> since been fixed (`a003b164`). Several are live defects rather than refactors, and four assert
> sequencing claims against candidates below — see **Debt sequencing**.
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

*No `TECH` ticket is a ranked candidate above — but four assert a sequencing claim on the
candidates that are, so picking a candidate without reading this makes the choice blind. Claims
are the tickets' own, restated; ranking them into the queue is a routing decision, not recorded
here. Full detail: [topic_07](topics/topic_07_technical_debt.md).*

| Ticket | Claim | Against |
|---|---|---|
| `TECH-019` 🟢 | **Delivered 2026-08-08** — claim discharged. Twelve instruction sites repaired (six more than the ticket claimed) and `check_skill_references.py` now enforces the invariant in the `doc` gate. | — |
| `TECH-017` 🔴 | Ships a tier-ratio guardrail at **planning** time; recording it as a review check did not stop the next day's plan being unit-only. | **Any** candidate's planning phase |
| `TECH-014` 🔴 | Live fan-out `RunContext` race in shipped `C-FLOW-03`; should land **before** `C-FLOW-12`. | Candidate 4 (`C-EXEC-07`) → `C-FLOW-12` |
| `TECH-020` 🔴 | `runner.py` at **exactly 600/600 RED**, `_execute_loop` 360 lines under `# noqa: C901`; sequence before `C-FLOW-12`'s fan-out work or that feature pays the tax. | Candidate 4 (`C-EXEC-07`) → `C-FLOW-12` |

**Unblocked, no claim on a candidate:** `TECH-018` 🔜 (audit-only; its precondition — INT-US-21
SF-03 committed — is now met), `TECH-015` 🔴, `TECH-016` 🔴.

**Order among the debt tickets themselves (recorded 2026-08-08).** Distinct from the claims above,
which are about feature candidates. This is a dependency order: seven tickets contend for the same
six files (`runner.py`, `runner_utils.py`, `staleness.py`, `decompose.py`, `dual_pipeline.py`,
`handlers/registry.py`), so the wrong order means doing the work twice. No status markers here on
purpose — they live on each ticket's own `### TECH-NNN` header, and duplicating them is what let
this section drift for a month.

| # | Ticket | Why it sits here |
|---|---|---|
| 1 | `TECH-019` | ✅ Done 2026-08-08. Fixed the instructions every later ticket is executed through, and shipped the checker that keeps them fixed. |
| 2 | `TECH-025` | Docs only, independent, and establishes the citation convention each ticket below meets at its own closure gate. |
| 3 | `TECH-014` | A live bug, not cleanup. Cheapest now: `TECH-006` SF-02 put its three racing fields (`run_id`, `step_records`, `pipeline_runner`) into one `RunHandle`, so each sub-run takes a copy instead of three writes interleaving. |
| 4 | `TECH-020` | Reshapes `runner.py`; removes flow's largest complexity offender and changes the import graph 6 and 7 measure. |
| 5 | `TECH-015` | Moves/renames modules, changing those imports again. |
| 6 | `TECH-024` | Measure cycles after 4 and 5. Its three isolated cycles (validation registry, llm rate-limit/factory, API layer) need no waiting; only the 6-module `core.flow` one does. |
| 7 | `TECH-023` | **Last, not first.** 3, 4 and 5 each delete complexity as a side effect — it fell 98 → 97 from `TECH-006` alone. Starting here means redoing it. |

`TECH-023` and `TECH-024` must not share a working tree: extracting helpers to cut complexity
changes imports, which is exactly what the cycle check measures, so neither number stays
attributable. `TECH-010`, `TECH-011`, `TECH-013`, `TECH-016` are independent of this chain and fit
anywhere; `TECH-017` and `TECH-018` are audits and want the code still first.
**Pre-existing, never ranked:** `TECH-001` 🟢, `TECH-002` 🟢, `TECH-005` 🟢, `TECH-009` 🟢,
`TECH-010` 🔴, `TECH-011` 🔴. *(Synced 2026-07-31 — this note had drifted from each ticket's own
`### TECH-NNN` header since 2026-07-28; statuses above now match those headers, code-verified.
2026-08-01: `TECH-001` corrected to 🟡 — SF-04 outstanding. `TECH-002` corrected to 🟡 — shipped
mechanism never matched the entry's description. `TECH-005` corrected to 🟡 — SF-3 outstanding
(raw-sqlite3 tables never prefixed). 2026-08-02: `TECH-001` corrected back to 🟢 — SF-04 landed
(commit `346f64c3`), all three circular dependencies eliminated. `TECH-005` corrected back to
🟢 — SF-3 landed (commit `4ebb89cf`), all six raw-sqlite3 tables prefixed with a zero-data-loss
migration path. 2026-08-08: `TECH-002` corrected back to 🟢 — the description defect that caused
the 🟡 was fixed in `cea3548c`; re-verified against code (explicit `ToolRegistry` in
`sandbox/registry.py`, zero `__init_subclass__` anywhere, validation layer free of sandbox imports,
proof test passing) and no work was ever outstanding. `TECH-006` closed 🟢 — SF-02 landed,
`RunContext` 32 fields → 15 attributes.)*

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
        *   `[ ]` **C-FLOW-10:** Deferred Router Mapping Capabilities
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
**Benefit:** *SpecWeaver mathematically prevents my project from degrading by enforcing strict test intensities (e.g., DAL-A requires mutation tests) and blocking forbidden dependencies across the DAG.*
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
    *   🔴 **Autonomous DAG Execution** *(blocked on `C-EXEC-07`, `TECH-014`)*:
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
        *   `✅` SF-04: Eliminate `core.config` Circular Dependencies — commit `346f64c3` (2026-08-02); `core.config` now has `depends_on = []` in `tach.toml`.
*   **Verifiable Proof:**
    *   `tests/e2e/capabilities/infrastructure/test_cqrs_e2e.py`
    *   `tests/unit/test_architecture.py::test_core_config_has_no_cross_domain_runtime_imports`
*   **Known separate gap:** `TECH-025` tracks a pre-existing FR-traceability citation gap in SF-01/02/03 (found by SF-04's own closure gate) — unrelated to this ticket's substantive claim, which is now true.

### 🟢 TECH-002: BaseTool Registry
**Benefit:** *Eliminates manual tool registration and automates dependency injection bindings for all sandbox tools via an explicit `ToolRegistry`. The originally-described `__init_subclass__` mechanism was never built — the approved design deliberately rejected it in favor of the registry actually shipped.*
*   **Core Required (MVS):**
    *   `✅` **TECH-002:** [BaseTool Registry](features/topic_07_technical_debt/TECH-002/TECH-002_design.md)
*   **Verifiable Proof:**
    *   `tests/integration/sandbox/test_dispatcher_registry_delegation.py`
*   **Known separate gap:** `TECH-025` tracks a pre-existing FR-traceability citation gap in all four sub-features — unrelated to this ticket's substantive claim, which is code-verified.

### 🟢 TECH-003: Structural Refactoring of Workspace AST Module
**Benefit:** *Crystal clear boundary separation between mechanical Tree-Sitter extraction and semantic ontology mapping.*
*   **Core Required (MVS):**
    *   `✅` **TECH-003:** [Structural Refactoring of Workspace AST Module](features/topic_07_technical_debt/TECH-003/TECH-003_design.md)

### 🟢 TECH-004: Architectural Analysis & Refactoring of `sw graph build` CLI
**Benefit:** *Strips hardcoded logic from the CLI, enabling pure headless execution of the Graph Builder from any background Atom.*
*   **Core Required (MVS):**
    *   `✅` **TECH-004:** [Architectural Analysis & Refactoring of `sw graph build` CLI](features/topic_07_technical_debt/TECH-004/TECH-004_design.md)

### 🟢 TECH-005: Database Table Prefix Harmonization
**Benefit:** *Every database table — SQLAlchemy-managed and raw-sqlite3 alike — uses a consistent domain-prefix naming convention, preventing naming collisions and making schema ownership crystal clear as domain count grows.*
*   **Core Required (MVS):**
    *   `✅` **TECH-005:** [Database Table Prefix Harmonization](features/topic_07_technical_debt/TECH-005/TECH-005_design.md)
        *   `✅` SF-1: Model Refactoring
        *   `✅` SF-2: Alembic Migration
        *   `✅` SF-3: Prefix Raw-SQLite3 Tables — commit `4ebb89cf` (2026-08-02); `nodes`/`edges`, `pipeline_runs`/`audit_log`/`state_schema_version`, `sw_reservations` renamed with a zero-data-loss migration path for pre-SF-3 installations.
*   **Verifiable Proof:**
    *   `tests/unit/alembic/test_table_prefix_migration.py`
    *   `tests/unit/graph/core/store/test_repository_schema.py`
    *   `tests/unit/core/flow/engine/test_engine_store.py::TestStoreSchema`
    *   `tests/unit/core/flow/engine/test_reservation.py`
*   **Known separate gap:** `TECH-025` tracks a pre-existing FR-traceability citation gap in SF-1/2 (found by SF-3's own closure gate) — unrelated to this ticket's substantive claim, which is now true.

### 🟢 TECH-006: Context Loading Pipeline Refactoring
**Benefit:** *Eliminates business logic from CLI layers and kills the cross-interface spider web of private helper imports. `RunContext` is down from 32 flat fields to 15 attributes — 10 flat plus 7 frozen sub-models — and `check_class_health.py` no longer reports the file at all.*
*   **Core Required (MVS):**
    *   `✅` **TECH-006:** [Context Loading Pipeline Refactoring](features/topic_07_technical_debt/TECH-006/TECH-006_design.md)
        *   `✅` SF-01: Delete All CLI Wrappers
        *   `✅` SF-02: Reduce `RunContext` God Object — 32 fields → 15 attributes.
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
*   **Deferred future scope:** see [TECH-009_design.md](features/topic_07_technical_debt/TECH-009/TECH-009_design.md) (two documented `noqa: TID251` git queries in `assurance/`).

### 🔴 TECH-010: MCP Persistent-Process Executor Migration
**Benefit:** *Closes the last raw `subprocess.Popen()` in the sandbox via a persistent/streaming-process executor mode for the MCP bridge.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-010:** [MCP Persistent-Process Executor Migration](features/topic_07_technical_debt/TECH-010/TECH-010_design.md)

### 🔴 TECH-011: Load-Time Params Validation for All Pipeline Step Types
**Benefit:** *Fast, load-time validation of every step type's `params` instead of confusing runtime handler errors.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-011:** [Load-Time Params Validation for All Pipeline Step Types](features/topic_07_technical_debt/TECH-011/TECH-011_design.md)

### 🟢 TECH-012: Multi-Step Git-Worktree Isolation is Broken (Reconcile Never Commits; Crashes on Step 2)
**Benefit:** *Multi-step untrusted loops actually run in isolation instead of crashing on step 2.*
*   **Core Required (MVS):**
    *   `✅` **TECH-012:** [Multi-Step Git-Worktree Isolation is Broken (Reconcile Never Commits; Crashes on Step 2)](features/topic_07_technical_debt/TECH-012/TECH-012_design.md)

### 🔴 TECH-013: API Composition Roots Do Not Resolve Worktree-Isolation Policy
**Benefit:** *REST-triggered pipeline runs honor the operator's `[sandbox]` worktree-isolation policy.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-013:** [API Composition Roots Do Not Resolve Worktree-Isolation Policy](features/topic_07_technical_debt/TECH-013/TECH-013_design.md)

### 🔴 TECH-014: Fan-Out RunContext Isolation (Concurrent Sub-Run State Corruption)
**Benefit:** *Lineage and telemetry from concurrent sub-runs are attributed to the sub-run that actually produced them.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-014:** [Fan-Out RunContext Isolation (Concurrent Sub-Run State Corruption)](features/topic_07_technical_debt/TECH-014/TECH-014_design.md)
*   **Sequencing:** Live defect in shipped `C-FLOW-03` fan-out; should land before `C-FLOW-12`.

### 🔴 TECH-015: Retire Grab-Bag Modules (Name-Says-Nothing Refactor)
**Benefit:** *Every module is named for its contract, so the next addition has something to violate instead of somewhere to hide.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-015:** [Retire Grab-Bag Modules (Name-Says-Nothing Refactor)](features/topic_07_technical_debt/TECH-015/TECH-015_design.md)

### 🔴 TECH-016: Unified Artifact Writer & Serialization Format Enforcement
**Benefit:** *One artifact writer, and a check that makes it required — an enum field can no longer silently break a YAML writer.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-016:** [Unified Artifact Writer & Serialization Format Enforcement](features/topic_07_technical_debt/TECH-016/TECH-016_design.md)

### 🔴 TECH-017: Integration-Contract Proof Audit (Test Tier Must Match Story Tier)
**Benefit:** *Every `INT-US-NN` contract is proven by integration/e2e tests, and capability stories that shipped incomplete are named.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-017:** [Integration-Contract Proof Audit (Test Tier Must Match Story Tier)](features/topic_07_technical_debt/TECH-017/TECH-017_design.md)
*   **Sequencing:** Ships a tier-ratio guardrail at *planning* time — precedes whatever candidate is planned next.

### 🔜 TECH-018: Delivered Add-On Re-Validation Against an Integrated Base (INT-US-21-SUB / C-INTL-01)
**Benefit:** *A delivered add-on's integration claim is re-checked against the base that now exists underneath it.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-018:** [Delivered Add-On Re-Validation Against an Integrated Base](features/topic_07_technical_debt/TECH-018/TECH-018_design.md)
*   **Sequencing:** Audit-only; precondition (INT-US-21 SF-03 committed) met 2026-07-28. Findings become NEW stories.

### 🟢 TECH-019: Skill Instruction Integrity — Dangling Doc References and Contradictory Gate Orders
**Benefit:** *Skill instructions cannot order the agent to read files that do not exist, and two phases cannot both mandate opposite formats.*
*   **Core Required (MVS):**
    *   `[x]` **TECH-019:** [Skill Instruction Integrity — Dangling Doc References and Contradictory Gate Orders](features/topic_07_technical_debt/TECH-019/TECH-019_design.md)
*   **Verifiable Proof:**
    *   `tests/unit/scripts/test_check_skill_references.py`
*   **Sequencing:** Delivered 2026-08-08 (`ffaa4a8b`, `fdc4eac2`).

### 🔴 TECH-020: Extract the Step-Execution Loop from PipelineRunner
**Benefit:** *`runner.py` has headroom again, and `_execute_loop`'s complexity is fixed rather than suppressed.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-020:** [Extract the Step-Execution Loop from PipelineRunner](features/topic_07_technical_debt/TECH-020/TECH-020_design.md)
*   **Sequencing:** File sits at exactly 600/600 RED; sequence before `C-FLOW-12`'s fan-out work. The `# noqa: C901` must be removed, not relocated.

### 🟢 TECH-021: `loop_back` Discards the Failing Step's Result
**Benefit:** *A human parked at a loop-back target can see which step failed and why, instead of an identical prompt every resume.*
*   **Core Required (MVS):**
    *   `✅` **TECH-021:** [`loop_back` Discards the Failing Step's Result](features/topic_07_technical_debt/TECH-021/TECH-021_design.md)
*   **Verifiable Proof:**
    *   `tests/e2e/capabilities/workflows/test_feature_decomposition_e2e.py::TestE8ValidationFailureLoopsBack` — fixed `a003b164`.

### 🔴 TECH-023: Repo-Wide Cyclomatic Complexity Violations (complexipy)
**Benefit:** *`complexipy` reports a clean baseline instead of 98 chronic failures, so a NEW violation is visible instead of lost in noise.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-023:** [Repo-Wide Cyclomatic Complexity Violations](features/topic_07_technical_debt/TECH-023/TECH-023_design.md)
*   **Sequencing:** Found running `quality.py cb` for `TECH-001` SF-04 (2026-08-02); confirmed chronic and unrelated via `git stash`. Excludes `TECH-020`'s and `TECH-006` SF-02's already-owned functions.

### 🔴 TECH-024: Repo-Wide Dependency Cycles (check_coupling)
**Benefit:** *`check_coupling.py --cycles-only` reports zero cycles instead of 4 chronic ones, so modules can be understood, tested, and extracted independently.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-024:** [Repo-Wide Dependency Cycles](features/topic_07_technical_debt/TECH-024/TECH-024_design.md)
*   **Sequencing:** Found running `quality.py cb` for `TECH-001` SF-04 (2026-08-02); confirmed chronic and unrelated via `git stash`. One cycle overlaps `TECH-020`/`TECH-015`'s files — coordinate sequencing rather than duplicating.

### 🟡 TECH-025: Registry IDs Leaking Into Proofs — FR Traceability Gap and Story-Named Tests
**Benefit:** *`check_fr_coverage.py` passes cleanly for TECH-001, TECH-002 and TECH-005 instead of reporting 21 uncited FRs between them, and no test is named after the ticket that paid for it — closing the loop between each design's promises and what actually proves them.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-025:** [Registry IDs Leaking Into Proofs](features/topic_07_technical_debt/TECH-025/TECH-025_design.md)
*   **Sequencing:** Found running `check_fr_coverage.py TECH-001` as SF-04's closure gate (2026-08-02), then again for `TECH-005` the same day, and for `TECH-002` on 2026-08-08 while verifying whether its amber status still reflected outstanding work (it did not). Three stories, 21 FRs, one cause: all shipped before this gate was wired into the closure process. FR-1 through FR-8 (all SF-01/02/03, delivered before this session) are uncited by the literal `FR-N` string in any plan or test naming `TECH-001` — a citation-convention gap, not a functional one; SF-01/02/03's own `Verifiable Proof` suite passes. `TECH-001` itself is not blocked on this — its substantive circular-dependency claim is independently verified true.

### 🔴 TECH-026: Roadmap Placement Contract — One Registry ID, One Line
**Benefit:** *What belongs in this file is written down and enforced, so an agent updating roadmap state no longer has to derive the convention from whichever entries it happens to grep.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-026:** [Roadmap Placement Contract](features/topic_07_technical_debt/TECH-026/TECH-026_design.md)
*   **Sequencing:** Spun off from `TECH-025` SF-02 (2026-08-08). Docs-and-tooling only; unranked in the debt chain above.

### 🔴 TECH-027: Sub-Feature Identifier Contract — Two Digits and an Explicit Owner
**Benefit:** *An `SF-NN` is spelled one way and always says which story it belongs to, so a reference outside its own folder resolves instead of pointing at the nearest ID.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-027:** [Sub-Feature Identifier Contract](features/topic_07_technical_debt/TECH-027/TECH-027_design.md)
*   **Sequencing:** Split from `TECH-026` (2026-08-11). Filename half delivered ahead of design to unblock `TECH-025` SF-05. Docs-and-tooling only; unranked in the debt chain above.

### 🔴 TECH-028: Split `dev` Dependency Definitions — Broken Default Sync, Test Tooling in the Container Image
**Benefit:** *A bare `uv sync` produces an environment that can actually run the suite, and `--no-dev` stops putting `pytest`, `ruff`, `mypy` and `tach` inside the container image.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-028:** [Split `dev` Dependency Definitions](features/topic_07_technical_debt/TECH-028/TECH-028_design.md)
*   **Sequencing:** Found 2026-08-11 rebuilding the environment on Linux. Manifest and `Containerfile` change land in one commit. Docs-and-build only; unranked in the debt chain above.

### 🔴 TECH-029: Sandbox Process Cap Uses `RLIMIT_NPROC`, Which Bounds the User and Not the Sandbox
**Benefit:** *The sandbox's process cap bounds the sandbox instead of the whole login session, so an isolated run stops failing because the developer had other things open.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-029:** [Sandbox Process Cap Uses `RLIMIT_NPROC`](features/topic_07_technical_debt/TECH-029/TECH-029_design.md)
*   **Sequencing:** Found 2026-08-12 on Linux; explains 18 of 29 failures. Live `src/` defect in `C-EXEC-02`/`B-EXEC-01` territory — not `TECH-025`'s.

### 🔴 TECH-030: An Empty `FolderGrant` Path Grants the Whole Project on POSIX and Nothing on Windows
**Benefit:** *A grant means the same thing on every platform, so an empty path cannot quietly widen read access to the whole project including `.git/`.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-030:** [An Empty `FolderGrant` Path Diverges by Platform](features/topic_07_technical_debt/TECH-030/TECH-030_design.md)
*   **Sequencing:** Found 2026-08-12 on Linux. Live `src/` security divergence; needs a decision (invalid vs project-root) before any code change.
