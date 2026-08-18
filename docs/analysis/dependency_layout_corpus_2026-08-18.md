# What share of real Python projects can the container sandbox prepare?

`TECH-031` measured which dependency layouts the prepare phase can turn into a working QA
environment, using fixtures built on this box. That answered *which kind* of project works and
explicitly left the share unmeasured: "a percentage would need a corpus of real repositories".
This is that corpus.

> **The first version of this document used the wrong predicate** and its numbers were wrong. It
> counted a project as working if any dependency group declared `pytest`, `nox` **or** `tox`. The
> Python QA runner invokes `python -m pytest` and nothing else, so a venv holding `tox` fails
> exactly as it did before. Eight OpenTelemetry packages were credited on a `dev` group holding
> `tox`, which inflated both ends of the comparison. Every figure below uses the predicate that
> matches what the runner actually invokes: **pytest is importable in the prepared environment**.

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

## What the sandbox can prepare

The prepare phase runs `uv sync --frozen`. Two preconditions must both hold: a committed `uv.lock`,
and pytest reachable by the sync — which before this ticket meant the `dev` group or the runtime
dependencies, because `uv sync` installs neither `[project.optional-dependencies]` nor any
non-default group.

| Condition | n | share |
|---|---|---|
| `uv.lock` committed at the repo root | 33 | 27.3% |
| pytest declared anywhere in the manifest | 40 | 33.1% |
| pytest reachable by a **default** `uv sync` | 17 | 14.0% |
| **usable before the fix** (lock + default sync) | **10** | **8.3%** |
| **usable after the fix** (lock + any group) | **20** | **16.5%** |

Group detection doubles the supported share. The full cross-tab, which is the honest way to read
the failures — the two causes overlap, so a single ordered list would misattribute them:

| | `uv.lock` committed | no `uv.lock` |
|---|---|---|
| **declares pytest** | **20** — usable | 20 |
| **declares no pytest** | 13 | 68 |

**81 of 121 projects never name pytest in `pyproject.toml` at all.** That, not the lockfile, is the
dominant reason the sandbox cannot prepare a target: 32 of them hand the whole dev environment to
`tox` or `nox`, and the rest use requirements files or declare nothing in-tree.

## The group-name defect, and why it was bigger than it looked

50 projects use PEP 735. Only **15** put pytest in the `dev` group that `uv sync` installs unasked:

| Group | declared by | of those, carry pytest |
|---|---|---|
| `dev` | 40 | 15 |
| `test` | 17 | 14 |
| `tests` | 9 | 9 |
| `typing` | 4 | 4 |
| `coverage` | 4 | 2 |
| `docs` / `lint` / `build` / `release` | 34 | 0 |

So **23 projects put pytest in `test` or `tests`** against 15 in `dev`. A project could sit exactly
on the layout the prepare phase supports and still get a venv with no runner in it — and that was
the more common case, not the exception.

The prepare phase now reads the target's `pyproject.toml` and requests the groups that declare
pytest. Detection is by **content, not name**:

- The names are a long tail. `testing`, `ci`, `test-core` and `dev-base` all carry pytest, so no
  fixed list covers them.
- The tail cuts the other way too: SQLAlchemy declares `tests-postgresql`, `tests-mysql` and
  `tests-oracle`, which hold database drivers and no runner, so a `test*` prefix rule would install
  three database stacks to find nothing.
- A name list is unsafe, not merely incomplete. `uv sync --group nosuchgroup` exits 2 —
  *"Group `nosuchgroup` is not defined in the project's `dependency-groups` table"*, verified against
  uv 0.12.3 — so a speculative name breaks the prepare phase for every project that does not happen
  to use it. Only groups the manifest declares are ever passed.

`tox` and `nox` are excluded from detection even though both are test runners: they build their own
environments, so installing one leaves `python -m pytest` failing exactly as before while pulling in
the rest of that group. The prepare phase executes arbitrary sdist build code, so widening what an
untrusted project builds for no gain is the wrong trade. `coverage` is excluded for the simpler
reason that it measures a run and cannot start one.

## The extras branch is worth nothing, measured

`TECH-031`'s first candidate approach also proposed requesting a specific extra when the tooling
lives in `[project.optional-dependencies]`. Measured against the corpus, that branch would add
**zero** projects: every uv-managed repository that declares pytest in an extra already declares it
in a group or in its runtime dependencies. The branch is closed by measurement rather than left
half-built. (`--all-extras` was separately rejected by the user on 2026-08-12.)

## Rung 1, delivered: the lockfile is no longer a wall

20 of the 121 declare pytest and commit no lockfile. They now take a second route — `uv venv` then
`uv pip install`, resolving from the manifest and writing nothing into the read-only source tree —
which takes the supported share from **16.5% to 33%**. A committed lockfile still takes the frozen
path, because a fresh resolution does not reproduce the project's own pinned set; the phase logs by
name when it resolves instead.

