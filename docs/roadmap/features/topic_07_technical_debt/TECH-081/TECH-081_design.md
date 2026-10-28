# Design: The Layer Check Reports Clean While the Layers Are Broken

- **Feature ID**: TECH-081
- **Phase**: Topic 07 (Technical Debt)
- **Status**: APPROVED (by the user, 2026-10-27)
- **Kind**: `refactor` for the moves (SF-03..SF-07); `tooling` for the gate changes (SF-01, SF-02,
  SF-08, and SF-03 CB-1, which adds the purity test `[agreed 2026-10-28]`), which add guard tests
  a refactor may not (`scripts/tests.py`)
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_design.md
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 18 below.

## Feature Overview

TECH-081 makes `tach check` see every module and every import, then removes the imports that go the
wrong way. It solves a layer check that passes while four modules are not registered, type-only imports
are ignored, and the flow engine, the CLIs, the sandbox and the graph modules import each other in
loops; registered, they show 142 hidden errors (measured 2026-10-26). It touches `tach.toml`, the
module manifests (`context.yaml`), the known-violations ledger, and the code of `commons`, `sandbox`,
`core/flow`, `interfaces/cli`, `assurance` and `workspace/context`. It changes no command, option,
API field or behaviour. These are gaps in delivered work; `finished-stories-immutable` bars editing the
closed stories, so this ticket owns them.

All 18 findings are fixed here, in steps: first the check sees the truth, then each wrong import goes
`[agreed 2026-10-27]`.

## Findings this ticket owns

Re-measured 2026-10-26 (two read-only surveys; facts with `file:line` below and in the bindings).

| Finding | What is wrong (today) | Fixed by |
|---|---|---|
| Fix first #8 | `assurance.graph`, `commons`, `workflows.scenarios`, `workflows.evaluators` are not tach modules; registered, `tach check` reports 142 `UndeclaredDependency` errors from 34 edges | FR-1, FR-3 |
| CW-11 | `commons/prepare_plan.py:136,189,191,268` and `tooling_sources.py:64,71,109` read files; `commons` is unregistered | FR-9 |
| CW-14 | `core/config/context.yaml` names removed validation overrides; `workspace/context.yaml` uses another schema and names `standards`; `workspace/project/context.yaml` drifted; `workspace/memory/context.yaml` missing | FR-6, FR-7 |
| AG-16 | `assurance/standards/context.yaml:25` exposes `StandardsInferrer`, which does not exist; 4 real dependencies undeclared | FR-6, FR-7 |
| SB-18 | 16 sandbox manifests have no `name`/`purpose`; `sandbox/web/interfaces` says `orchestrator` but calls `httpx.post` (`tool.py:112`); `sandbox/execution` has no archetype | FR-6, FR-8 |
| WV-21 | manifests drift from `tach.toml` and nothing compares them | FR-4 |
| CW-24 | ledger rows `:11,:12,:16-18` stale; 8 real gaps missing | FR-5 |
| AG-22 | ledger `:14` lists `exclusions.py` (no I/O now); `topology.py:219,302` I/O missing | FR-5 |
| FL-7 | `core/flow/context.yaml:18-32` misses ~13 real dependencies; it forbids `workflows/drafting` while `draft.py:138,326` import it and `tach.toml` allows it | FR-7, FR-13 |
| AG-3 | `graph/core/builder/orchestrator.py:255` → `assurance.graph.loader`, and `loader.py:52` → `graph.topology.engine`: a loop | FR-17 |
| CW-15 | `workspace/project/interfaces/cli.py:294` imports `assurance.graph` lazily; `tach_sync.py:17` type-only | FR-1, FR-2, FR-3 |
| SB-16 | `sandbox/dispatcher.py:234` → `workflows.evaluators`; `python/scenario_converter.py:40` → `workflows.scenarios`; `security.py:22` → `core.flow` (type-only) | FR-10 |
| SB-17 | `core/flow` reaches `sandbox.language.core._detect` (`task_files.py:60`) and two factories past the atom | FR-14 |
| FL-6 | engine → handlers 3 module-level imports (`handover.py:9`, `step_execution.py:41`, `runner.py:48`); handlers → engine 19 | FR-11, FR-12 |
| EP-9 | 10 domain CLIs import `interfaces.cli._core`; the shell imports them; `llm/interfaces/command.py:17` imports `_core` | FR-15 |
| WV-13 | the Python scenario converter lives in `workflows/scenarios`, the other four in `sandbox/language/core/*` | FR-10 |
| WV-14 | `assurance/validation` is `pure-logic` but reads files (`pipeline_loader.py:80`, `rubrics/loader.py:85`) and loads code (`loader.py:105-113`) | FR-18 |
| CW-16 | `workspace/context` (`contract`) writes `context.yaml` (`inferrer.py:139`) | FR-19 |
| AG-15 | the six `graph/**` manifests use another schema (`allowed_imports`, no `archetype`); moved here from `TECH-080` `[agreed 2026-10-27]` | FR-6 |

