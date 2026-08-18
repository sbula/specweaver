# Design: The Container Prepare Phase Has Never Installed a Toolchain

- **Feature ID**: TECH-031
- **Epic**: Topic 07 (Technical Debt)
- **Status**: every defect this ticket found is fixed, the three Next Step questions are answered,
  and all three candidate approaches are delivered. Nothing is left open. See §Measured,
  2026-08-12, which **corrects the Problem Statement below rather than extending it**.
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
| runner never installed, so the group is never synced | groups declaring pytest are requested | live podman + unit |
| the absent toolchain explained as an internal path | the reason names the cause and the remedy | live podman + unit |
| no `uv.lock`, so no environment at all | `uv venv` + `uv pip install` off the sync path | live podman + unit |
| runner declared outside the manifest | `tox.ini` / `requirements*.txt` read when pyproject is silent | live podman + unit |
| runner declared nowhere | the sandbox supplies pytest, and the result says so | live podman + unit |
| the layout only checked when a run fails | `sw sandbox preflight` reports the plan first | e2e + unit |

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

## The layout gap (defect 3), measured and closed

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

### Delivered: a lockless project no longer gets nothing

That last paragraph stands — but it argues only that `uv sync` cannot be *made* to work without a
lockfile. It does not follow that nothing can, and something can: `uv venv` followed by `uv pip
install` resolves from the manifest and writes nothing into the source tree. Verified against live
podman before it was written, and the source tree is asserted untouched afterwards.

So the prepare phase now has two routes:

| Project | Route | Reproduces the project's pins |
|---|---|---|
| `uv.lock` committed | `uv sync --frozen`, groups beyond `dev` | **yes** — unchanged |
| no `uv.lock` | `uv venv` + `uv pip install`, every group **including `dev`**, plus `/workspace` | no |

Three things about the second route are easy to get wrong and are each pinned by a test:

- **`uv pip install` installs no group unless named, where `uv sync` always installs `dev`.** Reusing
  the sync path's group list would silently drop the most common runner location. The detector now
  returns `dev` and each route filters for its own semantics.
- **`/workspace` must be installed too**, or pytest is present and the tests cannot import what they
  test. Measured: omitting it leaves collection failing on the project's own package.
- **A committed lockfile still wins.** Routing everything through `uv pip install` would pass every
  other test here while quietly ending reproduction of the project's own CI.

**The cost is real and is logged, not hidden**: a fresh resolution is not the project's pinned set,
and the prepare phase says so by name when it takes that route. Surfacing it into the *QA report*
rather than the log is not done — recorded here rather than left to be discovered.

Worth against the corpus: **16.5% → 33%** of the 121 repositories, and it is the precondition for
rung 2 being worth more than nine projects.

### Delivered: the runner is read from where the project actually declares it

Rung 2, and it is **worth less than the 73% projected**: 27 of the 48 are reachable, taking the
corpus to **55%**. The projection assumed all 48 could be read. Parsing all 30 real `tox.ini`
files first showed 891 of their dependency lines carry `{...}` substitution against 236 plain
ones, and only 18 of the 30 have a plain `pytest` line at all. Measuring before building is the
only reason that number is honest rather than discovered later.

The reader takes what it can read and **logs what it skipped**, because a partial environment
that looks complete is the failure mode this whole ticket exists to remove. It never runs when
the manifest declares pytest: that project pinned its runner, and a second unpinned set over a
locked resolution is worse than nothing.

That reframes the remaining work. "Detect the layout and sync accordingly" was scoped against
extras-versus-groups; it now has to answer what the prepare phase does for a project that is not
uv-managed at all — which is a larger question than the one the ticket was written to ask, and the
reason this is a decision rather than a fix. `--all-extras` remains rejected (user, 2026-08-12).

## Functional Requirements

