# Design: The Container Prepare Phase Assumes a Target Project's Dependency Layout

- **Feature ID**: TECH-031
- **Epic**: Topic 07 (Technical Debt)
- **Status**: PARTIAL — the QA-runner half is delivered; the prepare phase is not. See
  §Measured, 2026-08-12, which **corrects the Problem Statement below rather than extending it**.
- **Origin**: Found 2026-08-12 during `TECH-028`. That ticket fixed **this** repo's manifest, which
  incidentally fixed the prepare phase for SpecWeaver itself. The gap for *other* target projects is
  what remains, and is recorded here rather than left implied.

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
