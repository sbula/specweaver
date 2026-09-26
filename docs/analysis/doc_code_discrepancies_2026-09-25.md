# Doc/code discrepancies — census from the 2026-09-25 docs rewrite

Found while 395 docs were rewritten to the short format (roadmap topics 01–06 and 08, dev guides,
user guides, architecture). Each agent checked doc claims against `src/` and recorded what disagreed.
The rewrite changed no code and no FR text; it only added dated "Since moved" / "As built" notes.

Owner: [`TECH-071`](../roadmap/features/topic_07_technical_debt/TECH-071/TECH-071_design.md).

Each row is **unresolved** until someone decides which side is wrong. "Likely" is the finding agent's
reading, not a decision.

## A — Built, but the path never runs in production

| # | Where | Finding | Likely |
|---|---|---|---|
| A-01 | A-SENS-01 SF-04, C-FLOW-06, pipeline guide §9 | `GraphContext.stale_nodes` is read but never written, so the incremental test bypass never activates. C-FLOW-06 is ✅ | code |
| A-02 | D-VAL-02 FR-3 | Custom rule directories: `load_rules_from_directory` / `load_rules_from_paths` have no production caller; `sw config add-rule-path` does not exist | code or descope |
| A-03 | E-SENS-02 | `workspace_roots` is never written in production; the component-level boundary is not wired | code |
| A-04 | `cqrs_and_database.md` | The CQRS write queue is never used (no `enqueue` caller); reads are capped at 500, doc says unlimited | doc or code |
| A-05 | `cli_architecture.md` | CLI "rescue core" not built: only `ImportError` is caught, so a plugin with a `SyntaxError` crashes the CLI; no always-mounted `FileSystemTool` | code or descope |
| A-06 | `mcp_architecture_design.md` | MCP vault injection `${VAULT:DB_URL}` not found in the code | doc or code |
| A-07 | D-UI-01 | `/config` endpoints, `POST /projects/{name}/scan`, `POST /constitution/check` never built; no SIGTERM handling (decision 23) | descope or code |
| A-08 | `spec_review_pipeline.md` | Marked ACTIVE; nothing in `src/` runs its stages, the NOPE loop or `.review/`; cites missing `external_strategy_review.md` | doc |
| A-09 | pipeline guide §7 | Per-step strip-merge only logs a warning on failure (C-EXEC-06 FR-4 forbids this for the per-run path) | code |
| A-10 | C-FLOW-03 SF-02 | Marked DONE; `RunContext.env_vars` and `SW_PORT_OFFSET` do not exist (FR-3/FR-4 descoped to `TECH-062`) | doc |
| A-11 | INT-US-03 follow-ups | `api/v1/implement.py` still has `# type: ignore[call-arg]`; `new_feature.yaml` has no `lint_fix` step | code |
| A-12 | `topology_evolution.md` | Only the NetworkX engine exists; centrality, God Nodes, Leiden, Rocket Mode, inferred edges not built | doc |
| A-13 | `context_yaml_spec.md` | `context_yaml_lint`, `sw context validate`, `BoundaryArchitectInterface`, `context.lock` do not exist | doc or code |
| A-14 | `database_migrations.md` | Describes per-domain migration branches; code has one linear alembic timeline (3 revisions), models in `store.py` | doc |

## B — Requirement text disagrees with the code

