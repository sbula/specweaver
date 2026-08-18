# Design: The Container Prepare Phase Has Never Installed a Toolchain

- **Feature ID**: TECH-031
- **Epic**: Topic 07 (Technical Debt)
- **Status**: PARTIAL — the QA-runner half is delivered; the prepare phase is not. See
  §Measured, 2026-08-12, which **corrects the Problem Statement below rather than extending it**.
- **Origin**: Found 2026-08-12 during `TECH-028`. **That ticket's claimed side-effect was wrong** —
  it fixed this repo's manifest, but §Measured shows the prepare phase fails for SpecWeaver too, on
  a defect the manifest cannot reach. The layout gap is real but is not what stops the phase.
- **Renamed 2026-08-12**, from *"…Assumes a Target Project's Dependency Layout"*. The old title
  named defect 3 of 3 and read as though the phase otherwise worked. Recorded rather than done
  silently, since registry/design title drift is itself a tracked defect.

## Problem Statement

`B-EXEC-01`'s prepare phase runs a **bare `uv sync`** against the target project
(`container_executor.py:215`), and the Python QA runner then invokes `python -m pytest`,
`python -m ruff` and `python -m tach` from the venv that produced
(`sandbox/language/core/python/runner.py:105,188,442`).

`uv` installs `[dependency-groups]` by default and `[project.optional-dependencies]` only when asked.
So for any target project that declares its dev tooling as an **extra** — the older and still common
convention, and what this repo itself did until `TECH-028` — the prepare phase produces a venv with
**no test runner**, and sandboxed QA cannot run.

### This is a promise, not an inference

`B-EXEC-01` AD-7 states the phase's purpose explicitly:

