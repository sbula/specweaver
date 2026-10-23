# Design: Each Entry Point Builds Its Run by Hand, and the API Gets Less

- **Feature ID**: TECH-077
- **Phase**: Topic 07 (Technical Debt)
- **Status**: APPROVED (by the user, 2026-10-23)
- **Kind**: `bugfix`
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-077/TECH-077_design.md
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 17 below.

## Feature Overview

TECH-077 adds one run builder, a new delivery-side module `interfaces/run_setup`, that every CLI
command and API route calls to set up a run. It solves runs that differ by the door they came
through: ten places build a run by hand, API runs get no rule file, no coding standards and no
isolation by risk level, `sw resume` takes the current folder's project, and the API standards scan
finds nothing under a dot-folder. It touches the CLI and API doors, the project lookups in
`workspace`, the archetype and project-root lookups, and moves `sw draft` into the drafting
workflow. It does not change the run engine's own rule that it never uses project discovery
`[agreed 2026-10-23]`. These are gaps in delivered work; `finished-stories-immutable` bars editing
the closed stories, so this ticket owns them.

## Findings this ticket owns

Re-measured 2026-10-23 (all still hold; two changed shape).

| Finding | What is wrong | Fixed by |
|---|---|---|
| Fix first #4, FL-8, EP-1 | ten `RunContext` constructions each set a different subset of rule file, standards, `[docs]`/`[autonomy]`/`[implement]`, isolation, router, config, topology (`interfaces/api/v1/pipelines.py:61,153`, `interfaces/api/v1/_llm.py:64`, `core/flow/interfaces/cli.py:265`, `workflows/implementation/interfaces/cli.py:308`, `assurance/validation/interfaces/cli_drift.py:75,212`, `assurance/standards/interfaces/cli.py:170`, `workflows/review/interfaces/cli.py:210,317`) | FR-1, FR-2, FR-12 |
| EP-3 | isolation decided by two functions or skipped; only `sw implement` escalates by DAL, and it never sets the per-step policy (`workflows/implementation/interfaces/cli.py:325`) | FR-3 |
| EP-4 | three router factories (`infrastructure/llm/interfaces/command.py:71,102`, `interfaces/api/v1/_llm.py:27`); API runs never set `config`; `sw run` loads settings twice (`core/flow/interfaces/cli.py:309,328`) | FR-1 |
| EP-5 | "which project" differs per command: `sw implement` takes standards from the active project (`:298`), `sw run` registered-or-active (`:259`), API `/check` the active domain profile (`interfaces/api/v1/validation.py:108`) | FR-4 |
| Real defect 10 | `sw resume` rebuilds the run for the current folder, not the run's project (`core/flow/interfaces/cli.py:549`), and skips the topology | FR-5 |
| FL-12 | the archetype is found three ways: root `context.yaml` only (`core/flow/handlers/run_context.py:244`), nearest file (`archetype_pipelines.py:41`), topology (`context_assembler.py:47`) | FR-6 |
| EP-6 (from `TECH-075`) | API `selector` accepted and ignored (`interfaces/api/schemas.py:129,186`); `new_feature` impossible through the API (`pipelines.py:143`) | FR-7 |
| EP-12, Real defect 5 | the API standards scan re-implements discovery and drops every file whose absolute path has a dot-folder: a project under `~/.local` scans zero files (`interfaces/api/v1/standards.py:71-79`) | FR-8 |
| X-3 | validation rules find the project root four ways (`c02_tests_exist.py:36`, `c03_tests_pass.py:98`, `c09_traceability.py:96`, `graph/.../hasher.py:55`) | FR-9 |
| FL-20 | "registered project with fallback" four times (`naming.py:17`, `scenario_store.py:19`, `validation.py:38,540`) | FR-10 |
| CW-8 | "project registered at this path" four times, two DB styles (`workspace/store.py:87,102,110`, `interfaces/cli/_core.py:107`) | FR-10 |
| CW-9 | "project name to root" six times with different checks (`settings_loader.py:103`, `_core.py:99`, `workspace/project/interfaces/cli.py:106,276`, `assurance/standards/interfaces/cli.py:36`, `interfaces/api/v1/paths.py:88`) | FR-10 |
| CW-20 | the 5120-byte constitution limit is two literals (`constitution_loading.py:22`, `workspace/store.py:55`) | FR-10 |
| WV-19 | `sw draft` lives in the review CLI; each CLI builds its one-step pipeline inline (`workflows/review/interfaces/cli.py:34,147,307`, `workflows/implementation/interfaces/cli.py:34`, `cli_drift.py:63,201`) | FR-11 |

