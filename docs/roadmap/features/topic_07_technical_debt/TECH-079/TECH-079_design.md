# Design: Language and Toolchain Are Decided in a Dozen Places That Disagree

- **Feature ID**: TECH-079
- **Phase**: Topic 07 (Technical Debt)
- **Status**: APPROVED (the user, 2026-11-05)
- **Kind**: `bugfix`
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_design.md
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 10 below. Started
  2026-11-05, after `TECH-082` (the user, 2026-10-31). These are gaps in delivered work;
  `finished-stories-immutable` bars editing the closed stories, so they are owned here.

## Feature Overview

TECH-079 gives SpecWeaver one answer to "which language, build tool and framework is this
project", and makes every part ask it. The decision is pure and lives in `commons`; one reader in
`workspace/project` feeds it the project root `[agreed 2026-11-05]`. SpecWeaver stops guessing: when
the root holds build files of more than one language, a language it cannot generate, or both Maven
and Gradle, it refuses and names the setting that decides `[agreed 2026-11-05]`. File endings come
from one table, parsers from one lookup, and the two analyzer families parse through the shared
tree-sitter library. It does not add generation for new languages and does not touch the findings
owned by `TECH-075`..`TECH-091`.

## The Defect (re-measured 2026-11-05)

| Finding | Re-measured |
|---|---|
| Fix first #6, AG-5 | `commons/languages.py:14` is the shared table, and parsers, rename, imports, the boundary check, `archetype_pipelines` and prompts read it. Separate tables remain: `workspace/analyzers/factory.py:258-345` (one ending per language; no `.pyi`, `.kts`, `.tsx`, JavaScript, Go, C, C++), `assurance/standards/languages/{python:77,javascript:105,typescript:40}` (no `.pyi`; TS adds `.cts`, `.mts`), `assurance/standards/scope_detector.py:33` and `recency.py:29`, `workspace/project/interfaces/cli.py:84` (the `sw init` hint), `workspace/ast/refactor/python.py:50` (`.py` only, though rename sends `.pyi`), `refactor/c_family.py:342` (reads `.h` as C++; `commons` says C). Language→ending twice (`sandbox/language/core/detect.py:24`, `workflows/implementation/contract_renderers.py:34`), both falling back to `py`. The five generatable languages three times (`detect.py:21`, `core/config/implement_policy.py:17`, `workflows/implementation/languages.py:18`) |
| FL-4 | `archetype_pipelines.py:94` keeps its own `language_of`. JVM build files are read in three orders: `frameworks.py:30` (all together), `task_files.py:138,152` (pom first), `detect.py:56` (gradle first). `package.json` is parsed three times, `Cargo.toml` twice |
| SB-2, CW-10 | `detect_language` (`detect.py:33`): package.json → typescript, Cargo → rust, JVM → kotlin/java, else python. `detect_toolchain` (`workspace/project/prepare_plan.py:132`): pyproject/uv.lock → uv first, then cargo, maven, gradle. Runners pick gradle before pom (`java/runner.py:53`, `kotlin/runner.py:45`); task files pick pom first. The `[implement] language` pin reaches task files, the runner and validation only; the toolchain, image, scenario converter, stack-trace filter and dual run ignore it; `core/flow/engine/isolation.py:58` hard-codes `python` |
| SB-7 | Per-language ladders in `runner_factory._runner_class:63`, `scenario_converter_factory.py:42`, `stack_trace_filter_factory.py:30`, `contract_renderers.py:350`, `task_files.task_files_for:61`: case-sensitive, an unknown language becomes Python. Only the runner and task files take a language; the converter and filter always detect |
| AG-6 | "Find a parser for this file" in 9 places (`graph_adapter.py:62`, `graph/core/builder/orchestrator.py:156`, `boundary_check.py:113`, `rename.resolver_for:72`, `code_structure/core/atom.py:107`, `code_structure/interfaces/tool.py:497`, `refactor/files.py:37`, `refactor/_base.py:31`, `refactor/imports.py:139`); four are case-sensitive; `tool.py` and `files.py` rebuild the registry on every call |
| AG-8 | `TreeSitterAnalyzerBase` (`workspace/analyzers/factory.py:161`, structure per folder, 5 languages) and `TreeSitterAnalyzer` (`assurance/standards/tree_sitter_base.py:31`, style per file list, JS and TS) have near-identical names and share no method. `PythonStandardsAnalyzer` (`assurance/standards/languages/python/analyzer.py:70`) parses with the standard library `ast`, although `workspace/ast/parsers/python` reads Python with tree-sitter |
| WV-10 | `context.yaml` `archetype` names a layer role or a framework; `frameworks.project_framework:43` and `archetype_pipelines.archetype_of:32` read framework names from it, while `workflows/planning/models.py:30` `KNOWN_ARCHETYPES` lists only roles, so the planner warns on `spring-boot` |
| WV-11 | Framework languages are declared in `workflows/frameworks/*.md` (`languages:`) and `workflows/evaluators/frameworks/*.yaml` (`supported_languages`); they disagree on `nestjs`. Generation detects the framework from the build file (`frameworks.py:43`); validation (`archetype_pipelines.code_pipeline:70`) reads only the archetype, so a Spring Boot project with no archetype gets Spring Boot code and default checks |

