# Implementation Plan: The Container Prepare Phase Has Never Installed a Toolchain [SF-01]

- **Feature ID**: TECH-031
- **Sub-Feature**: SF-01 — the whole ticket; it was never decomposed
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-031/TECH-031_design.md
- **Design Section**: §Delivered, §Functional Requirements
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-031/TECH-031_sf01_implementation_plan.md
- **Status**: APPROVED

**FRs owned: FR-1 through FR-14.** All of them, in one plan, because the ticket shipped as one
sequence rather than as sub-features. FR-11 to FR-14 were added when the ticket was re-opened for
Rust, Java and Kotlin — the first target project is Python, Rust and Kotlin.

> [!IMPORTANT]
> **This plan was written after the code, and says so.** Recorded under `specweaver-dev` §3.2c —
> backfill FRs on contact — when the ticket came to be closed and `check_fr_coverage.py` found a
> design that declared nothing to verify against. It is an honest record of what was built and which
> test carries each claim; it is not a record of a plan anyone followed, and reading it as one would
> misdescribe how the work happened. The tests came first, against behaviours; the numbered
> requirements came last, from the tests.

## Goal

Make the container prepare phase build an environment the QA runner can actually use, for the widest
set of real projects that can be reached without widening what an untrusted project installs — and
make every case it cannot reach say so.

## 1. The environment is built somewhere writable, and used

### [MODIFY] `src/specweaver/sandbox/execution/container_executor.py`

`_PREPARED_VENV = "/cache/venv"` and `-e UV_PROJECT_ENVIRONMENT={_PREPARED_VENV}` on every prepare
step, so `uv` does not try to create `.venv` inside the `:ro` workdir. **(FR-1)**

`--frozen` on the locked route, so a drifted lockfile is never re-resolved and rewritten into the
same read-only mount. **(FR-2)**

`_CONTAINER_PATH` puts `/cache/venv/bin` first, and the execute phase mounts `-v {cache}:/cache:ro`,
so `python -m pytest` resolves to what prepare installed rather than the image's interpreter. The
cache is read-only in the execute phase deliberately: that phase runs untrusted code and has no
business writing into an environment the next run reuses. **(FR-3)**

`_ensure_prepared` raises `RuntimeError` naming the failing step and its stderr, instead of logging a
warning nobody reads. **(FR-4)**

## 2. The runner is found where the project actually declares it

### [MODIFY] `src/specweaver/commons/prepare_plan.py`

`_groups_holding_a_runner` returns every PEP 735 group whose contents declare pytest, `dev`
included — the two prepare routes disagree about `dev`, so filtering it at the source would strip it
from the route that needs it named. `_TEST_RUNNERS` is `("pytest",)` and nothing else: the QA runner
invokes `python -m pytest`, so a group holding only `tox` would leave it failing exactly as before.
**(FR-5)**

`plan_for` chooses the route from whether `uv.lock` exists, and carries the warnings that follow.
**(FR-6, FR-10)**

### [MODIFY] `src/specweaver/commons/tooling_sources.py`

`declared_pytest` reads the `requirements` family first — `uv pip install -r` needs no parsing and
resolves its own includes — then `tox.ini`'s `testenv` deps blocks. Lines needing tox's substitution
engine are returned as `skipped`, never dropped. **(FR-7)**

### [MODIFY] `src/specweaver/sandbox/execution/container_executor.py`

`_prepare_steps` returns the locked route (`uv sync --frozen` plus non-default groups) or the
unlocked one (`uv venv`, then `uv pip install` with every group named and `/workspace` installed so
the tests can import what they test). **(FR-6)**

`_fallback_step` installs what `declared_pytest` found, or `_LAST_RESORT_RUNNER` when the project
declared nothing, recording the substitution on `supplied_toolchain`. **(FR-7, FR-8)**

`_fallback_fingerprint` folds the manifest and any fallback file contents into the cache stamp, since
both decide the command. **(NFR-3)**

## 3. What the caller is told

### [MODIFY] `src/specweaver/commons/qa.py`

