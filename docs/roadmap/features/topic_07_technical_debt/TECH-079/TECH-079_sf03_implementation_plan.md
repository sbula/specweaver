# Implementation Plan: Language and Toolchain Are Decided in a Dozen Places That Disagree [SF-03: One framework answer]
- **Feature ID**: TECH-079
- **Sub-Feature**: SF-03 — One framework answer
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_sf03_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-06)

## Scope

Generation and validation get one framework answer for a file. FRs: **FR-9, FR-10, FR-11**.
NFRs: NFR-1 (only tests that pin the old framework rules change), NFR-2 (the edge
`assurance.validation.orchestration → workspace.project`; `commons` stays I/O-free), NFR-3 (no
shims), NFR-4 (the build files are read once per decision), NFR-5 (mutants re-pointed). Path: P-5,
and the framework half of P-1. AD-1, AD-2, AD-5.

Today (measured 2026-11-06):

- **Generation** (`workflows/implementation/frameworks.py:43`
  `project_framework(project_root, code_path, language) -> FrameworkChoice | None`): the nearest
  `context.yaml` `archetype` counts when a guide `workflows/frameworks/<name>.md` exists and lists
  `language` in its `languages:` line; else the build file decides (`_DETECTORS`: JVM text rules
  quarkus → spring-boot → spring, `@nestjs/core` in `package.json`, `actix-web` in `Cargo.toml`,
  `fastapi` in `pyproject.toml`/`requirements*.txt`). Callers: `core/flow/handlers/generation.py:150`,
  `workflows/implementation/interfaces/cli.py:111` (`sw implement` prints "Framework: key (source)").
- **Validation** (`assurance/validation/orchestration/archetype_pipelines.py`): `code_pipeline:70`,
  `own_pipeline:84` and `spec_pipeline:42` read only the archetype (`archetype_of:32`, via
  `core/config/archetype_resolver.ArchetypeResolver`). A pipeline `validation_code_<archetype>` is
  used when the evaluator schema's `supported_languages` covers the file (`languages_of:149`,
  `covers:166`). Callers: `core/flow/handlers/validation.py:321` (validate steps; then
  `_test_rules_only` when no archetype and not Python), `assurance/validation/interfaces/cli.py:145`
  (`sw check`). So a Spring Boot project with no archetype gets Spring Boot code and default checks.
- **Languages declared twice**: guides `languages:` (`spring-boot`, `spring`, `quarkus`: java,
  kotlin; `nestjs`: typescript; `actix-web`: rust; `fastapi`: python) and schemas
  `workflows/evaluators/frameworks/*.yaml` `metadata.supported_languages` (`nestjs`: typescript,
  javascript). **`spring` has a guide and no schema.** Schemas are loaded by
  `sandbox/evaluator_schemas.load_evaluator_schemas(project_dir)` (packaged, then the project's
  `.specweaver/evaluators/`); importers in `src`: `archetype_pipelines.py`, `sandbox/dispatcher.py`.
- **Writers**: `workspace/project/scaffold.py` (`sw init`) and `workspace/analyzers/factory.py:197`
  `infer_archetype` write only roles (`orchestrator`, `pure-logic`, `adapter`); no framework is
  written anywhere today. `workflows/planning/models.py:30` `KNOWN_ARCHETYPES` = the five roles;
  `planning/renderer.py:52` warns on any other.
- **Profile**: `commons/project_profile.ProjectProfile(language, build_tool)`; the reader
  `workspace/project/project_profile.read_project_profile` already reads root build files through
  `read`. A run carries it (`core/flow/engine/run_profile.run_profile(context)`); `sw check` has no run.
- tach: `workflows.implementation` → `core.config`, `infrastructure.llm`;
  `assurance.validation.orchestration` → `assurance.validation(.io)`, `core.config`,
  `infrastructure.llm`, `sandbox`; `workspace.project` → `assurance.graph`, `workspace.analyzers`,
  `workspace.ast.parsers`; `sandbox` → `workspace.project`, `core.config`, …; `core.config` imports
  `workspace.store` only.

## Decisions (Phase 4, the user 2026-11-06: all proposals taken)

