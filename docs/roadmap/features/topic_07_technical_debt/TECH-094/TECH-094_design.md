# Design: No CI Runs the Tests

- **Feature ID**: TECH-094
- **Phase**: Topic 07 (Technical Debt)
- **Status**: APPROVED (the user, 2026-11-06)
- **Kind**: `tooling`
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-094/TECH-094_design.md
- **Origin**: 2026-11-06, after `TECH-079`; the user's order puts CI before RAG. Only
  `.github/workflows/container.yml` exists, and it builds the container image on a version tag.

## Feature Overview

TECH-094 adds a GitHub Actions workflow that runs, on every push to `main` and every pull request,
the same gate a local commit runs: the default suite (unit, integration, e2e) and `quality.py cb`
and `doc`, on Python 3.11 and 3.14 `[agreed 2026-11-06]`. CI never calls a real model: it holds no
secrets, and every non-live test fails when it tries to reach a server outside the machine, through
either HTTP library the model clients use `[agreed 2026-11-06]`. A test that skips on CI for a
reason other than the platform fails the run, so a missing tool never looks like a pass
`[agreed 2026-11-06]`. The README shows the result as a badge. It does not touch the `live` and
`toolchain` tiers, the nightly mutation run, or any product code outside what 3.11 needs.

## The Defect (measured 2026-11-06)

| Finding | Measured |
|---|---|
| No test runs on GitHub | `.github/workflows/` holds only `container.yml` (`on: push: tags: ['v*']`, image build) |
| The README promises 3.11 untested | README badge "Python 3.11+", `pyproject.toml` `requires-python = ">=3.11"`; the venv and every run are 3.14 (`.venv/bin/python3.14`) |
| The model guard has a gap | `tests/conftest.py:103` `_no_real_network` blocks `httpx2` only (`tests/fake_http.py:block_real_httpx2`: openai, anthropic). `google-genai` (`infrastructure/llm/adapters/gemini.py:14`) and `mistralai` send through `httpx`, which `respx` fakes only where a test asks; an unfaked request leaves the machine |
| Tools some tests need | git, bash, cargo, mvn, npm, javac, kotlinc, rg (`shutil.which` in tests); locally all present; the 9 local skips are 8 Windows-only and 1 `rg not on PATH` |

## Path List (`ADR-005`)

| # | Path | Span | Owner | Status |
|---|---|---|---|---|
| P-1 | push to `main` → workflow → suite + `cb` + `doc` on 3.11 and 3.14 → status on GitHub and the README badge | GitHub Actions, the repo's gates | TECH-094 (FR-1..FR-3, FR-6, FR-8) | ⬜ |
| P-2 | a pull request from a fork → the same jobs with a read-only token and no secrets | GitHub Actions | TECH-094 (FR-1, FR-4) | ⬜ |
| P-3 | a non-live test sends a request to a real server through `httpx` or `httpx2` → the test fails, locally and on CI | tests, the model client libraries | TECH-094 (FR-4) | ⬜ |
| P-4 | a test skips on CI because a tool is missing → the run fails naming the test | tests, GitHub Actions | TECH-094 (FR-5) | ⬜ |

## Research Findings

### Codebase Patterns
- `scripts/commit_gated.py` is the local gate: the full suite, then `quality.py cb`, then `doc`.
  CI repeats those three; it does not commit.
- `pyproject.toml:72` `addopts = ... -m 'not live and not toolchain'`: a plain `pytest` already
  leaves out real models and real build tools. `pytest-xdist` is a dev dependency (`-n auto`).
- `uv.lock` (`requires-python = ">=3.11"`) resolves for 3.11 to 3.14. Every `.py` under `src`,
  `tests` and `scripts` parses with `ast.parse(..., feature_version=(3, 11))` (probe 2026-11-06).
- `tests/conftest.py:54` points `SPECWEAVER_DATA_DIR` at a temp folder, so CI never needs a home
  setup.
- Tests mocking `httpx` use `respx`; the new `httpx` block must let `respx` answer first and allow
  loopback hosts (local test servers).