`TestRunResult.toolchain_note` — a field, not a log line, so a green result can carry the fact that
the runner was not the project's. **(FR-8)**

### [MODIFY] `src/specweaver/sandbox/execution/executor.py`

`SubprocessExecutor.supplied_toolchain`, empty for a host executor, which substitutes nothing.
**(FR-8)**

### [MODIFY] `src/specweaver/sandbox/language/core/python/toolchain_absence.py`

`absent_module` names the missing module, calls it a setup failure rather than a test failure, and
gives the remedy for a sandboxed and a host run alike. `why_it_did_not_run` wraps the shared
`did_not_run` so every tool the runner drives benefits, falling back unchanged for anything the
pattern does not recognise. `supplied_note` renders the disclosure. **(FR-8, FR-9)**

### [NEW] `src/specweaver/interfaces/cli/routers/sandbox_router.py`

`sw sandbox preflight` prints the plan and exits 1 on any warning, so CI can gate on it. It reads
`plan_for` from `commons` and never imports the sandbox — the delivery layer delegates rather than
importing execution. **(FR-10)**

## 4. The other three languages

### [NEW] `src/specweaver/sandbox/language/core/rust/cargo_output.py`

`parse_cargo_test` reads cargo's stable text output — summing every suite's `test result:` line,
because a crate with doc-tests reports two — and returns `None` when no summary appeared at all, so a
compile error stays distinguishable from a suite with no tests. **(FR-11)**

### [MODIFY] `src/specweaver/sandbox/language/core/rust/runner.py`

`cargo test`, with no `--format` and no `cargo2junit` pipe. **(FR-11)**

### [MODIFY] `src/specweaver/sandbox/language/core/toolchain.py`

`build_failed_without_results` — non-zero exit plus zero harvested results is an error, not an empty
suite. Guarded on `total` so a red suite, which also exits non-zero, keeps its counts. **(FR-14)**

### [MODIFY] `java/runner.py`, `kotlin/runner.py`

Both call the guard after harvesting. **(FR-12, FR-13, FR-14)**

### [NEW] `tests/integration/sandbox/language/test_polyglot_runners_live.py`

Real `cargo`, `mvn` and `kotlinc` against projects written by the test, skipping only on a missing
toolchain. **(FR-11, FR-12, FR-13, FR-14)**

## 5. Proof

| FR | Test file |
|---|---|
| FR-1, FR-2, FR-3, FR-4 | `tests/unit/sandbox/execution/test_container_executor_prepare.py`, `tests/integration/sandbox/execution/test_container_executor_integration.py` |
| FR-5 | `tests/unit/sandbox/execution/test_container_executor_prepare.py`, `tests/integration/sandbox/execution/test_container_executor_integration.py` |
| FR-6 | `tests/unit/sandbox/execution/test_container_executor_prepare.py`, `tests/integration/sandbox/execution/test_container_executor_integration.py` |
| FR-7 | `tests/unit/commons/test_tooling_sources.py`, `tests/integration/sandbox/execution/test_container_executor_integration.py` |
| FR-8 | `tests/unit/sandbox/execution/test_container_executor_prepare.py`, `tests/integration/sandbox/execution/test_container_executor_integration.py` |
| FR-9 | `tests/unit/sandbox/language/core/language/python/test_toolchain_absence.py`, `tests/integration/sandbox/execution/test_container_executor_integration.py` |
| FR-10 | `tests/unit/commons/test_prepare_plan.py`, `tests/e2e/capabilities/sandbox/test_preflight_reports_the_prepare_plan_e2e.py` |
| FR-11 | `tests/unit/sandbox/language/core/language/rust/test_cargo_output.py`, `tests/integration/sandbox/language/test_polyglot_runners_live.py` |
| FR-12, FR-13 | `tests/integration/sandbox/language/test_polyglot_runners_live.py` |
| FR-14 | `tests/unit/sandbox/language/core/test_runner_migration.py`, `tests/integration/sandbox/language/test_polyglot_runners_live.py` |

Every behaviour above was mutation-verified as it was written, individually, against the test that
claims it. The counts are in the commit messages; the discipline is that a citation whose mutant
survives is not a proof.