Written after the fact, from what shipped. That is backfill, and it cannot make these requirements
TDD retroactively — the tests were written first against behaviours, and these name the behaviours.
Each row says *why* it exists, because a row restating its own test teaches a later reader nothing.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Environment on a writable mount | Prepare phase | Point `UV_PROJECT_ENVIRONMENT` at the rw cache mount | `uv`'s default `.venv` lands in the workdir, which is `:ro` inside a `--read-only` container, so without this the phase fails for **every** project on every layout before the manifest is read. |
| FR-2 | The source tree is never written | Prepare phase | Pass `--frozen` on the locked route | A lockfile that has drifted makes `uv` re-resolve and rewrite `/workspace/uv.lock`, hitting the same read-only mount and reporting an error that names the lockfile rather than the sandbox. |
| FR-3 | The execute phase uses what prepare built | Execute phase | Mount the cache `:ro` and put `/cache/venv/bin` first on `PATH` | Fixing FR-1 and FR-2 changes nothing observable without this: `python -m pytest` otherwise resolves to the image's own interpreter, and the prepared environment is not even mounted. |
| FR-4 | A failed prepare reaches the caller | Prepare phase | Raise rather than log | The phase failed on every run for years behind a `logger.warning`; the QA runner then reported an absent toolchain as an empty suite, and both looked like nothing happening. |
| FR-5 | The group holding the runner is synced | Prepare phase | Request the groups whose contents declare pytest | `uv sync` installs `dev` and nothing else. Of 50 corpus projects on PEP 735, 15 put pytest in `dev` and 23 put it in `test`/`tests`, so the supported layout was the *less* common case. Detection is by content: names are a long tail, and `uv sync --group <undeclared>` exits 2, so a guessed name breaks every project that does not use it. |
| FR-6 | A project with no lockfile still gets an environment | Prepare phase | Take a `uv venv` + `uv pip install` route when `uv.lock` is absent | 20 of 121 corpus repositories declare pytest and commit no lockfile. A committed lockfile still takes the frozen route, because a fresh resolution does not reproduce the project's pins — and the phase says so by name when it resolves instead. |
| FR-7 | A runner declared outside the manifest is installed | Prepare phase | Read `tox.ini` and the `requirements` family when `pyproject.toml` names no runner | 81 of 121 corpus repositories never name pytest in their manifest. What cannot be read is reported rather than dropped: 891 of the corpus's tox dependency lines need tox's own substitution engine, and silence would let a partial environment pass for a complete one. |
| FR-8 | A supplied runner is disclosed on the result | Prepare phase, QA runner | Install pytest when the project declares none, and set `TestRunResult.toolchain_note` | Without the disclosure a green run attests to a suite executed against a version nobody chose, with none of the plugins it may need — the same vacuous success this ticket exists to remove, better dressed. A field rather than a log line, because the caller has to be able to repeat it. |
| FR-9 | An absent toolchain explains itself | QA runner | Name the missing module, the cause and the remedy | The reason forwarded the interpreter's own line, naming `/cache/venv/bin/python` — a path inside our container that appears nowhere in the reader's project — and said nothing about why pytest was absent or what would make it present. |
| FR-11 | Rust tests run through cargo's real output | Rust runner | Issue `cargo test` and parse the stable text summary | The runner issued `cargo test --format=json -q`, which real cargo rejects with *"unexpected argument '--format' found"*, then piped it into a `cargo2junit` installed nowhere. Cargo has no stable machine-readable form — the JSON libtest format is nightly-only — so its own output is the only honest source, and it needs no external converter. |
| FR-12 | Java tests run against the real build tool | Java runner | Drive `mvn`/`gradle`, falling back from the wrapper when a project has none | Nothing had ever run a JVM toolchain: no test gated on `shutil.which("mvn")`, and the four project-shaped fixtures hold no source files. The wrapper fallback was unexercised, and it is what makes a wrapper-less project reachable at all. |
| FR-13 | Kotlin tests run against the real build tool | Kotlin runner | Drive the declared build tool and harvest its reports | Same absence as FR-12. The first real run also settled the route: the system Gradle is 4.4.1, and a Gradle wrapper would fetch its own distribution — network the execute phase does not have — so Maven with the Kotlin plugin is the reachable path. |
| FR-14 | A failed build is never an empty suite | Java runner, Kotlin runner | Report an error when the build exits non-zero having written no reports | `did_not_run` keys on empty stdout, and a build tool that fails to compile prints freely, so it slipped through and an empty report directory harvested as `0 passed, 0 failed`. Measured against real Maven: `BUILD FAILURE`, exit 1, `TestRunResult(total=0)`. The guard is skipped when reports *were* written, because Maven and Gradle also exit non-zero on a red suite. |
| FR-15 | A failure carries enough to act on | Java runner, Kotlin runner, Rust runner | Report the test's identity, the assertion and the stack | Both JVM runners harvested counts and returned `failures=[]` while the surefire report beside them held `expected:<42> but was:<41>` and the full stack. A caller given `failed=1` and nothing else must re-run the suite by hand to learn anything, which is the one thing a sandboxed QA run exists to avoid. Rust already carried its panic; its message now stops at the diagnostic rather than trailing cargo's own index of failed names. |
| FR-16 | Non-Python projects have a prepare plan at all | Prepare phase | Detect the build tool and fetch its dependencies before the run | The phase returned immediately without a `pyproject.toml`, so a Rust or JVM project reached the execute phase with nothing installed — and that phase runs `--network none` by design, so resolution must happen in the prepare phase or not at all. Rust fetches into `CARGO_HOME=/cache/cargo` and builds into `/scratch/target`, because `/workspace` is read-only. Maven resolves into `/cache/m2` with `dependency:go-offline`. Gradle is reported unsupported rather than silently skipped: a wrapper fetches its own distribution on first use and the system Gradle is 4.4.1. |
| FR-17 | The executor acts on a non-Python plan | Prepare phase, execute phase | Run the fetch, pick an image containing the toolchain, and carry the environment into both phases | A plan nothing consumes is half a deliverable. The image must follow the toolchain or `cargo` is simply absent; the environment must reach both phases or the fetch lands where the run cannot see it; and `PATH` must not be rewritten with the Python venv, which hides the binary the image was chosen for. **Rust runs end to end in the container**, verified against live podman: crates fetched in prepare, compiled into `/scratch`, run offline, source tree untouched. |
| FR-18 | A JVM project runs in the sandbox | Prepare phase, execute phase, JVM runners | Give the build a writable workspace, warm the provider, and find the reports afterwards | Four container-only defects, none visible from outside one: the image's entrypoint creating `/root/.m2` as a non-root user; `target/` under a read-only mount, which Maven cannot be told to move; surefire's provider resolved at execution time and fetched by no offline goal; and its forked VM dying inside the sandbox's budget. An overlay workspace keeps the host source tree untouched while letting the build write. |
| FR-19 | Lint, complexity and compile give a verdict or say why not | Rust runner, Java runner, Kotlin runner | Read the tool's own output, and treat a missing report as an error | Every one of these surfaces returned `0 findings` when it had learned nothing. Rust piped clippy into `clippy-sarif` and complexity into the same, a binary installed nowhere: the pipe produced nothing and the guard around it reported a clean project for code clippy had just flagged. The JVM runners guarded a SARIF report with `if path.exists()` and fell through to zero when the plugin had never written one. And `cargo build` writes progress to stderr, so a healthy crate had empty stdout and was reported as an absent toolchain. |
| FR-10 | The plan is readable before a run | CLI | Report the prepare plan, non-zero on any warning | Every decision above was otherwise met inside a container, minutes into a run. `plan_for` decides once and both the executor and the report read it, so the report cannot describe a phase other than the one that runs. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Isolation is not widened to buy coverage | The prepare phase executes arbitrary sdist build code, so nothing may be installed that the project did not declare — no `--all-extras`, no `--all-groups`, and no group requested for a runner the QA runner never invokes. |
| NFR-2 | Reproducibility is preferred, never silently lost | A committed `uv.lock` always takes the frozen route. Where a fresh resolution is unavoidable, the phase states that the environment does not reproduce the project's pinned set. |
| NFR-3 | Every input to the command is in the cache stamp | The manifest and any fallback declaration decide the command, so a stamp keyed on the lockfile alone would serve a stale environment for ever. |