**What a user sees today.** A root with `pyproject.toml` and `package.json` gets TypeScript task files
and the TypeScript runner, but the Python image, `uv` and the Python dual run. A root with `pom.xml`
and `package.json` runs npm in the Maven image. A Go, C or C++ project gets Python files. A
JavaScript project gets `.ts` files.

## Path List (`ADR-005`)

| # | Path | Span | Owner | Status |
|---|---|---|---|---|
| P-1 | `sw implement` → `[implement]` pins + root → profile → task files, framework, contract | CLI, workspace project, commons, workflows/implementation | TECH-079 (FR-1..FR-8) | ⬜ |
| P-2 | `POST /api/v1/implement` → the same profile → task files, or an error naming the setting | API, workspace project, commons | TECH-079 (FR-8) | ✅ (SF-02) |
| P-3 | `sw run` → run setup → profile in the run → QA runner, scenario converter, stack-trace filter, dual run, isolation | run setup, flow engine and handlers, sandbox language | TECH-079 (FR-7, FR-14) | ✅ (SF-02) |
| P-4 | `sw sandbox preflight` and a sandboxed run → profile → prepare plan and image | sandbox CLI, workspace project, sandbox execution | TECH-079 (FR-7) | ✅ (SF-02) |
| P-5 | `sw check <code file>` → validation pipeline chosen by the profile's framework | validation orchestration, workspace project | TECH-079 (FR-9) | ✅ (SF-03) |
| P-6 | `sw scan`, topology, C09 → structure analyzers → folder language from `commons` | workspace analyzers, assurance graph | TECH-079 (FR-16) | ⬜ |
| P-7 | `sw standards scan` → style analyzers → shared parsers | assurance standards, workspace parsers | TECH-079 (FR-16, FR-17) | ⬜ |
| P-8 | rename, code-structure tools, C05 → one parser lookup, `.h` by project | workspace parsers and refactor, sandbox code structure | TECH-079 (FR-13, FR-15) | ✅ (SF-04) |

## Research Findings

### Codebase Patterns
- `commons` is `pure-logic`, `utility = true` in tach, importable by every module, and does no file
  I/O today (`languages.py` uses only `PurePath`). It may not read files or import `core/config`.
- `workspace/project` is an `adapter` and already holds `detect_toolchain` and `plan_for`. `sandbox`,
  `core.flow.handlers`, `interfaces.api`, `interfaces.cli`, `interfaces.cli_kit` and
  `interfaces.run_setup` depend on it in tach. `core.flow.engine` and
  `assurance.validation.orchestration` do not; they are the two edges this design adds.
- `core/config` is marked `pure-logic` but reads files (`archetype_resolver.py:50,84`,
  `_context_walk.py:72`, `profiles.py:85,186`). Putting the registry there was rejected
  `[agreed 2026-11-05]`; the existing reads are not this ticket's.
- `ImplementPolicy` (`core/config/implement_policy.py:20`) is `extra="forbid", frozen=True` with
  `language: Language | None`; it is read at `interfaces/api/v1/implement.py:85`,
  `interfaces/run_setup/builder.py:135` and `interfaces/cli_kit/_core.py:134`. Its user doc is
  `docs/user_guides/1_installation_and_setup.md` §6c, which states today's detection order.