> *"The exact mechanism for getting **the target project's installed toolchain (pytest/ruff/tach/mypy,
> etc.)** into the ephemeral container without a full reinstall on every invocation … a **prepare
> phase** (network-enabled, runs `uv sync` from the project's own lockfile …)"*

It names the four tools. A bare `uv sync` does not deliver them for an extras-based layout, so the
stated intent is unmet for that class of project.

### Why `B-EXEC-01` is not being reopened

Considered and rejected, with the precedent weighed. `TECH-001` was reverted 🟢→🟡 and `TECH-022`
retired into it because *"TECH-001 itself was corrected to reflect that it was never actually
finished."* That test does not fit here:

- `B-EXEC-01` **implemented AD-7 as written** — it runs `uv sync` from the project's lockfile, gated
  by a lockfile hash, in a network-enabled phase separated from execution per AD-9. The code does
  what the design says.
- What is too narrow is AD-7's **assumption** that a default `uv sync` installs a project's dev
  tooling. True for some layouts, false for others.

The story finished; its assumption did not cover the field. That is the promise-versus-delivery
shape a TECH ticket exists for — as distinct from `B-EXEC-04`, which is a **capability** because the
mechanism it needs (cgroups `pids.max`) was never built at all.

## Measured, 2026-08-12

Reproduced against live podman on the Linux box, not inferred from reading. **The Problem
Statement above is wrong about which defect fires first.** There are three, chained, and this
ticket's stated subject is the last of them.

### 1. The prepare phase cannot create a venv — for any project, on any layout

`/workspace` is mounted `:ro` and the container is `--read-only`, but `uv sync` writes `.venv`
into the workdir. It fails before it ever reads the manifest:

```
error: failed to create directory `/workspace/.venv`: Read-only file system (os error 30)
podman exit = 2      # identical for [dependency-groups] and [project.optional-dependencies]
```

`_ensure_prepared` only `logger.warning`s that exit code, so nothing surfaces it. Two corrections
follow. **`TECH-028` did not incidentally fix the prepare phase for SpecWeaver** — this repo hits
the same wall, and the Origin note above should be read with that in mind. And a target with no
`uv.lock` fails one step earlier still, on `failed to write to file /workspace/uv.lock` — the
current fallback from `uv.lock` to `pyproject.toml` walks straight into it.

### 2. The execute phase would not use the prepared venv anyway

`_build_container_cmd` sets no `PATH` and no `UV_PROJECT_ENVIRONMENT`, so the QA runner's
`python -m pytest` resolves to the **image's** interpreter. Fixing defect 1 alone changes nothing
observable, which is worth knowing before anyone fixes defect 1 alone.

### 3. An extras layout gets no dev tooling — this ticket's stated subject, and real

Confirmed once defect 1 is removed by pointing `UV_PROJECT_ENVIRONMENT` at the rw cache mount:

| Target layout | `uv sync` | pytest in the venv |
|---|---|---|
| `[dependency-groups]` | installs 7 packages | `pytest 9.1.1` |
| `[project.optional-dependencies]` | `Audited in 0.00ms` | `No module named pytest` |

### 4. The QA runner reported an absent toolchain as success — **fixed**

Why none of the above was ever noticed, and the ticket's own item 2. `_parse_pytest_output('')`
returns all zeros and `run_tests` never inspected `exit_code` or `stderr`, so a missing pytest was
indistinguishable from "no tests" — a **vacuous proof inside the QA gate itself**. `run_linter`
had the same hole (empty stdout parses identically to ruff's own `[]`), and so did
`run_architecture_check`: its `shutil.which("tach")` guard tests the *host* PATH and is skipped in
container mode, so the one configuration that can genuinely lack tach had no guard.

Delivered TDD in `sandbox/language/core/python/toolchain.py` (`did_not_run`), used by all three
paths. **The discriminator is empty stdout, not the exit code** — the first version keyed on the
exit code and broke `sw implement` against a fresh project, because pytest exits **4** for a
`tests/` directory that does not exist yet, having run correctly and printed `no tests ran`. Exit
4 and 5 both mean a verdict was reached; only a tool that never started prints nothing. That
regression is pinned by its own test.

### Answering the Next Step questions

- **Q2 (what should the runner do when a tool is absent)** — answered and delivered, above.
- **Q3 (do the non-Python runners share it)** — the *prepare-phase* assumption, no: they resolve
  toolchains without `uv`. The *silent-success* shape, yes: Java, Kotlin and Rust, in both
  `run_tests` and `run_linter`. TypeScript's two are declared `STUB`s that never call the
  executor. Six paths with a different root cause, so **not folded in here** — see §Out of scope.
- **Q1 (how wide the layout gap is)** — still open, and now clearly the *third* question to ask.

## Re-measured and partly delivered, 2026-08-18

Reproduced against live podman before touching anything, per the skill's rule about stale audit
evidence. **Every measurement from 2026-08-12 still held, verbatim** — including
`failed to create directory /workspace/.venv: Read-only file system (os error 30)`, exit 2.

Two things the original measurement did not record, both found by walking the chain rather than
reading it:

- **`--frozen` is required, not merely tidy.** The note above says a target with no `uv.lock` fails
  on `failed to write to file /workspace/uv.lock`. Measured further: a lockfile that merely *exists*
  is not enough. Adding one dependency after locking makes `uv` re-resolve and rewrite the lock, and
  it fails the same way. A bare `uv sync` therefore works only while the target's lockfile happens to
  be current — the failure is a property of the target's tidiness, not of the sandbox.
- **The execute phase never mounted the cache at all.** Defect 2 above is recorded as "sets no `PATH`
  and no `UV_PROJECT_ENVIRONMENT`". It also attaches only `scratch_root`, so `/cache/venv` did not
  exist inside the execute container. Setting `PATH` alone would have pointed at nothing.

### Delivered

| Wall | Fix | Verified |
|---|---|---|
| `.venv` into a read-only workdir | `UV_PROJECT_ENVIRONMENT=/cache/venv`, on the rw mount | live podman + unit |
| lockfile rewritten into a read-only mount | `uv sync --frozen` | live podman + unit |
| prepared environment absent at execute | cache mounted at `/cache:ro` | live podman + unit |
| image interpreter shadowing it | `PATH` puts `/cache/venv/bin` first | live podman + unit |
| failure reaching only a log line | `_ensure_prepared` raises | unit |

The cache is mounted **read-only** in the execute phase deliberately: that phase runs untrusted code
and has no business writing into an environment the next run reuses.

`tests/integration/sandbox/execution/test_container_executor_integration.py` now drives the **real
executor against a real engine** — prepare installs the project's declared `pytest`, execute finds it,
and a project declaring no test runner fails rather than reporting an empty suite. Every other proof
of this path built the podman argv by hand, which tests podman rather than this code. Each of the four
fixes was mutated individually and each kills at least one test.

**`INT-US-09-SF01-MIG` was held on "container execution actually exercised". It now is** — for the
prepare/execute round trip. The layout question below is what remains.

### One test's contract changed

`test_prepare_failure_does_not_write_stamp_and_warns` asserted that a failed prepare returns normally
after logging. That contract is why the phase could fail on every run unnoticed, so it is now
`..._and_raises`. Updated rather than deleted, so the change is visible in the history of the test
that pinned the old behaviour.

## Still open: the layout gap (defect 3)

Unchanged and confirmed today:

| Target layout | `uv sync --frozen` | pytest in the environment |
|---|---|---|
| `[dependency-groups]` | installs it | `pytest 9.1.1` |
| `[project.optional-dependencies]` | `Audited in 0.00ms` | `No module named pytest` |

### Q1 answered by measurement, and the answer is wider than the question

Each layout family was built as a fixture and driven through the fixed prepare phase against live
podman on 2026-08-18:

| Layout | `uv.lock` | usable toolchain |
|---|---|---|
| PEP 735 `[dependency-groups]` | yes | **yes** |
| `[project.dependencies]` (runtime) | yes | yes — but nobody declares a test runner there |
| `[project.optional-dependencies]` | yes | no — venv builds, `No module named pytest` |
| Poetry `[tool.poetry.group.dev]` | **no** — `uv lock` fails outright | no |
| `requirements-dev.txt` | yes | no — `uv` never reads it |
| any of the above **without** `uv.lock` | — | no — `--frozen` refuses: *"Unable to find lockfile at `uv.lock`"* |

**So the supported target is not "a project that avoids extras". It is a uv-managed project that
declares its tooling in PEP 735 dependency groups.** Everything else gets a venv with no test runner,
which is a far narrower set than "extras are the older convention" implies:

- **PEP 735 was accepted in 2024.** No project predating it is in the working set without migrating.
- **`uv.lock` exists only if the project uses `uv`.** pip, Poetry, PDM and Hatch projects have no such
  file, so the prepare phase cannot proceed for them at all.

The intersection — uv-managed *and* PEP 735 — is a small and recent slice of the ecosystem, and the
share is now measured against a corpus rather than asserted: **10 of 121 real repositories, 8.3%**,
rising to 20 (16.5%) with the group-detection fix below.
The corpus is the 150 most-downloaded packages on PyPI, an externally ordered list so the sample
cannot be steered; 121 of them resolve to a `pyproject.toml` at a repo root. Full method, denominators
and bias: `docs/analysis/dependency_layout_corpus_2026-08-18.md`.

Two things in that measurement change what this ticket has left to decide.

**Not declaring pytest dominates, not the lockfile and not the layout.** 81 of 121 projects never
name pytest in `pyproject.toml` at all — 32 hand the whole dev environment to `tox` or `nox`, the
rest use requirements files or declare nothing in-tree. The two causes overlap, so the cross-tab is
the honest reading: 20 declare pytest and have a lock (usable), 20 declare pytest with no lock, 13
have a lock and no pytest, 68 have neither. "Detect the layout and sync accordingly" was scoped
against a problem that is not the big one. The corpus is entirely libraries, which have two standing
reasons to look worse than an application — no lockfile by design, and `tox`/`nox` for multi-version
testing — so 16.5% is a floor for application targets rather than an estimate; the ranking is
unavailable from here, so the size of that gap stays unmeasured.

**A second defect, independent of all of the above — now fixed, and bigger than it first looked.**
50 corpus projects use PEP 735, and only **15** put pytest in the `dev` group `uv sync` installs
unasked; **23** put it in `test` or `tests`. So a project could sit exactly on the supported layout
and still get a venv with no runner, and that was the *more common* case. The prepare phase now reads
the target's manifest and requests the groups that declare pytest: **8.3% → 16.5%** of the corpus
(10 → 20 of 121), which doubles the supported share.

Detection is by content rather than name, which the corpus forced: the tail includes `testing`, `ci`,
`test-core` and `dev-base`, and cuts the other way through SQLAlchemy's `tests-postgresql` /
`tests-mysql` / `tests-oracle`, which hold database drivers and no runner. A name list is also unsafe
rather than merely partial: `uv sync --group <undeclared>` exits 2 (verified against uv 0.12.3), so a
guessed name breaks every project that does not use it. Only declared groups are passed. The same
evidence rules out `--all-groups`, which would install the 20 projects' `docs` toolchains to run
their tests and fail the whole phase on one unresolvable doc dependency.

`tox` and `nox` are excluded from detection although both are test runners. They build their own
environments, so installing one leaves `python -m pytest` — the only thing `PythonQARunner` invokes —
failing exactly as before, while pulling in the rest of that group through a prepare phase that
executes arbitrary sdist build code. Counting them was the error in this document's first set of
figures: eight OpenTelemetry packages were credited on a `dev` group holding `tox`.

**The extras branch of the first candidate approach is closed by measurement.** Requesting a specific
extra when the tooling lives in `[project.optional-dependencies]` would add **zero** corpus projects:
every uv-managed repository declaring pytest in an extra already declares it in a group or at
runtime. Nothing left to build there.

The cache stamp now covers `pyproject.toml` as well as `uv.lock`, because the manifest decides the
command: moving a runner from `dev` to `tests` changes the `--group` flags without touching the lock,
and a lockfile-keyed stamp would have served the pre-move environment forever.

**`--frozen` does not cause this and removing it would not help.** The lockfile cannot be written to a
read-only mount either way; `--frozen` converts a confusing `failed to write /workspace/uv.lock` into
a message that names the actual precondition. Coverage is unchanged, diagnosis is better.

That reframes the remaining work. "Detect the layout and sync accordingly" was scoped against
extras-versus-groups; it now has to answer what the prepare phase does for a project that is not
uv-managed at all — which is a larger question than the one the ticket was written to ask, and the
reason this is a decision rather than a fix. `--all-extras` remains rejected (user, 2026-08-12).

## Candidate Approaches (not yet designed)

- **Detect the layout and sync accordingly.** Read the target's `pyproject.toml`; if the tools the
  QA runner will invoke are absent from the default groups but present in an extra, request that
  extra. Precise, and it installs nothing the project did not already declare for the purpose.
- **Fail loudly instead of silently.** Whatever the sync strategy, the QA runner should say *"pytest
  is not present in the prepared environment"* rather than surfacing a bare non-zero exit. Today the
  failure looks like a test failure rather than a setup failure, which sends the reader to the wrong
  place — the same misdirection `TECH-029` produced with `fork: retry`.
- **Document the expected layout** and check it at configuration time, rather than at the moment a
  QA run fails inside a container.

## Non-Goals (proposed, pending design)

- **Not** `--all-extras` in the prepare phase. Rejected at the point this was found (user,
  2026-08-12): widening what an untrusted project installs cuts against the sandbox's purpose, and
  the prepare phase already executes arbitrary sdist build code, which is why AD-7/AD-9 isolate it.
- **Not** a change to this repo's own manifest — `TECH-028` did that, and it is why SpecWeaver's own
  sandboxed QA works today.
- **Not** reopening `B-EXEC-01`'s status. See above.
- **Not** the non-Python runners, unless the design finds the same assumption in them. The design
  looked (Q3 above): the prepare-phase assumption is absent from them, and the silent-success
  shape is present in six of their paths but has a different root cause. Left for its own ticket
  rather than absorbed, per the scope rules in `specweaver-ticket`.

## Adjacent finding, recorded because nobody has looked

`check_fr_coverage.py B-EXEC-01` **exits 1** — its FR ledger was never closed. It was not one of
`TECH-025`'s three subject stories, so no one has audited whether its nine requirements have proofs.
That is not this ticket's scope, but a reader treating `B-EXEC-01`'s design as verified should know
it has not been.

## Next Step

Run through `specweaver-design`. Establish first:

1. **How wide the gap is.** Sample real Python projects: how many put pytest in a dependency-group
   versus an extra versus a `requirements-dev.txt` that `uv sync` never reads at all? The third case
   may matter more than the second and is not yet considered here.
2. **What the QA runner should do when a tool is absent** — that decision is worth making before the
   sync strategy, because a clear failure may be most of the value.
3. **Whether the same assumption exists for the non-Python runners**, which resolve their toolchains
   differently.

## Carried down from the topic entry (2026-08-13, `TECH-044`)

Moved here verbatim when the entry was shortened to four lines — recorded rather than dropped.

- Container QA now fails loudly instead of silently, and `execution_mode` defaults to `"host"`, so the remaining chain is **latent, not live**.

- Out of scope: `--all-extras` (rejected — widening what untrusted code installs cuts against the
  sandbox's purpose); this repo's manifest (`TECH-028`); `B-EXEC-01`'s status; the non-Python
  runners' own silent-success shape (`TECH-032`).