## Approaches, as decided

All three were taken, and one of them changed shape once measured.

- **Detect the layout and sync accordingly** — delivered. The groups half is FR-5. The extras half is
  **closed by measurement rather than built**: requesting a specific extra would add zero corpus
  projects, because every uv-managed repository declaring pytest in an extra already declares it in a
  group or at runtime.
- **Fail loudly instead of silently** — delivered as FR-4 and FR-9. The guess in the original entry
  was right that a clear failure is most of the value.
- **Document the expected layout and check it at configuration time** — delivered as FR-10,
  `sw sandbox preflight`.

## Non-Goals, as decided

- **Not** `--all-extras`, and not `--all-groups` either. Rejected on 2026-08-12 and reconfirmed by
  measurement: `--all-groups` would install twenty corpus projects' documentation toolchains to run
  their tests, and fail the whole phase on one unresolvable doc dependency. Recorded as NFR-1.
- **Not** a change to this repo's own manifest — `TECH-028` did that.
- **Not** reopening `B-EXEC-01`'s status.
- **Not** the non-Python runners. The design looked (Q3): the prepare-phase assumption is absent from
  them, and their silent-success shape has a different root cause. `TECH-032`.
- **Not** surfacing the fresh-resolution warning into the QA report. It is logged by name and stated
  in NFR-2; moving it into the report needs plumbing through the runner and is not done. Recorded
  rather than left to be discovered.

