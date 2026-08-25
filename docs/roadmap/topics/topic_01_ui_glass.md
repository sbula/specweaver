# Topic 01: The UI (Glass)

Capabilities for the user interface, dashboards, and external developer touchpoints.

Entries follow `R-ENTRY` (`specweaver-ticket/references/roadmap-placement.md`): seven keyed fields,
no prose. `—` means none. **`UNKNOWN` means nobody decided it** — a real answer, not a gap to fill with
something plausible. **`FOUNDATIONAL:` means the purpose is genuinely thin**, and it must still name
what stands on the floor. **🟡 means derived from an existing document, never confirmed** — the
source is named so you can judge whether it actually explains this capability. Where the superseded
entry made a claim, it is carried as `Claimed:` and
still marked ungrilled.

## DAL-E: Prototyping

* **`E-UI-01` ✅: CLI Scaffold** (Legacy: Step 1)
  > - **Purpose:** FOUNDATIONAL: the floor every `sw` command stands on. Without it SpecWeaver is libraries with no way for a person to invoke them
  > - **Trigger:** When a developer runs `sw <command>`
  > - **Needs:** —
  > - **Reads:** command-line arguments
  > - **Produces:** memory → routing to each command's implementation · `sw init` → target project scaffold and configuration
  > - **Enables:** `init` · `draft` · `check spec|code` · `review spec|code` · `implement` → the seven commands the product is used through
  > - **Done when:** all seven commands route to their implementation (FR-1..FR-7)

* **`E-UI-02` ✅: Web Dashboard** (Legacy: 3.8 / 4.10)
  > - **Purpose:** Approve a pending review from a tablet — the "train" scenario the capability was justified by
  > - **Trigger:** When an operator opens the dashboard served by `sw serve`
  > - **Needs:** `D-UI-01` → the REST/WebSocket contract it calls
  > - **Reads:** per-project pipeline storage — a SQLite `pipelines` table
  > - **Produces:** memory → server-rendered HTML (FastAPI + Jinja2/HTMX, no JS framework, mobile-responsive)
  > - **Enables:** operator → project list, pipeline status, HITL approve/reject, verdict display, remarks
  > - **Done when:** an operator approves a pending review from a tablet, with no terminal

* **`E-UI-03` 🔜: File Watcher** (Legacy: 3.37, inspired by PasteMax)
  > - **Purpose:** 🟡 derived — `US-7` benefit is about VS Code and does **not** fit a file watcher. Nearest stated intent, from the superseded entry: DX polish for iterative authoring.
  >   **Poor fit — needs you**
  > - **Trigger:** When a spec file changes on disk
  > - **Needs:** UNKNOWN → whatever runs validation
  > - **Reads:** spec files on disk
  > - **Produces:** UNKNOWN → a re-validation result, destination unstated
  > - **Enables:** spec author → validation without re-running a command
  > - **Done when:** UNKNOWN

