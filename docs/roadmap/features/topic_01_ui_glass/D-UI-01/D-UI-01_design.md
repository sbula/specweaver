# Design: Core Orchestration API (`sw serve`)

- **Feature ID**: D-UI-01
- **Epic**: Topic 01 (UI Glass)
- **Status**: 🔧 IN WORK — built and proven, **not approved**. The `specweaver-design`
  Phase 6 gate was never run for this capability. Status returns to ✅ only after that
  review and any corrections it produces.
- **Legacy**: 3.7 MVP

## What shipped

`sw serve` starts a FastAPI server exposing the SpecWeaver operations an external UI needs, plus a
WebSocket that streams a run's progress as it happens. 23 routes across projects, pipelines, runs,
review, check, constitution and standards.

Every external front end — the tablet dashboard, the VS Code extension, the IntelliJ plugin —
would otherwise have to shell out to the CLI and parse its console output. This is the seam that
lets them call a contract instead.

## What the design pass found

The implementation was complete and its 145 tests passed. Two things were not:

- **No requirement was attributed.** Not one test named `D-UI-01`, so nothing connected the code
  to the promise, and `check_fr_coverage.py` had nothing to judge.
- **The bind address had no test.** Phase 1 ships **no authentication** and justifies it by the
  server being local-only, which makes the default bind the entire access-control story. Changing
  `127.0.0.1` to `0.0.0.0` would have exposed every endpoint — including the ones that start runs
  and execute generated code — to anything on the network, with the suite green on both sides. The
  nearest existing test asserted a CORS regex, which governs which browser origins may call a
  server the caller can already reach: a different question.

Both are closed here. `FR-3` and `FR-5` are new tests; `FR-1`, `FR-2` and `FR-4` cite tests that
already proved them and only lacked the tag.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | A remote client can drive a project | External UI | Registers, lists, renames, removes and **selects** a project over HTTP | A front end can do the thing every other call depends on — say which project it means — without shelling out to the CLI |
| FR-2 | A run is observable while it runs | External UI | Subscribes to `/api/v1/ws/pipeline/{run_id}` and receives the same NDJSON events the CLI's JSON display emits, ending with `done` | A gate partway through a ten-minute run is visible to a dashboard, and the two front ends cannot describe the same run differently |
| FR-3 | The server reaches the network only when asked | System | Binds `127.0.0.1` by default and forwards whatever `--host` was given to the server | An install with no authentication is not remotely reachable by default, and a deliberate `--host` still works for a container or a LAN |
| FR-4 | An HTTP-started run is the run the CLI would start | System | Applies the same `[sandbox]` isolation policy at the API composition root | Untrusted generated code is bounded identically whichever root launched it |
| FR-5 | A failure is a typed error, not a traceback | System | Returns `{detail, error_code}` with the declared status, defaulting to a client error | A program can branch on the failure, and no response carries module paths or a stack trace |

`FR-4` is a **seam FR** — the policy is resolved in `core.flow.engine.isolation` and consumed here
— and is proven at integration tier.

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | Project registration and selection | `E-FLOW-01` · `Database` + the projects repository | read `src/specweaver/interfaces/api/v1/projects.py` and `src/specweaver/core/config/database.py` |
| FR-2 | Live run events | `C-FLOW-02` · `event_bridge.get_event_bridge()` | read `src/specweaver/interfaces/api/v1/ws.py` — streams NDJSON, then `{"event": "done"}` and closes |
| FR-3 | The process entry point | `E-UI-01` · `serve_router.serve(port, host, reload, cors_origins)` | read `src/specweaver/interfaces/cli/routers/serve_router.py:28` — `host` defaults to `127.0.0.1` and is forwarded to `uvicorn.run` |
| FR-4 | Worktree isolation policy | `C-EXEC-06` · `isolation.apply_isolation_policy(context, settings, logger)` | read `src/specweaver/core/flow/engine/isolation.py` — the composition root serving both CLI and API |
| FR-5 | The structured failure shape | `E-UI-01` · `errors.SpecWeaverAPIError` / `specweaver_error_handler` | read `src/specweaver/interfaces/api/errors.py:16` |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | No authentication in Phase 1 | Justified **only** by the local-only bind, which `FR-3` is the test for. Any change to the default bind reopens this and requires the `X-API-Key` phase the plan describes |
| NFR-2 | Optional dependency | FastAPI and Uvicorn are an extra; `sw serve` reports the install command and exits 1 rather than raising an `ImportError` **[proof: meta — a rule about the failure message, not about product behaviour]** |
| NFR-3 | Layer placement | The API lives in `interfaces.api` and reaches the engine through the same surfaces the CLI does **[proof: arch — `tach check`, not pytest]** |

## Non-Goals

- Authentication. Phase 2 territory, and gated on the bind default changing.
- Rendering. Structured output schemas are `D-UI-02`; the dashboard is its own capability.
- Replacing the CLI. Both are front ends over the same engine.