| # | Where | Finding | Likely |
|---|---|---|---|
| B-01 | B-INTL-09 FR-8 | Breaker fires at `attempt_count > 3`; code (`resilience.py`) uses `>= 3` | decide |
| B-02 | B-VAL-02 FR-1/2/6/8 | Command names wrong (`sw hooks install`, `sw drift check-rot`); FR-6 names `Spec.md`; FR-8 says exit `1`, code exits `42`; the hook lacks the python-binary check the plan requires | doc + code |
| B-03 | C-EXEC-02 FR-2/12/13, NFR-4 | FR-2/12/NFR-4 describe load-time checks; SF-02 Q1 chose runtime-only (load-time → `TECH-011`). FR-13 says `StepStatus.ERROR`; code returns `FAILED` | doc |
| B-04 | D-INTL-06 FR-1..9, NFR-2/5 | Wording predates the code: `MemoryQueryService`, JSON in `<agent_memory trust="low">`, `RenderProfile`, runner calls `save_handover_context()`, `RunContext.task_id` added. As-built table sits beside the FRs | doc |
| B-05 | C-VAL-04 FR-2/4 | Say `@traces(req_id)` decorators; AD-3, NFR-2 and code use `# @trace(FR-x)` comments. Code reads all `specs/**/*.md`, not `spec_text` | doc |
| B-06 | E-UI-01 FR table | Old commands (`sw init --project`, `sw check spec`, `sw review spec`) | doc |
| B-07 | C-INTL-02 FR-2, NFR-2 | Docker only; code also allows podman (`TECH-063`) | doc |
| B-08 | D-VAL-04 AD-1, FR-2, FR-4 | Defaults from `context.db`; code has a literal dict in `core/flow/handlers/standards.py`. FR-4 names a TopologyGraph actor no SF implements | doc |
| B-09 | INT-US-02 FR-7 | Says "default bound is 3"; the gate has an explicit `max_retries: 3` | doc |
| B-10 | Several docs, `src/specweaver/context.yaml` | "10-test battery"; code runs 12 spec rules (S01–S12) | doc |
| B-11 | D-EXEC-01 FR-3, test T3 | Reason that `USER` after `ENTRYPOINT` "changes nothing" — the last `USER` wins, so T3 may assert a line order that does not matter | test + doc |
| B-12 | INT-US-04 AD-1, D-9, RB-1/D-12 | AD-1 extends `FlowRepository`, data lives in `StateStore`; D-9 says the pipeline guide records the grain (now added); RB-1 says 12 exposes, D-12 says 17 | doc |
| B-13 | E-EXEC-01 AD-7, NFR-6 | AD-7 `archetype: executor`, `consumes: [sandbox/security]`; code `adapter`, `commons.qa`. NFR-6 caps `executor.py` at 300 lines; it is 338 | decide |
| B-14 | INT-US-03 AD-1 | "Warn and continue" is overridden by AD-5 (refuse) but not marked superseded | doc |
| B-15 | D-FLOW-03 SF-02 | Test file named two ways: `test_config_routing_commands.py` vs `test_config_routing.py` | doc |

## C — Proof missing

| # | Where | Finding |
|---|---|---|
| C-01 | D-INTL-06 | FR-1, FR-2, FR-3, FR-7 have no `Proves:` citation; RT-2 (`_generate_common()`) never built |
| C-02 | B-INTL-09 | `check_fr_coverage.py B-INTL-09` BLOCKED on FR-1, FR-6 |
| C-03 | C-VAL-03 | NFR-1..3 are bullets with no test; as `\| NFR-n \|` rows `nfr_sweep` flags 3 uncited NFRs |
| C-04 | B-VAL-01 SF-02 | `tests/integration/cli/test_cli_drift.py` "to be created" does not exist |
| C-05 | INT-US-16 | Plan and commits disagree on which CB kills which mutant; CB-2 cites M-4, never defined; corpus holds M-1, M-2 |

## D — Status and tracker drift (work on `main`, doc says not done)

| # | Where | Finding |
|---|---|---|
| D-01 | Progress Trackers showing ⬜ for committed work | A-VAL-01 SF-04, B-VAL-02 SF-02, C-INTL-02 SF-03/04, C-FLOW-02, C-FLOW-05, C-FLOW-06 SF-02, B-INTL-05 SF-02, D-SENS-02 SF-02, D-EXEC-02 SF-02, C-INTL-01 SF-01/02, D-SENS-03 SF-05, D-VAL-03 SF-04 |
| D-02 | Plans still `DRAFT` though delivered | B-SENS-03 SF-02..06, D-VAL-04 SF-01, B-FLOW-01 SF-B2 (also missing from its tracker), B-INTL-09 SF-04, A-SENS-01 SF-02, C-INTL-05 SF-02, D-INTL-06 SF-02, B-SENS-02 SF-03, C-INTL-02 SF-04 |
| D-03 | Status "Proposal — awaiting approval" though ✅ and built | C-VAL-01, C-VAL-02 |
| D-04 | FR marked pending though done | E-FLOW-03 FR-6 (extras declared in `pyproject.toml`); C-VAL-03 SF-04 "[ ] Pending" |
| D-05 | Closed tickets listed as open | INT-US-21 "deliberately left open": `TECH-014/015/018/020/021/033` are all 🟢 |
| D-06 | Guides owed, never written | B-SENS-03 Guide-1 (visibility vocabulary); D-VAL-04 "Adding Built-in Standards" |

