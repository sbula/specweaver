# Design: The Container Prepare Phase Assumes a Target Project's Dependency Layout

- **Feature ID**: TECH-031
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
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
- **Not** the non-Python runners, unless the design finds the same assumption in them.

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