## Path List (`ADR-005`)

| Path | Span | Proof |
|---|---|---|
| P-1 the same pipeline through `sw run` and `POST /pipelines/{name}/run` → the same context parts | `interfaces/run_setup` → CLI, API → `core/flow` | integration (FR-1, FR-2, FR-12, NFR-1) |
| P-2 a DAL_B project → `sw run` / API run → session isolation on | `run_setup` → `core/flow/engine/isolation` | integration (FR-3) |
| P-3 `sw implement` in project B while project A is active → B's standards, settings, router | `run_setup` → `workspace`, `assurance/standards` | integration (FR-4) |
| P-4 a parked run → `sw resume` from another folder → the run's own project | CLI → `run_setup` → `core/flow/engine/store` | e2e (FR-5) |
| P-5 API run with `selector` → topology slice; API `new_feature` → spec drafted inside the project | API → `run_setup` | integration (FR-7) |
| P-6 `POST /standards/scan` on a project under a dot-folder → files found | API → `assurance/standards/discovery` | integration (FR-8) |
| P-7 validation rules C02, C03, C09 and the hasher in one run → one project root | `assurance/validation`, `graph` | integration (FR-9) |

## Research Findings

### Codebase Patterns

- Surfaces the builder composes (read 2026-10-23):
  `find_constitution(project_path, spec_path=None)` (`workspace/project/constitution.py`),
  `load_standards_content(db, project_name, project_path, target_path=None, *, max_chars=2000)` and
  its `_async` twin (`assurance/standards/loader.py:25,82`),
  `load_settings(db, project)` / `load_settings_async` (`core/config/bootstrap/settings_loader.py`),
  `load_section(root, parse)` (`core/config/bootstrap/project_settings.py`),
  `apply_isolation_policy(context, settings, logger)` and
  `apply_session_policy(context, settings, logger, *, dal_auto_escalate=False)`
  (`core/flow/engine/isolation.py:61,107`), `build_router(files, *, project, roles, db)`
  (`infrastructure/llm`), `load_topology(root)` / `select_topology_contexts(graph, module, *,
  selector_name)` (`assurance/graph/loader.py`), `attach_topology` (`core/flow/interfaces/run_topology.py`).
- Error styles today: the CLI refuses with `_core.refuse_settings` (exit 1); the API raises
  `SpecWeaverAPIError` (500 with a code). `build_router` and the loaders raise `SettingsFileError`.
- `ArchetypeResolver(project_path).resolve(target_path)` (`core/config/archetype_resolver.py:34`)
  is the nearest-`context.yaml` rule chosen for FR-6 `[agreed 2026-10-23]`.
- `discover_files(project_path, analyzer_factory)` (`assurance/standards/discovery.py:41`) honours
  `.specweaverignore` and judges dot-folders relative to the project.
- `core/flow/context.yaml` `consumes` excludes `workspace/project` on purpose
  (`core/flow/handlers/decomposition_artifacts.py:44`); the builder therefore lives outside the
  engine `[agreed 2026-10-23]`.
- The runner records the run's project (`core/flow/engine/runner.py:177`, `registered_name`).

### External Tools

None beyond the standard library and the packages already used.

### Blueprint References

