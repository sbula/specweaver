# What share of real Python projects can the container sandbox prepare?

`TECH-031` measured which dependency layouts the prepare phase can turn into a working QA
environment, using fixtures built on this box. That answered *which kind* of project works and
explicitly left the share unmeasured: "a percentage would need a corpus of real repositories".
This is that corpus.

## Corpus

The 150 most-downloaded packages on PyPI, taken from `hugovk/top-pypi-packages` (15,000 ranked
entries, snapshot read 2026-08-18). The list is defined outside this repo and ordered by download
count, so the sample cannot be steered by whoever runs the measurement — that is the only reason
it was chosen over anything hand-assembled.

Each project was resolved to its GitHub repository through the PyPI JSON API (`project_urls`,
falling back to `home_page`), and its `pyproject.toml` read from `main`, then `master`.

| Outcome | n |
|---|---|
| classified — `pyproject.toml` read at the repo root | **121** |
| no `pyproject.toml` at the repo root (monorepo path, or `setup.py` only) | 22 |
| no GitHub URL in the package metadata | 7 |

The 29 unresolved projects are excluded from the denominator rather than counted as failures.
Including them would move every share below downward; 121 is the conservative denominator.

## What they declare

| Layout | n | share of 121 |
|---|---|---|
| PEP 735 `[dependency-groups]` | 50 | 41.3% |
| neither groups nor Poetry | 55 | 45.5% |
| `[project.optional-dependencies]` with a dev-ish extra | 11 | 9.1% |
| Poetry | 5 | 4.1% |

The 66 projects that declare no dependency group split by what actually manages their dev
environment:

| Mechanism | n |
|---|---|
| `tox.ini` / `noxfile.py` | 32 |
| an extra named `dev`/`test`/`lint`/… | 11 |
| nothing declared in-tree | 16 |
| extras, none of them dev-ish | 7 |

## What the sandbox can actually prepare

The prepare phase runs `uv sync --frozen`. Two preconditions must both hold: a committed `uv.lock`,
and the test tooling reachable by a **default** sync — which means the `dev` group or the runtime
dependencies, because `uv sync` installs neither `[project.optional-dependencies]` nor any
non-default group.

| Condition | n | share |
|---|---|---|
| `uv.lock` committed at the repo root | 33 | 27.3% |
| test tooling reachable by a default `uv sync` | 29 | 24.0% |
| **both — the sandbox produces a usable toolchain** | **21** | **17.4%** |

Failure is dominated by the lockfile, not by the layout debate the ticket opened with:

| Why the other 100 fail | n | share |
|---|---|---|
| no `uv.lock` — `--frozen` refuses | 88 | 72.7% |
| groups exist, but the tooling is not in the default `dev` group | 9 | 7.4% |
| no group carries the test tooling at all | 3 | 2.5% |

The middle row is a distinct defect from the one `TECH-031` fixed. 50 projects use PEP 735, but only
40 name a group `dev`; `test` (17) and `tests` (9) are common and `uv sync` does not install them.
Being on the supported layout is not sufficient — the group has to be named the one thing uv syncs
by default.

### That row is now closed

The prepare phase reads the target's `pyproject.toml` and requests the groups that declare a test
runner. Measured against the same corpus, the usable share moves **17.4% → 23.1%** (21 → 28 of 121).
The 93 that still fail are 88 with no lockfile and 5 that declare no runner anywhere.

Detection is by **content, not name**, and the corpus is the reason. The names are a long tail —
`testing`, `ci`, `test-core`, `dev-base`, `nox` and `emscripten` all carry a runner — so `{test,
tests}` recovers 6 of the 7 and no list covers the tail. The tail cuts the other way too: SQLAlchemy
declares `tests-postgresql`, `tests-mysql` and `tests-oracle`, which hold database drivers and no
runner, so a `test*` prefix rule would install three database stacks to find nothing.

A name list is not merely incomplete, it is unsafe. `uv sync --group nosuchgroup` exits 2 —
*"Group `nosuchgroup` is not defined in the project's `dependency-groups` table"*, verified against
uv 0.12.3 — so a speculative name breaks the prepare phase for every project that does not happen to
use it. Only groups the manifest declares are ever passed.

`coverage` is excluded from the runner set: it measures a run and cannot start one. Including it
changed the corpus result by zero projects.

## Dropping `--frozen` is not the fix

Removing the flag raises the ceiling from 17.4% to at most 24.0% — the share whose tooling a default
sync would reach if a lockfile appeared from somewhere. It does not reach that ceiling in practice:
`/workspace` is mounted read-only, so `uv` cannot write the lockfile it would have to resolve, and
resolving would need network the sandbox does not grant. `--frozen` converts that into an error that
names the precondition. It costs no coverage.

## Bias, stated

**This corpus is entirely libraries.** Ranking by PyPI downloads selects for published packages, and
published packages have a specific reason not to commit a lockfile: they must resolve against many
dependency versions, so pinning one set is against their interest. Applications — the kind of
repository someone points SpecWeaver at — commit `uv.lock` precisely because they deploy.

So **17.4% is a floor, not an estimate.** The direction of the bias is known; its size is not. An
application corpus would need a repository ranking this box cannot obtain (GitHub code search
requires authentication, and `gh` is not installed here), so it is left unmeasured rather than
approximated.

What survived the bias was the second finding, which has nothing to do with lockfiles: a fifth of the
projects already on PEP 735 failed because their group was named `test` rather than `dev`. That one
was ours, did not depend on how the ecosystem trends, and is fixed.

## Method note

Layout classification parses `pyproject.toml` with `tomllib` rather than matching text. The test
runner was detected by matching dependency names against `pytest|nox|tox|coverage`; a looser
substring rule that also caught `hatch` and `unittest` produced the identical headline (21/121), so
the number is not an artefact of where that line was drawn.
