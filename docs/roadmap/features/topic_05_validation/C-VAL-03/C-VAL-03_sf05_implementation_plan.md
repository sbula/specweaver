# C-VAL-03 SF-05 — Polyglot Architecture Configs

**Status**: APPROVED · **FRs owned**: none — deliberate, recorded 2026-08-17 from
`INT-US-25-SF01-MIG` · Design: [C-VAL-03_design.md](C-VAL-03_design.md) ·
Feature ID 3.20b

## Goal

Architectural boundary checks for non-Python languages, tied to `DALLevel` — the analog of Python's
`tach check`:

- TS: generate `.eslintrc.json` rules mirroring the `context.yaml` restrictions.
- Java: generate temporary `@Test` payloads checking the same limits under `ArchUnit`.

## Changes

1. **Foundation module `specweaver.commons`** (no business or execution logic)
   - [NEW] `src/specweaver/commons/context.yaml` — archetype `raw-data`, `consumes: []`.
   - [NEW] `src/specweaver/commons/enums/dal.py` — `DALLevel` and its schema metadata move out of
     `config`.
   - [NEW] `src/specweaver/commons/enums/__init__.py`
2. **Config (`specweaver.core.config`)**
   - [DELETE] `src/specweaver/config/dal.py`
   - [MODIFY] `src/specweaver/config/dal_resolver.py` — `from specweaver.commons.enums.dal import DALLevel`
3. **QARunner interfaces (`specweaver.core.loom.commons.qa_runner`)**
   - [MODIFY] `src/specweaver/loom/commons/qa_runner/context.yaml` — add `specweaver/commons` to
     `consumes: `.
   - [MODIFY] `src/specweaver/loom/commons/qa_runner/interface.py` — `run_architecture_check` gains
     `dal_level: DALLevel | None = None`.
   - [NEW] `src/specweaver/loom/commons/qa_runner/factory.py` — `resolve_runner(cwd: Path) -> QARunnerInterface`
     picks JVM / TS / Python from marker files.
4. **Language adapters**
   - [MODIFY] `src/specweaver/loom/commons/qa_runner/typescript/runner.py` — `run_architecture_check`
     builds JSON `no-restricted-imports` and parses the CLI output.
   - [MODIFY] `src/specweaver/loom/commons/qa_runner/java/runner.py` — generates JUnit/ArchUnit
     source into `.tmp/`.
5. **Internal callers**
   - [MODIFY] `src/specweaver/validation/rules/code/c05_import_direction.py`
   - [MODIFY] `src/specweaver/loom/atoms/qa_runner/atom.py`
   - Refactor every `from specweaver.core.config.dal import DALLevel` import to `commons`.

Dev task order:

1. `Task 1`: **Commons Foundation Enum** — `specweaver/commons/enums/dal.py`, its `context.yaml` as
   an `L0` layer without consumers; migrate `DALLevel`; update `config/dal_resolver.py`.
2. `Task 2`: **QARunner Boundaries & Interface** — `qa_runner/context.yaml` consumes
   `specweaver/commons`; `QARunnerInterface.run_architecture_check(target, dal_level=None)` through
   the Python/Kotlin/Rust stubs.
3. `Task 3`: **QARunner Auto-Discovery Factory** — `src/specweaver/loom/commons/qa_runner/factory.py`
   with `resolve_runner(cwd) -> Interface` scanning for marker files.
4. `Task 4`: **Wiring Validation Callers** — `c05_import_direction.py` and `QARunnerAtom` route
   through the factory.
5. `Task 5`: **TypeScript ESLint Pipeline** — constraints in `TypeScriptRunner.run_architecture_check`;
   JSON payload into `.tmp`, run `npx eslint`.
6. `Task 6`: **Java ArchUnit Pipeline** — `JavaRunner` JUnit generator writes `ArchitectureTest.java`,
   runs `mvn`, extracts output.

**Since moved** (noted 2026-09-25): the factory now lives at
`src/specweaver/sandbox/qa_runner/core/factory.py`.

## Tests

1. **Unit:** parsing and rule generation (`TSRunner` `.eslintrc` output, `JavaRunner` test source).
2. **Integration gate:** a fake node `package.json` project with a `context.yaml` `forbids: [...]`
   rule; run `c05_import_direction` against it; expect an architectural failure exit code and
   correctly parsed ESLint output.

## Decisions (audit, HITL)

| # | Decision | Why |
|---|---|---|
| 1 | **Auto-discovery:** `qa_runner` checks marker files (`package.json`, `pom.xml`, etc.) statelessly via a `Factory` | Passing `context.db` down would break layer rules and create cycles |
| 2 | **Commons enum namespace:** `DALLevel` moves to an `L0` foundation layer (`specweaver.commons.enums.dal`) | Deep adapters such as `qa_runner` can import the typed enum everywhere in the DAG |
| 3 | **Java:** a generated `SpecweaverArchUnitTest.java` in the target `.tmp/`, run via `mvn`, then cleaned up | Execution artifact pattern |
| 4 | **TS:** generated restrictions run via `npx eslint -c .eslint-specweaver-arch.json` | Execution artifact pattern |
