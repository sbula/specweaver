# D-UI-01 — `sw serve` REST API Server (Feature 3.7)

**FRs owned**: FR-1, FR-2, FR-3, FR-4, FR-5 · **Depends on**: all existing CLI commands
(Phase 1–3.6) · **Consumers**: Feature 3.8 (Web Dashboard), Feature 3.23 (VS Code Extension) ·
Design: [D-UI-01_design.md](D-UI-01_design.md)

One plan, three TDD phases. The FRs were written afterwards, from why the capability exists rather
than from its routes; splitting them across the phases retrospectively would be fiction.

## Goal

Expose SpecWeaver CLI operations as REST endpoints via a FastAPI server
([FastAPI](https://fastapi.tiangolo.com/) — async, auto-generates OpenAPI docs, native Pydantic
support), plus a WebSocket channel for real-time pipeline progress. Foundation for all external UIs
(web dashboard 3.8, VS Code extension 3.23, IntelliJ plugin). Why: see the design.

## Decisions (audit)

| # | Decision | Choice | Audit # |
|---|----------|--------|---------|
| 1 | **Framework** | FastAPI. Async, auto OpenAPI docs (`/docs`), built-in Pydantic validation, WebSocket support. | — |
| 2 | **Entry point** | `sw serve --port 8000 --host 127.0.0.1` starts Uvicorn. Flags: `--port`, `--host`, `--reload`, `--cors-origins`. Missing FastAPI/Uvicorn gives: `pip install specweaver[serve]`. | Q14, Q15 |
| 3 | **Module location** | New `specweaver/api/` package. Does NOT depend on `specweaver/cli/` — both depend on the same core modules. `context.yaml`: archetype `adapter`, consumes `config`, `flow`, `validation`, `review`, `implementation`. | Q5, Q27 |
| 4 | **Endpoint naming** | RESTful: `/api/v1/projects`, `/api/v1/check`, `/api/v1/pipelines/{name}/run`. CLI command names, resource-oriented. | — |
| 5 | **Versioning** | `/api/v1/` prefix. Breaking changes → `/api/v2/`. Non-breaking additions are backward-compatible. | — |
| 6 | **Authentication** | **Phase 1: None** (local-only, `--host 127.0.0.1`). UUIDs are unguessable. Phase 2: optional API key via `X-API-Key` header. Document security posture. | Q11 |
| 7 | **Pipeline execution model** | **Fire-and-forget.** `POST /run` returns `{"run_id": "..."}` immediately; a background `asyncio.Task` runs the pipeline. Client polls `GET /runs/{run_id}` or subscribes via WebSocket. Max 3 concurrent runs (configurable). Auto-cleanup after completion. | Q2, Q20 |
| 8 | **HITL gate handling** | Runner **terminates on park**. `POST /runs/{run_id}/gate` saves the decision to `StateStore`, then triggers a new `PipelineRunner.resume()` as a background task. Context rebuilt from stored state (same as `sw resume`). | Q3 |
| 9 | **WebSocket progress** | `/api/v1/ws/pipeline/{run_id}`. Streams the same NDJSON events as `JsonPipelineDisplay`. No auth in Phase 1 (local-only). | Q7, Q11 |
| 10 | **Shared logic** | Handlers call core modules directly (`validation/`, `review/`, `implementation/`, `flow/`). **No service layer refactoring** — core logic is not in `cli/`. | Q5 |
| 11 | **DB connections** | New connection per request via dependency injection (`Depends(get_db)`). SQLite WAL mode makes concurrent CLI + API access safe. | Q4, Q6 |
| 12 | **File paths** | All paths relative to the registered project root. Absolute paths and `../` traversals rejected (security). | Q7 |
| 13 | **CORS** | Configurable. Default: allow `localhost:*` origins. Via `--cors-origins` flag or DB setting. | — |
| 14 | **Error responses** | `SpecWeaverAPIError` with an `error_code` field. The handler returns `{"detail": "msg", "error_code": "PROJECT_NOT_FOUND"}`. FastAPI validation errors keep the default format. | Q18 |
| 15 | **New dependencies** | `fastapi`, `uvicorn[standard]` as optional extras: `pip install specweaver[serve]`. | Q12, Q14 |
| 16 | **Existing code impact** | Zero changes to existing CLI code. The API is a parallel entry point. | — |
| 17 | **`draft` endpoint** | **Deferred to 3.8** (Web Dashboard). `draft` is the only multi-turn interactive CLI command — it needs a conversation UI, not a stateless endpoint. | Q1 |
| 18 | **Response formats** | `POST /check`: envelope `{"summary": {...}, "results": [...], "overall": "FAIL"}`. `POST /review`: blocks and returns the result (single LLM call, <30s). `POST /implement`: writes files AND returns content (`write_to_disk: bool`, default `true`). `GET /runs/{id}`: `?detail=summary|full`. | Q8, Q9, Q10, Q17 |
| 19 | **Standards scan** | Two-step: `POST /standards/scan` returns results without saving; `POST /standards/accept` saves selected categories. | Q13 |
| 20 | **Project init** | `POST /projects` accepts `scaffold: bool` (default `true`). Local clients get full init; tests skip scaffold. | Q12 |
| 21 | **Health check** | `GET /healthz` → `{"status": "ok", "version": "..."}`. For monitoring and future container probes (3.9). | Q22 |
| 22 | **OpenAPI branding** | `title="SpecWeaver API"`, `description="Spec-first development toolkit"`, `version` from package metadata. | Q21 |
| 23 | **Graceful shutdown** | On SIGTERM, wait up to 30s for the current pipeline step, then force-stop. | Q26 |
| 24 | **Pagination** | None. All lists are small (<100 items). Add if/when needed. | Q16 |
| 25 | **Rate limiting** | None. Local server. Defer to a reverse proxy for multi-user. | Q24 |
| 26 | **Logging** | Unified: Uvicorn uses SpecWeaver's `logging.py` settings. | Q25 |

## Changes

Paths below are as planned. **Since moved**: `specweaver/api/` → `src/specweaver/interfaces/api/`;
`cli/serve.py` → `interfaces/cli/routers/serve_router.py`.

### Phase 1 — Core API server + project endpoints

`sw serve` starts a FastAPI server with project management, health check and OpenAPI docs.

| Component | Module | What |
|-----------|--------|------|
| `api/__init__.py` | `api/` | Package init. |
| `api/app.py` | `api/` | App factory `create_app()`: mounts v1 router, CORS middleware, lifespan (DB connection), exception handlers. OpenAPI `title="SpecWeaver API"`. |
| `api/deps.py` | `api/` | Dependency injection: `get_db()` (new connection per request), `get_state_store()`, `get_project_path()`. |
| `api/errors.py` | `api/` | `SpecWeaverAPIError` base class with `error_code` field. Exception handlers. |
| `api/v1/__init__.py` | `api/v1/` | v1 router aggregation. |
| `api/v1/projects.py` | `api/v1/` | `GET /projects`, `POST /projects` (init, `scaffold: bool`), `DELETE /projects/{name}`, `PUT /projects/{name}`, `POST /projects/{name}/use`, `POST /projects/{name}/scan`. |
| `api/v1/schemas.py` | `api/v1/` | Request/response models: `ProjectCreate`, `ProjectResponse`, `CheckResponse` envelope, etc. |
| `api/v1/health.py` | `api/v1/` | `GET /healthz` → status + version. |
| `api/context.yaml` | `api/` | Module manifest. Archetype: `adapter`. |
| `cli/serve.py` | `cli/` | `sw serve`: `--port`, `--host`, `--reload`, `--cors-origins`. Import check for FastAPI/Uvicorn with a friendly error. |
| `pyproject.toml` | root | `[project.optional-dependencies] serve = ["fastapi>=0.115", "uvicorn[standard]>=0.34"]`. |

Tests: ~30-40, using `TestClient`.

### Phase 2 — Validation, review, implementation endpoints

| Component | Module | What |
|-----------|--------|------|
| `api/v1/validation.py` | `api/v1/` | `POST /check` (envelope), `GET /rules` (list rules). |
| `api/v1/review.py` | `api/v1/` | `POST /review` (blocking, returns `ReviewResult`). `POST /draft` **not included** (deferred to 3.8). |
| `api/v1/implement.py` | `api/v1/` | `POST /implement` (writes files + returns content, `write_to_disk: bool`). |
| `api/v1/standards.py` | `api/v1/` | `POST /standards/scan` (no save), `POST /standards/accept` (saves selected), `GET /standards`, `DELETE /standards`. |
| `api/v1/constitution.py` | `api/v1/` | `GET /constitution`, `POST /constitution/check`, `POST /constitution/init`. |
| `api/v1/config.py` | `api/v1/` | `GET/PUT /config`, `GET/PUT /config/profiles`, `GET/PUT /config/overrides`. |

Tests: ~40-50.

### Phase 3 — Pipeline execution + WebSocket progress

Run/resume pipelines (fire-and-forget), stream progress over WebSocket, handle HITL gate decisions.

| Component | Module | What |
|-----------|--------|------|
| `api/v1/pipelines.py` | `api/v1/` | `GET /pipelines`, `POST /pipelines/{name}/run` (body: `{"spec": "...", "project": "...", "selector": "direct"}`), `POST /runs/{run_id}/resume`, `GET /runs/{run_id}` (`?detail=summary|full`), `GET /runs/{run_id}/log` (audit log), `POST /runs/{run_id}/gate` (HITL approve/reject → triggers resume). |
| `api/v1/ws.py` | `api/v1/` | WebSocket `/ws/pipeline/{run_id}`. Streams NDJSON events. No auth in Phase 1. |
| `api/event_bridge.py` | `api/` | Adapts `PipelineRunner.on_event` → WebSocket broadcast. Background task registry (max 3 concurrent, auto-cleanup). |

Tests: ~25-35 (WebSocket tests use `httpx-ws`).

### Endpoints

| Method | Path | CLI Equivalent | Phase |
|--------|------|---------------|-------|
| `GET` | `/healthz` | _(new)_ | 1 |
| `GET` | `/api/v1/projects` | `sw projects` | 1 |
| `POST` | `/api/v1/projects` | `sw init` | 1 |
| `DELETE` | `/api/v1/projects/{name}` | `sw remove` | 1 |
| `PUT` | `/api/v1/projects/{name}` | `sw update` | 1 |
| `POST` | `/api/v1/projects/{name}/use` | `sw use` | 1 |
| `POST` | `/api/v1/projects/{name}/scan` | `sw scan` | 1 |
| `POST` | `/api/v1/check` | `sw check` | 2 |
| `GET` | `/api/v1/rules` | `sw list-rules` | 2 |
| `POST` | `/api/v1/review` | `sw review` | 2 |
| `POST` | `/api/v1/implement` | `sw implement` | 2 |
| `POST` | `/api/v1/standards/scan` | `sw standards scan` | 2 |
| `POST` | `/api/v1/standards/accept` | _(new — HITL)_ | 2 |
| `GET` | `/api/v1/standards` | `sw standards show` | 2 |
| `DELETE` | `/api/v1/standards` | `sw standards clear` | 2 |
| `GET` | `/api/v1/constitution` | `sw constitution show` | 2 |
| `POST` | `/api/v1/constitution/init` | `sw constitution init` | 2 |
| `GET` | `/api/v1/config` | `sw config show` | 2 |
| `PUT` | `/api/v1/config` | `sw config set` | 2 |
| `GET` | `/api/v1/pipelines` | `sw pipelines` | 3 |
| `POST` | `/api/v1/pipelines/{name}/run` | `sw run` | 3 |
| `POST` | `/api/v1/runs/{run_id}/resume` | `sw resume` | 3 |
| `GET` | `/api/v1/runs/{run_id}` | _(new)_ | 3 |
| `GET` | `/api/v1/runs/{run_id}/log` | _(new)_ | 3 |
| `POST` | `/api/v1/runs/{run_id}/gate` | _(new — HITL)_ | 3 |
| `WS` | `/api/v1/ws/pipeline/{run_id}` | `--json` flag | 3 |

Not included: `POST /draft` — deferred to Feature 3.8 (multi-turn, interactive).

## Tests

- All use `TestClient` (Starlette in-process) — no real server.
- WebSocket tests use `httpx-ws` or `starlette.testclient.TestClient`.
- Planned total: ~95-125 across 3 phases. Full regression: `python -m pytest tests/ --tb=short -q`;
  `ruff check` + `mypy` on all new files.

Manual:

- `sw serve --port 8000`, open `http://localhost:8000/docs` → OpenAPI UI shows "SpecWeaver API".
- `curl -X POST http://localhost:8000/api/v1/projects -d '{"name":"test","path":"/tmp/test"}'` →
  project created.
- Start a run, connect `websocat ws://localhost:8000/api/v1/ws/pipeline/{run_id}` → real-time events.
- HITL gate: run `new_feature` → parks at the HITL step → `POST /runs/{id}/gate {"action":"approve"}`
  → the pipeline resumes.

## As built (checked against the code 2026-09-25)

- 145 tests pass. FR tags: `test_projects.py` (FR-1), `test_ws.py` (FR-2),
  `test_serve_binds_locally.py` (FR-3), `test_error_contract.py` (FR-5).
- **Not built**: `api/v1/config.py` (the `/config` endpoints), `POST /projects/{name}/scan`,
  `POST /constitution/check`. No SIGTERM handling for decision 23 was found in `interfaces/api` or
  `serve_router.py`.
- Added beyond the plan: HTML dashboard routes under `interfaces/api/ui` (`/dashboard`, …) — its
  own capability.
