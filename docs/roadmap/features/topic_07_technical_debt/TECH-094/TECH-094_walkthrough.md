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
