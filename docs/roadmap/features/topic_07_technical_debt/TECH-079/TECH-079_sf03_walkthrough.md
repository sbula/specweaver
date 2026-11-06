# Walkthrough: TECH-079 SF-03 — One framework answer

## CB-1: the build-file framework is in the profile (FR-10 third clause, AD-5)

**What changed**
- `ProjectProfile.framework` (`""` = none; F9 `[agreed 2026-11-06]`). `decide_profile` names the
  framework of the decided language from the root's build files: Quarkus before Spring Boot before
  Spring in the JVM build text, `@nestjs/core` in `package.json` dependencies, `actix-web` in
  `Cargo.toml` dependencies, `fastapi` in `pyproject.toml` or `requirements*.txt`. One small reader
  per language, chosen from `_FRAMEWORK_OF`. It reads only files the root holds.
- `workflows/implementation/frameworks.py` lost its detectors. `project_framework(root, code_path,
  language, build_framework)`: the archetype rule is unchanged until CB-2; otherwise the profile's
  framework decides. The generation handler and `sw implement` pass `run_profile(context).framework`.
- `read_project_profile` reads each root file at most once (NFR-4): a Kotlin Spring Boot build file
  is read for Kotlin and for the framework.
- Found at dev: the first draft read `package.json` and `Cargo.toml` even when the root had none;
  the agreement test's strict reader raised. Each reader now checks the root first, and a unit test
  holds it.

**What a user sees.** Nothing new. A pinned language takes only its own build files' framework: a
Python-pinned root with a NestJS `package.json` gets no NestJS guidance (before, generation never
asked another language's file either).

**Tests**
- Red first: `tests/unit/commons/test_profile_names_the_framework.py` (red: `ProjectProfile` had no
  `framework`); `test_read_project_profile.py` gained a Spring Boot root and the read-once test.
- Rewritten (NFR-1): `test_frameworks.py` build-file cases now pass the profile's framework (the
  detection cases moved to the commons test); `test_project_profile.py::test_only_build_files_are_read`
  allows the Python build file the framework reads; the FastAPI generation test decides its profile
  from the root instead of a hand-built one, so it proves build file → profile → prompt.

**Mutants.** TECH-079 FR-10: `requirements-not-read`, `pinned-language-takes-any`,
`generation-ignores-profile-framework`; NFR-4: `reader-not-cached`. D-INTL-08 FR-8 `detection-none`
and `spring-before-boot` re-anchored to `commons/project_profile.py`; the commons test joined that
campaign's scope. 21 others re-pinned after their symbols changed, each re-run on its scope and
objected. `stale_mutants.py`: 0.

**Red/blue (2 cycles).** No finding above threshold. Checked: the undecided raise in generation
fires where `_files` already raised; the reader stays root-confined; JavaScript and other languages
that cannot be generated never reach the framework step.

**Gate.** Full suite 12,539 passed, 9 skipped; `cb` 17/17; `doc` 14/14; tach OK; mypy clean. The
complexity gate caught the first `_framework` (24); it is now a table of four small readers.

## CB-2: one framework answer per file; languages declared once (FR-10, FR-11)

**What changed**
- `sandbox/evaluator_schemas.py` moved to `workspace/project/evaluator_schemas.py`, no shim (F1
  `[agreed 2026-11-06]`). Its importers and its two test files moved with it
  (`tests/unit/workspace/project/test_evaluator_schemas.py`, `test_framework_schemas.py`). New tach
  edges: `workspace.project → core.config`, `workflows.implementation → workspace.project`,
  `assurance.validation.orchestration → workspace.project` (AD-2; `widens` reason recorded).
- New `workspace/project/frameworks.py`: `framework_for(root, path, profile | None) ->
  FrameworkAnswer(key, source, languages)`. Order: the nearest `framework:`
  (`ArchetypeResolver.resolve_framework`), an `archetype:` with a schema (warns to move it), the
  profile's build-file framework; the first whose schema languages cover the file. A name without
  a schema is no framework; `framework:` naming one warns (F3). `languages_of` lives here; the
  validation copy delegates to it until CB-3.
- `spring.yaml` (metadata only, F2). The guides lost `languages:`; `FrameworkGuide.languages` is
  gone. `project_framework(root, code_path, profile)` takes `framework_for`'s answer and adds the
  guide; a project guide whose name has no schema warns and is not used (F3).
- Deviation, recorded: F6 said "once per `context.yaml`"; the warning fires once per (project,
  archetype) per process, because `ArchetypeResolver.resolve` returns the value, not the file. It
  warns less often, never more.

**What a user sees.** `framework: quarkus` in a folder's `context.yaml` now names the framework for
generation. `archetype: spring-boot` still works and logs a warning. A project framework written
as a guide alone (`.specweaver/frameworks/x.md`) now needs `.specweaver/evaluators/x.yaml`; the
warning says so. The user guide's Frameworks paragraph says all of it.

**Tests**
- Red first: `tests/integration/workspace/project/test_one_framework_answer.py` (red: no module),
  16 tests, generation included.
- Rewritten (NFR-1): `test_frameworks.py` passes a profile; the project-only framework test now
  ships its schema; the guide test no longer asserts `languages`. Guard: no shipped guide has a
  `languages:` line (a mutant adding one objects).

**Mutants.** TECH-079 FR-10: `framework-key-ignored`, `archetype-move-not-warned`,
`unknown-framework-key-silent`, `guide-without-schema-silent`; FR-11: `schema-languages-ignored`.
Re-anchored to `framework_for`: D-INTL-08 `archetype-ignored`, `language-check-dropped`; B-INTL-01
`unknown-language-kept` (to `languages_of`); TECH-081 `sandbox-imports-workflows` (new import
line); TECH-079 `generation-ignores-profile-framework`. Two drafted TECH-079 mutants duplicated
those and were dropped. 15 others re-pinned and re-run. `stale_mutants.py`: 0.

**Red/blue (2 cycles).** No finding above threshold. Accepted: `framework_for` loads the schemas
on each call (as `languages_of` did before); a non-text `framework:` value is read as text, finds
no schema and warns; a path-like key is only a dictionary key, and `framework_guide` refuses
non-plain names.

**Found at the gate.** Each full run failed 2 different tests that check log output
(`test_execution_executor` debug logging, `test_runner_telemetry`, `test_scenario_handlers`). Cause:
`setup_logging` (any CLI test runs it) sets the `specweaver` logger's level and no test put it
back; `caplog.at_level` sets only the root's, so a later test lost its DEBUG records. Moving the
schema tests changed how xdist spread the files and exposed it. Reproduced in one process
(`test_console_log_level.py` then `test_execution_executor.py`: 2 failed); fixed with an autouse
fixture in `tests/conftest.py` that restores the logger's level, handlers and project tag.

**Gate.** `cb` 17/17; `doc` 14/14; `sf` 18/18; tach OK; mypy clean; the full suite runs in the
gated commit.
