# Design: Project Settings Are Read Two Ways, and One Fails Open

- **Feature ID**: TECH-076
- **Phase**: Topic 07 (Technical Debt)
- **Status**: APPROVED (by the user, 2026-10-23)
- **Kind**: `bugfix`
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-076/TECH-076_design.md
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 7 below.

## Feature Overview

TECH-076 puts every section of a project's `specweaver.toml`, and the project's
`.specweaver/dal_definitions.yaml`, through one strict reader that names the file, key and line of
an error. It solves a fail-open path: today a typo in `[sandbox]` silently runs untrusted code on the
host, and two entry points swallow any settings error and turn isolation off. It touches
`core/config`, the CLI and API entry points that load project settings, and moves the doc block
helpers to `commons`. It does not change what a valid file means, and it does not touch the machine
`settings.toml` rules beyond sharing the reader. These are gaps in delivered work;
`finished-stories-immutable` bars editing the closed stories, so this ticket owns them.

## Findings this ticket owns

Re-measured 2026-10-23; every one still holds. Each maps to the requirement that fixes it.

| Finding | What is wrong | Fixed by |
|---|---|---|
| Fix first #1 | `[sandbox]` and `[standards]` are read by a lenient copy: invalid TOML, a misspelt key or a bad value falls back to defaults and only logs (probed: `execution_mod`, `"containr"` and a broken header all give `host`; `core/config/bootstrap/settings_loader.py:45-82`) | FR-1, FR-2 |
| CW-1 | strict and lenient `specweaver.toml` readers side by side (`core/config/project_sections.py:21` vs `settings_loader.py:45-82`) | FR-1 |
| CW-2 | three copies of "TOML text → strict model → located error" that report keys and lines differently (`project_sections.py:21`, `doc_policy.py:82-100`, `llm_settings.py:305-330`) | FR-6 |
| CW-3 | each section costs a model, a loader and a CLI wrapper; `PROJECT_FILE_NAME` lives in the LLM loader (`bootstrap/*_loader.py`, `interfaces/cli/_core.py:118-180`, `bootstrap/llm_settings_loader.py:28`) | FR-7 |
| CW-4 | the shared error and its CLI handler are named as LLM things: `refuse_llm_settings` refuses doc and autonomy errors (`llm_settings.py:49`, `_core.py:182`) | FR-8 |
| CW-18 | schema, parsing, role resolution, currency and a CLI report in one 560-line module (`llm_settings.py`) | FR-9 |
| CW-19 | text patching of marked blocks lives in config (`doc_policy.py:121-160`; users `core/flow/handlers/bash_action.py:93`, `sandbox/git/core/worktree_ops.py:13`) | FR-10 |
| Found in design research | `[docs]` reports a TOML syntax error at line 0 before Python 3.14 (`doc_policy.py:87`, `getattr(exc, "lineno", 0)`) | FR-6 |
| Found in design research | a broken `.specweaver/dal_definitions.yaml` falls back to the default matrix and only logs (`settings_loader.py:96-118`) `[agreed 2026-10-23]` | FR-3 |
| Found in design research | `sw run` / `sw resume` and `POST /pipelines/{name}/run` catch every settings error and run with isolation off (`core/flow/interfaces/cli.py:330-340`, `interfaces/api/v1/pipelines.py:116-123`) `[agreed 2026-10-23]` | FR-4 |
| Found in SF-01 dev | `_resolve_merged_settings` catches every error while layering the target's DAL tier over the settings and validates without it, logging a WARNING (`core/flow/handlers/validation.py:57-72`) `[agreed 2026-10-23]` | FR-4 |
| Found in design research | `load_settings_for_active` has no caller (`settings_loader.py:147`) | FR-7 |
| Found in design research | `sw implement`, `sw review`, `sw standards scan`, `sw drift` and `sw run`'s model setup call `load_settings` with no handler, so a settings error would end in a traceback | FR-5 |

## Path List (`ADR-005`)