| # | Decision |
|---|---|
| F1 | `sandbox/evaluator_schemas.py` moves to `workspace/project/evaluator_schemas.py` (no shim; its importers `sandbox/dispatcher.py`, `archetype_pipelines.py` and 6 test files follow). `framework_for` lives in new `workspace/project/frameworks.py` beside the profile reader. New tach edges: `workspace.project → core.config` (the manifest already consumes it), `workflows.implementation → workspace.project` (manifest `consumes` too), and AD-2's `assurance.validation.orchestration → workspace.project` `[agreed 2026-11-06]` |
| F2 | New `workflows/evaluators/frameworks/spring.yaml`: `metadata` only (`framework: spring`, `supported_languages: [java, kotlin]`) `[agreed 2026-11-06]` |
| F3 | A name is a framework when it has an evaluator schema (packaged or `.specweaver/evaluators/`). A project guide without one is not used; a warning names the missing `.specweaver/evaluators/<name>.yaml` `[agreed 2026-11-06]` |
| F4 | `sw check` reads the profile; when the root does not decide, the build file names no framework, `framework:` and the archetype still count, and nothing is refused (logged at info) `[agreed 2026-11-06]` |
| F5 | Spec pipelines use the folder answer: `framework:`, then a framework archetype; never the build file `[agreed 2026-11-06]` |
| F6 | The archetype-names-a-framework warning fires once per `context.yaml` per process (a module-level set of warned paths: `ArchetypeResolver` is built anew per call, so its cache cannot dedupe) `[agreed 2026-11-06]` |
| F7 | A guard test: `sw init` and `infer_archetype` never write a framework name under `archetype:`. No writer changes `[agreed 2026-11-06]` |
| F8 | `planning/renderer.py` "unknown archetype" warning adds "a framework goes under `framework:`". `KNOWN_ARCHETYPES` stays the five roles `[agreed 2026-11-06]` |
| F9 | `ProjectProfile.framework: str = ""` `[agreed 2026-11-06]` |

## Architecture (Phase 3)

| Mechanism | Home | Allowed? |
|---|---|---|
| Framework markers (Spring/Quarkus, NestJS, Actix, FastAPI) on build-file text; "key, else framework archetype, else build file" | `commons/project_profile.py` (pure, `read` callback) | yes: no I/O (NFR-2) |
| `framework:` read from the nearest `context.yaml` | `core/config/archetype_resolver.py` (already reads `archetype:` and `plugins:` there) | yes |
| Schema loading, `framework_for(root, path, profile)` | `workspace/project/evaluator_schemas.py`, `workspace/project/frameworks.py` (adapter: reads files) | yes; `forbids: sandbox/*` holds — nothing imports `sandbox` |
| Guide text | `workflows/implementation/languages.py` (no `languages:`) | yes |

No cycle: `core.config` imports `workspace.store`, never `workspace.project`; `workspace.project`
imports no `sandbox`, `workflows` or `assurance.validation` module. Common closure: four modules
change, each for one reason (decision, key reader, assembler, two callers).

## Commit Boundaries

**CB-1 — the build-file framework is in the profile (FR-10 third clause, AD-5).**
- `ProjectProfile.framework` (`""` = none). The markers move from `frameworks.py` into `commons`;
  `decide_profile` names the framework of the decided language from the build files `read` returns.
- Tests first (unit, `tests/unit/commons/`): each marker; Spring Boot before Spring; the
  framework of a pinned language only (a pinned-Python root with `@nestjs/core` → none); an
  unreadable or broken manifest → none. Red reason: `ProjectProfile` has no `framework`.
- `frameworks.py` loses `_DETECTORS` in this same commit, so the markers are never in two places:
  `project_framework(project_root, code_path, language, build_framework)` takes the profile's
  framework; the generation handler and `sw implement` pass `run_profile(context).framework`
  (both have a run since SF-02).
- The reader reads each root file at most once per decision (NFR-4): `read` caches by name.
- NFR-5: the D-INTL-08 mutants anchored in `frameworks._jvm`/`_nest`/`_actix`/`_fastapi`
  re-anchor to `commons/project_profile.py`, re-pin, and re-run against their scope.