- `context.yaml` has no key schema: `topology._node_from` (`assurance/graph/topology.py:119`) and
  `ArchetypeResolver` read keys with `get`, so a new `framework:` key breaks no reader.
  `workspace/analyzers/inferrer.py:127` and `workspace/project/scaffold.py:66` write `archetype`.
- The evaluator schemas' `supported_languages` are read by `sandbox/code_structure/core/evaluator.py:115`
  and `archetype_pipelines.py:167`; the guides' `languages:` by generation.
- Tests that pin today's guesses, which FR-3/FR-4/FR-5 change: `test_detect.py:24,77,87,94,123`,
  `test_prepare_plan_languages.py:56,66`, `test_runner_factory.py:52,56,106,124`,
  `test_scenario_converters.py:299`, `test_stack_trace_filters.py:222`, `test_run_language.py:45,49`,
  `test_run_language_agrees_with_qa.py:52,87`; files that write `package.json` as `{}` may need a
  `tsconfig.json` (`test_task_brief.py`, `test_frameworks.py`, `test_qa_runner_atom.py`, and others).

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| tree-sitter, tree-sitter-python | already pinned | `workspace/ast/parsers/python/codestructure.py` | read the file |

Practice elsewhere (from memory, not re-checked): Nixpacks and Buildpacks detect from the app
root and let an explicit config win; Linguist decides `.h` by content heuristics; IntelliJ asks when
a project has both Maven and Gradle. This design takes root-only detection and "the pin wins", and
refuses where those tools pick by order.

