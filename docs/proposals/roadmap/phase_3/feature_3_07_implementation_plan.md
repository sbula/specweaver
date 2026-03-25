# Feature 3.7 — `sw serve` REST API Server

Expose SpecWeaver CLI operations as REST endpoints via a FastAPI server. Foundation for all external UIs (web dashboard 3.8, VS Code extension 3.23, IntelliJ plugin). WebSocket channel for real-time pipeline progress events.

> **Depends on**: All existing CLI commands (Phase 1–3.6)
> **Downstream consumers**: Feature 3.8 (Web Dashboard), Feature 3.23 (VS Code Extension)
> **Framework**: [FastAPI](https://fastapi.tiangolo.com/) — async, auto-generates OpenAPI docs, native Pydantic support

---

## Motivation

Today, SpecWeaver is CLI-only. This blocks:
- Browser-based HITL review (the "train scenario" — review on tablet)
- IDE extensions that need to send commands without spawning `sw` subprocesses
- CI/CD pipelines that want to trigger reviews or validations programmatically
- Monitoring dashboards showing pipeline status across projects

All existing response models are already Pydantic → JSON serialization is free.

---

## Design Decisions

| # | Decision | Choice | Audit # |
|---|----------|--------|---------|
| 1 | **Framework** | FastAPI. Async-native, auto OpenAPI docs (`/docs`), built-in Pydantic validation, WebSocket support. | — |
| 2 | **Entry point** | New `sw serve` CLI command: `sw serve --port 8000 --host 127.0.0.1`. Starts Uvicorn server. Flags: `--port`, `--host`, `--reload`, `--cors-origins`. Missing FastAPI/Uvicorn gives friendly error: `pip install specweaver[serve]`. | Q14, Q15 |
| 3 | **Module location** | New `specweaver/api/` package. Does NOT depend on `specweaver/cli/` — both depend on the same core modules. `context.yaml`: archetype `adapter`, consumes `config`, `flow`, `validation`, `review`, `implementation`. | Q5, Q27 |
| 4 | **Endpoint naming** | RESTful: `/api/v1/projects`, `/api/v1/check`, `/api/v1/pipelines/{name}/run`. Consistent with CLI command names but resource-oriented. | — |
| 5 | **Versioning** | `/api/v1/` prefix. Breaking changes → `/api/v2/`. Non-breaking additions are backward-compatible. | — |
| 6 | **Authentication** | **Phase 1: None** (local-only, `--host 127.0.0.1`). UUIDs are unguessable. Phase 2: optional API key via `X-API-Key` header. Document security posture. | Q11 |
| 7 | **Pipeline execution model** | **Fire-and-forget.** `POST /run` returns `{"run_id": "..."}` immediately. Background `asyncio.Task` runs the pipeline. Client polls `GET /runs/{run_id}` or subscribes via WebSocket. Max 3 concurrent runs (configurable). Auto-cleanup after completion. | Q2, Q20 |
| 8 | **HITL gate handling** | Runner **terminates on park**. `POST /runs/{run_id}/gate` saves decision to `StateStore`, then triggers a new `PipelineRunner.resume()` as a background task. Context rebuilt from stored state (same as `sw resume`). | Q3 |
| 9 | **WebSocket progress** | `/api/v1/ws/pipeline/{run_id}`. Streams same NDJSON events as `JsonPipelineDisplay`. No auth in Phase 1 (local-only). | Q7, Q11 |
| 10 | **Shared logic** | API handlers call existing core modules directly (`validation/`, `review/`, `implementation/`, `flow/`). **No service layer refactoring.** Core logic already lives in these modules, not in `cli/`. | Q5 |
| 11 | **DB connections** | New connection per request via FastAPI dependency injection (`Depends(get_db)`). SQLite WAL mode handles concurrency. Concurrent CLI + API access is safe. | Q4, Q6 |
| 12 | **File paths** | All paths relative to registered project root. Absolute paths and `../` traversals rejected (security). | Q7 |
| 13 | **CORS** | Configurable. Default: allow `localhost:*` origins. Via `--cors-origins` flag or DB setting. | — |
| 14 | **Error responses** | Custom `SpecWeaverAPIError` with `error_code` field. Exception handler returns `{"detail": "msg", "error_code": "PROJECT_NOT_FOUND"}`. Built-in FastAPI validation errors keep default format. | Q18 |
| 15 | **New dependencies** | `fastapi`, `uvicorn[standard]` as optional extras: `pip install specweaver[serve]`. | Q12, Q14 |
| 16 | **Existing code impact** | Zero changes to existing CLI code. API is a parallel entry point. | — |
| 17 | **`draft` endpoint** | **Deferred to 3.8** (Web Dashboard). `draft` is the only multi-turn interactive CLI command — requires a conversation UI, not a stateless REST endpoint. | Q1 |
| 18 | **Response formats** | `POST /check`: wrapped envelope `{"summary": {...}, "results": [...], "overall": "FAIL"}`. `POST /review`: blocks and returns result (single LLM call, <30s). `POST /implement`: writes files AND returns content (`write_to_disk: bool`, default `true`). `GET /runs/{id}`: `?detail=summary|full` query param. | Q8, Q9, Q10, Q17 |
| 19 | **Standards scan** | Two-step: `POST /standards/scan` returns results without saving. `POST /standards/accept` saves selected categories. | Q13 |
| 20 | **Project init** | `POST /projects` accepts `scaffold: bool` param (default `true`). Local clients get full init, tests skip scaffold. | Q12 |
| 21 | **Health check** | `GET /healthz` → `{"status": "ok", "version": "..."}`. Included from day 1 for monitoring and future container probes (3.9). | Q22 |
| 22 | **OpenAPI branding** | `title="SpecWeaver API"`, `description="Spec-first development toolkit"`, `version` from package metadata. | Q21 |
| 23 | **Graceful shutdown** | Wait up to 30s for current pipeline step to complete on SIGTERM. Then force-stop. | Q26 |
| 24 | **Pagination** | None. All lists are small (<100 items). Add if/when needed. | Q16 |
| 25 | **Rate limiting** | None. Local server. Defer to reverse proxy for multi-user. | Q24 |
| 26 | **Logging** | Unified config. Uvicorn uses SpecWeaver's `logging.py` settings. | Q25 |

---

## Sub-Phases

### Phase 1 of 3.7: Core API Server + Project Endpoints

**Goal**: `sw serve` starts a FastAPI server with project management endpoints, health check, and OpenAPI docs.

| Component | Module | What |
|-----------|--------|------|
| `api/__init__.py` | `api/` | Package init. |
| `api/app.py` | `api/` | FastAPI app factory: `create_app()`. Mounts v1 router, CORS middleware, lifespan (DB connection), custom exception handlers. OpenAPI: `title="SpecWeaver API"`. |
| `api/deps.py` | `api/` | FastAPI dependency injection: `get_db()` (new connection per request), `get_state_store()`, `get_project_path()`. |
| `api/errors.py` | `api/` | `SpecWeaverAPIError` base class with `error_code` field. Exception handlers. |
| `api/v1/__init__.py` | `api/v1/` | v1 router aggregation. |
| `api/v1/projects.py` | `api/v1/` | `GET /projects`, `POST /projects` (init, `scaffold: bool`), `DELETE /projects/{name}`, `PUT /projects/{name}`, `POST /projects/{name}/use`, `POST /projects/{name}/scan`. |
| `api/v1/schemas.py` | `api/v1/` | Request/response Pydantic models: `ProjectCreate`, `ProjectResponse`, `CheckResponse` envelope, etc. |
| `api/v1/health.py` | `api/v1/` | `GET /healthz` → status + version. |
| `api/context.yaml` | `api/` | Module manifest. Archetype: `adapter`. |
| `cli/serve.py` | `cli/` | `sw serve` command: `--port`, `--host`, `--reload`, `--cors-origins`. Import check for FastAPI/Uvicorn with friendly error. |
| `pyproject.toml` | root | Add `[project.optional-dependencies] serve = ["fastapi>=0.115", "uvicorn[standard]>=0.34"]`. |

**Tests**: ~30-40 tests using `TestClient`.

---

### Phase 2 of 3.7: Validation, Review, Implementation Endpoints

**Goal**: Expose check, review, implement, standards, constitution, and config operations.

| Component | Module | What |
|-----------|--------|------|
| `api/v1/validation.py` | `api/v1/` | `POST /check` (wrapped response envelope), `GET /rules` (list rules). |
| `api/v1/review.py` | `api/v1/` | `POST /review` (blocking, returns `ReviewResult`). `POST /draft` **not included** (deferred to 3.8). |
| `api/v1/implement.py` | `api/v1/` | `POST /implement` (writes files + returns content, `write_to_disk: bool`). |
| `api/v1/standards.py` | `api/v1/` | `POST /standards/scan` (returns without saving), `POST /standards/accept` (saves selected), `GET /standards`, `DELETE /standards`. |
| `api/v1/constitution.py` | `api/v1/` | `GET /constitution`, `POST /constitution/check`, `POST /constitution/init`. |
| `api/v1/config.py` | `api/v1/` | `GET/PUT /config`, `GET/PUT /config/profiles`, `GET/PUT /config/overrides`. |

**Tests**: ~40-50 tests.

---

### Phase 3 of 3.7: Pipeline Execution + WebSocket Progress

**Goal**: Run/resume pipelines via API (fire-and-forget), stream real-time progress over WebSocket, handle HITL gate decisions.

| Component | Module | What |
|-----------|--------|------|
| `api/v1/pipelines.py` | `api/v1/` | `GET /pipelines` (list), `POST /pipelines/{name}/run` (fire-and-forget, body: `{"spec": "...", "project": "...", "selector": "direct"}`), `POST /runs/{run_id}/resume`, `GET /runs/{run_id}` (`?detail=summary|full`), `GET /runs/{run_id}/log` (audit log), `POST /runs/{run_id}/gate` (HITL approve/reject → triggers resume). |
| `api/v1/ws.py` | `api/v1/` | WebSocket `/ws/pipeline/{run_id}`. Streams NDJSON events. No auth in Phase 1. |
| `api/event_bridge.py` | `api/` | Adapts `PipelineRunner.on_event` → WebSocket broadcast. Background task registry (max 3 concurrent, auto-cleanup). |

**Tests**: ~25-35 tests (WebSocket tests use `httpx-ws`).

---

## Proposed Endpoint Summary

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

> **Not included**: `POST /draft` — deferred to Feature 3.8 (Web Dashboard) due to multi-turn interactive nature.

---

## Verification Plan

### Automated Tests
- All tests use `TestClient` (Starlette in-process) — no real server needed
- Pipeline WebSocket tests use `httpx-ws` or `starlette.testclient.TestClient`
- Total: ~95-125 tests across 3 phases
- Full regression: `python -m pytest tests/ --tb=short -q`
- `ruff check` + `mypy` on all new files

### Manual Verification
- Start `sw serve --port 8000`, open `http://localhost:8000/docs` → verify OpenAPI UI shows "SpecWeaver API"
- `curl -X POST http://localhost:8000/api/v1/projects -d '{"name":"test","path":"/tmp/test"}'` → project created
- Start a pipeline run, connect WebSocket via `websocat ws://localhost:8000/api/v1/ws/pipeline/{run_id}`, verify real-time events
- Test HITL gate: run `new_feature` pipeline → parks at HITL step → `POST /runs/{id}/gate {"action":"approve"}` → verify pipeline resumes
