# Topic 01: The UI (Glass)

Capabilities for the user interface, dashboards, and external developer touchpoints.

Entries follow `R-ENTRY` (`specweaver-ticket/references/roadmap-placement.md`): seven keyed fields,
no prose. `—` means none. **`UNKNOWN` means nobody decided it** — a real answer, not a gap to fill
with something plausible. Where the superseded entry made a claim, it is carried as `Claimed:` and
still marked ungrilled.

## DAL-E: Prototyping

* **`E-UI-01` ✅: CLI Scaffold** (Legacy: Step 1)
  > **Purpose:**   UNKNOWN — never grilled. The superseded entry said only "CLI Scaffold"
  > **Trigger:**   UNKNOWN
  > **Needs:**     UNKNOWN
  > **Reads:**     UNKNOWN
  > **Produces:**  UNKNOWN
  > **Enables:**   every `sw` command → an entry point to attach to
  > **Done when:** UNKNOWN

* **`E-UI-02` ✅: Web Dashboard** (Legacy: 3.8 / 4.10)
  > **Purpose:**   UNKNOWN — never grilled. Claimed: approve pending reviews away from a desk ("the tablet train scenario")
  > **Trigger:**   When an operator opens the dashboard served by `sw serve`
  > **Needs:**     `D-UI-01` → the REST endpoints it renders
  > **Reads:**     per-project pipeline storage
  > **Produces:**  memory → server-rendered HTML (FastAPI + Jinja2/HTMX, no JS framework)
  > **Enables:**   operator → project list, pipeline status, HITL approve/reject, verdict display
  > **Done when:** UNKNOWN — 3142 tests pass, but no statement of what the operator can now do that they could not

* **`E-UI-03` 🔜: File Watcher** (Legacy: 3.37, inspired by PasteMax)
  > **Purpose:**   UNKNOWN — never grilled. Claimed: DX polish for iterative spec authoring
  > **Trigger:**   When a spec file changes on disk
  > **Needs:**     UNKNOWN → whatever runs validation
  > **Reads:**     spec files on disk
  > **Produces:**  UNKNOWN → a re-validation result, destination unstated
  > **Enables:**   spec author → validation without re-running a command
  > **Done when:** UNKNOWN

* **`E-UI-04` 🔜: CLI Command Arch Separation** (Legacy: Backlog)
  > **Purpose:**   UNKNOWN — never grilled. Claimed: eliminate ambiguity about what each CLI entry point does
  > **Trigger:**   Always — a structural property of the CLI layer
  > **Needs:**     —
  > **Reads:**     the CLI layer's own source
  > **Produces:**  UNKNOWN → documentation, refactor, or both; the entry says "audit and refactor"
  > **Enables:**   UNKNOWN
  > **Done when:** UNKNOWN — "strictly separate Discovery from Validation" states a shape, not a test

## DAL-D: Internal Tooling

* **`D-UI-01` 🔧: Core Orchestration API** (Legacy: 3.7 MVP)
  > **Purpose:**   UNKNOWN — never grilled. Claimed: foundation for remote orchestration and the tablet dashboard
  > **Trigger:**   When `sw serve` is running and a request arrives
  > **Needs:**     the CLI command layer → the behaviour each endpoint exposes
  > **Reads:**     UNKNOWN
  > **Produces:**  memory → HTTP responses for `init`, `projects`, `use`, `pipelines`, `run`, `resume`, `review`, `check`
  > **Enables:**   `E-UI-02` → the dashboard it renders · `D-UI-03..07` → endpoints to extend
  > **Done when:** UNKNOWN — 57 API tests pass; no statement of which remote task becomes possible