- Some gates and tests read git history or the working tree; CI checks out the full history
  (`fetch-depth: 0`) and installs with `uv sync --locked`, so a stale lock fails instead of
  resolving fresh.

### Red/Blue (Phase 6), 2 cycles
- R1 (MEDIUM) A stuck job runs up to GitHub's 6-hour default, and pushes in a row each run in full:
  put to the user, settled as NFR-4.
- R2 (MEDIUM) "skips for the platform" must be checkable: the allowed reasons are the ones naming
  Windows (`Windows-only`, `SIGBREAK only exists on Windows`); any other reason fails on CI.
- R3 (MEDIUM) Loopback is allowed, and a local Ollama listens on loopback. On CI nothing listens
  there except what a test starts, so FR-4 holds on CI; locally it is unchanged from today.
- R4 (MEDIUM) A shallow clone or a fresh lock would make CI judge a different tree than the local
  gate: fixed above (`fetch-depth: 0`, `--locked`).
- R5 (LOW) The workflow file name becomes the badge URL; it is named in FR-1 for approval.
Cycle 2: none above threshold.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| `actions/checkout` | v5 (first on Node 24) | `uses: actions/checkout@v5` | [checkout#2226](https://github.com/actions/checkout/pull/2226) |
| `astral-sh/setup-uv` | v7 (v8 drops floating tags) | `python-version:` input, `enable-cache:` | [setup-uv README](https://gitea.psi.ch/astral-sh/setup-uv/raw/commit/bd99ba67dcfee6c3164c643cc8f3fe3f597ca607/README.md), [v8 note](https://git.tainton.uk/repos/pypilot/pulls/435) |
| `ubuntu-24.04` runner | current image | Java 17/21/25, Kotlin, Rust/Cargo, Maven, Node; no ripgrep | [runner-images ubuntu24](https://github.com/actions/runner-images/releases/tag/ubuntu24%2F20260720.247) |

The versions are confirmed by the first real run (FR-8), not by reading.

### Blueprint References
None.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | `.github/workflows/tests.yml` SHALL run on every push to `main` and every pull request, those from forks included `[agreed 2026-11-06]`, with `permissions: contents: read` and no `secrets.` reference | GitHub | a push or a pull request | the jobs start; a fork's code gets a read-only token and nothing else |
| FR-2 | Each job SHALL install the locked dependencies with uv and run the default suite in parallel (`python -m pytest -n auto`), which selects unit, integration and e2e and never `live` or `toolchain` `[agreed 2026-11-06]` | the workflow | test | the same tests as a local plain `pytest` |
| FR-3 | Each job SHALL then run `scripts/quality.py cb` and `scripts/quality.py doc` `[agreed 2026-11-06]`; mypy stays the only type check `[agreed 2026-11-06]` | the workflow | gate | the same gate as `commit_gated.py` |
| FR-4 | CI SHALL never call a real model `[agreed 2026-11-06]`: the workflow sets no provider key, and every test not marked `live` SHALL fail when it sends a request to a host other than loopback through `httpx` or `httpx2`, unless a fake (`respx`, `fake_httpx2`) answers it | the tests | reach the network | the test fails naming the URL; no request leaves the machine |
| FR-5 | When `CI` is set (GitHub sets it), a test that skips for a reason other than the platform (Windows-only) SHALL fail the run, naming the test and the reason `[agreed 2026-11-06]`; the workflow installs every tool the suite looks for (ripgrep with apt; the rest are on the image) | the tests on CI | skip | a missing tool is a failure, never a silent pass |
| FR-6 | The README SHALL show the workflow's status badge beside the Python badge `[agreed 2026-11-06]` | a visitor | open the repo | sees whether `main` passes |
| FR-7 | A guard test SHALL fail when the workflow loses a promise: it names a secret or a provider key, selects `live` or `toolchain`, drops 3.11 or 3.14, drops `cb` or `doc`, or widens its permissions | the suite | read the workflow | the promises of FR-1..FR-5 cannot regress unseen |
| FR-8 | The suite and both gates SHALL pass on Python 3.11 and 3.14 on GitHub; code that fails on 3.11 is fixed in this ticket `[agreed 2026-11-06]` | the workflow | run on 3.11 | the README's "3.11+" is proven |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-2 | the default selection | `pyproject.toml` `[tool.pytest.ini_options] addopts` | read `pyproject.toml:72` |
| FR-3 | the gates | `scripts/quality.py cb`, `doc` | run 2026-11-06: 17/17, 14/14 |
| FR-4 | the existing guard | `tests/fake_http.py` `block_real_httpx2()`, `tests/conftest.py:103` `_no_real_network` | read both |
| FR-4 | the clients on `httpx` | `google.genai` (`adapters/gemini.py:14`), `mistralai` | read `tests/fake_http.py` docstring and `gemini.py` |
| FR-5 | skip reasons | pytest `TestReport` with `outcome == "skipped"` and its `longrepr` reason | to be probed at dev with a five-line test |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Behaviour stays the same | No product code changes except what FR-8 needs on 3.11; the local suite still passes |
| NFR-2 | CI cost stays at zero | No paid runner, no paid service, no card `[agreed 2026-11-06]` (GitHub-hosted `ubuntu-24.04`) |
| NFR-3 | The guard holds locally too | FR-4's block applies to every local run, not only on CI |
| NFR-4 | A run cannot burn hours | Each job stops after 30 minutes (`timeout-minutes: 30`), and a newer push to the same branch or pull request cancels the older run `[agreed 2026-11-06]` |

## External Dependencies

GitHub Actions (`actions/checkout@v5`, `astral-sh/setup-uv@v7`), hosted runner `ubuntu-24.04`. No
new Python dependency.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | One workflow file `tests.yml`, a matrix over Python 3.11 and 3.14, separate from `container.yml` | different trigger and job; one file per purpose | No |
| AD-2 | The model-call guard lives in the tests (`tests/fake_http.py`, `tests/conftest.py`), not in product code | the rule is about tests; product code keeps no CI branch | No |
| AD-3 | The skip rule lives in `tests/conftest.py`, active only when `CI` is set | locally a missing tool may skip, as today; on CI it must not | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| Workflow and badge | small | low |
| `httpx` guard | small | medium: tests that rely on a real loopback server must keep working |
| Skip rule and tools | small | low |
| 3.11 fixes | unknown until the first run | medium |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| The user (job search) | visible green CI on the repo | high |
| Users on 3.11..3.13 | the promised versions really work | medium |
| Maintainers | a broken push is seen on GitHub, not only locally | medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| A test passes locally but fails on the runner (paths, tools, cores) | medium | low | fixed in this ticket, before sign-off |
| A test reached a real server unnoticed | low | high | FR-4 makes it fail everywhere |

### Refactoring Opportunities
None.

## Non-Goals

- The `live` tier (real models) and the `toolchain` tier (real Maven, Gradle, npm, cargo): they stay
  in the local nightly run (`TECH-049` AD-8) `[agreed 2026-11-06]`.
- The nightly mutation corpus.
- pyright `[agreed 2026-11-06]`.
- Windows and macOS runners.

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `docs/dev_guides/working_in_this_repo.md` | what CI runs, the skip rule, the network guard | ⬜ To be updated during Pre-commit |

## Sub-Feature Breakdown

Single feature — no decomposition.
- **Scope**: the guards (FR-4, FR-5, FR-7), the workflow and badge (FR-1..FR-3, FR-6), and what the
  first real runs find (FR-8).
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8]
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-094/TECH-094_implementation_plan.md

## Execution Order

Single feature — no decomposition. FR-8 needs a real run, so the user pushes before the last
commit boundary.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| — | No CI runs the tests | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Grilling 2026-11-06** (the user): round 1 — ticket, suite plus `cb`, 3.11 and 3.14, mypy only;
round 2 — a non-platform skip fails CI, `gh run list`/`view` allowed to read results, `doc` too, a
README badge, fork pull requests run read-only. Each decision sits beside its fact above.
Q10 (30-minute limit, cancel superseded runs) agreed at approval. **Design approved 2026-11-06** (the user).
**Next step**: the implementation plan (`specweaver-implementation-plan TECH-094`).
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ and resume from
there using the appropriate skill.