* **`E-UI-04` 🔜: CLI Command Arch Separation** (Legacy: Backlog)
  > - **Purpose:** 🟡 derived — `US-1` benefit (prove a spec's structural quality) does **not** explain a CLI refactor. **Poor fit — needs you**
  > - **Trigger:** Always — a structural property of the CLI layer
  > - **Needs:** —
  > - **Reads:** the CLI layer's own source
  > - **Produces:** UNKNOWN → documentation, refactor, or both; the entry says "audit and refactor"
  > - **Enables:** UNKNOWN
  > - **Done when:** UNKNOWN — "strictly separate Discovery from Validation" states a shape, not a test

## DAL-D: Internal Tooling

* **`D-UI-01` 🔧: Core Orchestration API** (Legacy: 3.7 MVP)
  > - **Purpose:** Give every external front end a contract to call. Without it each one shells out to the CLI and parses console output
  > - **Trigger:** When `sw serve` is running and a request or WebSocket connection arrives
  > - **Needs:** the CLI command layer → the operations each route exposes
  > - **Reads:** project, pipeline and run state
  > - **Produces:** memory → 23 HTTP routes (projects, pipelines, runs, review, check, constitution, standards) · a WebSocket streaming run progress live
  > - **Enables:** `E-UI-02` tablet dashboard · `D-UI-03` VS Code · an IntelliJ plugin · `D-UI-04`..`D-UI-07` → endpoints to extend
  > - **Done when:** a front end drives a run end to end without shelling out to the CLI

* **`D-UI-02` 🔜: Structured Output Schemas** (Legacy: 3.34)
  > - **Purpose:** 🟡 derived from `US-6`: control pipelines from a browser on a tablet. One result shape so console, browser and IDE need not each restate it
  > - **Trigger:** When a pipeline step produces a result
  > - **Needs:** validation, review and generation steps → their result data
  > - **Reads:** —
  > - **Produces:** memory → declarative JSON schemas for pipeline results
  > - **Enables:** CLI → Rich console · Web UI → cards · IDE → inline decorations
  > - **Done when:** UNKNOWN

* **`D-UI-03` 🔜: VS Code Extension** (Legacy: 3.35)
  > - **Purpose:** 🟡 derived from `US-7`: approve/reject generated code inside VS Code without switching to the terminal
  > - **Trigger:** When the extension is open in an editor
  > - **Needs:** `D-UI-01` → REST endpoints · `D-UI-02` → the schemas it renders
  > - **Reads:** —
  > - **Produces:** UNKNOWN → editor UI: project tree, inline verdicts, approve/reject, progress panel
  > - **Enables:** developer → review without leaving the editor
  > - **Done when:** UNKNOWN

* **`D-UI-04` 🔜: REST API — Interactive Authoring**
  > - **Purpose:** 🟡 derived from `US-2`: have the LLM co-author a spec section by section — from the UI, not only the CLI
  > - **Trigger:** When a request arrives for `draft`, `implement` or `scan`
  > - **Needs:** `D-UI-01` → the server to extend
  > - **Reads:** UNKNOWN
  > - **Produces:** memory → HTTP responses for `draft`, `implement`, `scan`
  > - **Enables:** UNKNOWN → "the UI", unnamed
  > - **Done when:** UNKNOWN

* **`D-UI-05` 🔜: REST API — Enterprise Configuration**
  > - **Purpose:** 🟡 derived — `US-4` benefit is autonomous multi-step workflows, which does not obviously need config endpoints. **Weak fit — needs you**
  > - **Trigger:** When a request arrives for `config`, `list-rules`, `standards` or `constitution`
  > - **Needs:** `D-UI-01` → the server to extend
  > - **Reads:** project configuration
  > - **Produces:** memory → HTTP responses; UNKNOWN whether it also writes configuration
  > - **Enables:** UNKNOWN
  > - **Done when:** UNKNOWN

* **`D-UI-06` 🔜: REST API — Telemetry & Auditing**
  > - **Purpose:** 🟡 derived from `US-16`: see exactly what each agent spends, detect LLM friction, and route tasks to cheaper models. **Same purpose as `B-FLOW-05`**
  > - **Trigger:** When a request arrives for `costs`, `usage`, `lineage` or `drift`
  > - **Needs:** `D-UI-01` → the server to extend
  > - **Reads:** the SQLite ledgers
  > - **Produces:** memory → HTTP responses carrying ledger content
  > - **Enables:** `A-UI-01` → the remote operator it names as its consumer
  > - **Done when:** UNKNOWN

* **`D-UI-07` 🔜: REST API — Systems Integration**
  > - **Purpose:** 🟡 derived from `US-6`: keep the REST surface complete so the browser client is never blocked on a missing endpoint
  > - **Trigger:** When a request arrives for `hooks`, `update` or `remove`
  > - **Needs:** `D-UI-01` → the server to extend
  > - **Reads:** UNKNOWN
  > - **Produces:** memory → HTTP responses for `hooks`, `update`, `remove`
  > - **Enables:** UNKNOWN
  > - **Done when:** UNKNOWN
  > - **Standing rule:** a new CLI command requires a matching endpoint sub-capability, so the REST surface cannot fall behind

## DAL-C: Enterprise Standard

* **`C-UI-01` 🔜: Pipeline Visualizer** (Legacy: 3.33a)
  > - **Purpose:** 🟡 derived from `US-10`: instantly see a visual map of a 20-year-old C++ monolith's God Nodes and dependencies
  > - **Trigger:** When a developer exports the view
  > - **Needs:** `TECH-068` → real edge kinds. Centrality over a `CONTAINS`-only graph is
  >   meaningless ([ADR-006](../../architecture/07_architectural_decision_records/adr_006_graphs_are_truth_vectors_are_discovery.md), 2026-08-21)
  > - **Reads:** the knowledge graph
  > - **Produces:** file → static HTML (PyVis/D3.js)
  > - **Enables:** developer → sees degree centrality and cluster communities
  > - **Done when:** UNKNOWN

* **`C-UI-02` 🔜: Traceability Matrix UX** (Legacy: 3.48, inspired by Cavekit)
  > - **Purpose:** 🟡 derived from `US-15`: hand an auditor a ledger proving which LLM generated which line from which requirement. **Contradicts `A-UI-01`**, which was re-scoped away from
  >   the regulator consumer as one that does not exist. **Needs you**
  > - **Trigger:** When a plan exists and before it is executed
  > - **Needs:** the artifact lineage graph → spec-to-component links
  > - **Reads:** spec requirements, planned components and tasks
  > - **Produces:** memory → a Markdown/CLI matrix view
  > - **Enables:** reviewer → sees which requirements have no planned component
  > - **Done when:** UNKNOWN

* **`C-UI-03` 🔜: Analytics Dashboard** (Legacy: 4.5a)
  > - **Purpose:** 🟡 derived from `US-16`: see what each agent spends and route tasks to cheaper models. **Same purpose as `D-UI-06` and `B-FLOW-05`** — three capabilities, one benefit
  > - **Trigger:** UNKNOWN
  > - **Needs:** telemetry → per-run cost and usage. **Overlaps `B-FLOW-05`** — see [LLM routing & cost analysis](../../analysis/llm_routing_and_cost_analysis.md)
  > - **Reads:** the telemetry ledger
  > - **Produces:** UNKNOWN → cost breakdown by task type across models
  > - **Enables:** UNKNOWN → who chooses a model, and on what evidence, is unstated
  > - **Done when:** UNKNOWN

## DAL-B: High-Assurance

* **`B-UI-01` 🔜: Real-Time Feedback Sensor Dashboard** (Legacy: 4.10b)
  > - **Purpose:** 🟡 derived from `US-6`: watch a run progress from a browser rather than a terminal
  > - **Trigger:** While a pipeline run is executing
  > - **Needs:** `PipelineRunner` → DAG state transitions and file diffs
  > - **Reads:** —
  > - **Produces:** UNKNOWN → a streaming graph; transport and destination unstated
  > - **Enables:** UNKNOWN
  > - **Done when:** UNKNOWN

* **`B-UI-02` 🔜: External Proprietary Validation** (Legacy: 6.2)
  > - **Purpose:** 🟡 derived from `US-18`: prove the platform works by using it to build and manage an external proprietary trading system. Matches `PROJECT.md`'s enterprise-ready criterion
  > - **Trigger:** UNKNOWN
  > - **Needs:** UNKNOWN
  > - **Reads:** an external codebase — named example: a 20-microservice proprietary trading system
  > - **Produces:** UNKNOWN
  > - **Enables:** the enterprise-ready criterion → "used on an external system that is not this one" (`PROJECT.md`)
  > - **Done when:** UNKNOWN

## DAL-A: Mission-Critical

* **`A-UI-01` 🔜: Tamper-Evident Agent Audit Ledger** (Legacy: 4.12)
  > - **Purpose:** Make the agent's audit trail tamper-evident. **The adversary is the agent
  >   itself** — it runs with write access on the machine producing the record.
  >   Re-scoped 2026-08-20 ([benefit review](../../analysis/benefit_chain_analysis_2026-08-20.md))
  > - **Trigger:** When an agent action is recorded
  > - **Needs:** `B-SENS-01` → artifact lineage records
  > - **Reads:** —
  > - **Produces:** db → append-only, hash-chained audit entries
  > - **Enables:** `D-UI-06` + US-6 → an operator auditing agent work remotely. **Not a regulator** — the former "Dark Factory Compliance Logging" framing named a consumer that does not exist
  > - **Done when:** UNKNOWN — but the adversary and the consumer are both named, which is more than any other entry here has

* **`A-UI-02` 🔜: Standardized Benchmarking CI** (Legacy: 6.1)
  > - **Purpose:** 🟡 derived from `US-17`: prove SpecWeaver has not degraded by autonomously solving standardized SWE-bench tickets before every release
  > - **Trigger:** UNKNOWN
  > - **Needs:** UNKNOWN
  > - **Reads:** public `SWE-bench` tickets
  > - **Produces:** UNKNOWN → normalized dashboard validation
  > - **Enables:** UNKNOWN
  > - **Done when:** UNKNOWN