`core/flow/interfaces/cli.py` `_build_run_context` is the most complete of the ten today (rule file,
standards, sections, isolation, router, topology); the builder starts from it.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | One run builder in `interfaces/run_setup` SHALL build a run's context from (project, spec or target, pipeline, run options): the rule file, the standards, `[docs]`/`[autonomy]`/`[implement]`, isolation, the model router and `config` when a step needs a model, and the topology slice; it SHALL raise errors, never exit, and load each settings file once | run setup | builds a run | one context, one set of errors |
| FR-2 | Every CLI door (`sw run`, `sw resume`, `sw implement`, `sw review`, `sw draft`, `sw drift check`, `sw drift check-rot`, `sw standards scan`) SHALL build its run through FR-1 and turn its errors into the existing CLI refusals | CLI | starts a run | the same context as every other door |
| FR-3 | Every door SHALL apply both isolation policies (per step and per run) with DAL auto-escalation `[agreed 2026-10-23]`, except that the read-only doors (`sw review`, `sw drift check`, `sw drift check-rot`, `sw standards scan`, `POST /review`) skip the per-run worktree `[agreed 2026-10-23]`; a high-DAL project with no git repository stops instead of running on the host (`sw implement` used to warn and run on the host, `INT-US-03` AD-8, now reversed) `[agreed 2026-10-23]` | run setup | decides isolation | untrusted steps are bounded the same way through every door |
| FR-4 | A run SHALL use one project for everything (settings, router, standards, profiles, rule file): the project registered at the target's folder, else the active project when no path is given; the API uses the request's project `[agreed 2026-10-23]`; a folder no project is registered at is refused, naming it and `sw init` `[agreed 2026-10-23]` | run setup | picks the project | no mix of active and target project |
| FR-5 | `sw resume` SHALL rebuild the run for the project the run recorded, with its topology, whatever the current folder; a recorded project that is no longer registered stops the resume, naming it | CLI | resumes a run | a resumed run gets its own project's context |
| FR-6 | The archetype SHALL be found one way, the nearest `context.yaml` above the file (`ArchetypeResolver`), in the run context, the archetype pipelines and the context assembler `[agreed 2026-10-23]` | engine, handlers | ask for the archetype | one answer per file |
| FR-7 | The API run SHALL honour `selector` (topology slice) and SHALL accept `new_feature`, whose spec does not exist yet and is created inside the project `[agreed 2026-10-23]`; with no interactive channel the drafting step parks as a headless CLI run does, and the run resumes through the existing gate answer | API | starts a run | the API matches the CLI |
| FR-8 | `POST /standards/scan` SHALL find files with `discover_files`, so dot-folders are judged relative to the project and `.specweaverignore` applies | API | scans standards | a project under `~/.local` scans its files |
| FR-9 | Validation rules C02, C03, C09 and the dependency hasher SHALL use the run's project root when they have it, else one shared root search `[agreed 2026-10-23]` | validation | locate the project | one root per run |
| FR-10 | One lookup each SHALL answer "project registered at this path", "project name to root" and "registered project with fallback", in one DB style; the constitution size limit SHALL be one constant `[agreed 2026-10-23]` | workspace, CLI, API | look up a project | one answer, one place |
| FR-11 | `sw draft` SHALL live in the drafting workflow (the command name unchanged), and one helper SHALL build a one-step pipeline for every CLI that needs one `[agreed 2026-10-23]` | CLI | registers commands | each command where its workflow is |
| FR-12 | Every API door (`POST /pipelines/{name}/run`, resume, gate answers, `/review`, `/implement`) SHALL build its run through FR-1 and turn its errors into the existing HTTP answers | API | starts a run | API runs get the rule file, standards, sections and isolation |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | rule file, standards, sections, settings, router, topology | the surfaces listed in §Codebase Patterns | read 2026-10-23 |
| FR-3 | both policies | `apply_isolation_policy`, `apply_session_policy(..., dal_auto_escalate=True)` | read `core/flow/engine/isolation.py:61-130` |
| FR-4 | project at a path, active project | `workspace/store.py:87-115`, `_core.registered_project_at` | read 2026-10-23 |
| FR-5 | the run's project | `PipelineRun.project_name` / `registered_name` (`runner.py:177`) | read 2026-10-23 |
| FR-6 | archetype | `ArchetypeResolver.resolve` (`core/config/archetype_resolver.py:34`) | read 2026-10-23 |
| FR-8 | source files | `discover_files` (`assurance/standards/discovery.py:41`) | read 2026-10-23 |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | The same pipeline and project give the same context parts through every door (agreement test across CLI and API) | one test compares them |
| NFR-2 | The engine (`core/flow`) gains no `workspace/project` dependency; the new module's links all point from doors to it and from it downward `[agreed 2026-10-23]` **[proof: arch — tach/lint gate, not pytest]** | `tach check` clean |
| NFR-3 | The builder raises; only doors exit or answer HTTP | no `typer` import in `run_setup` |
| NFR-4 | Behaviour not named here stays as it is | existing tests green |