* **`D-UI-02` 🔜: Structured Output Schemas** (Legacy: 3.34)
  > **Purpose:**   UNKNOWN — never grilled. Claimed: one result renders three ways without restating it
  > **Trigger:**   When a pipeline step produces a result
  > **Needs:**     validation, review and generation steps → their result data
  > **Reads:**     —
  > **Produces:**  memory → declarative JSON schemas for pipeline results
  > **Enables:**   CLI → Rich console · Web UI → cards · IDE → inline decorations
  > **Done when:** UNKNOWN

* **`D-UI-03` 🔜: VS Code Extension** (Legacy: 3.35)
  > **Purpose:**   UNKNOWN — never grilled
  > **Trigger:**   When the extension is open in an editor
  > **Needs:**     `D-UI-01` → REST endpoints · `D-UI-02` → the schemas it renders
  > **Reads:**     —
  > **Produces:**  UNKNOWN → editor UI: project tree, inline verdicts, approve/reject, progress panel
  > **Enables:**   developer → review without leaving the editor
  > **Done when:** UNKNOWN

* **`D-UI-04` 🔜: REST API — Interactive Authoring**
  > **Purpose:**   UNKNOWN — never grilled. Claimed: interactive co-authoring from the UI
  > **Trigger:**   When a request arrives for `draft`, `implement` or `scan`
  > **Needs:**     `D-UI-01` → the server to extend
  > **Reads:**     UNKNOWN
  > **Produces:**  memory → HTTP responses for `draft`, `implement`, `scan`
  > **Enables:**   UNKNOWN → "the UI", unnamed
  > **Done when:** UNKNOWN

* **`D-UI-05` 🔜: REST API — Enterprise Configuration**
  > **Purpose:**   UNKNOWN — never grilled. Claimed: move YAML configuration into the UI
  > **Trigger:**   When a request arrives for `config`, `list-rules`, `standards` or `constitution`
  > **Needs:**     `D-UI-01` → the server to extend
  > **Reads:**     project configuration
  > **Produces:**  memory → HTTP responses; UNKNOWN whether it also writes configuration
  > **Enables:**   UNKNOWN
  > **Done when:** UNKNOWN

* **`D-UI-06` 🔜: REST API — Telemetry & Auditing**
  > **Purpose:**   UNKNOWN — never grilled. Claimed: expose SQLite ledgers to managers and auditors
  > **Trigger:**   When a request arrives for `costs`, `usage`, `lineage` or `drift`
  > **Needs:**     `D-UI-01` → the server to extend
  > **Reads:**     the SQLite ledgers
  > **Produces:**  memory → HTTP responses carrying ledger content
  > **Enables:**   `A-UI-01` → the remote operator it names as its consumer
  > **Done when:** UNKNOWN

* **`D-UI-07` 🔜: REST API — Systems Integration**
  > **Purpose:**   UNKNOWN — never grilled
  > **Trigger:**   When a request arrives for `hooks`, `update` or `remove`
  > **Needs:**     `D-UI-01` → the server to extend
  > **Reads:**     UNKNOWN
  > **Produces:**  memory → HTTP responses for `hooks`, `update`, `remove`
  > **Enables:**   UNKNOWN
  > **Done when:** UNKNOWN
  > **Standing rule:** a new CLI command requires a matching endpoint sub-capability, so the REST surface cannot fall behind

## DAL-C: Enterprise Standard

* **`C-UI-01` 🔜: Pipeline Visualizer** (Legacy: 3.33a)
  > **Purpose:**   UNKNOWN — never grilled. Claimed: expose god-nodes and clusters to developers
  > **Trigger:**   When a developer exports the view
  > **Needs:**     `TECH-068` → real edge kinds. Centrality over a `CONTAINS`-only graph is
  >                meaningless ([ADR-006](../../architecture/07_architectural_decision_records/adr_006_graphs_are_truth_vectors_are_discovery.md), 2026-08-21)
  > **Reads:**     the knowledge graph
  > **Produces:**  file → static HTML (PyVis/D3.js)
  > **Enables:**   developer → sees degree centrality and cluster communities
  > **Done when:** UNKNOWN

