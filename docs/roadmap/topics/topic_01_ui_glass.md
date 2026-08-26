# Topic 01: The UI (Glass)

Capabilities for the user interface, dashboards, and external developer touchpoints.

Seven keyed fields per entry, plus optional `Limits:` and `Note:` — no prose (`R-ENTRY`). Values are written plainly.
**🟡 marks a guess** · **🔴 marks nothing found**. Markers are the exception.

## DAL-E: Prototyping

* **`E-UI-01` ✅: CLI Scaffold** (Legacy: Step 1)
  > - **Purpose:** Single entry point for all user commands. Validates input, routes to the right workflow
  > - **Trigger:** When a user runs `sw <command>`
  > - **Precondition:** —
  > - **Reads:** command-line arguments
  > - **Produces:** routing to each command's workflow · `sw init` writes the project scaffold and config
  > - **Enables:** `init` · `draft` · `check` · `review` · `implement`
  > - **Done when:** all seven commands route to their workflow

* **`E-UI-02` ✅: Web Dashboard** (Legacy: 3.8 / 4.10)
  > - **Purpose:** Review and approve pipeline work from a browser, including a tablet away from the desk
  > - **Trigger:** When an operator opens the dashboard
  > - **Precondition:** `D-UI-01` → REST and WebSocket endpoints
  > - **Reads:** per-project pipeline storage
  > - **Produces:** server-rendered HTML — FastAPI + Jinja2/HTMX, mobile-responsive, no JS framework
  > - **Enables:** operator → project list, pipeline status, approve/reject, verdicts
  > - **Done when:** an operator approves a pending review from a tablet, with no terminal

* **`E-UI-03` 🔜: File Watcher** (Legacy: 3.37)
  > - **Purpose:** Re-validate a spec as it is edited, instead of re-running `check` by hand
  > - **Trigger:** When a spec file changes on disk
  > - **Precondition:** the validation battery
  > - **Reads:** spec files
  > - **Produces:** 🟡 a re-validation result — where it surfaces is unstated
  > - **Enables:** spec author → feedback while writing
  > - **Done when:** 🔴

* **`E-UI-04` 🔜: CLI Command Arch Separation**
  > - **Purpose:** 🟡 Make each CLI command's job unambiguous — discovery separated from validation
  > - **Trigger:** Always
  > - **Precondition:** —
  > - **Reads:** the CLI layer
  > - **Produces:** 🟡 a refactored CLI layer, and documented behaviour per entry point
  > - **Enables:** 🔴
  > - **Done when:** 🔴

## DAL-D: Internal Tooling

* **`D-UI-01` 🔧: Core Orchestration API** (Legacy: 3.7 MVP)
  > - **Purpose:** Give external front ends a contract to call, so none has to shell out to the CLI and parse its output
  > - **Trigger:** When `sw serve` is running and a request arrives
  > - **Precondition:** the CLI command layer
  > - **Reads:** project, pipeline and run state
  > - **Produces:** 23 HTTP routes · a WebSocket streaming run progress live
  > - **Enables:** `E-UI-02` · `D-UI-03` · `D-UI-04`..`D-UI-07`
  > - **Done when:** a front end drives a run end to end without the CLI

* **`D-UI-02` 🔜: Structured Output Schemas** (Legacy: 3.34)
  > - **Purpose:** One result shape rendered three ways — console, browser, IDE — without each restating it
  > - **Trigger:** When a pipeline step produces a result
  > - **Precondition:** the validation, review and generation steps
  > - **Reads:** —
  > - **Produces:** JSON schemas for pipeline results
  > - **Enables:** CLI → Rich console · web → cards · IDE → inline decorations
  > - **Done when:** 🔴

* **`D-UI-03` 🔜: VS Code Extension** (Legacy: 3.35)
  > - **Purpose:** Approve or reject generated code inside the editor, without switching to a terminal
  > - **Trigger:** When the extension is open
  > - **Precondition:** `D-UI-01` → endpoints · `D-UI-02` → schemas
  > - **Reads:** —
  > - **Produces:** editor UI — project tree, inline verdicts, approve/reject, progress panel
  > - **Enables:** developer → review in place
  > - **Done when:** 🔴

* **`D-UI-04` 🔜: REST API — Interactive Authoring**
  > - **Purpose:** Co-author a spec with the LLM from the UI, not only the CLI
  > - **Trigger:** When a request arrives for `draft`, `implement` or `scan`
  > - **Precondition:** `D-UI-01`
  > - **Reads:** 🔴
  > - **Produces:** HTTP endpoints for `draft`, `implement`, `scan`
  > - **Enables:** 🟡 the web UI
  > - **Done when:** 🔴