### Blueprint References
None.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | `commons` SHALL hold one pure function that decides a project's profile (language, build tool, framework) from the names of the files in the project root, a reader for a named root file, and the two `[implement]` pins; it SHALL do no file I/O itself `[agreed 2026-11-05]` | any caller | decide a profile | the same answer from the same inputs |
| FR-2 | A set pin SHALL win over detection: `[implement] language` (python, java, kotlin, rust, typescript) and the new `[implement] build_tool` with the values `uv`, `maven`, `gradle`, `cargo`, `npm` `[agreed 2026-11-05]`; an unknown value SHALL be refused when the settings load, naming the allowed values | a user | pin the language or build tool | every part uses the pin |
| FR-3 | Detection SHALL read only the build files in the project root `[agreed 2026-11-05]`: `pyproject.toml`, `uv.lock` or `requirements*.txt` → python; `package.json` → typescript when the root has `tsconfig.json` or a `.ts`/`.tsx` file, else javascript `[agreed 2026-11-05]`; `Cargo.toml` → rust; `pom.xml`, `build.gradle` or `build.gradle.kts` → kotlin or java by today's rule (Kotlin sources under `src/main/kotlin` or the Kotlin plugin in the build file; this split is inside one language, so it may look below the root); `go.mod` → go; `CMakeLists.txt` → C or C++. A root with none of these build files SHALL name the languages of the code files in the root folder by their endings `[agreed 2026-11-05]` | the profile function | detect | one candidate per language found |
| FR-4 | When the root names more than one candidate language and no language pin is set, the profile SHALL be a refusal naming the build files found and telling the user to set `[implement] language` `[agreed 2026-11-05]` | the profile function | detect a mixed root | no silent pick |
| FR-5 | When the decided language cannot be generated (go, c, cpp, javascript), the profile SHALL be a refusal naming the language and the five that can; no part SHALL fall back to Python `[agreed 2026-11-05]` | the profile function | detect an unsupported language | a refusal, never Python files |
| FR-6 | When the root has `pom.xml` and `build.gradle` or `build.gradle.kts` and no build-tool pin is set, the profile SHALL be a refusal telling the user to set `[implement] build_tool` `[agreed 2026-11-05]`; otherwise the build tool SHALL follow the language and its build file as today (python with `pyproject.toml` or `uv.lock` → uv, python with only `requirements*.txt` → none, rust → cargo, typescript → npm, JVM → the one build file present) | the profile function | detect a JVM project | one build tool, or a refusal |
| FR-7 | Task files, the QA runner, the scenario converter, the stack-trace filter, the dual run, run isolation, the prepare plan and the sandbox image SHALL all take the language and build tool from the one profile; `detect_language`, `detect_toolchain` and `isolation.py`'s `python` default SHALL be gone (seam: run setup, flow, sandbox, workspace project → profile) | `sw run`, `sw implement`, `sw sandbox preflight` | run on a project | every part agrees; a pinned mixed root runs entirely in the pinned language |
| FR-8 | A refusal SHALL reach the user where a project-wide language is needed and only there `[agreed 2026-11-05]`: `sw implement`, `sw run` and `sw sandbox preflight` print it and exit 1; `POST /api/v1/implement` returns 400 with the error code `PROJECT_UNDECIDED` and the message `[agreed 2026-11-05]`, and so do `POST /pipelines/{name}/run` and `/runs/{id}/resume` `[agreed 2026-11-06]`; a run with session isolation on refuses an undecided project on any door, never running without it `[agreed 2026-11-06]`; `sw check` on one file keeps using that file's ending (seam: CLI and API → profile) | a user | start work on an undecided project | one message naming the setting, no run started |
| FR-9 | The validation pipeline of a code file SHALL be chosen by the profile's framework, the same answer generation uses `[agreed 2026-11-05]` (seam: validation orchestration → profile) | `sw check`, the validate steps | check a Spring Boot file with no archetype | Spring Boot checks |
| FR-10 | The framework SHALL come from `context.yaml` `framework:` first, then from an `archetype:` that names a framework (with a warning naming the move to `framework:`), then from the build file's markers (today's Spring/Quarkus, NestJS, Actix, FastAPI detectors) `[agreed 2026-11-05]`; `KNOWN_ARCHETYPES` stays layer roles; `context_yaml_spec.md` documents `framework:`; `sw init` and the archetype inferrer write a framework under `framework:` | the profile function, the planner | read a framework | one answer; old manifests still work |
| FR-11 | Each framework's languages SHALL be declared once, in its evaluator schema's `supported_languages`; the guides' `languages:` line SHALL be gone and generation SHALL read the schema | generation, validation, the code-structure evaluator | ask a framework's languages | one list (`nestjs` keeps typescript and javascript) |
| FR-12 | Every "which language is this file" and "which endings does this language have" SHALL read `commons`: the structure analyzers, the style analyzers, `scope_detector`, `recency` (which keep their own extra non-code endings such as `.rb`, `.cs`, `.swift`), the `sw init` hint, `refactor/python.py`, `archetype_pipelines.language_of`, one language→main-ending function replacing `detect.py:24` and `contract_renderers.py:34`, and one set of generatable languages replacing the three copies; a guard test SHALL fail when a module under `src/specweaver` outside `commons` writes one of the endings only a language table needs (`.pyi`, `.kts`, `.tsx`, `.jsx`, `.mjs`, `.cjs`, `.hpp`, `.cc`, `.cxx`) | every caller | ask a file's language | one table |
| FR-13 | A `.h` file SHALL be C++ when the project has C++ source files, else C `[agreed 2026-11-05]`; `commons` SHALL answer it from the path and a "has C++ sources" flag, and the C/C++ import resolver and the boundary check SHALL agree | C05, rename | read a header | the same language everywhere |
| FR-14 | The runner, scenario-converter, stack-trace-filter, contract-renderer and task-file factories SHALL each take the language as a required argument, choose from one table, and refuse an unknown language with an error naming it; none SHALL detect | the factories | build for a language | no ladder falls back to Python |
| FR-15 | One function in `workspace/ast/parsers` SHALL return the parser for a file path, matching its ending case-insensitively through `commons`, from a registry built once per process; the 9 lookups listed in The Defect SHALL use it | parsers' callers | find a parser | `A.PY` and `a.py` get the same parser; one registry |
| FR-16 | The style analyzers' base class SHALL be renamed `TreeSitterStyleAnalyzer`; both analyzer families SHALL pick a file's language through `commons`, so a folder holding only `.kts` or `.tsx` files gets its analyzer `[agreed 2026-11-05]` | `sw scan`, `sw standards scan` | analyze a folder | no clashing names; every ending found |
| FR-17 | The Python style analyzer SHALL parse with the shared tree-sitter Python parser and SHALL return the same category results as before on a fixture set pinned first `[agreed 2026-11-05]` | `sw standards scan` | scan Python code | the same results, one way to parse Python |
| FR-18 | The code rules that parse Python (C01, C06, C08) SHALL read a file that starts with a UTF-8 byte order mark, as Python does; a mark later in the file stays a syntax error `[agreed 2026-11-06]` | `sw check`, the API check, the validate steps | check a Python file saved with a BOM | C01 passes, C06 and C08 judge it |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1, FR-3 | the shared ending table | `commons/languages.py` · `LANGUAGE_SUFFIXES`, `language_of(path) -> str \| None` | read `commons/languages.py:14,40` |
| FR-2 | the language pin | `core/config/implement_policy.py` · `ImplementPolicy.language: Language \| None`, `parse_implement(text, source) -> ImplementPolicy` | read `implement_policy.py:17-30` |
| FR-6, FR-7 | the toolchain table and prepare plan | `workspace/project/prepare_plan.py` · `detect_toolchain(source_root: Path) -> str`, `plan_for(source_root: Path) -> PreparePlan` | read `prepare_plan.py:114-136,180` |
| FR-7 | the run's language today | `core/flow/engine/run_language.py` · `run_language(project_root: Path, language: str \| None) -> str` | read `run_language.py:22`; callers `interfaces/api/v1/implement.py:91`, `workflows/implementation/interfaces/cli.py:178`, `core/flow/engine/isolation.py:58-59` |
| FR-7, FR-14 | runner, converter, filter construction | `runner_factory.resolve_runner(cwd: Path, executor: SubprocessExecutor, language: str \| None = None)`, `create_scenario_converter(cwd: Path)`, `create_stack_trace_filter(cwd: Path)` | read `runner_factory.py:44,63`, `scenario_converter_factory.py:33`, `stack_trace_filter_factory.py:21`; callers `core/flow/handlers/qa_targets.py:75`, `arbiter.py:298` |
| FR-7 | the image | `sandbox/execution/sandbox_image.py` · `_resolve_image(source_root: Path) -> str` | read `sandbox_image.py:58,142` |
| FR-7 | the dual run's check | `core/flow/handlers/dual_pipeline.py:51` · `detect_toolchain(context.project_path) not in ("uv", "")` | read the line |
| FR-8 | the API error shape | `SpecWeaverAPIError(detail=, error_code=, status_code=)` | read `interfaces/api/v1/implement.py:73-92` |
| FR-9 | the pipeline choice | `archetype_pipelines.code_pipeline(code_path, project_path) -> tuple[ValidationPipeline, str \| None]` | read `archetype_pipelines.py:70` |
| FR-10 | the framework today | `workflows/implementation/frameworks.py` · `project_framework(project_root: Path, code_path: Path, language: str) -> FrameworkChoice \| None`, `_DETECTORS` | read `frameworks.py:43,88-116` |
| FR-10 | `context.yaml` keys | `topology.load_nodes(project_root)`, `ArchetypeResolver` | read `topology.py:90,119`, `core/config/archetype_resolver.py:21` |
| FR-11 | framework languages | evaluator schema `metadata.supported_languages` | read `sandbox/code_structure/core/evaluator.py:115`, `archetype_pipelines.py:167` |
| FR-16 | the analyzer families | `TreeSitterAnalyzerBase.detect(directory)` (glob of one ending), `StandardsAnalyzer.file_extensions() -> set[str]` | read `workspace/analyzers/factory.py:161-170`, `assurance/standards/analyzer.py:73-101` |
| FR-17 | Python via tree-sitter | `workspace/ast/parsers/python/codestructure.py` (tree-sitter-python grammar and tags query) | read `codestructure.py:11,55,66` |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Behaviour stays the same outside FR-2..FR-10, FR-13, FR-16 | The full suite passes; tests that pin a guess FR-3..FR-6 removes (listed in Research Findings) change to the refusal or the pinned answer, and no other test assertion changes **[proof: meta — rule about the diff]** |
| NFR-2 | `commons` stays I/O-free and the boundaries hold | A guard test fails when a `commons` module calls `open`, `read_text`, `iterdir`, `exists` or `glob`; `tach check` passes with the two new edges `core.flow.engine → workspace.project` and `assurance.validation.orchestration → workspace.project` **[proof: arch — tach gate plus the guard test]** |
| NFR-3 | No shims | Importing `detect_language`, `detect_toolchain` or `detect_scenario_extension` from their old modules raises `ImportError` |
| NFR-4 | The root is read once per decision | Deciding a profile lists the root once and reads at most the build files it names (`pyproject.toml`, `requirements*.txt`, `package.json`, `Cargo.toml`, `pom.xml`, `build.gradle*`); a run decides once and carries the profile |
| NFR-5 | Mutants still find their code | Every mutant anchored in a moved or removed symbol is re-pointed or retired with a reason; `stale_mutants.py` reports none stale **[proof: meta — rule about tests]** |

