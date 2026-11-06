# Walkthrough: TECH-094 — No CI Runs the Tests

## CB-1: no test reaches a server (FR-4, FR-9, FR-10)

**What changed**
- `tests/conftest.py`: `_no_real_network` now blocks at the socket for every test not marked
  `live`: `socket.socket.connect` and `connect_ex` refuse any address that is not loopback, and
  loopback port 11434 (Ollama) `[agreed 2026-11-06]`; `socket.getaddrinfo` refuses an outside host
  name, because a lookup already sends a DNS query off the machine. A Unix socket, a loopback server
  a test starts, and numeric addresses still work. Fakes (`fake_httpx2`, `respx`) answer before a
  socket opens.
- `tests/fake_http.py`: `block_real_httpx2` is gone; the socket guard covers `httpx2`, `httpx`
  (google-genai, mistralai) and every other client.

**Why it matters.** Before, a non-live test could reach a real Gemini or Mistral server through
`httpx`, and any test could reach a local Ollama. Now no test that runs by default can, and a new
test is covered without anyone remembering to do anything.

**Tests**
- Red first: the canary `tests/unit/test_no_test_reaches_a_server.py` (red: 6 of 8; the two allow
  cases passed). Outside addresses are documentation ranges and a `.invalid` name, so a missing
  guard reaches nothing real.
- `tests/unit/test_no_real_network.py` gains `httpx` cases (sync and async).
- `tests/unit/test_live_keys_only_in_live_tests.py`: a file that reads `SPECWEAVER_LIVE_KEYS` must
  be marked `live` (today: 4 files, all marked).
- Full suite with the guard: 12,685 passed; no test needed the network.

**Mutants.** TECH-094 corpus (new): `every-address-allowed`, `name-lookups-open`,
`connect-ex-open`, `ollama-port-open`, `unmarked-reader-passes`, each objected.

**Red/blue (2 cycles).** Cycle 1: (MEDIUM, accepted) a session- or module-scoped fixture that
connects during its setup runs before this function-scoped guard; none does today. (MEDIUM,
checked) `asyncio` resolves through `socket.getaddrinfo` and connects through `socket.connect`, so
async clients are covered (canary case). (LOW, checked) xdist workers talk over pipes, not
sockets. (LOW, accepted) a test that starts `sw` in a subprocess is outside the in-process guard;
it gets the temp data folder with no `keys.env`. Cycle 2: none above threshold.

## CB-2: the workflow (FR-1, FR-2, FR-3, FR-5, FR-6, FR-7, NFR-4)

**What changed**
- `.github/workflows/tests.yml`: on push to `main` and every pull request; `permissions: contents:
  read`; a newer push cancels the older run; one job per Python (3.11, 3.14) on `ubuntu-24.04`,
  30 minutes at most `[agreed 2026-11-06]`. Steps: full checkout (`fetch-depth: 0`), ripgrep from
  apt, `astral-sh/setup-uv@v7`, `uv sync --locked`, `pytest -n auto`, `quality.py cb --base <the
  pull request's base, or the commit before the push>`, `quality.py doc`. No secret, no key.
- `tests/ci_skips.py`, registered by `tests/conftest.py`: with `CI` set, a skip whose reason does
  not name Windows fails the session and lists each such test `[agreed 2026-11-06]`; an `xfail` is
  not a skip; under xdist only the controller judges.
- README: the Tests badge. `working_in_this_repo.md` gains trap 11 (the network guard, live keys,
  what CI runs); `CLAUDE.md` says eleven traps.

**What a user sees.** A Tests badge on the repo; once pushed, each push shows a check on GitHub.

**Tests**
- Red first: `tests/unit/test_ci_fails_on_a_tool_skip.py` (no module) and
  `tests/unit/test_ci_workflow_keeps_its_promises.py` (no workflow), which also checks the badge.
- Checked for real: `CI=1 pytest .../test_search.py -n 2` exits 1 naming the `rg` skip; without
  `CI` it exits 0.
- Found at the gate: the live-keys rule from CB-1 counted any mention of `SPECWEAVER_LIVE_KEYS`, so
  the new guard's search pattern tripped it. It now counts only real reads (`os.environ[...]`,
  `.get(...)`, `os.getenv(...)`); three cases added.

**Mutants.** TECH-094 FR-5: `ci-ignored`, `windows-not-allowed`, `xfail-counted`; FR-7:
`model-call-unseen`, `permissions-unseen`; each objected.

**Red/blue (2 cycles).** Cycle 1: (MEDIUM, checked) the workflow uses `pull_request`, never
`pull_request_target`, so a fork's code never gets the repo's token with write rights; the only
value put into a shell line is a commit hash. (MEDIUM, checked) the 9 skips today: 8 name Windows,
the `rg` one goes away because CI installs ripgrep. (LOW) action tags, not hashes (F1). Cycle 2:
none above threshold. The real proof is the first run on GitHub (CB-3).