This also unblocks the rest. Of the 68 projects in the two reachable failure classes, only 29 have a
lockfile, so reading `tox.ini` and friends *without* this would have recovered nine projects: we
would have learned what to install and had no environment to install it into.

## Rung 2, delivered — and worth less than projected

48 projects declare pytest outside the manifest. The reachable share is **27**, not 48, taking the
corpus from 33% to **55%**. The projection of 73% assumed every one of the 48 could be read; parsing
all 30 real `tox.ini` files showed otherwise.

| Route | projects |
|---|---|
| a `requirements` file naming pytest — installed with `-r`, no parsing | 20 |
| a plain `pytest` line in a tox `testenv` deps block | 18 |
| union (11 projects offer both) | **27** |
| not reachable at this scope | 21 |

**Why the tox half stops at 18 of 31.** Across those 30 files, **891** dependency lines carry
`{...}` substitution — tox factors like `py3{10-14}: -r reqs.pip`, `{[testenv]deps}`
back-references, `{toxinidir}` paths — against 236 plain requirement lines. Selecting the right
factor means knowing which environment tox would have run, which is implementing tox. Only 18 of the
30 have a plain `pytest` line at all.

What cannot be read is **reported, not dropped**: the prepare phase logs how many lines it skipped
and the first few verbatim, because silence would let a partial environment pass for a complete one
— and those lines are the likeliest home of the plugins a suite needs.

Two ordering rules, both load-bearing:

- **A `requirements` file wins over `tox.ini`.** `uv pip install -r` reads the format natively,
  including its own includes, so nothing is parsed. Installing both would risk two conflicting pins
  of the same package.
- **Nothing is read at all when the manifest declares pytest.** Such a project pinned its runner;
  layering a `tox.ini` block over a locked resolution turns a reproducible run into a mixed one for
  no gain.

## Rung 3, delivered: the sandbox supplies a runner, and says so

33 projects declare pytest nowhere any of the above can read. They now get pytest from the sandbox,
which takes the corpus to a ceiling of **83%** (100 of 121) — the remainder being projects whose
`pyproject.toml` is not at the repository root at all.

**This rung changes what a green run means, and that is why the disclosure is part of it.** The
version is the sandbox's choice, not the project's, and the plugins a suite may need are absent. So
the result carries a `toolchain_note` saying exactly that — not a log line, which nobody reads, but
a field on the `TestRunResult` the caller already handles. A passing result then describes the
sandbox's environment rather than the project's, and says so in the same object.

It fires strictly last: after the manifest, after `tox.ini`, after every `requirements` file. A
project that named a version — even an old one — has its own choice honoured.

**What the yield actually is, is only partly measured.** Of the 33, GitHub's unauthenticated rate
limit allowed 16 repository trees to be read. All 16 contain `test_*.py` or `*_test.py` files, so a
supplied runner has something to run. Six of those 16 also ship a `conftest.py`, which is where
plugin imports usually live — those are the runs most likely to trade *"no module named pytest"* for
a collection error naming a plugin instead. The other 17 are unmeasured, not assumed.

## Dropping `--frozen` is not the fix

Removing the flag raises the ceiling from 16.5% to at most **33.1%** — the share that declares pytest
at all, if a lockfile appeared from somewhere. It does not reach that ceiling in practice:
`/workspace` is mounted read-only, so `uv` cannot write the lockfile it would have to resolve, and
resolving would need network the sandbox does not grant. `--frozen` converts that into an error that
names the precondition. It costs no coverage.

## Bias, stated

**This corpus is entirely libraries.** Ranking by PyPI downloads selects for published packages, and
published packages have two specific reasons to look worse here than an application would: they must
resolve against many dependency versions, so committing a lockfile is against their interest, and
they test across many interpreters, which is what `tox` and `nox` are for. Applications commit
`uv.lock` because they deploy, and typically invoke pytest directly.

So **16.5% is a floor, not an estimate.** The direction of the bias is known; its size is not. An
application corpus would need a repository ranking this box cannot obtain (GitHub code search
requires authentication, and `gh` is not installed here), so it is left unmeasured rather than
approximated.

What survives the bias is the group-name finding, which has nothing to do with lockfiles or with
`tox`: among projects that *do* declare pytest in a PEP 735 group, more put it outside `dev` than
in it.

## Method note

Layout classification parses `pyproject.toml` with `tomllib` rather than matching text. Runner
detection normalises each dependency spec to its distribution name — stripping extras, version
constraints and environment markers, lowercasing, and folding `_` to `-` — then matches `pytest`
exactly or as a `pytest-` prefix. That accepts `pytest-cov` and `pytest_asyncio` and rejects
`my-pytest-plugin`.
