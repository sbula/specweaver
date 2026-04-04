# Feature 3.8 — Web Dashboard (Minimal)

A lightweight, server-rendered HTML dashboard powered by FastAPI + Jinja2 + HTMX, served alongside the existing REST API (`sw serve`). Designed for mobile-responsive use on a tablet ("the train scenario") to monitor pipelines and perform HITL (Human-in-the-Loop) gate approvals.

> **Depends on**: Feature 3.7 (REST API)
> **Stack**: FastAPI, [Jinja2](https://jinja.palletsprojects.com/), [HTMX](https://htmx.org/), Vanilla CSS or lightweight CSS framework (e.g., PicoCSS)

---

## Motivation

SpecWeaver is powerful on the CLI, but pipeline execution and HITL reviews (especially long semantic reviews) often require waiting. The "train scenario" envisions a developer starting a long pipeline from their laptop, then taking their tablet on the commute to review the LLM's work (code, specs, plans) and clicking "Approve" or "Reject" with remarks.

A heavy SPA (React/Vue/Angular) is overkill. SpecWeaver requires a simple, interactive, fast-loading dashboard that ships in the same Python package without requiring Node.js build steps.

## Design Decisions

| # | Decision | Choice | 
|---|----------|--------|
| 1 | **Architecture** | **HTMX + Jinja2**. Server-rendered HTML fragments returned directly from FastAPI endpoints. HTMX handles the DOM swapping without writing custom JavaScript. |
| 2 | **Server Integration** | The dashboard runs on the **same FastAPI app** created in Feature 3.7 (`sw serve`). It simply mounts a UI router at `/dashboard`. The CLI prints the URL on startup (no auto-open). |
| 3 | **Data Fetching** | **Internal Function Calls.** The UI router imports and calls the `api/v1` router functions directly for data retrieval, keeping it decoupled from direct DB queries while avoiding HTTP overhead. |
| 4 | **Markdown Rendering** | **Server-side**. Use Python's `markdown` package (plus `bleach` for XSS safety) inside Jinja filters to render LLM responses. |
| 5 | **Static Assets** | **Vendored in Git**. `htmx.min.js` and `pico.min.css` will be committed directly to the repo for instant offline support without build steps. |
| 6 | **HITL UX** | Built-in HTMX request handlers show a CSS spinner while the backend orchestrates the run resumption. |
| 7 | **Dependencies** | Add `jinja2`, `python-multipart`, `markdown`, and `bleach` to `pyproject.toml` `[serve]` extra. |

## Feature 3.7 REST API Updates

To support the dashboard cleanly without embedding complex logic in Jinja, we need to add explicit fields to the existing `/runs/{id}` response in `schemas.py`:
- `pending_gate: bool`
- `pending_gate_prompt: str | None`

---

## Proposed Changes

### 1. UI Directory Structure
Create a new package for the frontend assets inside the existing `api/` module.

#### [NEW] `src/specweaver/api/ui/templates/`
Jinja2 HTML templates:
- `base.html` (boilerplate, imports HTMX and CSS)
- `projects.html` (list projects)
- `runs.html` (list recent pipeline runs)
- `run_detail.html` (view specific run, logs, and HITL gate)
- `partials/run_status.html` (HTMX fragment for status updates)
- `partials/log_line.html` (HTMX fragment for WebSocket streaming)

#### [NEW] `src/specweaver/api/ui/static/`
- `style.css` (custom tweaks)
- `htmx.min.js` (vendored to avoid CDN dependency on trains/airplanes)
- `pico.min.css` (vendored)

### 2. UI Routers
#### [NEW] `src/specweaver/api/ui/routes.py`
Endpoints that return `HTMLResponse` via `Jinja2Templates`. These functions import and call `api.v1.projects` and `api.v1.pipelines` functions directly to get Pydantic model data.
- `GET /` -> Redirects to `/dashboard`
- `GET /dashboard` -> Render `projects.html`
- `GET /dashboard/runs` -> Render `runs.html`
- `GET /dashboard/runs/{run_id}` -> Render `run_detail.html`

### 3. FastAPI App Integration
#### [MODIFY] `src/specweaver/api/app.py`
- Mount the `StaticFiles` application to `/static`.
- Include the new UI router.

#### [MODIFY] `src/specweaver/cli/serve.py`
- Update the success message to explicitly print `Dashboard available at: http://{host}:{port}/dashboard`.

### 4. API Endpoints for HTMX
HTMX expects HTML fragments in response to mutations.
We will either create UI-specific HTMX endpoints (e.g., `POST /dashboard/runs/{id}/gate`), or rely on the UI intercepting the REST API JSON and triggering a page reload. Given HTMX patterns, dedicated UI endpoints that return HTML fragments are preferred.
#### [NEW] `src/specweaver/api/ui/htmx.py`
- `POST /ui/gate/{run_id}` -> Calls `event_bridge`, returns an updated `#run-status-card` HTML fragment.

---

## Verification Plan
1. **Automated Tests**: Test that the `GET /dashboard` endpoints return 200 OK and valid HTML containing expected strings. Test that `POST /ui/gate` returns the correct HTML fragment.
2. **Manual Testing**: 
   - Start `sw serve`, open `http://localhost:8000/dashboard` in a desktop browser.
   - Resize window to tablet/mobile dimensions, verify responsive layout.
   - Run a pipeline that pauses at a HITL gate. Verify the dashboard shows the pending gate.
   - Submit text in the "Remarks" field and click "Approve".
   - Verify the pipeline resumes execution on the backend.
3. **Offline mode test**: Disconnect WiFi, verify HTMX and CSS still load properly (vendored assets).
