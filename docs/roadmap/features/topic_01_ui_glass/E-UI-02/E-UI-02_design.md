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

## Recorded future direction

After `3.12a`, the dashboard gains cost-override editing through the existing REST endpoints —
**zero new backend code**.

## Origins

See also [A2UI](https://github.com/google/A2UI), a declarative component catalog for agent-generated
UI, with Phase 3.19 structured output schemas as the foundation — `ORIGINS.md` § A2UI.