| Path | Span | Proof |
|---|---|---|
| P-1 user writes a broken `[sandbox]` → `sw run` → refused, file and line named | `core/config` → `core/flow` CLI | e2e (FR-1, FR-4) |
| P-2 API client → `POST /pipelines/{name}/run` on a project with a broken `[sandbox]` → 500 `SANDBOX_SETTINGS` | `core/config` → `interfaces/api` | integration (FR-4) |
| P-3 broken `[standards]` → `sw standards scan` / `sw implement` → refused | `core/config` → CLI | integration (FR-1, FR-5) |
| P-4 broken `dal_definitions.yaml` → `sw run` → refused | `core/config` → `core/flow` CLI | integration (FR-3, FR-4) |
| P-5 any section with a TOML syntax error → its real line | `core/config` alone | unit (FR-6) |
| P-6 `bash_action` fills a doc block; the worktree merge compares outside blocks | `core/flow`, `sandbox/git` → `commons` | existing integration tests stay green (FR-10) |

## Research Findings

### Codebase Patterns

- `parse_section(text, source, name, model)` (`core/config/project_sections.py:21`) is the strict
  reader `[implement]` and `[autonomy]` use: `tomllib.loads`, then `model.model_validate`, unknown
  key first, raising `SettingsFileError(source, key, line, message)`.
- `SettingsFileError(source, key, line, message)` (`core/config/llm_settings.py:49`) prints as
  `source:line: key: message`. The CLI stops on it with `refuse_llm_settings` (`_core.py:182`,
  exit 1); the API maps it to 500 with a per-section code (`interfaces/api/v1/run_settings.py:39-58`:
  `DOC_POLICY`, `AUTONOMY_POLICY`, `IMPLEMENT_POLICY`; `LLM_SETTINGS`).
- `path_line(text, path) -> int` (`core/config/toml_lines.py:33`) finds a key's line, else 1.
- `SandboxSettings` and `StandardsSettings` (`core/config/settings.py:86-140`) are plain
  `BaseModel`s, so they accept unknown keys; the strict sections use `_Strict` (`extra="forbid"`,
  `llm_settings.py:64`).
- `load_settings(db, project) -> SpecWeaverSettings` (`settings_loader.py:86`) builds
  `standards`, `sandbox` and `dal_matrix` for every caller listed in the findings.
- `docs/dev_guides/subprocess_execution.md:193` documents today's fallback ("An absent, empty or
  malformed `[sandbox]` falls back"); it changes with FR-1.
- `commons` forbids every other package (`commons/context.yaml`), so both `core/flow` and
  `sandbox/git` may import a helper placed there.

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Python `tomllib` | 3.11+ | `tomllib.loads`; `TOMLDecodeError.lineno` exists only from 3.14, so the line is read from the message before that | https://docs.python.org/3/library/tomllib.html |
| `ruamel.yaml` | pinned | `YAML(typ="rt")` keeps line marks (`.lc.line`, `.lc.key(k)`); `YAMLError.problem_mark.line` | https://yaml.dev/doc/ruamel.yaml/ |

### Blueprint References

