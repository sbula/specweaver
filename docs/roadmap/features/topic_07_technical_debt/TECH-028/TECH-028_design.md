# Design: Split `dev` Dependency Definitions — Broken Default Sync, Test Tooling in the Container Image

- **Feature ID**: TECH-028
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED (2026-08-12)
- **Origin**: Found 2026-08-11 rebuilding the environment on a Linux server after the Windows
  laptop failed, during the `TECH-025`/`026`/`027` session. A plain `uv sync` produced an
  environment in which **5347 tests errored**. The cause was not the move, the Python version or the
  lockfile — it was the manifest.

## Problem Statement

`pyproject.toml` defines **two different things named `dev`**, and the split between them follows no
principle:

| `[dependency-groups] dev` (`pyproject.toml:139-146`) | `[project.optional-dependencies] dev` (`pyproject.toml:60-69`) |
|---|---|
| `pytest-xdist`, `complexipy`, `respx`, `types-networkx`, `types-pyyaml` | `pytest`, `pytest-cov`, `pytest-asyncio`, `ruff`, `mypy`, `tach`, `httpx`, `respx` |

`respx` is declared in both. More importantly the *runner* and its *plugin* are separated:
`pytest-xdist` sits in the group, `pytest` sits in the extra.

### Consequence 1 — the tool's default command yields an environment that cannot work

`uv` installs dependency-groups by default and extras only on request. So a bare `uv sync` installs
the parallel-test plugin **without the test runner**, and `pytest-asyncio` not at all. Measured on
this repo, 2026-08-11:

```
uv sync                  ->  5347 errors      (every async fixture: no plugin handles it)
uv sync --extra dev      ->  5442 passed, 13 failed, 12 errors
uv sync --all-extras     ->  5567 passed, 6 failed
```

The 5347-error state is not a partial install a developer would recognise as incomplete — `pytest`
resolves transitively via `pytest-xdist`, so the suite *runs* and reports mass failure. Under
`pytest 9` the missing async plugin is a hard error rather than a warning, which is what turns a
confusing environment into a wall.

### Consequence 2 — the container image would ship lint and test tooling

`Containerfile:25` reads:

```dockerfile
RUN uv sync --all-extras --no-dev --frozen
```

`--no-dev` drops the dependency-group; `--all-extras` pulls the `dev` **extra** straight back in.
Verified by dry-run on 2026-08-11 — the flag pair removes exactly two packages:

```
$ uv sync --all-extras --no-dev --frozen --dry-run
 - complexipy==6.2.0
 - pytest-xdist==3.8.0
```

Everything else stays. The image built from this file therefore contains `pytest`, `pytest-cov`,
`pytest-asyncio`, `ruff`, `mypy`, `tach`, `respx` and `httpx` — while omitting the two packages a
developer would actually want. The `--no-dev` flag reads as "no development dependencies" and
delivers close to the opposite.

> [!NOTE]
> **There is no full containerized support yet (user, 2026-08-11).** `Containerfile` is not a
> released deployment artifact, so "the production image" overstates it — nothing is shipping this
> today and no user is affected right now. Read consequence 2 as **a latent defect in an
> unfinished build path**, not a live production leak. That lowers its urgency but not its scope:
> the flag pair is wrong wherever containerization lands, and fixing it now is cheaper than
> discovering it during whatever story completes that work. The design phase should confirm the
> current state of container support before writing an FR that assumes a shipped image.

### This is not a documentation gap

The correct command is already documented in three places and all three agree:

| File | Line | Says |
|---|---|---|
| `README.md` | 95 | `uv sync --all-extras` |
| `CONTRIBUTING.md` | 16 | `uv sync --all-extras` |
| `docs/user_guides/1_installation_and_setup.md` | 15 | `uv sync --all-extras` |

Adding a fourth copy would not have prevented this. The defect is that the project's own default
command is wrong, and the documentation has been compensating for it — which is why nobody
noticed until a machine was set up without following the docs to the letter.

## Candidate Approaches (not yet designed)

- **Collapse the two definitions into `[dependency-groups] dev`.** Everything a contributor needs to
  run tests, lint and type-check lives in one place, so a bare `uv sync` produces a working
  environment and `--no-dev` means what it says. Delete the `dev` extra.
- **Keep the extras for genuine optional features only** — `openai`, `anthropic`, `mistral`, `qwen`,
  `all-llm`, `serve`. Those are real user-facing choices and are not part of this ticket.
- **Fix `Containerfile:25`** to `uv sync --extra serve --no-dev --frozen`, so the image gets FastAPI
  and Uvicorn and nothing else. Rebuild and smoke-test the image in the same commit — cheap to do
  now, and cheaper than discovering it inside whatever story finishes containerization.
- **Ship the guardrail with the fix.** The cheapest one that actually prevents regrowth: assert no
  name appears as both a `[dependency-groups]` key and a `[project.optional-dependencies]` key. A
  stronger variant asserts that a bare `uv sync` yields an importable `pytest` plus every plugin the
  suite requires — closer to the real invariant, but it needs a resolver run rather than a parse.