## Path List (`ADR-005`)

| Path | Span | Proof |
|---|---|---|
| P-1 a developer runs `tach check` → every module is checked and every wrong import fails | `tach.toml` → all of `src` | the `tach` gate in `scripts/quality.py`, and the tests of FR-1..FR-5 |
| P-2 a developer edits a manifest or `tach.toml` alone → a test says they disagree | manifests ↔ `tach.toml` | unit test (FR-4) |
| P-3 a user runs any `sw` command or API call after a move → same result as before | CLI/API → every moved module | the full suite before every commit (NFR-1) |

## Research Findings

### Codebase Patterns

- `tach.toml` is written by hand (`exact = true`, 35 modules). `scripts/_quality_runners.py:44` only
  runs `tach check`. `tests/unit/test_architecture.py` checks that its paths exist, not that they match
  the manifests. `workspace/project/tach_sync.py` generates rules only for target projects (`sw scan`).
- 63 manifests vs 35 tach modules: a tach module (for example `specweaver.sandbox`) covers several
  manifests, so the agreement test (FR-4) maps each manifest path to the tach module that holds it.
- `commons` is meant as the L0 leaf every layer may use (its manifest; `core/flow/context.yaml`
  comment). 119 imports from 21 modules use it.
- A precedent guard exists: `tests/unit/graph/core/builder/test_declared_imports.py` checks a package's
  module-level imports against its manifest.
- The ledger is `docs/architecture/06_lessons_and_future/known_boundary_violations.md`.

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| tach | 0.34.1 (`.venv`) | `root_module = "forbid"`; `ignore_type_checking_imports = false`; `forbid_circular_dependencies = true`; `utility = true`; `depends_on = [{ path, deprecated = true }]` (reported, not failed) | tach docs `usage/configuration.md`, `usage/deprecate.md`, `usage/faq.md` (via Context7); `tach/extension.pyi:100-174` |

tach checks imports inside functions (62 of the 142 errors are lazy); only `TYPE_CHECKING` imports
are skipped by default.

### Blueprint References

