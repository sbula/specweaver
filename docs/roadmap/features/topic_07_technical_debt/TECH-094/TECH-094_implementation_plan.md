# Implementation Plan: No CI Runs the Tests
- **Feature ID**: TECH-094
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-094/TECH-094_design.md
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-094/TECH-094_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-06)

## Scope

FR-1..FR-10, NFR-1..NFR-4 of the design. Three commit boundaries: the guards (local, provable
now), the workflow (provable by reading it), and the first real runs on GitHub (FR-8), which need
the user to push.

## Decisions (Phase 4, the user 2026-11-06)

| # | Decision |
|---|---|
| F1 | The workflow names actions by major tag (`actions/checkout@v5`, `astral-sh/setup-uv@v7`), not by commit hash: a hijacked action would find only a read-only token and no secrets `[agreed 2026-11-06]` |

Mine to take, recorded for review:
- One network guard, at the socket: `block_real_httpx2` and its fixture go; `fake_httpx2` and
  `respx` stay, because they answer before a socket opens (probe 2026-11-06: the suite passes).
- `quality.py cb` on CI gets `--base` (the pull request's base, or the commit before the push), so
  its one changed-files check (`class_health`) judges what the push changed.

## Architecture (Phase 3)

| Mechanism | Home | Allowed? |
|---|---|---|
| Socket guard, skip rule | `tests/conftest.py` (test infrastructure) | yes: no product module changes |
| Guard tests (FR-7, FR-9, FR-10) | `tests/unit/` beside `test_live_marker_isolation.py` | yes |
| Workflow | `.github/workflows/tests.yml` | yes: repo tooling, no `src` change |

No tach edge; no `context.yaml` touched. `quality.py` stays as it is.

## Commit Boundaries

**CB-1 — no test reaches a server (FR-4, FR-9, FR-10).**
- Tests first:
  - Canary `tests/unit/test_no_test_reaches_a_server.py`: from a non-live test, a socket connect to
    `192.0.2.1:443` (TEST-NET-1, RFC 5737: routes nowhere) and to `127.0.0.1:11434` must raise the
    guard's error, naming the address. Red today: the first times out or fails with `OSError`, the
    second is refused by the OS (or reaches a local Ollama), never the guard's error. Also: a
    loopback connect to another port is allowed (a socket server started by the test answers).
  - Live keys `tests/unit/test_live_keys_only_in_live_tests.py`: every test file that names
    `SPECWEAVER_LIVE_KEYS` carries the `live` marker (today: 4 files, all marked); a planted
    unmarked file is caught.
- Green: in `tests/conftest.py`, the autouse fixture `_no_real_network` patches
  `socket.socket.connect` and `connect_ex` for every test not marked `live`: an address that is
  not loopback, or loopback port 11434, raises `RuntimeError("a test tried to reach the network:
  <address> — use fake_httpx2 or respx")`. A Unix socket path is allowed. Remove
  `block_real_httpx2`.
- Mutants (corpus `TECH-094_mutants.json`): the guard allows every address → canary objects; the
  11434 check dropped → canary objects; the live-keys check ignores the marker → its test objects.

**CB-2 — the workflow (FR-1, FR-2, FR-3, FR-5, FR-6, FR-7, NFR-4).**
- Tests first:
  - Skip rule `tests/unit/test_ci_fails_on_a_tool_skip.py` (with `pytester`): with `CI` set, a
    skip whose reason does not name Windows fails the session, naming the test and the reason; a
    Windows-only skip passes; without `CI` both pass. Red today: no rule.
  - Workflow guard `tests/unit/test_ci_workflow_keeps_its_promises.py` reads
    `.github/workflows/tests.yml` with `yaml.safe_load` and fails when: a `secrets.` reference or a
    `*_API_KEY` / `SPECWEAVER_LIVE_KEYS` name appears; a run line selects `live` or `toolchain`
    (`-m`) or calls `scripts/live.py` / `scripts/toolchain.py`; the matrix lacks `3.11` or `3.14`;
    `quality.py cb` or `doc` is missing; `permissions` is anything but `contents: read`; the
    triggers lack `push` to `main` or `pull_request`; `timeout-minutes` is missing or above 30;
    `concurrency` lacks `cancel-in-progress: true`. Red today: no file.
- Green:
  - `tests/ci_skips.py` (loaded by `tests/conftest.py` through `pytest_plugins`): a
    `pytest_runtest_logreport` hook collects skips; `pytest_sessionfinish` on the controller sets a
    failing exit status when `CI` is set and a reason does not contain `Windows`.
  - `.github/workflows/tests.yml`: `on: push: branches: [main]` and `pull_request`;
    `permissions: contents: read`; `concurrency: {group: tests-${{ github.ref }},
    cancel-in-progress: true}`; one job, `runs-on: ubuntu-24.04`, `timeout-minutes: 30`, matrix
    `python: ["3.11", "3.14"]`. Steps: `actions/checkout@v5` with `fetch-depth: 0`;
    `sudo apt-get install -y ripgrep`; `astral-sh/setup-uv@v7` with `python-version`;
    `uv sync --locked`; `uv run python -m pytest -n auto`; `uv run python scripts/quality.py cb
    --base <base>`; `uv run python scripts/quality.py doc`.
  - README: the badge `[![Tests](https://github.com/sbula/specweaver/actions/workflows/tests.yml/badge.svg)](https://github.com/sbula/specweaver/actions/workflows/tests.yml)`
    beside the Python badge.
  - `docs/dev_guides/working_in_this_repo.md`: what CI runs, the skip rule, the network guard.
- Mutants: the skip rule ignores `CI` → its test objects; the guard test's `live` check removed →
  a planted workflow line `pytest -m live` passes, its test objects.

**CB-3 — the first real runs (FR-8). Closes TECH-094 (HITL).**
- The user pushes CB-1 and CB-2. I read the run with `gh run list` and `gh run view --log-failed`
  (allowed 2026-11-06). Whatever fails on 3.11 or on the runner is fixed test-first, as a
  failing local test where one can be written, then pushed again by the user.
- Done when both matrix jobs are green on `main`; the run URL is the live demo in the design.

## Research Notes

- Socket probe 2026-11-06: refusing every non-loopback `connect` across the full suite left 12,669
  passed; no test reaches an outside server today. The 4 errors in that run came from the probe
  plugin's own fixture, not the block (the same tests pass without it).
- `httpcore`-level probe: 17 failures, all false: those tests answer with a `respx` fixture that
  started before the probe's patch. The socket level sits below every fake, so fakes still win.
- Port 11434 appears in no test or source file (grep 2026-11-06).
- `scripts/quality.py:103-117`: only `class_health` is diff-scoped at `cb`; `changed_files(base)`
  adds `git diff <base>...HEAD`, hence `fetch-depth: 0`.
- `tests/unit/test_live_marker_isolation.py` already keeps `live` opt-in (`addopts`, no gate script
  runs it, the marker on the tests); FR-7 and FR-10 extend that net to CI.

## Consistency (Phase 5)

- FR-4, FR-9, FR-10 → CB-1; FR-1, FR-2, FR-3, FR-5, FR-6, FR-7, NFR-4 → CB-2; FR-8 → CB-3.
  NFR-1: no `src` change before CB-3; NFR-2: hosted runner, no paid service; NFR-3: the socket
  guard runs in every local test, not only on CI.
- Red/blue, 2 cycles. Cycle 1:
  - (MEDIUM) the canary's red run sends one connection attempt to `192.0.2.1`, an address that
    routes nowhere; it uses a 0.5 s socket timeout, so a missing guard fails fast.
  - (MEDIUM) `pytester` starts a fresh session that does not load `tests/conftest.py`: the skip
    rule lives in `tests/ci_skips.py`, loaded by `conftest.py` through `pytest_plugins`, so the
    test can run it with `-p tests.ci_skips`.
  - (MEDIUM) under xdist each worker also ends a session: the rule acts only on the controller
    (no `workerinput` on its config), where every report arrives.
  - (MEDIUM) `asyncio` connects through `socket.socket.connect` on its sockets, so async clients
    are covered too; the canary has an async case.
  - (LOW) the first push of a branch has an all-zero `before`: `--base` then falls back to `HEAD~1`.
  - (LOW, accepted) a test that starts `sw` in a subprocess is outside the in-process guard. It gets
    the temp `SPECWEAVER_DATA_DIR` (no `keys.env`), so no hosted model has a key; on CI nothing
    listens on 11434. Recorded in the walkthrough.
  Cycle 2: none above threshold.

## Backlog

None.
