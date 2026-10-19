# Implementation Plan: Core Orchestration API [Corrections from the Phase 6 review]
- **Feature ID**: D-UI-01
- **Design Document**: docs/roadmap/features/topic_01_ui_glass/D-UI-01/D-UI-01_design.md
- **Implementation Plan**: docs/roadmap/features/topic_01_ui_glass/D-UI-01/D-UI-01_corrections_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-19

**FRs owned**: FR-6, FR-7, FR-8, NFR-1 (new, from the review of 2026-10-19); FR-2's WebSocket ending, found there

## Shape

| Piece | Where | Tag |
|---|---|---|
| a guard in front of every route: no token, no answer (401, `{detail, error_code: "UNAUTHORIZED"}`); the health check stays open | `interfaces/api/auth.py` (an ASGI middleware, so the WebSocket is guarded too) | NEW |
| the token is read from `Authorization: Bearer`, from the `sw_token` cookie, or — on a WebSocket, which a browser cannot give a header — from `?token=`; compared with `hmac.compare_digest` | `auth.py` | NEW |
| a browser's first visit with `?token=` gets the cookie (`HttpOnly`, `SameSite=Strict`, path `/`) and a redirect to the same address without the token | `auth.py` | NEW |
| `create_app` takes the token and has no default, so no app is ever built open | `interfaces/api/app.py` | MODIFY |
| `sw serve` makes a token each start (`secrets.token_urlsafe(32)`), writes it to `serve.token` beside `settings.toml`, readable by its owner only, and prints the dashboard address with it | `interfaces/cli/routers/serve_router.py` | MODIFY |
| `[serve] max_runs` in the machine settings; the run and resume endpoints refuse without it, naming the key (409, `SETTING_NOT_SET`), and the run registry takes its limit from it | `core/config/llm_settings.py`, `interfaces/api/v1/pipelines.py`, `event_bridge.py` | MODIFY |
| the API tests build their app with a test token and send it | `tests/` (18 files), a shared helper beside `tests/fake_http.py` | MODIFY |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the token: guard, cookie, file, `sw serve` | FR-6, NFR-1 | a request with no token — or with `Host: evil.example`, as a rebinding page sends — starts a pipeline |
| CB-2 | `[serve] max_runs` | FR-7 | a fourth run is refused by a number nobody set |
| CB-3 | the WebSocket ends for a run not running and for a client that leaves; the `US-06` tablet journey | FR-2, FR-8 | a stream for an unknown run waits for ever |

| CB | Tier | Test |
|---|---|---|
| CB-1 | integration + e2e | through `TestClient`: an API route, a dashboard page, a form post and the WebSocket without the token are refused; with the header, the cookie or the WebSocket query they answer; a wrong token is refused; the health check answers without one; a first visit with `?token=` sets a strict, HttpOnly cookie and redirects without the token. e2e: `sw serve` (uvicorn replaced) writes `serve.token` with mode 600 and prints an address carrying it, and no log line carries the token |
| CB-2 | integration | with `[serve] max_runs = 1` a second concurrent run is refused; without the section a run is refused naming `serve.max_runs` |
| CB-3 | integration + e2e | an unknown run answers `RUN_NOT_FOUND`, a finished one `done`, a client that leaves is unsubscribed, each failing after 10 s rather than hanging; a browser opens the printed address, approves a parked run's gate in the dashboard, and the run completes; without the cookie the gate is refused |

## Mutants (into `D-UI-01_mutants.json`)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | the guard passes everything; the health exception widened to every path; the cookie without `SameSite`; the WebSocket left unguarded; the token file world-readable | CB-1 tests |
| CB-2 | the limit fixed at 3 again; the refusal skipped | CB-2 tests |

## Research Notes

- 28 routes: 23 under `/api/v1`, `/healthz`, four dashboard routes (`interfaces/api/ui/routes.py`,
  `htmx.py`); the dashboard's gate is a form post (`ui/htmx.py:23`), which a cross-site page can send.
- CORS (`app.py:61-74`) allows local origins by regex plus `--cors-origins` and `CORS_ORIGINS`.
- `create_app` is built in 18 test files; `sw serve` builds it at `serve_router.py:64`.
- Runs start through `get_event_bridge().start_run` (`v1/pipelines.py:77`, `:193`), limited by
  `MAX_CONCURRENT_RUNS = 3` (`event_bridge.py:20`).
- `keys.env` is refused unless only its owner can read it (`C-FLOW-13` NFR-2): `serve.token` follows
  the same rule.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | How `sw serve` protects itself | a token per start, Jupyter-style `[agreed 2026-10-19]` |
| Q2 | The limit of 3 concurrent runs | `[serve] max_runs`, required to start a run `[agreed 2026-10-19]` |
| Q3 | Who owns `US-06` P-3 and P-4 | `D-UI-01` FR-8, an e2e; `US-07`'s paths go to `D-UI-03` alone `[agreed 2026-10-19]` |

## Backlog

none