None.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | `tach check` SHALL fail when any file under `src/specweaver` belongs to no registered module (`root_module = "forbid"`); today that is the 4 modules above plus `_version.py` and `telemetry_logger.py` (measured 2026-10-27) | tach gate | checks | no module hides from the check |
| FR-2 | `tach check` SHALL check imports under `TYPE_CHECKING` like any other (`ignore_type_checking_imports = false`) `[agreed 2026-10-27]` | tach gate | checks | type-only imports obey the layers |
| FR-3 | Every wrong-way dependency that exists when it is registered SHALL be declared in `tach.toml` as `deprecated = true` and listed in the ledger with the FR that removes it | `tach.toml`, ledger | declare | `tach check` passes but names every owed fix |
| FR-4 | A test SHALL fail when a module's `tach.toml` `depends_on` is not covered by its manifest's `consumes`, or a manifest `forbids` what `tach.toml` allows; `tach.toml` and the manifests stay hand-written `[agreed 2026-10-27]` | test | compares | the two copies cannot drift silently |
| FR-5 | The ledger SHALL hold only violations that exist: the stale rows go, the missing ones (topology I/O and the rows FR-3 adds) are listed | ledger | records | the ledger is true |
| FR-6 | Every manifest SHALL carry `name`, `purpose` and `archetype`, and every name in `exposes` SHALL be defined somewhere in that module's package (test) | manifests, test | declare | no phantom surface |
| FR-7 | The modules with code but no manifest SHALL get one: `sandbox`, `core/flow/engine`, `core/flow/handlers`, `workflows/scenarios`, `workflows/evaluators`, `workspace/memory`, `graph/lineage`; `core/config`, `workspace`, `workspace/project`, `assurance/standards`, `core/flow` manifests SHALL state what the code does | manifests | declare | the manifests describe today's code |
| FR-8 | A manifest whose archetype does not match its code SHALL be corrected, except `pure-logic` (FR-18): `sandbox/web/interfaces` → `adapter`; `sandbox/execution` gets one `[agreed 2026-10-27]` | manifests | label | labels say what modules do |
| FR-9 | `commons` SHALL depend on nothing and read no files; the file-reading parts of `prepare_plan.py` and `tooling_sources.py` move into `sandbox/execution` `[agreed 2026-10-27]`; `commons` is a registered `utility` module | commons | — | the shared leaf is pure |
| FR-10 | `sandbox` SHALL import nothing from `workflows` or `core.flow`: the Python scenario converter moves into `sandbox/language/core/python`, the scenario models into `commons`, the evaluator-schema loader into `sandbox`; `security.py` types its argument with a Protocol | sandbox | imports | the sandbox sits below the workflows |
| FR-11 | `core/flow/engine` SHALL import nothing from `core/flow/handlers`; the shared run state (`RunContext`, `log_step_failure`, `scenario_store`, `target_dal`, `engine/registered.py`) moves to `core/flow/run_state` `[agreed 2026-10-27]` | engine | imports | handlers use the engine, never the reverse |
| FR-12 | `PipelineRunner` SHALL take its step-handler registry from its caller (seam: every caller passes `StepHandlerRegistry()`) | callers of `PipelineRunner` | construct | the engine needs no handler import |
| FR-13 | `core/flow` SHALL import nothing from `workflows/drafting`; the draft handlers receive a drafter factory from the run's builder (seam: `interfaces/run_setup`) | draft handlers | draft | the manifest's `forbids` holds, and the 2026-07-24 switch is retired |
| FR-14 | `core/flow` SHALL reach `sandbox/language` only through public names (no `_detect`) | core/flow | imports | no internals crossed |
| FR-15 | No domain CLI SHALL import `interfaces/cli`: the shared helpers move to `interfaces/cli_kit`, the run doors to `interfaces/run_doors`; only the shell (`interfaces/cli`) imports the domain CLIs | domain CLIs | import | no CLI loop |
| FR-16 | `core/config/bootstrap` SHALL depend only on the flow table definitions (`core/flow/store` as its own module), not on all of `core/flow` | bootstrap | imports | no config ↔ flow loop |
| FR-17 | `graph` SHALL import nothing from `assurance/graph`; `graph/interfaces` passes the service name in; `TopologyContext` moves to `commons` | graph | imports | `assurance.graph` uses `graph`, never the reverse |
| FR-18 | `assurance/validation` SHALL read no files and load no code: the readers move to `assurance/validation/io` (archetype `adapter`), the parsers stay pure `[agreed 2026-10-27]` | validation | — | pure-logic is pure |
| FR-19 | `workspace/context` SHALL hold contracts only: the `context.yaml` writer (`inferrer.py`) moves to `workspace/analyzers` | workspace/context | — | the contract module writes nothing |
| FR-20 | `tach check` SHALL fail on any import loop (`forbid_circular_dependencies = true`), and no `deprecated` dependency is left | tach gate | checks | the fix cannot regrow |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1, FR-2, FR-20 | the check's settings | tach · `root_module`, `ignore_type_checking_imports`, `forbid_circular_dependencies` | tach docs `configuration.md` (Context7); `tach/extension.pyi:152,160` |
| FR-3 | allowed-but-flagged edges | tach · `{ path, deprecated = true }` | tach docs `deprecate.md` |
| FR-9 | who uses the file readers | `interfaces/cli/routers/sandbox_router.py:23` (`plan_for`); `core/flow/handlers/dual_pipeline.py:33`; `sandbox/execution/sandbox_image.py:21`, `container_executor.py:23` | read 2026-10-27 |
| FR-11, FR-12 | what the run state needs | `run_context.py:23-28` (commons, core.config; lazy llm, ast.parsers); `PipelineRunner(` built at `interfaces/cli/run_doors.py:100`, `interfaces/api/v1/pipelines.py:68,136`, `interfaces/api/v1/_llm.py:50`, `core/flow/interfaces/cli.py:343,471`, `engine/runner.py:136`, drafting `:184`, implementation `:193`, review `:94` CLIs | read 2026-10-27 |
| FR-13 | how drafting is called | `DraftSpecHandler._execute_drafting` (`draft.py:126-163`), `DraftFeatureHandler` (`:314-350`); built by `StepHandlerRegistry.__init__` (`registry.py:98-99`) | read 2026-10-27 |
| FR-14 | public language surface | tach `[[interfaces]]` already exposes `detect_language`, the two factories and `LanguageAtom`; `LanguageAtom.run` intents `detect_language`, `convert_scenario` (`sandbox/language/core/atom.py:31`) | read 2026-10-27 |
| FR-15 | what each CLI takes from the shell | `_core` symbols per CLI (`console`, `get_db`, `project_path_or_exit`, `run_repo_op`, ...); `run_doors.run_one_step`, `build_run_or_exit`; shell registers apps in `main.py:63-167` | read 2026-10-27 |
| FR-16 | the one config → flow edge | `core/config/bootstrap/db_bootstrap.py:15` imports `core.flow.store.Base` | read 2026-10-27 |
| FR-17 | graph → assurance.graph use | `orchestrator.py:255` only computes `service_name`; `build_target` called only from `graph/interfaces/cli.py:58` | read 2026-10-27 |
| FR-18 | loader callers | `pipeline_loader`: `interfaces/api/v1/validation.py:71,145`, `archetype_pipelines.py:182`, `core/config/interfaces/cli.py:209`, `assurance/validation/interfaces/cli.py:111,243,327`; `rubrics/loader`: `handlers/review.py:127` | read 2026-10-27 |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | No behaviour changes: every `sw` command, option, API field and output stays as it is **[proof: meta — the full suite before every commit]** | the full suite green at every commit |
| NFR-2 | `tach check` passes at every commit; after SF-01 a `deprecated` edge may only be removed, never added **[proof: arch — tach gate]** | `quality.py cb` green |
| NFR-3 | A move keeps one home per symbol: no re-export shim left at the old path **[proof: meta — each SF's diff deletes the old file]** | no old path imports the new one |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| tach | 0.34.1 | the five settings above | yes (docs + `extension.pyi`) | already a dev dependency |

## Architectural Decisions

Each move follows one rule: a file goes to the lowest layer that uses it, and every move is listed here
for approval `[agreed 2026-10-27]`.

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | `tach.toml` and the manifests stay two hand-written files; a test compares them (FR-4) `[agreed 2026-10-27]` | generating `tach.toml` with `tach_sync` would make a dev gate depend on a product feature | No |
| AD-2 | Wrong edges found at registration are `deprecated` (FR-3) and each SF removes its own | `tach check` stays green at every commit while it already names every owed fix | No |
| AD-3 | `commons` is a tach `utility` module (anyone may import it; it imports nothing) | it is the declared L0 leaf; 21 modules use it | No |
| AD-4 | `sandbox_router` moves to a new CLI module `sandbox/interfaces/cli.py`, registered by `main.py` like the other domain CLIs | keeps `interfaces/cli` off the sandbox; the alternative adds `interfaces.cli → sandbox` | **Yes — new module; approved by the user 2026-10-27** |
| AD-5 | Scenario models and `TopologyContext` move to `commons` | every user (sandbox, core.flow, llm, planning, drafting) may use `commons`; both are pydantic data | **Yes — moves; approved by the user 2026-10-27** |
| AD-6 | The evaluator-schema loader moves to `sandbox/evaluator_schemas.py`; the YAML data stays in `workflows/evaluators/frameworks` (read as a package resource, not an import) | its users are `sandbox/dispatcher` and `core/flow`; `core/flow` may use the sandbox | **Yes — move; approved by the user 2026-10-27** |
| AD-7 | New module `core/flow/run_state` (FR-11); `PipelineRunner` gets its registry from its caller (FR-12) | the registry imports every handler, so the engine cannot build it | **Yes — new module, signature change (internal); approved by the user 2026-10-27** |
| AD-8 | The draft handlers get a drafter factory from `interfaces/run_setup` (FR-13) | removes `core.flow → workflows.drafting`, approved as a deferred switch 2026-07-24 (INT-US-21 AD-3) | **Yes — retires that switch; approved by the user 2026-10-27** |
| AD-9 | New modules `interfaces/cli_kit` and `interfaces/run_doors` (FR-15); `hitl_provider` stays in the shell and reaches drafting by injection, as `set_context_provider_factory` already does | breaks the 10 CLI loops without a plugin system | **Yes — new modules; approved by the user 2026-10-27** |
| AD-10 | `core/flow/store.py` becomes its own module (FR-16) | bootstrap needs only the table classes | **Yes — new module; approved by the user 2026-10-27** |
| AD-11 | New module `assurance/validation/io` for the readers (FR-18); `assurance/validation/loader.py` (custom-rule loader, no caller in `src`, tests only) is **deleted** | pure-logic stays pure; dead code is not moved | **Yes — new module, delete; approved by the user 2026-10-27** |
| AD-12 | `ContextProvider` and the analyzer protocols stay in `workspace/context` (they are contracts); only `inferrer.py` moves to `workspace/analyzers` (FR-19). Drafting, planning and standards declare their type-only use of `workspace/context` | a contract module is the right home for contracts | **Yes — move; approved by the user 2026-10-27** |
| AD-13 | `sandbox/language` makes `detect_language` public (`_detect` → `detect`); `core/flow` keeps the two public factories | cheaper than new atom intents; the factories are already public | **Yes — rename (internal); approved by the user 2026-10-27** |
| AD-14 | `sandbox/security.py` types its context argument with a Protocol defined in `sandbox` | the sandbox may not import `core/flow` | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| 8 sub-features, 20 FRs, ~60 files moved or edited, ~200 test imports updated | 6–8 sessions | medium: wide moves; NFR-1 (full suite) and NFR-2 (tach) guard each commit |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| Every later ticket (TECH-079..091) | `tach check` tells the truth while they move code | high |
| Developers | a module's manifest and `tach.toml` say the same thing | medium |
| The CLI and flow engine | no import loops; lazy imports no longer hide them | medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| A move breaks a lazy import that no test reaches | medium | high | `root_module = "forbid"` + tach see lazy imports; full suite; one SF per area |
| Mutation corpora point at moved code | high | low | re-point in the same commit (`.tmp/stale.py`) |
| A test patches an old import path | high | low | the suite fails on it; update in the same commit |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| TECH-079..091 | each moves code across modules | a truthful gate during their moves | none extra |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `docs/architecture/03_system_topology/hard_dependency_rules.md`, `module_dependency_graph.md` | replace the stale tables with a pointer to `tach.toml` and the manifests, and the three tach settings | ⬜ SF-08 |
| `docs/dev_guides/layer_isolation_and_di.md` | the run-state module, registry and drafter injection | ⬜ SF-04 |
| `docs/dev_guides/domain_driven_cli_creation.md` | `cli_kit` and `run_doors` instead of `_core` | ⬜ SF-05 |

## Works For Real

`python -m tach check` prints "All modules validated" with no `deprecated` line, `tach.toml` holds
`root_module = "forbid"`, `ignore_type_checking_imports = false` and
`forbid_circular_dependencies = true`, and `sw --help` lists every command it lists today.

## Non-Goals

- `assurance/graph/hasher.py` and `assurance/validation/project_root.py` file I/O: ledger rows owned by
  earlier decisions (Feature 3.48; `TECH-078` decision 2); they stay rows.
- `assurance/graph/topology.py` file I/O (`:219,302`): listed in the ledger (FR-5), not moved.
- The root `context.yaml` stub (`purpose: TODO`): a separate `T-ARCH` decision, recorded in the ledger.
- Findings owned by `TECH-075`..`TECH-091` and `TECH-070`.

## Sub-Feature Breakdown

### SF-01: The check sees every module
- **Scope**: register every module, count type-only imports, declare today's wrong edges as `deprecated`, make the ledger true.
- **FRs**: [FR-1, FR-2, FR-3, FR-5]
- **Inputs**: `tach.toml`; the ledger.
- **Outputs**: a `tach check` that sees all of `src`; a deprecated-edge list each later SF shrinks.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf01_implementation_plan.md

### SF-02: The manifests tell the truth
- **Scope**: manifest fields, phantom exposes, missing manifests, wrong labels, and the agreement test.
- **FRs**: [FR-4, FR-6, FR-7, FR-8]
- **Inputs**: SF-01's `tach.toml`.
- **Outputs**: manifests that match `tach.toml`, guarded by a test.
- **Depends on**: SF-01 (the `core/flow` ↔ `workflows/drafting` pair stays owed to FR-13)
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf02_implementation_plan.md

### SF-03: The sandbox sits below the workflows
- **Scope**: `commons` pure; the sandbox stops importing `workflows` and `core/flow`. `commons` is labelled `mixed`
  until its file reading leaves; then `pure-logic`.
- **FRs**: [FR-9, FR-10]
- **Inputs**: SF-01's deprecated edges.
- **Outputs**: those edges removed.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf03_implementation_plan.md

### SF-04: The flow engine stands alone
- **Scope**: engine/handlers split, registry and drafter injection, public language names, bootstrap.
- **FRs**: [FR-11, FR-12, FR-13, FR-14, FR-16]
- **Inputs**: SF-01's deprecated edges.
- **Outputs**: those edges removed.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf04_implementation_plan.md

### SF-05: The CLIs stop importing the shell
- **Scope**: `cli_kit` and `run_doors`.
- **FRs**: [FR-15]
- **Inputs**: SF-04 (`run_doors` builds runners with the injected registry).
- **Outputs**: the 10 CLI loops removed.
- **Depends on**: SF-04
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf05_implementation_plan.md

### SF-06: Graph and assurance in one direction
- **Scope**: the graph ↔ assurance.graph loop; `TopologyContext` to `commons`.
- **FRs**: [FR-17]
- **Inputs**: SF-01.
- **Outputs**: that loop removed.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf06_implementation_plan.md

### SF-07: Pure-logic and contract modules do no I/O
- **Scope**: validation readers to `assurance/validation/io`; the context writer to `workspace/analyzers`.
- **FRs**: [FR-18, FR-19]
- **Inputs**: SF-01.
- **Outputs**: two labels made true.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf07_implementation_plan.md

### SF-08: The guard
- **Scope**: forbid loops; no deprecated edge left; architecture docs point at the enforced rules.
- **FRs**: [FR-20]
- **Inputs**: SF-02..SF-07 committed.
- **Outputs**: a check that keeps the fix.
- **Depends on**: SF-02, SF-03, SF-05, SF-06, SF-07
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_sf08_implementation_plan.md

## Execution Order

1. SF-01
2. SF-02, SF-03, SF-04, SF-06, SF-07 (each depends only on SF-01; run one at a time, they edit `tach.toml`)
3. SF-05 (after SF-04)
4. SF-08 (last)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | The check sees every module | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | The manifests tell the truth | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | The sandbox sits below the workflows | SF-01 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-04 | The flow engine stands alone | SF-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-05 | The CLIs stop importing the shell | SF-04 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-06 | Graph and assurance in one direction | SF-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-07 | Pure-logic and contract modules do no I/O | SF-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-08 | The guard | SF-02, SF-03, SF-05, SF-06, SF-07 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

### Red/Blue (Phase 6), 2 cycles
- R1 (HIGH) `root_module = "forbid"` fails on files in no module, not only the four named. Blue:
  measured — `_version.py`, `telemetry_logger.py`; SF-01 registers them (FR-1).
- R2 (HIGH) counting type-only imports (FR-2) adds errors the 142 do not include. Blue: SF-01
  measures them and declares each as `deprecated` (FR-3), so no number is assumed.
- R3 (MEDIUM) 63 manifests vs 35 tach modules: FR-4 could flag a `forbids` on a sub-path of a
  module `tach.toml` allows (`sandbox/*/interfaces` inside `specweaver.sandbox`). Blue: a forbid
  conflicts only when it names the whole tach module; sub-path forbids are checked by
  `test_declared_imports`-style tests, not by tach.
- R4 (MEDIUM) "exists" in FR-6 was vague. Blue: defined as "defined somewhere in the package".
- R5 (MEDIUM) NFR-3 cited tach, which cannot see a re-export shim. Blue: proof is the diff (meta).
- R6 (MEDIUM) SF-04 and SF-05 both edit `PipelineRunner` callers in the CLIs. Blue: SF-05 depends on
  SF-04; SF-04 edits only the call, SF-05 moves the file.
- R7 (LOW) deleting `assurance/validation/loader.py` is irreversible in spirit. Blue: AD-11 flags it
  for the user; git keeps it.
- Cycle 2: challenged R3 (a whole-module forbid that tach allows is the FL-7 drafting case — FR-13
  removes it, so FR-4 goes green only after SF-04: SF-02 marks that one pair as owed by FR-13). No
  new finding.

**Current status**: Design APPROVED 2026-10-27.
**Next step**: dev SF-03 CB-1 (plan approved 2026-10-28).
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume
from there using the appropriate skill.
