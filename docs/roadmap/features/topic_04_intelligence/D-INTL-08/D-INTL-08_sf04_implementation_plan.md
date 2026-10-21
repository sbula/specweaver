# Implementation Plan: Polyglot Implementation Loop [SF-04: Frameworks]
- **Feature ID**: D-INTL-08
- **Sub-Feature**: SF-04 — Frameworks
- **Design Document**: docs/roadmap/features/topic_04_intelligence/D-INTL-08/D-INTL-08_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/D-INTL-08/D-INTL-08_sf04_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-21

**FRs owned**: FR-8 · **NFRs**: NFR-1, NFR-4 · **Depends on**: SF-03 (committed 688371f2) ·
US-03 P-9.

## Shape

| Piece | Where | Tag |
|---|---|---|
| Six content files: `spring`, `spring-boot`, `quarkus`, `nestjs`, `actix-web`, `fastapi`. Each has `name:` and `languages:` front matter and two sections, `# Code` (idioms) and `# Tests` (test style: Spring's test slices `@WebMvcTest`/`@DataJpaTest`, Quarkus `@QuarkusTest`, Nest's `Test.createTestingModule`, `actix_web::test`, FastAPI's `TestClient`) | `workflows/frameworks/*.md` (+ `context.yaml`) | NEW |
| One loader for both kinds of content: `language_guide` keeps its shape; `framework_guide(name, project_dir) -> FrameworkGuide(name, languages, code, tests) | None` reads `.specweaver/frameworks/<name>.md` first, then the shipped file; None when neither exists. A name that is not `[a-z0-9][a-z0-9-]*` is never turned into a path | `workflows/implementation/languages.py` (shared parser) | MODIFY |
| Which framework: the archetype of the task's code file (`ArchetypeResolver.resolve`) when a framework file of that name exists and lists the run's language; else detected from the build file for the run's language — JVM: `io.quarkus` → quarkus, `spring-boot` / `org.springframework.boot` → spring-boot, `org.springframework` → spring; TypeScript: `@nestjs/core` in `package.json` dependencies → nestjs; Rust: `actix-web` in `Cargo.toml` `[dependencies]` → actix-web; Python: the word `fastapi` in `pyproject.toml` or a `requirements*.txt` → fastapi (Q1); else none. An archetype naming a framework of another language is ignored, logged, and detection decides (Q2). An archetype is user text: only a name matching `[a-z0-9][a-z0-9-]*` is looked up | `core/flow/engine/frameworks.py` (`project_framework(project_root, code_path, language)`), beside `task_files.py`: `workflows.implementation` may not read `core.config`'s archetype (tach) | NEW |
| Generation adds the framework's section after the language's instructions — `# Code` to the code step, `# Tests` to the tests step, agentic or one-shot | `core/flow/handlers/generation.py` | MODIFY |
| `sw implement` prints the framework and where it came from: `Framework: spring-boot (archetype)` / `(build file)` | `workflows/implementation/interfaces/cli.py` | MODIFY |

> [!NOTE]
> The guidance sits in the instruction slot, after the language text: it is the same for every task
> of a project, so the prompt start stays cacheable (`C-FLOW-14`).

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the six files, the loader, the choice, the prompt, the printed line, the journey | FR-8, US-03 P-9 | the journey: a Spring Boot project's prompt has no `@WebMvcTest`, a Quarkus one no `@QuarkusTest` |

| Tier | Test |
|---|---|
| unit | the loader: each shipped framework; project file first; a project-only framework (`micronaut.md`) found through the archetype; a missing section refused, naming the file; a path-like name refused. The choice: archetype wins; an archetype that is not a framework (`orchestrator`) falls to detection; an archetype for another language is ignored (Q2); each detection rule, and Spring Boot over Spring; nothing found → none; an unreadable build file → none; FastAPI from `requirements.txt`; NestJS from `devDependencies`; Quarkus from a Gradle Kotlin DSL `id("io.quarkus")` |
| integration (**seam**: archetype → generation) | a doubled model records the prompt: a `context.yaml` `archetype: quarkus` folder → the code prompt has the Quarkus code section, the tests prompt the Quarkus tests section; a Python project without a framework keeps today's prompt byte for byte (NFR-1) |
| e2e (**journey**, red first) | `sw implement` in a Spring Boot (Maven parent), a Quarkus (Gradle) and a NestJS project, doubled model and runner: the tests prompt names the framework's test style, and the output shows `Framework: <name>` |

## Mutants (into `D-INTL-08_mutants.json`, FR-8)

| Neutralise | Killed by |
|---|---|
| the guidance not added; the archetype ignored; detection returns none; Spring Boot read as Spring; the project file ignored; the language check dropped | unit, integration, e2e above |

## Research Notes

- `ArchetypeResolver(project_root).resolve(path)` (`core/config/archetype_resolver.py`) walks up
  from `path` to the nearest `context.yaml` `archetype:`; a file not yet written resolves through its
  folders (`_context_walk.resolve_up_tree`).
- Archetypes are not only frameworks: `orchestrator`, `pure-logic`, `adapter`, `data` appear across
  the repo, so an archetype names a framework only when a framework file of that name exists.
- The evaluator schemas (`workflows/evaluators/frameworks/*.yaml`) are for validation markers and
  hold no generation text; they stay as they are. Their `supported_languages` match the new files'
  `languages:` lines.
- `language_guide` and `_parse` (`workflows/implementation/languages.py`) are the loader to share;
  `_SECTIONS` becomes a parameter.
- The handler builds instructions as `self._instructions(guide)` (`generation.py`); the framework text
  joins it there, so one-shot and agentic both get it.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | FastAPI guidance changes a FastAPI project's Python prompt; NFR-1 says Python is unchanged | FastAPI projects get the guidance; a Python project without a framework keeps today's prompt byte for byte `[agreed 2026-10-21]` |
| Q2 | An archetype that names a framework of another language (a `spring-boot` folder in a Python run) | ignored and logged; detection decides — as validation skips an archetype that does not cover the file's language `[agreed 2026-10-21]` |

Settled in the plan, no trigger fired: both sections are required in a framework file; one framework per task, the most specific (Spring Boot over
Spring); guidance in the instruction slot; the printed line; evaluator schemas untouched.

## Backlog

none