## Where the container journey stands

Measured against live podman on 2026-08-18, with the images the executor selects.

| Toolchain | Prepare | Runs in the container |
|---|---|---|
| `uv` (Python) | yes | **yes** |
| `cargo` (Rust) | `cargo fetch --locked` | **yes** |
| `maven` (Java) | full `mvn test`, network on | **yes** |
| `maven` (Kotlin) | same | **yes** |
| `gradle` | no | no — a wrapper fetches its own distribution, and the run has no network |

**Rust needs a committed `Cargo.lock`.** `cargo fetch` resolves, resolving writes `Cargo.lock`, and
`/workspace` is read-only — cargo says so itself under `--locked`. A crate without one is refused
with that one-line remedy rather than attempted.

### The four defects between Maven and a green run

Each was measured, not guessed, and none is visible from outside a container.

1. **The image's entrypoint creates `MAVEN_CONFIG`**, which it sets to `/root/.m2`. The sandbox runs
   as a non-root user, so the run died at `mkdir: cannot create directory '/root'` before Maven
   started — an error naming a path that appears nowhere in the project or in our configuration.
   `HOME` and `MAVEN_CONFIG` both point into `/scratch` now.
2. **A JVM build writes `target/` inside the project**, and Maven cannot be told to build elsewhere:
   `project.build.directory` is a model field, not a user property, and setting it on the command
   line left the compiler unable to create its output directories. The workspace is now an **overlay
   mount**: writable inside the container, every write landing in an ephemeral layer, the host source
   tree untouched. Scratch is mounted over `target/` so the reports survive the overlay being
   discarded. Python and Rust keep the stronger read-only mount, because neither needs to write there.
3. **Surefire resolves its *provider* at execution time** — `surefire-junit4` is named in no POM, so
   neither `dependency:go-offline` nor `test -DskipTests` fetches it, and the offline run died on
   *"Cannot access central … in offline mode"*. Measured across all three: only a full `mvn test`
   warms it. The preparation therefore runs the suite once, with
   `-Dmaven.test.failure.ignore=true` so a red suite still reaches the run that reports it.
