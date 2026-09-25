# Testing Guide

Use when: you run tests while working, pick what to run at a commit boundary, or wonder why a test
was skipped or deselected.

> [!WARNING]
> Run inside the project virtual environment (`uv sync`). Never `pip install` globally.

## 1. Local iteration (`pytest`)

For the loop you are in. Not the gate — the gate is §3.

```bash
pytest
```

Whole suite, all tiers (unit, integration, e2e). `pytest -q` for short output, `pytest -v` for verbose.
Full NDJSON tracebacks: `logs/<project_name>/specweaver.log`.

| Run | Command |
|---|---|
| One tier | `pytest tests/unit` · `pytest tests/integration` · `pytest tests/e2e` |
| Unit + integration, no e2e | `pytest tests/unit tests/integration` |
| One module, both tiers | `pytest tests/unit/core/flow tests/integration/core/flow` |
| One module | `pytest tests/unit/assurance/standards` |
| One file | `pytest tests/unit/core/flow/engine/test_engine_runner.py` |
| One class | `pytest tests/integration/core/flow/engine/test_flow_engine.py::TestFlowEngineCompletion` |
| One test | `pytest tests/integration/core/flow/engine/test_flow_engine.py::TestFlowEngineCompletion::test_empty_pipeline_completes_immediately` |

By keyword, across files:

```bash
pytest -k "hitl"           # Runs any test function/class containing "hitl"
pytest -k "not validate"   # Runs tests except those containing "validate"
```

Paths moved in the domain restructure: `tests/unit/flow` → `tests/unit/core/flow`,
`tests/unit/standards` → `tests/unit/assurance/standards`, `tests/unit/validation` →
`tests/unit/assurance/validation` (same for `tests/integration/`).

### Daily loop

1. Edit a file, e.g. `src/specweaver/core/flow/engine/runner.py`.
2. Its unit tests: `pytest tests/unit/core/flow/engine/test_engine_runner.py`.
3. Module integration: `pytest tests/integration/core/flow`.
4. Lint + complexity: `ruff check src/specweaver/`.
5. Types on changed files: `mypy src/specweaver/core/flow/engine/runner.py --ignore-missing-imports`.
6. Full suite: `pytest`.

### Module examples (Standards / Constitution: Feature 3.5a-4)

```bash
# All constitution tests (unit)
pytest tests/unit/workspace/project/test_project_constitution.py

# All standards tests (unit + integration)
pytest tests/unit/assurance/standards tests/integration/interfaces/cli/test_cli_standards_integration.py

# Config database tests (includes schema migrations)
pytest tests/unit/core/config/test_database.py

# CLI tests for constitution and config commands
pytest tests/unit/workspace/project/interfaces/test_project_cli_constitution.py tests/unit/core/config/interfaces/test_config_cli.py
```

| Area | Command |
|---|---|
| Flow engine | `pytest tests/unit/core/flow tests/integration/core/flow` |
| Validation rules | `pytest tests/unit/assurance/validation tests/integration/assurance/validation` |
| Agent Memory Bank | `pytest tests/unit/workspace/test_memory_store.py` |

## 2. Traps

### Polyglot toolchains are installed but not on `PATH`

Java, Kotlin and Rust are on the Linux dev box (2026-08-12) but **not** on a fresh shell's `PATH` —
the same trap as `.venv/bin`. Export them before anything that calls a non-Python toolchain:

```bash
export PATH="$HOME/.cargo/bin:$HOME/.sdkman/candidates/java/current/bin:\
$HOME/.sdkman/candidates/kotlin/current/bin:$PATH"
```

Verified present: `openjdk 25`, `kotlinc`, `rustc 1.97.1`, `cargo`, `clippy-driver`.

Without it the run does not fail — it passes having done nothing. `TECH-032` records **13 paths** in
the Java, Kotlin, Rust and TypeScript QA runners that report an **absent toolchain as success**. Until
it lands, a wrong `PATH` and a clean run look the same.

### A serial pass can hide a failure — confirm with `-n auto`

Measured 2026-08-12: `test_fan_out_log_observability_context_isolation` passed serially and failed on
**every** parallel run of `tests/integration/core/flow/`. `TECH-020` had moved the run-tagged step
logs from `engine.runner` to `engine.step_execution`; the test pinned
`caplog.set_level(..., logger=".....runner")`, captured nothing, and its `count >= 1` assertion was
right to fail. Serially it passed only because **another test had already lowered a log level
process-wide**. xdist gives each worker a fresh process, so the parallel run was the honest one.

- **A green serial run does not prove a log-capture test.** Run it under `-n auto`.
- **Set `caplog` levels on the package**, `specweaver.core.flow.engine`, not
  `specweaver.core.flow.engine.runner`. A test pinned to one module stops observing anything once a
  refactor moves the call, and still reads as a real check.