The repo's own strict sections (`[llm]`, `[docs]`, `[autonomy]`, `[implement]`) are the pattern:
one shape of error everywhere, the unknown key reported first.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | `[sandbox]` and `[standards]` SHALL be read by the shared strict reader: invalid TOML, an unknown key or a bad value SHALL raise `SettingsFileError` naming the file, key and line, and never fall back to defaults `[agreed 2026-10-23]`; an absent file or section still gives the defaults | settings loader | loads project settings | a typo stops the command instead of running on the host |
| FR-2 | `SandboxSettings` and `StandardsSettings` SHALL refuse unknown keys `[agreed 2026-10-23]` | settings models | validate a section | a misspelt key is an error, not ignored |
| FR-3 | A broken `.specweaver/dal_definitions.yaml` (invalid YAML, unknown key, bad value) SHALL raise `SettingsFileError` naming the file, key and line `[agreed 2026-10-23]`; an absent file still gives the default matrix | settings loader | loads the DAL matrix | a broken matrix stops the command |
| FR-4 | `sw run`, `sw resume`, `POST /pipelines/{name}/run` and the API's resume and gate-answer routes (both through `_apply_isolation`, `pipelines.py:69`) SHALL stop on a `SettingsFileError` while resolving isolation instead of running with isolation off: the CLI exits 1 printing the located message, the API answers 500 with `SANDBOX_SETTINGS` or `STANDARDS_SETTINGS` `[agreed 2026-10-23]`, or `DAL_DEFINITIONS` for the DAL file `[agreed 2026-10-23]`; any other failure there keeps today's best effort `[agreed 2026-10-23]`; the validation handler SHALL stop when it cannot layer the target's DAL tier over the settings, instead of validating without it `[agreed 2026-10-23]` | CLI, API | start a run | no run executes on a project whose settings cannot be read |
| FR-5 | Every CLI command that loads project settings (`sw implement`, `sw review`, `sw standards scan`, `sw drift`, `sw run`) SHALL stop on a `SettingsFileError` with exit 1 and the located message, never a traceback | CLI | loads project settings | one clear refusal on every door |
| FR-6 | One function SHALL turn settings text into a strict model or a located `SettingsFileError`; `[docs]`, `[llm]`, the machine file and the project sections SHALL use it, and a TOML syntax error SHALL name its real line on every supported Python | settings readers | parse settings text | one error shape; no "line 0" |
| FR-7 | One loader SHALL read any project section by name and model, and one CLI wrapper SHALL refuse its error; `PROJECT_FILE_NAME` SHALL live with that loader, not in the LLM loader; the unused `load_settings_for_active` is removed | settings loader, CLI | load a section | adding a section costs a model only |
| FR-8 | The shared error and its CLI handler SHALL live in a settings-file module and carry settings names, not LLM names | config, CLI | report a broken file | the name says what it refuses |
| FR-9 | `llm_settings.py` SHALL be split so the schema, the parsing and the role resolution with its report are separate modules | config | — | each module has one reason to change |
| FR-10 | The marked-block text helpers (`fill_block`, `outside_blocks`) SHALL live in `commons`, and config SHALL keep only the `[docs]` policy | config, `commons` | patch a doc block | text patching is not configuration |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1, FR-2 | the project's settings text and a strict model | `read_settings_text(path: Path \| None) -> str` (`bootstrap/llm_settings_loader.py:62`); `parse_section(text, source, name, model)` (`project_sections.py:21`) | read both files 2026-10-23 |
| FR-3 | YAML line marks | `ruamel.yaml` round-trip loader (already a dependency, `settings_loader.py:108`) | read `settings_loader.py:96-118` |
| FR-4 | the run's isolation resolution | `load_settings` / `load_settings_async` (`settings_loader.py:86,121`); `apply_isolation_policy(context, settings, logger)` | read `core/flow/interfaces/cli.py:325-345`, `interfaces/api/v1/pipelines.py:104-123` |
| FR-4 | API error mapping | `SpecWeaverAPIError(detail, error_code, status_code)` as used in `interfaces/api/v1/run_settings.py:39-58` | read 2026-10-23 |
| FR-5 | CLI refusal | `refuse_llm_settings(err) -> NoReturn` (`interfaces/cli/_core.py:182`) | read 2026-10-23 |
| FR-10 | block helpers' callers | `bash_action.py:93`, `worktree_ops.py:13` | grep 2026-10-23 |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Fail closed: a settings file that cannot be read stops the command; it never yields defaults `[agreed 2026-10-23]` | refusal, never a pass |
| NFR-2 | A valid file, an absent file and an absent section behave exactly as today | existing tests green |
| NFR-3 | The error text keeps today's shape `source:line: key: message` | one shape for every section |
| NFR-4 | No new layer edge except `core/flow` and `sandbox/git` importing `commons` (already allowed), and `interfaces.cli → workspace.project`, so the CLI's one "find the project folder or exit" helper replaces ten copies `[agreed 2026-10-23]` **[proof: arch — tach/lint gate, not pytest]** | `tach check` clean |