- Mutant: drop the Spring Boot rule → the Spring Boot test objects.

**CB-2 — one framework answer per file; languages declared once (FR-10, FR-11).**
- `ArchetypeResolver.resolve_framework(path)` reads `framework:`.
- `framework_for(root, path, profile) -> FrameworkAnswer(key, source, languages)`: `framework:`
  → archetype that names a framework (warning per F6) → `profile.framework`; applies only when the
  file's language is in the schema's `supported_languages` (none = any).
- Schemas are the one declaration: `spring.yaml` (F2); guides lose `languages:`;
  `FrameworkGuide.languages` goes; `project_framework` takes the answer.
- Tests first: integration `test_one_framework_answer.py` — generation's and validation's
  framework agree for: `framework:` only; archetype only (warns); build file only; `framework:`
  over archetype over build file; a file in another language → none; a project guide without a
  schema → none with the warning (F3). Red reason: `framework_for` does not exist.
- `framework_for(root, path, profile: ProjectProfile | None)`; `None` = `sw check` on an
  undecided root (F4). `languages_of` moves from `archetype_pipelines.py` into
  `workspace/project/frameworks.py` and keeps raising on an unknown language, naming the schema;
  `archetype_pipelines.covers` takes `answer.languages`.
- `evaluator_schemas.py` moves (F1); mutants anchored there re-anchor (NFR-5).
- Guard: no guide under `workflows/frameworks/` has a `languages:` line.
- Mutant: `framework:` read but ignored → the "`framework:` over archetype" test objects.

**CB-3 — validation uses the answer (FR-9); docs. Closes SF-03 (HITL).**
- `code_pipeline`, `own_pipeline` and `spec_pipeline` take the answer (F5 for spec); the validate
  handler passes `run_profile(context)`; `sw check` reads the profile and keeps going without one
  (F4). `add_payload`'s `active_archetype` becomes the framework key.
- Tests first: e2e `sw check` on a `.java` file in a Spring Boot root with no archetype runs the
  Spring Boot code pipeline (red today: default pipeline); integration: the validate step picks the
  same pipeline from the run's profile; `sw check` on an undecided root still checks.
- `validation.py` `_test_rules_only` keys on "no framework answer" instead of "no archetype".
- Guard test F7; renderer hint F8.
- Docs: `context_yaml_spec.md` (`framework:`), `language_support_guide.md`, the user guide.
- Mutant: `code_pipeline` ignores the profile framework → the e2e objects.

## Tests that change (NFR-1)

`tests/unit/workflows/implementation/test_frameworks.py` (guide `languages`, the detectors move),
`tests/integration/core/flow/handlers/test_generation_follows_the_framework.py`, and the schema
tests that count packaged schemas (`tests/unit/sandbox/test_framework_schemas.py`) for `spring.yaml`.

## Research Notes

- `evaluate_markers` (`sandbox/code_structure/core/evaluator.py:99`) skips a language outside
  `supported_languages` and finds nothing for a category the schema lacks: a metadata-only schema
  is safe.
- `ArchetypeResolver` caches per directory; a second key reader there reuses `resolve_up_tree`.
- `validation_code_spring-boot.yaml` lives in `workflows/pipelines/frameworks/java/`; the loader
  already finds it by name.
- No external tool. tree-sitter is untouched.

## Consistency (Phase 5)

- FR-9 → CB-3; FR-10 → CB-1 (build file), CB-2 (`framework:`, archetype, warning), CB-3 (F7, F8,
  `context_yaml_spec.md`); FR-11 → CB-2. NFR-1..NFR-5 and AD-1, AD-2, AD-5 are covered above.
- No cycle: `core.config` imports only `workspace.store`; `workspace.project` imports no `sandbox`,
  `workflows` or `assurance.validation` module after the move.
- Red/blue, 2 cycles: cycle 1 found 2 HIGH (markers in two places between CB-1 and CB-2;
  `_test_rules_only` keyed on the archetype) and 4 MEDIUM (reads per decision, `languages_of`
  twice, stale mutants, the `None` profile); all fixed above. Cycle 2 found none above threshold.

## Backlog

None.