4. **Surefire's forked VM died** inside the sandbox's memory and pid budget — *"The forked VM
   terminated without properly saying goodbye"*, reproducibly for Kotlin, whose compiler is the
   heavier. `-DforkCount=0` runs the tests in Maven's own JVM. Isolation between tests is weaker,
   which matters less here than on a shared machine: the run is already inside a container of its own.

The runners look for reports in both places, because the same runner serves a host run and a
sandboxed one and nothing tells it which happened.

## What each QA intent actually does, per language

Verified against the real toolchains. "Real" below means the intent was driven against the tool and
its output checked — not that a command exists in the source.

| Intent | Python | Rust | Java | Kotlin |
|---|---|---|---|---|
| tests | real | real | real | real |
| linter | real | real | **guarded** | **guarded** |
| complexity | real | partial | **guarded** | **guarded** |
| compiler | no-op | real | real | real |
| debugger | real | real | real | real |
| architecture | real | stub → 0 | real | stub → 0 |

- **partial** — Rust complexity reads clippy's own findings, but clippy's threshold is set in
  `clippy.toml` and cannot be given per run, so a caller's `max_complexity` has no effect. The result
  now reports the threshold clippy actually used rather than echoing the one it ignored.
- **guarded** — the JVM lint and complexity surfaces depend on a PMD or detekt report the project
  must configure. When none is written they now say so instead of reporting zero findings; a project
  that does configure one is parsed as before.
- **no-op** — Python has no compile step, and the surface returns a clean result by design.
- **stub → 0** — `TECH-064`, unchanged here.

Python's complexity honours the caller's threshold; Rust's cannot. Java's compiler detects a broken
build but reports the count without the compiler's message, and its debugger returns Maven's build
log rather than the program's output — both measured, neither fixed here.

## Verifiable Proof

Every file below passes and does not skip, except where a live container engine is absent — the
integration tier skips cleanly on that and only on that (NFR-10), which is an environment
capability rather than anything this repo controls.

- `tests/unit/sandbox/execution/test_container_executor_prepare.py` — FR-1, FR-2, FR-3, FR-4, FR-5,
  FR-6, FR-8
- `tests/unit/commons/test_tooling_sources.py` — FR-7, including a run against all 30 real `tox.ini`
  files from the corpus
- `tests/unit/commons/test_prepare_plan.py` — FR-10, and the two tests that tie the plan to what the
  executor does
- `tests/unit/sandbox/language/core/language/python/test_toolchain_absence.py` — FR-9
- `tests/integration/sandbox/execution/test_container_executor_integration.py` — FR-1 to FR-9 against
  live podman, across six project shapes
- `tests/e2e/capabilities/sandbox/test_preflight_reports_the_prepare_plan_e2e.py` — FR-10 through the
  real `sw` CLI in a subprocess

`python scripts/check_fr_coverage.py TECH-031` exits 0: ten FRs, each planned and each carried by an
authoritative `Proves:` tag in two files.

**Each citation was checked by mutation against the file that claims it, and two of the ten failed
that check first.** FR-3's assertion tested that `/cache/venv/bin` appeared *in* `PATH` rather than
first, so prepending `/usr/bin:` satisfied it while restoring the exact shadowing FR-3 exists to
prevent — the assertion is now positional. FR-8 was cited to the wrong file; its unit proof is the
runner-note class beside the prepare tests, not the explanation module. Neither would have been found
by the coverage gate, which proves attribution and never strength.

## Adjacent finding, recorded because nobody has looked

`check_fr_coverage.py B-EXEC-01` **exits 1** — its FR ledger was never closed. It was not one of
`TECH-025`'s three subject stories, so no one has audited whether its nine requirements have proofs.
That is not this ticket's scope, but a reader treating `B-EXEC-01`'s design as verified should know
it has not been.

## The Next Step questions, answered

All three are answered, two of them by work rather than argument.

1. **How wide the gap is** — measured against a corpus of 121 real repositories:
   `docs/analysis/dependency_layout_corpus_2026-08-18.md`. The answer reordered the ticket. The
   `requirements-dev.txt` case the question suspected would matter *does* matter, and is bigger than
   suspected: 81 of 121 projects never name pytest in `pyproject.toml` at all, 32 of them because
   `tox` or `nox` owns the dev environment.
