# Design: Polyglot Implementation Loop

- **Feature ID**: D-INTL-08
- **Epic**: Topic 04 (Intelligence)
- **Status**: APPROVED by the user 2026-10-20 — designed with them the same day (Q1–Q15)
- **Absorbs**: `TECH-073` (a task's target files named for Python only) `[agreed 2026-10-20]`

| | |
|---|---|
| Uses | `D-VAL-03` (the five language runners) · `D-INTL-01` (the generator) · `C-FLOW-11` (the agentic coder and its grant) · `D-EXEC-02` / `C-EXEC-06` (the merge allow-list) · `B-INTL-02` (the framework evaluators) · the `context.yaml` archetype |
| Enables | every non-Python journey of US-3 · `C-EXEC-07` (allow-lists for any pipeline) |
| Not touched | running non-Python toolchains inside the sandbox container (US-3 P-4) `[agreed 2026-10-20]` · what an agent may read |

## Feature Overview

`sw implement` and the `generate code` / `generate tests` steps produce code in the project's own
language — Python, Java, Kotlin, TypeScript or Rust — and in the style of its framework, then lint
and test it with that language's own tools. Today every one of them writes `src/<stem>.py` and
`tests/test_<stem>.py`, with a Python prompt, whatever the project is: a Java project gets `.py`
files holding Python. The five language runners exist and no user path reaches them.

## Research Findings

### Codebase Patterns (measured 2026-10-20)

- **The stem** is derived in 23 places across 16 files, two ways: `replace("_spec", "")` (generation,
  `derive_allowed_paths`, scenario, validation) and `removesuffix("_spec")` (topology, `sw implement`,
  `reviewed_spec`, `draft`, the API). `my_spec_tool_spec.md` gets two module names.
- **Python is written into the path** at: `implementation/interfaces/cli.py:75,82,95,264-268`;
  `handlers/generation.py:137,296,313-314,246`; `implementation/generator.py:28,39,44-55,73,135,
  189-190,210-212`; `engine/isolation.py:63`; `handlers/lint_fix.py:71,222,252-259,273-280`;
  `handlers/validation.py:300,348,397,438,568`; `handlers/validation_hydrator.py:223-228`.
- **Language detection** (`sandbox/language/core/_detect.py:33-54`, repeated in
  `qa_runner/core/factory.py:51-78`): `package.json` → typescript, `Cargo.toml` → rust,
  `build.gradle[.kts]` → **kotlin**, `pom.xml` → java, else python. A Gradle Java project is read as
  Kotlin; `pyproject.toml` is not consulted. No implement-path handler calls it.
- **The runners** (`sandbox/language/core/<lang>/runner.py`): Python runs one target with pytest and
  fixes lint with ruff; Java and Kotlin run the whole Maven/Gradle project and lint report-only
  (PMD, detekt); Rust runs `cargo test` for the whole crate and fixes with clippy; **TypeScript's
  `run_tests` and `run_linter` are stubs that always report zero** — only `tsc --noEmit` is real.
- **Lineage tags** (`commons/lineage.py:34-68`): `#`, `//`, `<!-- -->`, `--` by language; **Kotlin
  has no entry**, so a `.kt` file is never tagged. The generator's fence stripper knows only
  ```` ```python ````.
- **`validate_code`** runs C01–C08 (`ast.parse`, `test_<stem>.py`): every non-Python file FAILs C01
  and C02; its gate is CONTINUE, so the run goes on.
- **Frameworks**: evaluator schemas for Spring Boot, Quarkus, NestJS, Actix-web, FastAPI
  (`workflows/evaluators/frameworks/`); a Spring Boot validation pipeline; `ArchetypeResolver`
  reads `archetype` and `plugins` from `context.yaml`. Generation knows no framework.
- **Fixtures**: `tests/fixtures/{java,kotlin}_{maven,gradle}_project/`, `sample_project/`
  (Python); 17 real-toolchain runner tests in `test_polyglot_runners_live.py`, skipped where a tool
  is missing. No TypeScript fixture.

### External Tools

Maven `-Dtest=<Class>`, Gradle `--tests <Class>`, `cargo test --test <name>`, `npm test`,
`npx eslint` — each the tool's documented way to run one test class or a project's own script.

### Blueprint References

The standard layouts: Maven/Gradle `src/main/<lang>` + `src/test/<lang>`; Cargo `src/` + `tests/`;
a TypeScript `src/` + `tests/*.test.ts`.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | One stem rule | Engine | SHALL name a spec's module by `removesuffix("_spec")` everywhere `[agreed 2026-10-20]` | one spec, one module name |
| FR-2 | The project's language | Run roots | SHALL take the language from `[implement] language` in `specweaver.toml`, else detect it in today's manifest order — `pyproject.toml` counting as Python before the default, a Gradle build with Java sources as Java `[agreed 2026-10-20]`; a mixed repository names its language | a mixed repository says what it is; Gradle Java is not Kotlin |
| FR-3 | One derivation of a task's files | Engine | SHALL derive a task's code and test files once, per language — the layout below, the Java/Kotlin package from the existing code (the longest package prefix all its sources share) or else the build's `group`, a spec's `package:` line winning `[agreed 2026-10-20]`, and for Rust the `src/lib.rs` that declares the module, created beside a `main.rs` because tests reach only a library crate `[agreed 2026-10-21]` — and SHALL use that one derivation for generation, the merge allow-list, the coder's grant and the QA targets (**seam**: `D-EXEC-02`, `C-FLOW-11`) | generation, the merge and the grant can never disagree on a file |
| FR-4 | Generation speaks the language | Generator, coder | SHALL prompt in the project's language, strip that language's fences, and tag the file in its comment syntax, Kotlin included `[agreed 2026-10-20]` | a Java project gets Java, tagged for lineage |
| FR-5 | The task's own tests run | QA runner | SHALL run only the task's test — Maven `-Dtest`, Gradle `--tests`, `cargo test --test` `[agreed 2026-10-20]` — and for TypeScript the project's `npm test` `[agreed 2026-10-20]` (**seam**: `D-VAL-03`) | an unrelated failing test never sends the coder to fix code it did not write |
| FR-6 | Lint in the language | `lint_fix` | SHALL lint with the language's linter — `npx eslint` for TypeScript `[agreed 2026-10-20]` — and ask the model to fix "this <language> file" (**seam**: `D-VAL-03`) | lint repair stops being Python-shaped |
| FR-7 | Honest code rules | `validate_code` | SHALL, for a language without code rules, report "no code rules for <language>" and not block `[agreed 2026-10-20]` | no false C01/C02 failures |
| FR-8 | Framework-aware generation | Generator | SHALL add the framework's guidance — idioms and test style — for Spring, Spring Boot, Quarkus, NestJS, Actix-web and FastAPI `[agreed 2026-10-20]`, taken from the `context.yaml` archetype, else detected from the build file `[agreed 2026-10-20]`, from content files a project may override `[agreed 2026-10-20]` | generated Spring code uses its test slices, Quarkus code `@QuarkusTest`, and so on |
| FR-9 | `sw implement` end to end | `sw implement` | SHALL implement a spec in each of the five languages: generate, lint, run the task's tests, validate (**journey**) | US-3 P-5 |

### The layout `[agreed 2026-10-20]`

| Language | Code | Tests |
|---|---|---|
| Python | `src/<stem>.py` | `tests/test_<stem>.py` |
| Java | `src/main/java/<pkg>/<Name>.java` | `src/test/java/<pkg>/<Name>Test.java` |
| Kotlin | `src/main/kotlin/<pkg>/<Name>.kt` | `src/test/kotlin/<pkg>/<Name>Test.kt` |
| TypeScript | `src/<stem>.ts` | `tests/<stem>.test.ts` |
| Rust | `src/<stem>.rs` | `tests/<stem>.rs` |

`<Name>` is the stem in PascalCase (`greet_service` → `GreetService`); `<pkg>` is the package as
folders. No per-project layout override in this feature `[agreed 2026-10-20]`.

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-2 | the project's manifests and settings | `sandbox.language` · `detect_language(cwd)`; `core.config.bootstrap` · `read_settings_text` | read `_detect.py:33-54`, `llm_settings_loader.py` |
| FR-3 | the merge allow-list and the grant | `D-EXEC-02` · `derive_allowed_paths`/`task_files`; `C-FLOW-11` · `_run_coder` | read `isolation.py:40-110`, `generation.py` |
| FR-5, FR-6 | per-language test and lint | `D-VAL-03` · `<Lang>QARunner.run_tests(target, …)`, `run_linter` | read `sandbox/language/core/*/runner.py` |
| FR-4 | comment syntax for a tag | `commons.lineage.wrap_artifact_tag` | read `lineage.py:34-68` |
| FR-8 | the archetype | `core.config.archetype_resolver.ArchetypeResolver.resolve` | read `archetype_resolver.py:35-72` |

## Non-Functional Requirements

| # | NFR | Rule |
|---|---|---|
| NFR-1 | Python unchanged | A Python project implements exactly as before, except FR-1's stem for a spec with `_spec` inside its name |
| NFR-2 | Host mode only | Non-Python toolchains run on the host; the container stays Python-validated `[agreed 2026-10-20]` |
| NFR-3 | Fast default suite | Real-toolchain journeys run in an opt-in `toolchain` tier, nightly, skipped where a tool is missing; the default suite uses doubled runners `[agreed 2026-10-20]` |
| NFR-4 | One copy | The stem, the language and a task's files each have one derivation; no second copy anywhere in `src/` |

## Settings shape `[agreed 2026-10-20]`

```toml
[implement]
language = "java"   # python | java | kotlin | typescript | rust — else detected
```

## External Dependencies

None new: the project's own Maven, Gradle, npm, cargo, eslint.

## Architectural Decisions

| # | Decision | Why |
|---|---|---|
| AD-1 | One `TaskFiles` derivation in `core/flow/engine` (beside `task_files`), from the spec, the language and the package | FR-3, NFR-4: three callers, one answer |
| AD-2 | The language is resolved once at the run root onto the run context, like the doc policy | one detection per run, reviewed like `[docs]` |
| AD-3 | Framework guidance is content (`workflows/frameworks/<name>.md`), resolved like rubrics, project file first | FR-8, readable and overridable |
| AD-4 | Per-language prompt text is content beside it (`workflows/languages/<lang>.md`) | the generator holds no language strings |

## ROI Analysis

### Investment Cost

Five sub-features (below).

### Returns

The five existing runners become reachable; Java, Kotlin, TypeScript and Rust projects get
`sw implement`; Spring and Quarkus users get idiomatic code and tests; `TECH-073` closes.

### Risk Assessment

| Risk | Mitigation |
|---|---|
| A wrong package or layout puts code where the build does not see it | FR-3's derivation is unit-tested per language; the toolchain tier compiles it for real |
| Gradle/Maven are slow in tests | NFR-3 |
| Framework guidance drifts from real practice | content files a project can override (AD-3) |

### Refactoring Opportunities

The 23 stem derivations collapse to one (FR-1); `derive_allowed_paths` becomes the task-files
derivation (FR-3).

## Developer Guides Required

The user guide gains "Languages and frameworks": `[implement] language`, the layout table, the
package rule, the framework list and how to override a framework file.

## Non-Goals

- Non-Python toolchains inside the sandbox container (US-3 P-4) `[agreed 2026-10-20]`.
- A per-project layout override `[agreed 2026-10-20]`.
- Code rules (C01–C08 equivalents) for languages other than Python.
- Languages beyond the five runners.

## Sub-Feature Breakdown

### SF-01: One derivation

FR-1, FR-2, FR-3. Input: a spec and the project. Output: the stem, the language and the task's files,
used by every caller. Closes `TECH-073`.

### SF-02: The runners do what they say

FR-5, FR-6 (the runner half). Input: a language and a test target. Output: a real TypeScript test and
lint runner; per-class test filters for Maven, Gradle and cargo; Gradle Java detected as Java; the
QA runner factory uses `detect_language` instead of its own copy (NFR-4).

### SF-03: Generation speaks the language

FR-4, FR-6 (the `lint_fix` prompt), FR-7, FR-9 (the journeys with doubled model and runner). Input:
the language. Output: prompts, fences, tags and code rules per language; `sw implement` proven per
language in the default suite.

### SF-04: Frameworks

FR-8. Input: the archetype or the build file. Output: the framework's guidance in the prompt.

### SF-05: The real toolchains

FR-9 (the real-toolchain half), NFR-3. Input: a sample project per language (a TypeScript one is new).
Output: the `toolchain` tier — marker, nightly runner — and `sw implement` proven per language with the
real Maven, Gradle, npm and cargo.

## Execution Order

SF-01, then SF-02 and SF-03, then SF-04, then SF-05.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | One derivation | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | The runners do what they say | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | Generation speaks the language | SF-01 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-04 | Frameworks | SF-03 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-05 | The journeys | SF-02, SF-03, SF-04 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Now**: design approved 2026-10-20.
**Next**: SF-03 dev, CB-1 (generation in the language). SF-03 plan approved 2026-10-21.
