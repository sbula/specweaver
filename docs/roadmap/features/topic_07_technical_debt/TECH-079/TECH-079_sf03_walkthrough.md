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

## CB-3: validation uses the framework answer (FR-9); docs

**What changed**
- `archetype_pipelines.own_pipeline` / `code_pipeline` / `spec_pipeline` try names in order: the
  framework, then the folder's archetype. For code the framework is `framework_for`'s answer (with
  the run's profile); for a spec it is the folder's `framework:` only, never the build file (F5).
  The validate step passes `run_profile(context)`; `sw check` reads the profile with the
  `[implement]` pins and, when the root decides none or a pin is bad, goes on with the folder alone
  (F4). `_test_rules_only` keys on "no framework or archetype pipeline".
- Not in the plan, kept for compatibility: the archetype stays a fallback name, so a project's own
  `validation_code_<role>` pipeline (`test_code_validation_dal_strictness.py` uses one) still
  applies. F5's "a framework archetype" is the narrow reading; this keeps every archetype pipeline
  that worked before.
- Found at dev: the agent tools (`sandbox/dispatcher.py`) and the skeleton step read only the
  archetype to pick the evaluator schema, so a folder that followed our warning and moved
  `spring-boot` to `framework:` lost macro unrolling and tool hiding. Both now read
  `ArchetypeResolver.resolve_evaluator` (`framework:`, else archetype). The prompt's project
  description keeps naming the archetype, which is the layer role.
- `sw check`'s profile reader lives in `assurance/validation/interfaces/cli.py`: it needs
  `core.config.bootstrap.load_section`, which orchestration may not import; new tach edge
  `assurance.validation.interfaces → core.config.bootstrap`.
- F7 guard test and F8 planner hint. Docs: `context_yaml_spec.md` (`framework` field and rule),
  handbook 1 (code checks follow the framework), handbook 5 (`framework:` beside the role
  archetype), `adding_framework_guide.md` (sections 1, 2 and 4).

**What a user sees.** `sw check` on a Java file in a Spring Boot project with no archetype now runs
the Spring Boot code checks (C12), as `sw implement` writes Spring Boot code. Same in `sw run`'s
validate step.

**Known limit (not changed).** `POST /api/v1/check` never used an archetype pipeline and does not
use the framework either; it runs the named, profile or default pipeline as before. FR-9 names
`sw check` and the validate steps.

**Tests**
- Red first: `tests/e2e/capabilities/assurance/test_check_follows_the_framework_e2e.py` (red: the
  default pipeline ran, no C12), `tests/integration/assurance/validation/orchestration/test_pipeline_follows_the_framework.py`
  (red: no C12 from the profile, no spec pipeline from `framework:`), two agent-tool and skeleton
  tests in `test_one_framework_answer.py` (red: the archetype was read).
- `tests/integration/workspace/project/test_writers_name_no_framework.py` (F7);
  `test_renderer.py` asserts the hint (F8).
- Changed (NFR-1): `test_handlers_di_payload.py`'s mocked resolver now also answers "no
  `framework:`"; no assertion changed.

**Mutants.** TECH-079 FR-9: `validate-step-ignores-profile`, `framework-not-first`,
`role-archetype-pipeline-lost`, `sw-check-ignores-profile`, `sw-check-pins-ignored`,
`sw-check-refuses-undecided`, `sw-check-crashes-on-bad-pin`, `sw-init-writes-a-framework`; FR-10:
`agent-tools-ignore-framework-key`, `skeleton-ignores-framework-key`. Re-anchored: C-VAL-02
`profile-ignored`, D-INTL-08 `python-rules-on-java`, TECH-077 `skeleton-ignores-file-archetype`;
others re-pinned and re-run. `stale_mutants.py`: 0.

**Red/blue (2 cycles).** No finding above threshold. Accepted: a spec `framework:` with no
pipeline falls through to the archetype; a framework with no code pipeline (FastAPI) falls through
to the archetype, then the default; the API check limit above.

**Gate.** Full suite 12,573 passed, 9 skipped; `cb` 17/17; `doc` 14/14; `sf` 18/18; tach OK; mypy
clean.