2. **What the QA runner should do when a tool is absent** — answered, and the guess in the question
   was right that a clear failure is most of the value. The reason now names the missing module, says
   it is a setup failure rather than a test failure, states where the environment comes from, and
   gives the remedy for both a sandboxed and a host run. It no longer forwards
   `/cache/venv/bin/python: No module named pytest`, a path that exists only inside our container.
   Proven through `PythonQARunner` against live podman, not only as a pure function.
3. **Whether the same assumption exists for the non-Python runners** — answered in Q3: it does not.
   Their own silent-success shape is a different root cause and is `TECH-032`.

### Delivered: a supplied runner, disclosed on the result

Rung 3, taken on the user's decision after the case against it was put twice. 33 corpus projects
declare pytest nowhere readable; they now get it from the sandbox, for a ceiling of **83%** (100 of
121). The remainder have no `pyproject.toml` at the repository root at all.

The disclosure is the part that makes it defensible, and it is a field rather than a log line:
`TestRunResult.toolchain_note` says the runner was supplied, that its version is not the project's,
and that any plugins the suite needs are absent. `SubprocessExecutor.supplied_toolchain` is the seam
— empty for a host executor, which substitutes nothing.

**It cost two existing tests their premise, and they were repointed rather than deleted.** A project
with a manifest can no longer *have* an absent toolchain, so `test_a_project_that_declares_no_toolchain_fails_loudly`
and the absent-toolchain explanation test now run against a tree with **no manifest at all** — 22 of
the 150 corpus repositories, where `pyproject.toml` sits under a monorepo path or the project still
uses `setup.py`. The guarantee they encode is unchanged and still reachable; only the fixture that
reaches it moved.

Yield is partly measured, deliberately reported as such: of the 33, GitHub's unauthenticated rate
limit allowed 16 trees to be read, and all 16 contain test files. Six of the 16 ship a `conftest.py`,
where plugin imports live — those runs are the likeliest to trade one clear failure for a confusing
one. 17 are unmeasured.

### Delivered: `sw sandbox preflight`

The third candidate approach, and the last open item. It prints what the prepare phase will do with a
project before a run costs anything: which route builds the environment, where the runner comes from,
which lines could not be read, and every warning that applies. Exit 1 on any warning, so CI can gate
on it; exit 0 only when the run will use the project's own pinned toolchain.

**It is not a second implementation, and that is the design.** `plan_for` decides once; the container
executor acts on the plan and the command prints it. A preflight that re-derived the decision would
agree with the sandbox only until one of them changed, and a report describing a phase other than the
one that runs is worse than no report. Two tests pin the two ways they could drift apart.

**It also cost a layer boundary, and the boundary won.** The command was first written inside
`sandbox/execution/interfaces/`, which `test_interfaces_layer_does_not_import_the_sandbox` rejects —
the delivery layer delegates rather than importing execution, and nothing but that test enforces it.
The fix was to move the decision to L0 `commons`, beside the QA result models that live there for
exactly this reason, and the command to the CLI's own routers. `tach.toml` needed no change at all in
the end: the design was wrong, not the constraint.

The remaining *coverage* gap is not ours to close by code: 81 of 121 corpus projects declare no
pytest for `uv sync` to install, and no sync strategy reaches a manifest that does not name the
tool.

## Carried down from the topic entry (2026-08-13, `TECH-044`)

Moved here verbatim when the entry was shortened to four lines — recorded rather than dropped.

- Container QA now fails loudly instead of silently, and `execution_mode` defaults to `"host"`, so the remaining chain is **latent, not live**.

- Out of scope: `--all-extras` (rejected — widening what untrusted code installs cuts against the
  sandbox's purpose); this repo's manifest (`TECH-028`); `B-EXEC-01`'s status; the non-Python
  runners' own silent-success shape (`TECH-032`).
