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
