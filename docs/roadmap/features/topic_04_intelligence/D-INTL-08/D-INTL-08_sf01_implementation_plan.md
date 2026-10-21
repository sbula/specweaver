# Implementation Plan: Polyglot Implementation Loop [SF-01: One derivation]
- **Feature ID**: D-INTL-08
- **Sub-Feature**: SF-01 — One derivation
- **Design Document**: docs/roadmap/features/topic_04_intelligence/D-INTL-08/D-INTL-08_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/D-INTL-08/D-INTL-08_sf01_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-21

**FRs owned**: FR-1, FR-2, FR-3 · **NFRs**: NFR-1, NFR-4 · **Depends on**: none · **Closes**: `TECH-073`

## Shape

| Piece | Where | Tag |
|---|---|---|
| `module_stem(spec_path) -> str`: `removesuffix("_spec")` — the one stem rule (FR-1). Lives in `commons` because `sandbox.language`'s scenario converters need it too and may not import `core` | `commons/spec_names.py` | NEW |
| The 23 derivations in 16 files call it (list in Research Notes) | across `core`, `workflows`, `sandbox`, `interfaces` | MODIFY |
| `[implement] language` (`python \| java \| kotlin \| typescript \| rust`), strict, like `[autonomy]` | `core/config/implement_policy.py` + a loader in `core/config/bootstrap/` | NEW |
| `detect_language`: `pyproject.toml` → python before the default; a Gradle build is Kotlin only with `src/main/kotlin` or the Kotlin plugin, else Java (FR-2). The QA runner factory's own copy of the order goes, it calls this one (NFR-4 — moved here from SF-02 so the two never disagree) | `sandbox/language/core/_detect.py`, `sandbox/qa_runner/core/factory.py` | MODIFY |
| `RunContext.language`: the explicit setting, else detected, set by every run root (`_build_run_context`, `sw implement`, the API); `"python"` for a hand-built context | `core/flow/handlers/run_context.py` + the roots | MODIFY |
| `TaskFiles(code, tests, extra)` and `task_files_for(project_root, spec_path, language)`: the design's layout; the Java/Kotlin package from the spec's `> **Package**:` header line (Q1), else the longest package prefix all existing sources share (none when they share nothing), else the build's `group`/`groupId`, else the default package (no folder). A package that is not a dotted identifier (`[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)*`) — `../x`, `com/evil` — is refused, naming the spec line. `<Name>` splits the stem on `_` and `-`; a Rust file name turns `-` into `_`. For Rust `extra` holds `src/lib.rs` (or `src/main.rs` when only it exists). A session's configured `session_allowed_paths` still wins over the derivation | `core/flow/engine/task_files.py` (beside `isolation.task_files`) | NEW |
| Its callers: generation's `output_path`; `derive_allowed_paths`/`task_files` (the merge allow-list); the coder's grant (`_run_coder` — Rust's code step adds `extra`); `sw implement`'s `lint_fix`/`run_tests`/`validate_code` targets and its display; `validation.py`'s default test target and `_generated_code`; `validation_hydrator._test_file_for` | `generation.py`, `isolation.py`, `implementation/interfaces/cli.py`, `validation.py`, `validation_hydrator.py` | MODIFY |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the one stem rule, at every site | FR-1, NFR-4 | `my_spec_tool_spec.md` is `my_tool` to generation and `my_spec_tool` to `sw implement` |
| CB-2 | the language: setting, detection fix, one detector, on the run context | FR-2 | a Gradle Java project is detected as Kotlin; `[implement]` is ignored |
| CB-3 | `TaskFiles` and all its callers | FR-3, NFR-1 | a Java project's merge allow-list names `src/<stem>.py` |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit | `module_stem` on `greeter_spec.md`, `my_spec_tool_spec.md`, `spec.md`, `notes.md` |
| CB-1 | unit (guard) | no `replace("_spec"` or `removesuffix("_spec")` in `src/` outside `commons/spec_names.py` |
| CB-1 | integration | for `my_spec_tool_spec.md`, generation's target, the merge allow-list and `sw implement`'s targets agree |
| CB-2 | unit | `[implement]` parsing and refusals with their lines; detection: `pyproject.toml`, Gradle + `src/main/java`, Gradle + `src/main/kotlin`, Kotlin plugin, the five manifests, none |
| CB-2 | integration | `sw run`, `sw implement` and the API put the setting, else the detected language, on the context; the QA runner factory and `detect_language` agree on every fixture project |
| CB-3 | unit | the layout per language; the package from the header, from sources (longest prefix; sources sharing nothing), from `groupId`/`group`, none; a hostile header package (`../x`, `com/evil`) refused; `greet-service` as `GreetService` and Rust `greet_service.rs`; Rust with `lib.rs`, `main.rs`, neither |
| CB-3 | integration | on the Java Maven, Java Gradle, Kotlin and a Rust fixture: generation's target, the merge allow-list, the coder's grant and the QA targets name the same files; Python's are byte-identical to today (NFR-1) |

## Mutants (into `D-INTL-08_mutants.json`, new)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | `removesuffix` back to `replace` | CB-1 unit + integration |
| CB-2 | the `pyproject.toml` branch; the Gradle Java/Kotlin split; the setting ignored at a root | CB-2 tests |
| CB-3 | the header package ignored; the prefix rule replaced by "first package found"; Rust's `extra` dropped from the grant; the allow-list keeping the Python paths | CB-3 tests |

## Research Notes

- The 23 stem derivations: `interfaces/api/v1/implement.py:47`; `handlers/scenario.py:89,183`;
  `handlers/validation.py:386,567`; `handlers/dual_pipeline.py:209`; `handlers/reviewed_spec.py:99,120`;
  `handlers/draft.py:169`; `handlers/generation.py:136,361,502`; `flow/interfaces/cli.py:428`;
  `engine/isolation.py:62`; `review/interfaces/cli.py:295`; `implementation/interfaces/cli.py:254,263`;
  `scenarios/scenario_converter.py:118`; `language/core/{java,kotlin,rust,typescript}/scenario_converter.py`.
  `generation.py:361` builds a display title from the stem and keeps doing so.
- Spec headers are `> **Key**: value` lines under the title (`tests/fixtures/good_spec.md:3-6`:
  Status, Date, Layer, Parent Feature).
- `tests/fixtures/java_maven_project/pom.xml:7` `<groupId>com.example</groupId>`; the Gradle fixtures
  declare no `group`; sources under `src/main/java/com/...`.
- `detect_language` (`_detect.py:33-54`) and `qa_runner/core/factory.py:51-78` hold the same order
  twice; `stack_trace_filter_factory`, `scenario_converter_factory` and `LanguageAtom` call the first.
- `RunContext` is built at `_build_run_context` (`core/flow/interfaces/cli.py`), in `sw implement`
  (`implementation/interfaces/cli.py`) and twice in `interfaces/api/v1/pipelines.py`; `[docs]` and
  `[autonomy]` already ride in at those four places.
- `sandbox` may import `commons` and `core.config`; `core.flow` may import `sandbox`.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | How does a spec name its Java/Kotlin package? | a header line, `> **Package**: com.example.greet`, beside Status and Layer `[agreed 2026-10-21]` |

## Backlog

none
