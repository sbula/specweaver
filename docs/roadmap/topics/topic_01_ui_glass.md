# Topic 01: The UI (Glass)

This document tracks all capabilities related to the User Interface, visual dashboards, and external developer touchpoints.

## DAL-E: Prototyping
* **`E-UI-01` ✅: CLI Scaffold** (Legacy: Step 1)<br>
  > CLI Scaffold
* **`E-UI-02` ✅: Web Dashboard** (Legacy: 3.8 / 4.10)<br>
  > _(new)_ | Lightweight FastAPI + Jinja2/HTMX dashboard served by `sw serve`. Views: project list, pipeline status, pending HITL reviews with approve/reject buttons, review verdict display, remarks text area. Mobile-responsive — works on tablet (the "train" scenario). No heavy JS framework; server-rendered HTML. **Complete:** 3142 tests. _Future: after 3.12a, dashboard gains cost-override editing via existing REST endpoints — zero new backend code._ SpecWeaver as a daemon with REST/WebSocket API and browser-based UI. Includes **per-project pipeline storage** (layer 2): SQLite `pipelines` table, CRUD via `sw pipeline` CLI + REST API. _(See also: [A2UI](https://github.com/google/A2UI) declarative component catalog for agent-generated UI, Phase 3.19 structured output schemas as foundation — ORIGINS.md § A2UI)_
* **`E-UI-03` 🔜: File Watcher** (Legacy: 3.37)<br>
  > _(inspired by PasteMax)_ | Auto-re-validate specs on disk change; DX polish for iterative authoring
* **`E-UI-04` 🔜: CLI Command Arch Separation** (Legacy: Backlog)<br>
  > _(new)_ | Audit and refactor the `specweaver/interfaces/cli/` layer. Strictly separate Discovery (e.g. `sw scan`) from Validation (e.g. `sw check`). Document the exact use case, DAL interaction, and expected behavior for every CLI entrypoint to eliminate ambiguity.

## DAL-D: Internal Tooling
* **`D-UI-01` 🔧: REST API Server** (Legacy: 3.7)<br>
  > _(new)_ | FastAPI server exposing all CLI commands as REST endpoints. Foundation for **all** external UIs (web dashboard, VS Code extension, IntelliJ plugin, tablet). Endpoints: project management, validation, review triggers, pipeline status/control, config CRUD, gate decisions (approve/reject with remarks). JSON responses reuse existing Pydantic models. WebSocket channel for real-time pipeline progress. **In progress**: TDD phases 1–3 complete (57 API tests), 3128 total tests.
* **`D-UI-02` 🔜: Structured Output Schemas** (Legacy: 3.34)<br>
  > _(new)_ | Declarative JSON schemas for pipeline results (validation, review, generation). Same data renders as Rich console (CLI), cards (Web UI), or inline decorations (IDE). Prerequisite for dashboard and VS Code ext.
* **`D-UI-03` 🔜: VS Code Extension** (Legacy: 3.35)<br>
  > _(new)_ | Thin extension that calls `sw serve` REST endpoints. Tree view for registered projects, inline review verdicts, "Approve/Reject" buttons in status bar, pipeline progress panel.

## DAL-C: Enterprise Standard
* **`C-UI-01` 🔜: Pipeline Visualizer** (Legacy: 3.33a)<br>
  > _(brought forward)_ | Native static HTML exporter (powered by PyVis/D3.js). Visually exposes calculated Degree Centrality (God Nodes) and cluster communities from the AST graph engine directly to developers.
* **`C-UI-02` 🔜: Traceability Matrix UX** (Legacy: 3.48)<br>
  > _(inspired by Cavekit)_ | Exposes the underlying Artifact Lineage Graph to the user via a Markdown/CLI matrix view. Visually maps Spec Requirements to planned components/tasks before execution to allow human auditing of requirement coverage.
* **`C-UI-03` 🔜: Analytics Dashboard** (Legacy: 4.5a)<br>
  > _(split from original 3.12)_ — Aggregate telemetry from 3.12 into cost breakdown by task type (draft/review/plan/implement) across models. Data-driven model selection insights. See [LLM routing & cost analysis](../../analysis/llm_routing_and_cost_analysis.md).

## DAL-B: High-Assurance
* **`B-UI-01` 🔜: Real-Time Feedback Sensor Dashboard** (Legacy: 4.10b)<br>
  > _(new)_ | Exposes the internal `PipelineRunner` DAG state transitions and file-diffs as a real-time streaming graph.
* **`B-UI-02` 🔜: External Proprietary Validation** (Legacy: 6.2)<br>
  > _(new)_ | Adapt an internal pipeline designed specifically to ingest public `SWE-bench` tickets, generate code, and produce normalized dashboard validation of Attributed Lifecycle Scores regression.

## DAL-A: Mission-Critical
* **`A-UI-01` 🔜: Dark Factory Compliance Logging** (Legacy: 4.12)<br>
  > _(new)_ | Integrating with Artifact Lineage to emit immutable, signed ledgers matching Model IDs/Spec Hashes directly to physical Lines of Code for Enterprise regulatory audits.
* **`A-UI-02` 🔜: Standardized Benchmarking CI** (Legacy: 6.1)<br>
  > _(new)_ | Execute `sw init`, `draft`, and `check` workflows externally outside SpecWeaver's boundary (e.g., orchestrating an external 20-microservice proprietary trading system).