* **`C-UI-02` 🔜: Traceability Matrix UX** (Legacy: 3.48, inspired by Cavekit)
  > **Purpose:**   UNKNOWN — never grilled. Claimed: human auditing of requirement coverage before execution
  > **Trigger:**   When a plan exists and before it is executed
  > **Needs:**     the artifact lineage graph → spec-to-component links
  > **Reads:**     spec requirements, planned components and tasks
  > **Produces:**  memory → a Markdown/CLI matrix view
  > **Enables:**   reviewer → sees which requirements have no planned component
  > **Done when:** UNKNOWN

* **`C-UI-03` 🔜: Analytics Dashboard** (Legacy: 4.5a)
  > **Purpose:**   UNKNOWN — never grilled. Claimed: data-driven model selection insights
  > **Trigger:**   UNKNOWN
  > **Needs:**     telemetry → per-run cost and usage. **Overlaps `B-FLOW-05`** — see [LLM routing & cost analysis](../../analysis/llm_routing_and_cost_analysis.md)
  > **Reads:**     the telemetry ledger
  > **Produces:**  UNKNOWN → cost breakdown by task type across models
  > **Enables:**   UNKNOWN → who chooses a model, and on what evidence, is unstated
  > **Done when:** UNKNOWN

## DAL-B: High-Assurance

* **`B-UI-01` 🔜: Real-Time Feedback Sensor Dashboard** (Legacy: 4.10b)
  > **Purpose:**   UNKNOWN — never grilled
  > **Trigger:**   While a pipeline run is executing
  > **Needs:**     `PipelineRunner` → DAG state transitions and file diffs
  > **Reads:**     —
  > **Produces:**  UNKNOWN → a streaming graph; transport and destination unstated
  > **Enables:**   UNKNOWN
  > **Done when:** UNKNOWN

* **`B-UI-02` 🔜: External Proprietary Validation** (Legacy: 6.2)
  > **Purpose:**   UNKNOWN — never grilled. Claimed: run `init`, `draft` and `check` against a system outside SpecWeaver's own boundary
  > **Trigger:**   UNKNOWN
  > **Needs:**     UNKNOWN
  > **Reads:**     an external codebase — named example: a 20-microservice proprietary trading system
  > **Produces:**  UNKNOWN
  > **Enables:**   the enterprise-ready criterion → "used on an external system that is not this one" (`PROJECT.md`)
  > **Done when:** UNKNOWN

## DAL-A: Mission-Critical

* **`A-UI-01` 🔜: Tamper-Evident Agent Audit Ledger** (Legacy: 4.12)
  > **Purpose:**   Make the agent's audit trail tamper-evident. **The adversary is the agent
  >                itself** — it runs with write access on the machine producing the record.
  >                Re-scoped 2026-08-20 ([benefit review](../../analysis/benefit_chain_analysis_2026-08-20.md))
  > **Trigger:**   When an agent action is recorded
  > **Needs:**     `B-SENS-01` → artifact lineage records
  > **Reads:**     —
  > **Produces:**  db → append-only, hash-chained audit entries
  > **Enables:**   `D-UI-06` + US-6 → an operator auditing agent work remotely. **Not a regulator** — the former "Dark Factory Compliance Logging" framing named a consumer that does not exist
  > **Done when:** UNKNOWN — but the adversary and the consumer are both named, which is more than any other entry here has

* **`A-UI-02` 🔜: Standardized Benchmarking CI** (Legacy: 6.1)
  > **Purpose:**   UNKNOWN — never grilled. Claimed: regression signal on Attributed Lifecycle Scores
  > **Trigger:**   UNKNOWN
  > **Needs:**     UNKNOWN
  > **Reads:**     public `SWE-bench` tickets
  > **Produces:**  UNKNOWN → normalized dashboard validation
  > **Enables:**   UNKNOWN
  > **Done when:** UNKNOWN