## External Dependencies

None new. tree-sitter and its grammars are already pinned.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | The profile decision is a pure function in `commons`; one reader in `workspace/project` lists the root, reads the named build files and the pins, and calls it `[agreed 2026-11-05]` | Every module can import `commons`; I/O stays in an adapter; `core/config` would grow a defect it already has | Yes — approved by the user on 2026-11-05 (Q12) |
| AD-2 | Two new tach and manifest edges: `core.flow.engine → workspace.project`, `assurance.validation.orchestration → workspace.project` | They are the two callers without one; the other callers already depend on `workspace/project` | No — follows AD-1 |
| AD-3 | A run decides the profile once at its start and carries it; downstream factories take the language as an argument | One decision per run; the factories need no file access | No |
| AD-4 | The two analyzer families stay separate jobs (structure per folder, style per file list) on one ending table and one parser library `[agreed 2026-11-05]` | They share no method; merging would put two jobs in one class | No |
| AD-5 | The framework markers (which dependency names mean Spring Boot, NestJS, Actix, FastAPI) move from `frameworks.py` into the pure profile function | Generation and validation then get one answer | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| Profile function and reader | small | low |
| Rewiring 8 whole-project callers | medium | medium: many tests pin today's guesses |
| Framework key and one declaration | small | low |
| One ending table, one parser lookup | medium | low |
| Python style analyzer on tree-sitter | medium | medium: results must stay the same |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| Users of mixed repos | no run where files, runner and image disagree | high |
| Go, C, C++, JavaScript users | a clear refusal instead of Python files | high |
| Spring Boot users without an archetype | the right checks | medium |
| Maintainers | a new language or ending is one row | medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| A project that worked by luck now refuses | medium | medium | the message names the one setting that fixes it |
| Python style results change after the parser move | medium | low | FR-17 pins them first |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| `core/config` reading files though `pure-logic` | archetype mismatch | none here; noted for its own ticket | — |