* **`D-UI-05` 🔜: REST API — Enterprise Configuration**
  > - **Purpose:** 🟡 Manage project configuration from the UI instead of editing YAML by hand
  > - **Trigger:** When a request arrives for `config`, `list-rules`, `standards` or `constitution`
  > - **Precondition:** `D-UI-01`
  > - **Reads:** project configuration
  > - **Produces:** 🟡 HTTP endpoints — whether they also write is unstated
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`D-UI-06` 🔜: REST API — Telemetry & Auditing**
  > - **Purpose:** See what each agent spends and where runs slow down, so tasks can be routed to cheaper models
  > - **Trigger:** When a request arrives for `costs`, `usage`, `lineage` or `drift`
  > - **Precondition:** `D-UI-01` · the telemetry ledgers
  > - **Reads:** the SQLite ledgers
  > - **Produces:** HTTP endpoints carrying ledger content
  > - **Enables:** `A-UI-01` → the remote operator it names as its consumer
  > - **Done when:** 🔴
  > - **Note:** same purpose as `C-UI-03` and `B-FLOW-05` — three capabilities, one benefit

* **`D-UI-07` 🔜: REST API — Systems Integration**
  > - **Purpose:** 🟡 Keep the REST surface complete, so a UI client is never blocked on a missing endpoint
  > - **Trigger:** When a request arrives for `hooks`, `update` or `remove`
  > - **Precondition:** `D-UI-01`
  > - **Reads:** 🔴
  > - **Produces:** HTTP endpoints for `hooks`, `update`, `remove`
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Note:** a new CLI command requires a matching endpoint, so the REST surface cannot fall behind

## DAL-C: Enterprise Standard

* **`C-UI-01` 🔜: Pipeline Visualizer** (Legacy: 3.33a)
  > - **Purpose:** See a visual map of a large unfamiliar codebase — god nodes, clusters, dependencies
  > - **Trigger:** When a developer exports the view
  > - **Precondition:** `TECH-068` → real edge kinds. Centrality over a `CONTAINS`-only graph is meaningless
  > - **Reads:** the knowledge graph
  > - **Produces:** file → static HTML (PyVis/D3.js)
  > - **Enables:** developer → sees degree centrality and cluster communities
  > - **Done when:** 🔴

* **`C-UI-02` 🔜: Traceability Matrix UX** (Legacy: 3.48)
  > - **Purpose:** 🟡 Check requirement coverage before execution — which requirements have no planned
  >   component. `US-15` frames this as a ledger for a compliance auditor; `A-UI-01` says that
  >   consumer does not exist. **Needs you**
  > - **Trigger:** When a plan exists, before it is executed
  > - **Precondition:** the artifact lineage graph
  > - **Reads:** spec requirements, planned components and tasks
  > - **Produces:** a Markdown/CLI matrix view
  > - **Enables:** reviewer → sees which requirements have no planned component
  > - **Done when:** 🔴

* **`C-UI-03` 🔜: Analytics Dashboard** (Legacy: 4.5a)
  > - **Purpose:** Cost and friction per task type across models, so the right model is chosen per task
  > - **Trigger:** 🔴
  > - **Precondition:** the telemetry ledger
  > - **Reads:** telemetry
  > - **Produces:** 🟡 a cost breakdown by task type across models
  > - **Enables:** model choice per task
  > - **Done when:** 🔴
  > - **Note:** same purpose as `D-UI-06` and `B-FLOW-05`

## DAL-B: High-Assurance

* **`B-UI-01` 🔜: Real-Time Feedback Sensor Dashboard** (Legacy: 4.10b)
  > - **Purpose:** 🟡 Watch a run progress live — state transitions and file diffs — instead of reading logs afterwards
  > - **Trigger:** While a run is executing
  > - **Precondition:** `PipelineRunner` → DAG state transitions and file diffs
  > - **Reads:** —
  > - **Produces:** 🟡 a streaming graph; transport unstated
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`B-UI-02` 🔜: External Proprietary Validation** (Legacy: 6.2)
  > - **Purpose:** Prove the platform works by using it on an external system that is not SpecWeaver itself
  > - **Trigger:** 🔴
  > - **Precondition:** 🔴
  > - **Reads:** an external codebase — named example: a 20-microservice proprietary trading system
  > - **Produces:** 🔴
  > - **Enables:** the enterprise-ready criterion in `PROJECT.md`
  > - **Done when:** 🟡 `sw init`, `draft` and `check` complete against an external system

## DAL-A: Mission-Critical

* **`A-UI-01` 🔜: Tamper-Evident Agent Audit Ledger** (Legacy: 4.12)
  > - **Purpose:** Make the agent's audit trail tamper-evident. The adversary is the agent itself — it
  >   has write access to the machine that produces the record
  > - **Trigger:** When an agent action is recorded
  > - **Precondition:** `B-SENS-01` → artifact lineage records
  > - **Reads:** —
  > - **Produces:** db → append-only, hash-chained audit entries
  > - **Enables:** `D-UI-06` → an operator auditing agent work remotely. Not a regulator
  > - **Done when:** 🔴

* **`A-UI-02` 🔜: Standardized Benchmarking CI** (Legacy: 6.1)
  > - **Purpose:** Prove SpecWeaver has not got worse, by solving standard SWE-bench tickets before a release
  > - **Trigger:** 🟡 Before every release
  > - **Precondition:** 🔴
  > - **Reads:** public SWE-bench tickets
  > - **Produces:** 🟡 normalized scores
  > - **Enables:** 🔴
  > - **Done when:** 🔴