## E — Two cells changed by the rewrite, to confirm

| # | Where | Change |
|---|---|---|
| E-01 | D-FLOW-03 SF-02 | Tracker "Committed" ⬜ → ✅, citing `27b03522` (routing CLI exists) |
| E-02 | INT-US-10 CB-2 | open → done; `check_fr_coverage.py B-SENS-02` shows 5 of 5 cited |

## F — Registry and ownership inconsistencies

| # | Where | Finding |
|---|---|---|
| F-01 | B-SENS-02 | FR ownership differs between design and plans; no FR-4/FR-5; RT-2 assigned to nonexistent SF-04 |
| F-02 | C-EXEC-03 | FR ownership differs between design and plans; FR-11/FR-12 self-referential from an old find-and-replace ("moves `docs/roadmap/` into `docs/roadmap/`") |
| F-03 | C-VAL-03 | SF-03 owns FR-5 (FFI linter) but is the override cleanup; SF-05 owns none — looks swapped |
| F-04 | D-VAL-03 | FR-8 deleted but SF-01..03 still list it |
| F-05 | B-INTL-02 | FR-4 owned by no SF (delivered by SF-01's `load_evaluator_schemas`) |
| F-06 | D-FLOW-04 SF-03 plan | Six orphan bullets whose file headings were lost in an earlier edit |
| F-07 | B-INTL-09 | `CIRCUIT_BREAKER_DEFECT_TITLE` defined twice (`repository/core.py`, `repository/resilience.py`); SF-01 says 5 indexes, schema has 6; SF-02 cites missing `mvp_decision_register.md` |
| F-08 | D-VAL-01 | Title "QA Runner Tool", body describes `sw check code` / C01–C08 |
| F-09 | D-INTL-01 | Names `test_generator.py`, `config/layers.py`, `test_full_loop.py`; none exist |
| F-10 | D-INTL-03 | Says "DECOMPOSE action doesn't exist"; `StepAction.DECOMPOSE` exists |
| F-11 | B-FLOW-01 SF-C | Cites `ScenarioConverterFactory` (never existed); YAML example `kind: e2e` vs real `kind: scenario` |
| F-12 | C-INTL-05 SF-02 | Says 7 callers, lists 6 |
| F-13 | E-EXEC-01 SF-02 | Names `TECH-010` as the Java/Kotlin `except` narrowing; `TECH-010` is the MCP executor migration |
| F-14 | `known_boundary_violations.md` | The LLM row looks resolved (`review/`, `planning/` now use `ToolDispatcherProtocol`); several rows cite old paths |
| F-15 | Dev guides | Code examples out of date: framework YAML (`evaluate.annotations.unroll` vs `decorators:`), pipeline YAML (`steps:`/`rule_id` vs `add:`/`rule:`), `AstAtom`/`drift_detector.detect` renamed; user guide 5 `context.yaml` nests keys the resolver reads top-level; no C13 rollback |
| F-16 | `hard_dependency_rules.md`, `module_dependency_graph.md` | Old flat module names; the enforced rules are in `tach.toml` |

## Already fixed in the docs by the rewrite (no action)

User guides: `--provider` / `llm.provider` (→ `sw config set-provider`), `set-auto-bootstrap` argument,
`${vault:<key>}` claim, slot lists, JavaScript parser claim; 17 dead links in `docs/INDEX.md`;
`sw scan --standards` → `sw standards scan`; pipeline guide §7 per-run session mode.
