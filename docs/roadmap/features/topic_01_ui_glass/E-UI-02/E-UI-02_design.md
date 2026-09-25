# E-UI-02 — Web Dashboard

**Status**: ✅ Delivered — this document is a **record**, not a plan. · **Epic**: Topic 01 (The UI /
Glass) · **Legacy**: 3.8 / 4.10 · **Feature ID**: E-UI-02

Created 2026-08-13 under `TECH-044`: the capability shipped without a design document, so its topic
entry was the only record. The content is moved verbatim from that entry, not newly authored.

| | |
|---|---|
| Depends on | Feature 3.7 (REST API, `sw serve`) |
| Plan | [E-UI-02_implementation_plan.md](E-UI-02_implementation_plan.md) |

## What it does

A lightweight FastAPI + Jinja2/HTMX dashboard served by `sw serve`. Views: project list, pipeline
status, pending HITL reviews with approve/reject buttons, review verdict display, remarks text area.

Mobile-responsive — it works on a tablet, the "train" scenario the capability was justified by. No
heavy JS framework; server-rendered HTML.

Includes **per-project pipeline storage** (layer 2): a SQLite `pipelines` table with CRUD via the
`sw pipeline` CLI and the REST API. The wider shape is SpecWeaver as a daemon with a REST/WebSocket
API and a browser UI.

**Complete:** 3142 tests at delivery.

## Why this way

Pipeline runs and HITL reviews (especially long semantic reviews) mean waiting. The "train scenario":
a developer starts a long pipeline from the laptop, then reviews the LLM's work (code, specs, plans)
on a tablet during the commute and clicks "Approve" or "Reject" with remarks.

A heavy SPA (React/Vue/Angular) is overkill. The dashboard must be simple, interactive, fast-loading,
and ship in the same Python package without Node.js build steps.

## Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | **Architecture** | **HTMX + Jinja2**. Server-rendered HTML fragments returned from FastAPI endpoints; HTMX swaps the DOM without custom JavaScript. |
| 2 | **Server Integration** | The **same FastAPI app** as Feature 3.7 (`sw serve`), with a UI router mounted at `/dashboard`. The CLI prints the URL on startup (no auto-open). |
| 3 | **Data Fetching** | **Internal Function Calls.** The UI router calls the `api/v1` router functions directly — decoupled from DB queries, no HTTP overhead. |
| 4 | **Markdown Rendering** | **Server-side**. Python's `markdown` package (plus `bleach` for XSS safety) inside Jinja filters renders LLM responses. |
| 5 | **Static Assets** | **Vendored in Git**. `htmx.min.js` and `pico.min.css` are committed for offline support without build steps. |
| 6 | **HITL UX** | HTMX request handlers show a CSS spinner while the backend resumes the run. |
| 7 | **Dependencies** | `jinja2`, `python-multipart`, `markdown`, and `bleach` in the `pyproject.toml` `[serve]` extra. |

## Functional Requirements

Written 2026-08-17 under `specweaver-dev` §3.2c, on contact from `INT-US-06-MIG`. The design had
declared **no requirements at all** — one of the nineteen the capability matrix warns about, invisible
to `check_fr_sweep.py` by construction, since a design with no FRs has none to be uncited.

Written from **why the capability exists** — reading and steering a run from a browser on a tablet,
without the engine running locally — not from what the code does. Each is behind a killed mutant.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Remote run visibility | Reviewer | `GET /dashboard/runs` | The runs the state store holds are rendered, so a reader sees real run state rather than a page that always renders |
| FR-2 | Remote HITL resolution | Reviewer | POST an approve/reject decision from the run detail page | The decision reaches the run's gate — the browser is a real control surface, not a viewer |
| FR-3 | An unknown run is refused | Reviewer | `GET /dashboard/runs/<unknown>` | 404, rather than an empty page that reads as "this run has no activity" |

**FR-1 needed a test before it could be declared.** Its mutant — `runs = store.list_runs()` replaced by
`runs = []` — **survived the whole suite**: the only assertion was that the page rendered and contained
"Pipeline Runs". `test_get_dashboard_runs_lists_runs_from_the_store` closes that; the mutant now dies.

Not declared, deliberately: mobile responsiveness. It is the "train" scenario's whole justification,
but a CSS property no test in this repo can falsify — an FR row that cannot fail is worse than the
silence it replaces (§3.2c).

## Future direction

After `3.12a`, the dashboard gains cost-override editing through the existing REST endpoints —
**zero new backend code**.

## Origins

See also [A2UI](https://github.com/google/A2UI), a declarative component catalog for agent-generated
UI, with Phase 3.19 structured output schemas as the foundation — `ORIGINS.md` § A2UI.