## External Dependencies

None.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | The run builder is a new module `interfaces/run_setup`, used by the CLI, the API and the command modules | the engine keeps its rule; run setup is a door concern `[agreed 2026-10-23]` | Yes — approved by the user 2026-10-23 (option B) |
| AD-2 | The builder is async at its core with a sync entry for the CLI (`commons.async_bridge.run_sync`) | the API loaders are async; one implementation | No |
| AD-3 | Doors map builder errors with their existing refusals (`refuse_settings`, `SpecWeaverAPIError` codes) | no new error codes, except `WORKTREE_UNAVAILABLE` (409) for `POST /implement` `[agreed 2026-10-23]` | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| 4 sub-features, 12 FRs, ten doors moved onto one builder | 4–6 sessions | medium: every door changes; NFR-1's agreement test guards it |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| API users | runs get the rule file, standards, sections and isolation | high |
| Every high-DAL project | isolation by risk level through every door | high (security) |
| Maintainers | one place to change how a run is set up | high |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| A high-DAL project without git now stops in every door, `sw implement` included | medium | the run stops, naming `git init` and `auto_isolate_min_dal = "off"` | the user's choice 2026-10-23: high-DAL code never runs unbounded |
| A door loses a part it had | low | a run behaves differently | NFR-1 agreement test; existing door tests |
| An API run of a high-DAL project fails at its first isolated step, not at the request | medium | the run ends failed, naming the worktree error | the run starts in the background today; the failure is recorded on the run |

### Refactoring Opportunities
Covered by FR-10 and FR-11.

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `pipeline_engine_guide.md`, `docs/dev_guides` on adding a CLI command or API route | build a run through `run_setup` | ⬜ To be written during Pre-commit |

## Works For Real

On a DAL_B project with a `CONSTITUTION.md`, `sw run validate_only specs/<x>_spec.md` and
`POST /pipelines/validate_only/run` give the run the same rule file, standards and session
isolation (shown by the run's context in the e2e and by `sw run --verbose`). The same journey runs as
an e2e test in the suite.

## Sub-Feature Breakdown

### SF-01: One answer per lookup
- **Scope**: project lookups, archetype, project root, the constitution limit.
- **FRs**: [FR-6, FR-9, FR-10]
- **Inputs**: today's duplicated lookups.
- **Outputs**: one function per question, used by SF-02.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-077/TECH-077_sf01_implementation_plan.md

### SF-02: The run builder
- **Scope**: `interfaces/run_setup`: build, isolation with DAL escalation, the one-project rule.
- **FRs**: [FR-1, FR-3, FR-4]
- **Inputs**: SF-01's lookups.
- **Outputs**: `build_run` (async and sync) raising errors.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-077/TECH-077_sf02_implementation_plan.md

### SF-03: Every CLI door uses it
- **Scope**: the eight CLI doors, `sw resume`'s project, `sw draft`'s home, the one-step helper.
- **FRs**: [FR-2, FR-5, FR-11]
- **Depends on**: SF-02
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-077/TECH-077_sf03_implementation_plan.md

### SF-04: Every API door uses it
- **Scope**: the API run, resume, gate, `/review`, `/implement`; `selector`, `new_feature`; the
  standards scan.
- **FRs**: [FR-7, FR-8, FR-12]
- **Depends on**: SF-02
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-077/TECH-077_sf04_implementation_plan.md

## Execution Order

1. SF-01
2. SF-02
3. SF-03 and SF-04, in either order

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | One answer per lookup | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | The run builder | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | Every CLI door uses it | SF-02 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-04 | Every API door uses it | SF-02 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design APPROVED 2026-10-23; SF-01, SF-02 and SF-03 committed 2026-10-23
([SF-01](TECH-077_sf01_walkthrough.md), [SF-02](TECH-077_sf02_walkthrough.md),
[SF-03](TECH-077_sf03_walkthrough.md)).
**Next step**: Trigger the dev skill for SF-04 (CB-1).
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume
from there using the appropriate skill.
