# E-UI-02 — Web Dashboard (Feature 3.8, Minimal): Plan

**FRs owned**: FR-1, FR-2, FR-3 (recorded 2026-08-17 under `specweaver-dev` §3.2c, from
`INT-US-06-MIG`; the plan predates the FR ledger) · **Depends on**: Feature 3.7 (REST API) ·
Design: [E-UI-02_design.md](E-UI-02_design.md) · Proof and mutants:
`tests/unit/interfaces/api/test_ui.py`

## Goal

A server-rendered HTML dashboard (FastAPI + Jinja2 + HTMX) served alongside the REST API
(`sw serve`), usable on a tablet to monitor pipelines and approve HITL gates. Why and decisions: see
design.

**Stack**: FastAPI, [Jinja2](https://jinja.palletsprojects.com/), [HTMX](https://htmx.org/), Vanilla
CSS or lightweight CSS framework (e.g., PicoCSS).

**Since moved** (noted 2026-09-25): the code lives under `src/specweaver/interfaces/api/ui/`; the
serve message is in `src/specweaver/interfaces/cli/routers/serve_router.py`. Paths below are as of the
plan.

## Changes

1. **REST API fields** · `schemas.py` — add to the `/runs/{id}` response, so Jinja holds no logic:
   `pending_gate: bool`, `pending_gate_prompt: str | None`.
2. **Templates** · [NEW] `src/specweaver/api/ui/templates/` — `base.html` (imports HTMX and CSS),
   `projects.html`, `runs.html`, `run_detail.html` (run, logs, HITL gate),
   `partials/run_status.html` (status fragment), `partials/log_line.html` (WebSocket streaming
   fragment).
3. **Static** · [NEW] `src/specweaver/api/ui/static/` — `style.css`, `htmx.min.js` and
   `pico.min.css` (vendored: no CDN on trains/airplanes).
4. **UI router** · [NEW] `src/specweaver/api/ui/routes.py` — `HTMLResponse` via `Jinja2Templates`,
   calling `api.v1.projects` and `api.v1.pipelines` functions directly for Pydantic data:
   - `GET /` -> Redirects to `/dashboard`
   - `GET /dashboard` -> Render `projects.html`
   - `GET /dashboard/runs` -> Render `runs.html`
   - `GET /dashboard/runs/{run_id}` -> Render `run_detail.html`
5. **App** · [MODIFY] `src/specweaver/api/app.py` — mount `StaticFiles` at `/static`; include the UI
   router.
6. **CLI** · [MODIFY] `src/specweaver/cli/serve.py` — print
   `Dashboard available at: http://{host}:{port}/dashboard`.
7. **HTMX mutations** · [NEW] `src/specweaver/api/ui/htmx.py` — HTMX expects HTML fragments, so
   dedicated UI endpoints (e.g., `POST /dashboard/runs/{id}/gate`) return them — preferred over
   intercepting REST JSON and reloading the page:
   `POST /ui/gate/{run_id}` -> calls `event_bridge`, returns an updated `#run-status-card` fragment.

## Tests

| Tier | Case |
|---|---|
| Automated | `GET /dashboard` endpoints return 200 OK and valid HTML with expected strings; `POST /ui/gate` returns the correct HTML fragment |
| Manual | `sw serve`, open `http://localhost:8000/dashboard` on desktop; resize to tablet/mobile and check the layout; run a pipeline to a HITL gate and see it pending; enter "Remarks", click "Approve"; the pipeline resumes on the backend |
| Offline | Disconnect WiFi; HTMX and CSS still load (vendored assets) |

## As built

Checked against the code 2026-09-25:

- The gate endpoint is `POST /dashboard/runs/{run_id}/gate` (`submit_hitl_gate` in `htmx.py`), not
  `POST /ui/gate/{run_id}`.
- `templates/` holds `base.html`, `projects.html`, `runs.html`, `run_detail.html` — no `partials/`.
  `static/` holds `htmx.min.js` and `pico.min.css` — no `style.css`.
