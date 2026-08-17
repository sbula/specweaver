# Design: Web Dashboard

- **Feature ID**: E-UI-02
- **Epic**: Topic 01 (The UI / Glass)
- **Status**: ✅ Delivered — this document is a **record**, not a plan.
- **Legacy**: 3.8 / 4.10
- **Created**: 2026-08-13 under `TECH-044`. The capability shipped without a design document, so
  its topic entry was the only record and there was nowhere to redistribute its detail to.
  Everything below is moved verbatim from that entry, not newly authored.

## What shipped

A lightweight FastAPI + Jinja2/HTMX dashboard served by `sw serve`. Views: project list, pipeline
status, pending HITL reviews with approve/reject buttons, review verdict display, remarks text
area.

Mobile-responsive — it works on a tablet, which is the "train" scenario the capability was justified
by. No heavy JS framework; server-rendered HTML.

Includes **per-project pipeline storage** (layer 2): a SQLite `pipelines` table with CRUD via the
`sw pipeline` CLI and the REST API. The wider shape is SpecWeaver as a daemon with a REST/WebSocket
API and a browser UI.

**Complete:** 3142 tests at delivery.

## Functional Requirements

Written 2026-08-17 under `specweaver-dev` §3.2c, on contact from `INT-US-06-MIG`. This capability is
`✅` and its design declared **no requirements at all** — one of the nineteen the capability matrix
warns about, invisible to `check_fr_sweep.py` by construction because a design with no FRs has none
to be uncited.

Written from **why the capability exists** — reading and steering a run from a browser on a tablet,
without the engine running locally — not from what the code does. Each is behind a killed mutant;
none was believed before that.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Remote run visibility | Reviewer | `GET /dashboard/runs` | The runs the state store holds are rendered, so a reader sees real run state rather than a page that always renders |
| FR-2 | Remote HITL resolution | Reviewer | POST an approve/reject decision from the run detail page | The decision reaches the run's gate — the browser is a real control surface, not a viewer |
| FR-3 | An unknown run is refused | Reviewer | `GET /dashboard/runs/<unknown>` | 404, rather than an empty page that reads as "this run has no activity" |

**FR-1 needed a test before it could be declared.** Its mutant — `runs = store.list_runs()` replaced
by `runs = []` — **survived the whole suite**, because the only assertion was that the page rendered
and contained the words "Pipeline Runs". A page that always renders proves nothing about the data
behind it. `test_get_dashboard_runs_lists_runs_from_the_store` closes that, and the mutant now dies.

Not declared, deliberately: mobile responsiveness. It is the "train" scenario's whole justification
and it is a CSS property no test in this repo can falsify, so writing it as an FR would add a row
that cannot fail — worse than the silence it replaces (§3.2c).

## Recorded future direction

After `3.12a`, the dashboard gains cost-override editing through the existing REST endpoints —
**zero new backend code**.

## Origins

See also [A2UI](https://github.com/google/A2UI), a declarative component catalog for agent-generated
UI, with Phase 3.19 structured output schemas as the foundation — `ORIGINS.md` § A2UI.