- **Re-verify the three docs afterwards.** Once a bare `uv sync` works they may simplify, but each
  should be read rather than assumed — `README.md:95` sits under a heading that also promises the
  LLM extras.

## Non-Goals (proposed, pending design)

- **Not** the Python 3.14 / `uv.lock` re-resolution question. The lockfile was resolved on Windows
  and re-resolved here; whether to pin an interpreter is a separate decision.
- **Not** the 6 tests still failing on Linux (3 Windows-path-semantics tests in `sandbox/filesystem`,
  3 API endpoints returning 500). Unrelated cause, and they fail identically before and after this
  ticket's change.
- **Not** a migration away from `uv`, and not a restructure of the LLM provider extras.
- **Not** a version bump of any dependency. This ticket moves declarations between sections; it does
  not change what version resolves.

## Execution constraint

`Containerfile` is not released yet (see the note above), but it still builds from the manifest this
ticket edits, so the two changes land together with a rebuilt image verified, in **one commit** —
splitting them leaves a window where the image builds from a manifest that no longer has the extra
it names.

## Next Step

Run through `specweaver-design`. The change itself is small and the shape is not in doubt; the
design work is in two places:

1. **What `--no-dev` should mean for the image**, and whether anything currently depends on the lint
   and test tooling being present in it. Check the sandbox execution path in particular —
   `Containerfile.sandbox` and the `uv sync` prepare phase in `B-EXEC-01` run QA tooling inside
   containers, and it is worth confirming which image that uses before removing `pytest` from one.
2. **Which guardrail to ship** — the cheap name-collision parse, or the stronger "a bare `uv sync`
   can run the suite" assertion. The second is the real invariant and the first is what will
   actually stay green in CI; the design should say why it picked one.

---

## Delivery (2026-08-12)

### The stakes were higher than this document recorded

The stub framed this as a developer-setup defect with a latent container consequence. Research found
a third, live one: **`B-EXEC-01`'s prepare phase runs a bare `uv sync`**
(`container_executor.py:215`) and the Python QA runner then invokes `python -m pytest`,
`python -m ruff`, `python -m tach` from that venv. A project whose dev tooling sits in an extra
therefore gets a sandbox venv with **no test runner**, so sandboxed QA cannot run at all.

### What changed

- **`pyproject.toml`** — one `dev`, in `[dependency-groups]`, holding everything the gates need.
  The `[project.optional-dependencies] dev` is gone and `respx`'s duplicate with it. Extras keep
  only genuine user-facing features.
- The group **references** `specweaver[serve]` and `specweaver[all-llm]` rather than duplicating
  their contents. The suite exercises the REST layer and every LLM adapter, so testing the project
  requires those features installed — and listing them twice would be the same
  two-places-to-keep-in-step defect one level down.
- **`docs/dev_guides/testing_guide.md`** — `pip install -e .[dev]` no longer resolves; now `uv sync`.
- **`README.md`, `CONTRIBUTING.md`, the installation guide** — simplified from `uv sync --all-extras`
  to `uv sync`. They were not wrong, they were compensating; with the default correct there is
  nothing to compensate for.
- **`tests/unit/test_dependency_manifest.py`** — the guard.

### `Containerfile` needed no change, which was not the expected outcome

The stub proposed `--extra serve --no-dev`. Once `dev` stopped being an extra, the existing
`--all-extras --no-dev --frozen` became correct on its own — `--all-extras` can no longer pull dev
tooling back in because there is no dev extra to pull. Dry-run verified: it now removes `pytest`,
`pytest-asyncio`, `pytest-cov`, `pytest-xdist`, `ruff`, `mypy`, `tach`, `complexipy`, `respx` and
their transitive deps, while `fastapi`, `uvicorn`, `openai`, `anthropic` and `mistralai` all stay.

Fixing the manifest fixed the image. Editing the `Containerfile` as planned would have been a second
change papering over the first.

### Measured

```
                    before a bare `uv sync`    after
tests/unit          5347 errors                5633 passed, 0 failed
```

All three tiers green on a **default** `uv sync`: unit 5633/0, integration 591/0, e2e 191/0.

### The guard

Three tests, each pinning a distinct half of the defect: no name is both a group and an extra; every
tool the gates invoke is installed by a default sync; and `dev` is not an extra. They assert against
the **manifest**, not the live venv — deliberately, because the machine where someone already ran
`--all-extras` is exactly the machine where the defect is invisible.

### Recorded, not fixed

`B-EXEC-01`'s prepare phase still assumes a target project's dev tooling is installed by a default
`uv sync`. That is true for this repo now, and false for any project using the extras convention.
Filed separately rather than widening what an untrusted project installs, which would cut against
the sandbox's purpose.

Also noticed: **`check_fr_coverage.py B-EXEC-01` exits 1** — its own FR ledger was never closed. It
was never a `TECH-025` subject, so nobody has audited it.