## Non-Goals

- Generation, QA runners or images for Go, C, C++ or JavaScript `[agreed 2026-11-05]`.
- Detection in subfolders or monorepo support `[agreed 2026-11-05]`.
- Moving `core/config`'s own file reads.
- Findings owned by the other tickets of the same audit (`TECH-075`..`TECH-091`, `TECH-070`).

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `language_support_guide.md` | how a language is detected, where its endings live, the refusal | ⬜ To be updated during Pre-commit |
| `1_installation_and_setup.md` §6c | the pins, `build_tool`, the refusals | ✅ SF-02 (§6c), SF-03 (Frameworks) |
| `context_yaml_spec.md` | the `framework:` key | ✅ SF-03 |

## Sub-Feature Breakdown

### SF-01: One profile decision
- **Scope**: the pure profile function, its detection and refusal rules, and the `build_tool` pin.
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6]
- **Inputs**: root file names, a reader, the `[implement]` section.
- **Outputs**: `ProjectProfile` or a refusal; the reader in `workspace/project`.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_sf01_implementation_plan.md

### SF-02: Every caller asks it
- **Scope**: the whole-project callers take the profile, the factories take the language, and the refusal reaches the CLI and API.
- **FRs**: [FR-7, FR-8, FR-14]
- **Inputs**: SF-01's profile.
- **Outputs**: one language per run; `detect_language` and `detect_toolchain` gone.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_sf02_implementation_plan.md