## External Dependencies

None beyond the standard library and the already-pinned `ruamel.yaml`.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | `parse_section` grows into the one reader (FR-6); the lenient `_load_toml_*` functions are deleted | it already has the strict behaviour the other sections need | No |
| AD-2 | The error stays a `ValueError` subclass with the same fields; only its module and the CLI handler's name change | callers catch it by type; the fields are the message contract | No |
| AD-3 | The block helpers go to `commons`, added to its `exposes` list | both users may import `commons`; neither may import the other | No |
| AD-4 | `[standards]` gets the same posture as `[sandbox]` | one rule for every section `[agreed 2026-10-23]` | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| 3 sub-features, 10 FRs: one behaviour fix, then moves | 2–3 sessions | low: the strict reader exists and is proven |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| Every project with `[sandbox]` | a typo can no longer run untrusted code on the host | high (security) |
| Maintainers | one reader, one error, one loader | medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| A project with a stray key in `[sandbox]` or `[standards]` stops after the upgrade | low | one fix to the file | the error names the file, key and line (FR-1) |
| A broken `[sandbox]` now also stops commands that only need `[standards]` | low | the user fixes the file | one file, one fix; same as `[llm]` today |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| the three per-section loaders and wrappers | copies | one loader (FR-7) | small |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `subprocess_execution.md`, `pipeline_engine_guide.md` | a broken `[sandbox]` stops; no fallback | ⬜ To be written during Pre-commit |
| user guides `1_installation_and_setup.md`, `3_managing_constitutions.md` | `[sandbox]` / `[standards]` errors name file and line | ⬜ To be written during Pre-commit |

## Works For Real

In a project whose `specweaver.toml` holds `[sandbox]` / `execution_mod = "container"`,
`sw run validate_only specs/<x>_spec.md` exits 1 printing
`<project>/specweaver.toml:<line>: sandbox.execution_mod: Extra inputs are not permitted` and starts
no run. The same journey runs as an e2e test in the suite.

## Sub-Feature Breakdown

### SF-01: One strict reader
- **Scope**: the shared reader, `[sandbox]` / `[standards]` strict, the DAL file strict.
- **FRs**: [FR-1, FR-2, FR-3, FR-6]
- **Inputs**: `specweaver.toml` text, `dal_definitions.yaml` text.
- **Outputs**: `SettingsFileError` from `load_settings` for any broken project setting.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-076/TECH-076_sf01_implementation_plan.md

### SF-02: Every door stops on a broken setting
- **Scope**: the two catch-alls and every CLI command that loads project settings.
- **FRs**: [FR-4, FR-5]
- **Inputs**: `SettingsFileError` from SF-01.
- **Outputs**: CLI exit 1 with the located message; API 500 with the section's code.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-076/TECH-076_sf02_implementation_plan.md

### SF-03: One loader, honest names, one home each
- **Scope**: CW-3, CW-4, CW-18, CW-19. No behaviour change.
- **FRs**: [FR-7, FR-8, FR-9, FR-10]
- **Inputs**: the code after SF-01.
- **Outputs**: one loader and wrapper; the error in a settings-file module; `llm_settings` split;
  block helpers in `commons`.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-076/TECH-076_sf03_implementation_plan.md

## Execution Order

1. SF-01 (no deps)
2. SF-02 and SF-03, in either order (both depend only on SF-01)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | One strict reader | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Every door stops on a broken setting | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | One loader, honest names, one home each | SF-01 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design APPROVED 2026-10-23; SF-01 and SF-02 committed 2026-10-23 ([SF-01](TECH-076_sf01_walkthrough.md), [SF-02](TECH-076_sf02_walkthrough.md) walkthroughs).
**Next step**: Trigger the dev skill for SF-03 (CB-1).
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume
from there using the appropriate skill.
