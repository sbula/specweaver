# Topic 01: The UI (Glass)

This document tracks all capabilities related to the User Interface, visual dashboards, and external developer touchpoints.

## DAL-E: Prototyping
* **`E-UI-01` ✅: CLI Scaffold** (Legacy: Step 1)<br>
  > CLI Scaffold
* **`E-UI-02` ✅: Web Dashboard** (Legacy: 3.8 / 4.10)<br>
  > [Description](../features/topic_01_ui_glass/E-UI-02/E-UI-02_design.md) | _(new)_ | Lightweight FastAPI + Jinja2/HTMX dashboard served by `sw serve`: project list, pipeline status, pending HITL
  > reviews with approve/reject, verdict display. Mobile-responsive for the tablet "train" scenario; server-rendered, no heavy JS framework. Includes per-project pipeline storage. **Complete:** 3142
  > tests.
* **`E-UI-03` 🔜: File Watcher** (Legacy: 3.37)<br>
  > _(inspired by PasteMax)_ | Auto-re-validate specs on disk change; DX polish for iterative authoring
* **`E-UI-04` 🔜: CLI Command Arch Separation** (Legacy: Backlog)<br>
  > _(new)_ | Audit and refactor the `specweaver/interfaces/cli/` layer. Strictly separate Discovery (e.g. `sw scan`) from Validation (e.g. `sw check`). Document the exact use case, DAL interaction,
  > and expected behavior for every CLI entrypoint to eliminate ambiguity.

## DAL-D: Internal Tooling
* **`D-UI-01` 🔧: Core Orchestration API** (Legacy: 3.7 MVP)<br>
  > _(new)_ | FastAPI server (`sw serve`) exposing the minimum CLI commands needed for remote orchestration: `init`, `projects`, `use`, `pipelines`, `run`, `resume`, `review`, and `check`. Foundation
  > for the tablet Web Dashboard. **In progress**: TDD phases 1–3 complete (57 API tests).
* **`D-UI-02` 🔜: Structured Output Schemas** (Legacy: 3.34)<br>
  > _(new)_ | Declarative JSON schemas for pipeline results (validation, review, generation). Same data renders as Rich console (CLI), cards (Web UI), or inline decorations (IDE). Prerequisite for
  > dashboard and VS Code ext.
* **`D-UI-03` 🔜: VS Code Extension** (Legacy: 3.35)<br>
  > _(new)_ | Thin extension that calls `sw serve` REST endpoints. Tree view for registered projects, inline review verdicts, "Approve/Reject" buttons in status bar, pipeline progress panel.
* **`D-UI-04` 🔜: REST API - Interactive Authoring**<br>
  > _(new)_ | Extends FastAPI with endpoints for `draft`, `implement`, and `scan`. Enables interactive co-authoring from the UI.
* **`D-UI-05` 🔜: REST API - Enterprise Configuration**<br>
  > _(new)_ | Extends FastAPI with endpoints for `config`, `list-rules`, `standards`, and `constitution`. Moves YAML configuration into the UI.
* **`D-UI-06` 🔜: REST API - Telemetry & Auditing**<br>
  > _(new)_ | Extends FastAPI with endpoints for `costs`, `usage`, `lineage`, and `drift`. Exposes SQLite ledgers to managers/auditors.
* **`D-UI-07` 🔜: REST API - Systems Integration**<br>
  > _(new)_ | Extends FastAPI with endpoints for `hooks`, `update`, and `remove`. **Note on Future CLI Integrations:** Any new CLI commands added in the future must be accompanied by new specific UI
  > endpoint sub-capabilities to ensure the REST API and frontend stay up to date.

## DAL-C: Enterprise Standard
* **`C-UI-01` 🔜: Pipeline Visualizer** (Legacy: 3.33a)<br>
  > _(brought forward)_ | Native static HTML exporter (powered by PyVis/D3.js). Visually exposes calculated Degree Centrality (God Nodes) and cluster communities from the AST graph engine directly to
  > developers. **Graph reader** _(2026-08-21, [ADR-006](../../architecture/07_architectural_decision_records/adr_006_graphs_are_truth_vectors_are_discovery.md))_: centrality over a
  > `CONTAINS`-only graph is meaningless — behind `TECH-068`.
* **`C-UI-02` 🔜: Traceability Matrix UX** (Legacy: 3.48)<br>
  > _(inspired by Cavekit)_ | Exposes the underlying Artifact Lineage Graph to the user via a Markdown/CLI matrix view. Visually maps Spec Requirements to planned components/tasks before execution to
  > allow human auditing of requirement coverage.
* **`C-UI-03` 🔜: Analytics Dashboard** (Legacy: 4.5a)<br>
  > _(split from original 3.12)_ — Aggregate telemetry from 3.12 into cost breakdown by task type (draft/review/plan/implement) across models. Data-driven model selection insights. See
  > [LLM routing & cost analysis](../../analysis/llm_routing_and_cost_analysis.md).

## DAL-B: High-Assurance
* **`B-UI-01` 🔜: Real-Time Feedback Sensor Dashboard** (Legacy: 4.10b)<br>
  > _(new)_ | Exposes the internal `PipelineRunner` DAG state transitions and file-diffs as a real-time streaming graph.
* **`B-UI-02` 🔜: External Proprietary Validation** (Legacy: 6.2)<br>
  > _(new)_ | Execute `sw init`, `draft`, and `check` workflows externally outside SpecWeaver's boundary (e.g., orchestrating an external 20-microservice proprietary trading system).

## DAL-A: Mission-Critical
* **`A-UI-01` 🔜: Tamper-Evident Agent Audit Ledger** (Legacy: 4.12)<br>
  > _(new; re-scoped 2026-08-20 — [benefit review](../../analysis/benefit_chain_analysis_2026-08-20.md))_ | Integrates with Artifact Lineage (`B-SENS-01`) to make
  > the audit trail tamper-evident (append-only, hash-chained). The adversary is the agent itself: it runs with write access on the machine that produces the
  > record. The consumer is the operator auditing agent work remotely (`D-UI-06` + US-6), not a regulator — the former "Dark Factory Compliance Logging"
  > framing named a consumer that does not exist.
* **`A-UI-02` 🔜: Standardized Benchmarking CI** (Legacy: 6.1)<br>
  > _(new)_ | Adapt an internal pipeline designed specifically to ingest public `SWE-bench` tickets, generate code, and produce normalized dashboard validation of Attributed Lifecycle Scores
  > regression.
