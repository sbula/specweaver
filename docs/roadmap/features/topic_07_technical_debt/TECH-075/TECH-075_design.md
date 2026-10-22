# Design: Paths From Outside Can Leave the Project

- **Feature ID**: TECH-075
- **Phase**: Topic 07 (Technical Debt)
- **Status**: APPROVED (by the user, 2026-10-22)
- **Kind**: `bugfix`
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-075/TECH-075_design.md
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`.

## Feature Overview

TECH-075 puts one boundary check, the existing `WorkspaceBoundary` (`sandbox/security.py`), in front
of every path that comes from outside SpecWeaver: REST API request fields, agent tool arguments and
file mentions in a spec. It solves paths that leave the project today: an API client can point a
pipeline run at any file, and an agent can make the protocol tool and five of six QA intents read or
run any path. It also fixes four checks that judge a path by its text instead of where it lands. It
does not change the filesystem tools' grants (`E-SENS-01`, `E-SENS-03`), which already work. These
are gaps in delivered work; `finished-stories-immutable` bars editing the closed stories, so this
ticket owns them.

## Findings this ticket owns

Re-measured 2026-10-22 against the code; every one still holds. Each maps to the requirement that
fixes it, so none can drop out.

| Finding | What is wrong | Fixed by |
|---|---|---|
| Fix first #2 | `POST /pipelines/{name}/run` joins `project_root / body.spec` unchecked (`interfaces/api/v1/pipelines.py:204`) | FR-2 |
| EP-6 (path half) | same spec field, no guard; its other half moved to `TECH-077` `[agreed 2026-10-22]` | FR-2 |
| Fix first #3 | the protocol tool reads any path (`sandbox/protocol/core/atom.py:20-25`) | FR-4 |
| SB-10 | the path guard exists five ways; protocol and most QA intents have none | FR-1, FR-4, FR-5, AD-5 |
| SB-20 | QA target handling and guards differ per intent (`sandbox/qa_runner/core/atom.py`) | FR-5 |
| FL-18 | mention resolution and containment are private copies with different fallbacks | FR-6, FR-8 |
| Real defect 6 | `POST /projects` stores the path unresolved (`interfaces/api/v1/projects.py:54`) | FR-7 |
| Found in research | `PUT /projects/{name}` stores the new path unresolved (`interfaces/api/v1/projects.py:126`) `[agreed 2026-10-22]` | FR-7 |
| Found in research | `resolve_file_in_project` checks the text only, so an escaping link passes (`interfaces/api/v1/paths.py:52-74`) | FR-3 |
| Found in research | `relative_to_root` hands a path outside the root on unchanged (`core/flow/handlers/archetype_pipelines.py:190`) `[agreed 2026-10-22]` | FR-8 |
| Found in review | the pipeline `name` from the URL reaches `load_pipeline(Path(name))`, which first tries it as a file in the server's working folder (`core/flow/engine/parser.py:80-99`) | FR-10 |
| Found in SF-02 research | `POST /check` field `pipeline` reaches `load_pipeline_yaml(name, project_dir=…)`, so `../../x` loads a YAML file outside the project (probed; `assurance/validation/pipeline_loader.py:69-82`) `[agreed 2026-10-22]` | FR-10 |
| Found in SF-02 research | `sw update <name> path <value>` stores the path unresolved (`workspace/project/interfaces/cli.py:209`) `[agreed 2026-10-22]` | FR-7 |
| Found in SF-02 research | `PUT /projects/{name}` stores a path that does not exist; `POST` refuses one (`interfaces/api/v1/projects.py:105-131`) `[agreed 2026-10-22]` | FR-7 |
| Found in research | `export_graph_to_disk` and `directory_walk` compare path strings, so `/a/bc` counts as inside `/a/b` (`graph/core/builder/orchestrator.py:214-224`, `workspace/project/directory_walk.py:46`) `[agreed 2026-10-22]` | FR-9 |

## Path List (`ADR-005`)

| Path | Span | Proof |
|---|---|---|
| P-1 API client → `POST /pipelines/{name}/run` `spec` → run refused or started | API → `core/flow` → `sandbox` | e2e (FR-2) |
| P-1b API client → `POST /pipelines/{name}/run` `name`, `POST /check` `pipeline` → pipeline loaded | API → `core/flow`, `assurance/validation` | integration (FR-10) |
| P-2 API client → implement / review / validation file field → `resolve_file_in_project` | API → `core/flow` → `sandbox` | integration (FR-3) |
| P-3 agent → protocol tool → protocol atom | inside `sandbox` | integration (FR-4) |
| P-4 agent → QA tool, any intent → QA atom | inside `sandbox` | integration (FR-5) |
| P-5 spec mention → review handler → prompt | `core/flow` → `sandbox` | integration (FR-6) |
| P-6 API client → `POST /projects`, `PUT /projects/{name}`; `sw update <name> path` → stored path | API, CLI → `workspace` | integration (FR-7) |
| P-7 `sw check <file>` → archetype pipeline → code structure atom | `core/flow` → `sandbox` | integration (FR-8) |
| P-8 graph export, directory walk | `graph`, `workspace` alone | unit (FR-9) |

## Research Findings

### Codebase Patterns

- `WorkspaceBoundary` resolves the requested path (following links), then accepts it only inside a
  root or a read-only API path; `resolve_relative` joins to the primary root first. Probed
  2026-10-22: it refuses `../`, an escaping link and an absolute path. Two traps: `validate_path`
  resolves a *relative* path against the process folder, not the project; a null byte raises
  `ValueError`, not `WorkspaceBoundaryError`.
- `FileExecutor._validate_path` (`sandbox/filesystem/core/executor.py:389-445`) resolves, compares,
  and refuses every link component (`E-SENS-01` FR-2): stricter than `WorkspaceBoundary`.
  `SubprocessExecutor` resolves `cwd_override` before comparing (`sandbox/execution/executor.py:186`).
- Layer rules (`tach.toml`, `context.yaml`): `core/flow` and every `sandbox` sub-package may import
  `sandbox.security`; `interfaces/api` may not (it `forbids: sandbox/*`) but may import `core.flow`;
  `mention_scanner` is pure logic and may not do I/O.
- `docs/architecture/06_lessons_and_future/anti_patterns.md:10` names `WorkspaceBoundary` as a
  "parallel security class". This design makes it the one check for outside paths and corrects
  that row.
- Precedent: `C-EXEC-02` AD-3 reuses `WorkspaceBoundary` for script containment and NFR-1 "compare
  resolved paths, never string prefixes".

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Python `pathlib` | 3.11+ | `Path.resolve()`, `Path.relative_to()`; `is_relative_to` is lexical, so resolve first | https://docs.python.org/3/library/pathlib.html |
| CWE-22 / OWASP | — | canonicalize, then validate; generic error to the client, details in the server log | https://cwe.mitre.org/data/definitions/22.html, https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html |

### Blueprint References

The MCP reference filesystem server and LangChain's `FileManagementToolkit` use the same
resolve-then-check pattern with one shared function for every caller
(https://github.com/modelcontextprotocol/servers, `src/filesystem/path-validation.ts`).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | `WorkspaceBoundary` SHALL refuse, with `WorkspaceBoundaryError`, an empty path and a path containing a null byte, SHALL judge a relative path against its primary root, never the process folder, and a boundary with no root (`ReadOnlyWorkspaceBoundary`) SHALL refuse a relative path instead of failing with `IndexError` | `WorkspaceBoundary` | validates a requested path | the four traps refuse like every other way out |
| FR-2 | `POST /pipelines/{name}/run` SHALL refuse a `spec` that resolves outside the project (`..`, absolute, escaping link) with `PATH_TRAVERSAL` 400, before the existence check and before any run is created, so the answer never tells whether an outside file exists | API | starts a run | no run, no file read outside the project |
| FR-3 | `resolve_file_in_project` SHALL keep its text check (absolute or `..` refused) and SHALL also refuse a path whose resolved location lies outside the project, so an escaping link gets `PATH_TRAVERSAL` 400 on every API route that uses it | API | resolves a file field | implement, review and validation refuse the same paths |
| FR-4 | The protocol atom SHALL read only files inside its boundary; the protocol tool SHALL be built with the run's boundary | protocol tool | extracts a schema | a path outside returns a failed result and is never opened |
| FR-5 | Every QA runner intent (`run_tests`, `run_linter`, `run_complexity`, `run_compiler`, `run_debugger`, `run_architecture`) SHALL refuse a `target` or `targets` entry outside its root, and the debugger's `entrypoint` where it is a file (Python, TypeScript) `[agreed 2026-10-22]`, before any tool starts; a scenario run also accepts `/scenarios/…` | QA atom | runs a tool | one check for all six intents |
| FR-6 | Mention resolution SHALL check candidates with `WorkspaceBoundary` over the project root only, replacing the private `_is_within` | review handler | resolves mentions | a mention outside the project or behind an escaping link is dropped, as today |
| FR-7 | `POST /projects`, `PUT /projects/{name}` and `sw update <name> path` SHALL store, and answer with, the resolved absolute path, and SHALL refuse a path that is not an existing folder `[agreed 2026-10-22]`; rows stored relative before this fix are not rewritten `[agreed 2026-10-22]` | API, CLI | registers or moves a project | a relative path no longer depends on the server's working folder |
| FR-8 | `relative_to_root` SHALL never return a path outside its root; its callers SHALL skip that file with a WARNING | archetype pipelines, QA targets | hand a path to a sandboxed atom | no outside path reaches an atom |
| FR-9 | `export_graph_to_disk` and the directory walk SHALL compare resolved paths by component, not by string prefix | graph builder, directory walk | test containment | a sibling folder whose name starts with the root's name is outside |
| FR-10 | `POST /pipelines/{name}/run` SHALL accept only a bare pipeline name and SHALL never read a file relative to the server's working folder; it loads the project's own `.specweaver/pipelines/<name>.yaml` (inside the project) or else the bundled pipeline `[agreed 2026-10-22]`. `POST /check` SHALL accept only a bare `pipeline` name `[agreed 2026-10-22]`. A refused name answers 404 `PIPELINE_NOT_FOUND` `[agreed 2026-10-22]`; `extends:` stays out of scope `[agreed 2026-10-22]` | API | loads the named pipeline | a YAML file or folder beside the server, or outside the project, cannot be loaded through the API |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-2, FR-3 | the project's boundary for an API request | `core.flow` helper (new) over `WorkspaceBoundary.resolve_relative(relative: str) -> Path` | read `sandbox/security.py:126`; probed refusals 2026-10-22; `tach.toml:66` lets `interfaces.api` import `core.flow` |
| FR-2 | project root for a request | `resolve_project_root(project_name: str, db: Database) -> Path` | read `interfaces/api/v1/paths.py:33` |
| FR-4 | the run's boundary for the protocol tool | `sandbox/registry.py:100-105` builds `ProtocolTool()`; the registry closures receive `cwd` | read `sandbox/registry.py`, `docs/dev_guides/adding_tools_and_atoms.md:60-62` |
| FR-5 | the QA atom's root and scenario mount | `QARunnerAtom(cwd: Path, …, scenarios_root: Path | None)`, `_in_scenarios_mount` | read `sandbox/qa_runner/core/atom.py:106-123, 214-217` |
| FR-6 | project root for a run | `RunContext.project_path`; `_resolve_mentions(candidates, …)` | read `core/flow/handlers/review.py:375-430` |
| FR-7 | project path storage | `WorkspaceRepository` add / update path | read `interfaces/api/v1/projects.py:45-62, 126` |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Fail closed: when no boundary can be built (project root unknown), the path is refused `[agreed 2026-10-22]` | refusal, never a pass |
| NFR-2 | An API refusal answers `PATH_TRAVERSAL` 400 and echoes only the client's own input, never a resolved absolute path; the resolved path goes to the server log at WARNING | no absolute path in any 400 body |
| NFR-3 | Links are resolved before the check: a link inside the project that points inside is allowed, one that points outside is refused `[agreed 2026-10-22]` | resolve, then compare |
| NFR-4 | Inside = the project root, the read-only API paths, and `/scenarios/…` in a scenario run `[agreed 2026-10-22]`; mentions: the project root only, as `E-SENS-03` FR-5 promises `[agreed 2026-10-22]` | everything allowed today stays allowed |
| NFR-5 | No new layer edge: `interfaces/api` reaches the guard only through `core.flow` `[agreed 2026-10-22]` **[proof: arch — tach/lint gate, not pytest]** | `tach check` clean, no `tach.toml` change |

## External Dependencies

None beyond the standard library.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | `WorkspaceBoundary` is the one check for paths from outside; no new class | it already resolves before comparing; the anti-pattern row is corrected, not a second guard added | No |
| AD-2 | The API reaches the guard through a small `core.flow` helper | `interfaces/api` forbids `sandbox/*`; `core.flow` may import it and the API may import `core.flow` | No — chosen by the user 2026-10-22 over moving the guard |
| AD-3 | The protocol atom takes a root; the registry builds the protocol tool with the run's root | an atom with no root cannot check anything | No |
| AD-4 | One per-target check in the QA atom serves all six intents | replaces `_traversal_error`, which only `run_tests` called | No |
| AD-5 | `FileExecutor._validate_path` and `SubprocessExecutor`'s `cwd` check stay as they are | both already resolve before comparing; `FileExecutor` also refuses every link (`E-SENS-01` FR-2), stricter than `WorkspaceBoundary`; merging would change signed-off behaviour | No — kept `[agreed 2026-10-22]`; SB-10 counts as fixed for the broken copies only |
| AD-6 | No race hardening between check and open (`O_NOFOLLOW`, `dir_fd`) | a race needs someone already writing inside the project; a planted link is the real risk, and resolve-then-check catches it | No — `[agreed 2026-10-22]` |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| 3 sub-features, ~9 FRs, mostly call-site changes plus tests | 2–3 sessions | low: the guard exists and is proven |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| Every API user | a run or file field can no longer reach outside the project | high (security) |
| Every agent run | protocol and QA tools stay inside the project, in host mode too | high (security) |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| A legitimate path is refused (a monorepo link that points outside) | low | a run refuses a file | NFR-3 is the user's decision; the refusal names the input |
| `sw check` on a file outside `--project` loses its structure hint | low | weaker check | FR-8 logs a WARNING |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| `review.py` `_is_within`, QA `_traversal_error` | private copies of the guard | one check | small, inside FR-5/FR-6 |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `agent_tools_reference.md`, `security_guardrails.md`, `anti_patterns.md` | every path from outside goes through `WorkspaceBoundary`; correct the anti-pattern row | ⬜ To be written during Pre-commit |

## Works For Real

`sw serve`, then `curl -X POST http://127.0.0.1:<port>/api/v1/pipelines/<name>/run -H "Authorization:
Bearer <token>" -d '{"project":"<p>","spec":"../../etc/hosts"}'` answers 400 `PATH_TRAVERSAL` and starts
no run. The same journey runs as an e2e test in the suite.

## Sub-Feature Breakdown

### SF-01: The boundary refuses every way out
- **Scope**: harden `WorkspaceBoundary` and put it in front of the protocol and QA tools.
- **FRs**: [FR-1, FR-4, FR-5]
- **Inputs**: paths from agent tool arguments; the run's root from the registry.
- **Outputs**: a hardened `WorkspaceBoundary` that SF-02 and SF-03 call.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-075/TECH-075_sf01_implementation_plan.md

### SF-02: API paths stay in the project
- **Scope**: every API path field goes through one `core.flow` helper over the boundary.
- **FRs**: [FR-2, FR-3, FR-7, FR-10]
- **Inputs**: API request bodies; the project root from the database.
- **Outputs**: `PATH_TRAVERSAL` 400 refusals; resolved stored project paths.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-075/TECH-075_sf02_implementation_plan.md

### SF-03: The engine judges paths by where they land
- **Scope**: mentions, `relative_to_root` and the two string-prefix checks use resolved paths.
- **FRs**: [FR-6, FR-8, FR-9]
- **Inputs**: mention candidates, engine-chosen file paths, graph export and walk paths.
- **Outputs**: no outside path reaches a prompt or an atom; correct containment by component.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-075/TECH-075_sf03_implementation_plan.md

## Execution Order

1. SF-01 (no deps — start immediately)
2. SF-02 and SF-03, in either order (both depend only on SF-01)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | The boundary refuses every way out | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | API paths stay in the project | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | The engine judges paths by where they land | SF-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design APPROVED 2026-10-22; SF-01 committed 2026-10-22; SF-02 committed 2026-10-22
([SF-01 walkthrough](TECH-075_sf01_walkthrough.md), [SF-02 walkthrough](TECH-075_sf02_walkthrough.md)).
**Next step**: Trigger the implementation-plan skill for SF-03.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume
from there using the appropriate skill.