Same for any test whose subject can move between modules: pin the *contract*, not the location
(`TECH-015`'s argument, applied to assertions).

### Async SQLite stores (e.g. Agent Memory Bank)

Tests of async SQLAlchemy stores that rely on SQLite foreign keys (cascading deletes) MUST register
the PRAGMA hook on the test engine and set `expire_on_commit=False` (avoids `MissingGreenlet`).

> [!IMPORTANT]
> Async SQLite tests require explicitly calling `register_fk_pragma_listener(engine.sync_engine)` in the async fixture to ensure `ON DELETE CASCADE` fires during tests.

Why: `special_patterns_and_adaptations.md` §21.

## 3. The commit gate (`scripts/tests.py`)

At a commit boundary you do **not** pick tiers; the gate picks them from the story:

```bash
python scripts/tests.py cb C-FLOW-12           # capability story
python scripts/tests.py cb US-21               # (sub)story — integration + e2e, no unit tier
python scripts/tests.py cb TECH-020 --kind refactor|bugfix|tooling|audit
python scripts/tests.py matrix                 # every profile
```

- Story type chooses the profile, commit state (`quick`/`cb`/`sf`/`feature`) the row; DAL shifts the
  whole thing earlier or later.
- `--also`/`--all` may widen a run; **nothing narrows one**.
- It already passes `-n auto`.

**How a changed file becomes a test path.** `src/specweaver/` and `scripts/` are source, mirrored
under `tests/<tier>/`. A changed **test** contributes its own module too, for its own tier only; the
two sets are *unioned*, so a changed test can add a module but never redirect or remove one. Scope
then decides what each contributes: `touched` → the mirroring test file (a changed test resolves to
itself), `module` → the mirror directory, `domain` → the e2e domain directory, `all` → the whole
tier. Why union-only: pattern 26 in `special_patterns_and_adaptations.md`.

**A tier that selects zero tests FAILS.** The message names the cause: source with no mirror (missing
coverage — write the test, do not work around the scope), tests whose package has no mirror in that
tier, or nothing in the diff touching that tier.

The rest of the code gates run through `scripts/quality.py`
([`development_framework.md`](development_framework.md)). The tools below are for local iteration.

### Ruff (lint + import sort)

Config in `pyproject.toml`. See [Ruff](https://docs.astral.sh/ruff/).

```bash
ruff check src/specweaver/
```

```bash
ruff check src/specweaver/assurance/standards/interfaces/cli.py src/specweaver/workspace/project/constitution.py
```

```bash
ruff check --fix src/specweaver/
```

| Rule | Description |
|------|-------------|
| C901 | Cyclomatic complexity limit ≤ 10 |
| B007 | Unused loop variables must be prefixed with `_` |
| I001 | Import block must be sorted |
| TC001/TC003 | Type-only imports belong in `TYPE_CHECKING` |
| SIM102/SIM108 | Simplifiable control flow |
| N806 | Function-scope variables must be lowercase |

### Tach (layer boundaries)

SpecWeaver is a PEP-420 implicit namespace package; the "Layer Cake" layers and public interfaces are
enforced by [Tach](https://github.com/gauge-sh/tach), not `__init__.py` encapsulation.

```bash
tach check
```

```bash
tach sync
```

`tach sync` after moving files.

### mypy (strict)

Config in `pyproject.toml` under `[tool.mypy]`. See [mypy](https://mypy.readthedocs.io/).

```bash
mypy src/specweaver/workspace/project/constitution.py --ignore-missing-imports
```

> [!NOTE]
> The `--ignore-missing-imports` flag suppresses errors for third-party packages that lack type stubs. The project itself must have full type annotations.

### File sizes

`scripts/check_file_sizes.py` (`file_sizes` check). `src/` and `scripts/`: up to 450 lines green,
451–600 warning, above 600 blocks. `tests/`: up to 800 green, 801–900 warning, above 900 blocks.
Split a file before it gets there.

## 4. Test-gap analysis before closing

Run the **`specweaver-pre-commit` skill**; its Phase 2
(`.agents/skills/specweaver-pre-commit/references/phase-2-test-gap.md`) reads every modified source
file line by line, names untested branches, guards and edge cases, and builds a coverage matrix per
module.

### Two questions a coverage matrix cannot answer

1. **Is this only ever used together with something else?** Then testing each end does not test the
   pair. `TECH-056`'s two functions each passed every assertion while their composition could not
   work. `TECH-068`: the graph engine wrote the edge kind under one attribute name and the store read
   another, so 108 persisted edges all took the store's `"CALLS"` fallback; the fix then left the
   *loader* writing the old name, so a graph read from the database could never be written back.
2. **Does anything else in the repo do the same job?** Then assert that they **agree**. `TECH-058`:
   one whole-suite runner passed `-n auto`, the other did not — visible in both files, tested in
   neither.

**The agreement test answers both.** Feed one half's real output to the other half's real reader,
and name no key, constant or literal yourself:

```python
def test_the_loader_and_the_store_name_the_attribute_identically(tmp_path):
    repo.persist_semantic_digraph(_graph(("a", "b", EdgeKind.EXTENDS)))
    attrs = repo.load_from_db().edges["a", "b"]      # what one half produced
    assert _edge_kind("a", "b", attrs) == "EXTENDS"  # read by the other half's own reader
```

Renaming either side breaks it. An assertion that spells the key itself pins the literal and passes
for each half alone — how the split above survived twenty-two green tests. Two unit tests in
`tests/unit/graph/core/store/` asserted `edge["type"] == "CALLS"` and had to be repaired.

## 5. Coverage target

**70–90%.**

## 6. Deselected: `@pytest.mark.live`

`addopts = "-m 'not live'"` in `pyproject.toml` excludes them from every normal run (the full
`addopts` also sets `--import-mode=importlib -v --tb=short`). 31 tests as of 2026-09-25 (was 12).

They need valid API keys in env vars, network access, and quota/billing on the target service (e.g.
Google Gemini), or a real toolchain.

```bash
pytest -m live                       # Run ONLY live tests
pytest -m "live" --tb=long -v        # With verbose output
```

Run before releases, after changing LLM adapter code, or when debugging API integration. Never in CI
without secrets.

| Files | What |
|---|---|
| `tests/manual/test_llm_live.py` | Gemini API connectivity |
| `tests/manual/test_stitch_live.py` | Stitch/MCP integration |
| `tests/manual/test_api_live.py` | live API tests |
| `tests/integration/sandbox/{atoms,tools}/qa_runner/<lang>/` | QA runners against real Java, Kotlin, Python, Rust, TypeScript toolchains |

## 7. Skipped tests

Skipped at runtime via `pytest.skip()` or `skipIf()`. Expected on some platforms, not failures.

**Windows (5 tests in `tests/unit/sandbox/execution/test_execution_executor.py`)** — pass on
Linux/macOS:

| Test | Reason |
|------|--------|
| `test_read_symlink` | Symlinks require admin privileges on Windows |
| `test_list_directory_with_symlink` | Symlinks require admin privileges on Windows |
| `test_write_to_readonly_file` | `chmod` doesn't enforce read-only on Windows |
| `test_create_in_readonly_dir` | `chmod` doesn't enforce read-only on Windows |
| `test_delete_readonly_file` | `chmod` doesn't enforce read-only on Windows |

**Empty parameter set (1 test in `test_interfaces.py`; since moved (2026-09-25):
`tests/unit/sandbox/filesystem/interfaces/filesystem/test_filesystem_interfaces.py`)** —
`TestImplementerMethodVisibility::test_missing_method`: the implementer role has **all** filesystem
methods (`_ALL_METHODS == _IMPLEMENTER_METHODS`), so `_ALL_METHODS - _IMPLEMENTER_METHODS` is empty
and pytest skips. Correct by design.

**No container engine (`tests/integration/sandbox/execution/test_container_executor_integration.py`)**
— all 5 tests are module-wide `skipif`'d when neither a live `podman` nor `docker` is found
(`shutil.which()` + an `<engine> info` liveness probe, once at collection). There is no exclusion
marker: with an engine present they run for real (no mocking) in a normal `pytest tests/integration/`.
They validate `ContainerSubprocessExecutor`: `docs/dev_guides/subprocess_execution.md`, "Containerized QA
Execution".

## 8. Impact-aware validation

- **Pristine bypass** ("Pristine Topology Bypass"): if a module's AST hash is unchanged, i.e. not in
  `stale_nodes`, the test and lint atoms skip and return `SUCCESS`. Not yet live: `stale_nodes` is
  never populated (`pipeline_engine_guide.md` §9).
- **DAL enforcement**: for `DAL_A` and `DAL_B` boundaries, soft warnings become `FAIL`.
- **E2E realism**: tests of this run in temporary `git worktrees` with small purpose-built validation
  pipelines (e.g. `C06 - Bare Except`), not `unittest.mock`.

## Related

- Test-gap procedure: `.agents/skills/specweaver-pre-commit/references/phase-2-test-gap.md`
- [Architecture Completeness Tests](../architecture/04_pipelines_and_methodology/completeness_tests.md) — structural verification