### SF-03: One framework answer
- **Scope**: the `framework:` key, the framework in the profile, validation using it, one language declaration per framework.
- **FRs**: [FR-9, FR-10, FR-11]
- **Inputs**: SF-01's profile.
- **Outputs**: one framework for generation and validation.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_sf03_implementation_plan.md

### SF-04: One ending table, one parser lookup
- **Scope**: every ending table reads `commons`, `.h` follows the project, one parser lookup.
- **FRs**: [FR-12, FR-13, FR-15]
- **Inputs**: `commons/languages.py`.
- **Outputs**: one table, one lookup, the guard test.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_sf04_implementation_plan.md

### SF-05: Analyzers on one base
- **Scope**: the style base renamed, both families through `commons`, Python style on tree-sitter, the code rules read a leading BOM.
- **FRs**: [FR-16, FR-17, FR-18]
- **Inputs**: SF-04's table and lookup.
- **Outputs**: no clashing names; one way to parse Python.
- **Depends on**: SF-04
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_sf05_implementation_plan.md

## Execution Order

SF-01 and SF-04 can start at once. Then SF-02 and SF-03 (after SF-01) and SF-05 (after SF-04).
One order: SF-01, SF-02, SF-03, SF-04, SF-05.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | One profile decision | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Every caller asks it | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | One framework answer | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-04 | One ending table, one parser lookup | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-05 | Analyzers on one base | SF-04 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Grilling 2026-11-05** (the user): Q1..Q12 all A; Q6 was reopened after research showed the two
analyzer families share no method, and settled as "one ending table and one parser library, the
families stay separate". Each decision sits beside its fact above.
Q13 (no build file: the root's code endings decide) and the API error code `PROJECT_UNDECIDED`
agreed at approval. **Design approved 2026-11-05** (the user).
**SF-01 plan approved 2026-11-06** (the user): contradicting pins are refused, naming both.
**SF-01 committed 2026-11-06**: `commons.project_profile.decide_profile` and
`workspace.project.read_project_profile`; no caller uses them yet.
**SF-02 plan approved 2026-11-06** (the user): the API pipeline run and resume refuse like `sw run`;
session isolation never turns off for an undecided project.
**SF-02 committed 2026-11-06**: a run decides its profile once (`core/flow/engine/run_profile.py`);
`sw run`, `sw implement`, `sw sandbox preflight` and the API refuse an undecided project; every
factory takes the language from one table; the sandbox takes the build tool; `detect_language` and
`detect_toolchain` are gone. Found at dev: a fresh `sw init` project has no build file and is
refused until it has one or `[implement] language`; Go keeps C05 through `architecture_atom`.
**SF-03 plan approved 2026-11-06** (the user): the evaluator-schema loader moves to `workspace/project`, which also answers each file's framework; a framework is a name with an evaluator schema.
**SF-03 committed 2026-11-06**: `workspace/project/frameworks.framework_for` gives each file one
framework (`framework:`, a framework archetype with a warning, the build file); generation,
`sw check`, the validate steps, the agent tools and the skeleton follow it; a framework is a name
with an evaluator schema. Kept at dev: a project's own role-archetype pipeline still applies after
the framework. Known limit: `POST /api/v1/check` uses no archetype or framework pipeline
(unchanged).
**SF-04 plan approved 2026-11-06** (the user): the analyzers' endings move in SF-04 with the guard;
`.cts`/`.mts` join TypeScript; one parser registry per process, read-only; `.h` from the project's files.
**SF-04 committed 2026-11-06**: `workspace/ast/parsers.parser_for` is the one parser lookup over a
registry built once; every ending table reads `commons` and a guard test fails on a new one; a `.h`
is C++ in a project with C++ sources. Found at dev: the refactor resolvers name `LANGUAGES` and the
base derives their endings (the duplication gate flagged repeated imports).
**SF-05 plan approved 2026-11-06** (the user): a Python file with a leading BOM is read by the style
check and by C01, C06, C08 (FR-18, added); JavaScript and TypeScript keep reading trees with errors.
**Next step**: dev SF-05 (`specweaver-dev docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_sf05_implementation_plan.md`).
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate skill.
