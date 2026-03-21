# Test Coverage Matrix

> **2 539 passed** · 9 skipped · 87 source modules · 106 test files
> **Last updated**: 2026-03-21

Legend: ✅ covered · ❌ missing · ⚪ n/a

---

## Summary

| Metric | Count |
|--------|------:|
| Total stories / use cases catalogued | 185 |
| Fully covered (✅ at all applicable layers) | 69 |
| Missing **unit** tests | 49 |
| Missing **integration** tests | 67 |
| Missing **both** unit + integration | 39 |
| Missing **e2e** tests (proposed) | 22 |
| Missing **performance** tests | 3 |

---

## Module Inventory

| Package | Files | Unit | Integ | E2E | Total |
|---------|------:|-----:|------:|----:|------:|
| `cli/` | 10 | 194 | 84 | 53 | 331 |
| `config/` | 3 | 204 | 19 | — | 223 |
| `context/` | 4 | 53 | 8 | — | 61 |
| `drafting/` | 3 | 113 | 0 | — | 113 |
| `flow/` | 8 | 243 | 16 | — | 259 |
| `graph/` | 2 | — | — | — | (in context) |
| `implementation/` | 1 | — | — | — | (in llm) |
| `llm/` | 5 | 150 | 0 | — | 150 |
| `loom/` | 15 | 571 | 14 | — | 585 |
| `project/` | 3 | 69 | 0 | — | 69 |
| `review/` | 1 | 30 | 0 | — | 30 |
| `standards/` | 4 | 47 | 0 | — | 47 |
| `validation/` | 24 | 505 | 49 | — | 554 |
| `logging.py` | 1 | — | — | — | (in config) |
| **Total** | **87** | **2 179** | **190** | **53** | **2 422** |

---

## Next Stories to Fix Test Gap

> **Rule**: one story per commit. After each commit, mark the story ✅ and promote
> the next story from the detailed tables below. Keep this section at exactly 10 items.

| # | Story | Module | Tests to Write | Ref |
|---|-------|--------|---------------|-----|
| 1 | `Reviewer.review_spec()` / `review_code()` — full cycle with mocked LLM | `review/reviewer.py` | Unit + Integration | [§ 11.1](#111-reviewerpy) |
| 2 | `Drafter.draft()` — full section loop with mocked LLM | `drafting/drafter.py` | Unit + Integration | [§ 4.2](#42-drafterpy) |
| 3 | `sw run new_feature` — Draft→validate→review→implement cycle | `cli/pipelines.py` | E2E | [§ 1.6](#16-pipelinespy) |
| 4 | `GenerateCodeHandler` / `GenerateTestsHandler` / `DraftSpecHandler.execute()` | `flow/handlers.py` | Unit | [§ 5.3](#53-handlerspy) |
| 5 | `ReviewSpecHandler` / `ReviewCodeHandler.execute()` with mocked LLM | `flow/handlers.py` | Unit | [§ 5.3](#53-handlerspy) |
| 6 | `Generator.generate_code()` / `generate_tests()` / `_clean_code_output()` | `implementation/generator.py` | Unit + Integration | [§ 7.1](#71-generatorpy) |
| 7 | ~~Standards edge cases + e2e~~ ✅ | `standards/*` + `cli/standards.py` | ~~Edge-case Unit + E2E~~ | [§ 1.9](#19-standardspy) |
| 8 | `GeminiAdapter._parse_response()` / `_handle_error()` / `_messages_to_gemini()` | `llm/adapters/gemini.py` | Unit | [§ 8.5](#85-adaptersgeminipy) |
| 9 | `FeatureDrafter.draft()` — decomposition + drafting with mocked LLM | `drafting/feature_drafter.py` | Unit + Integration | [§ 4.3](#43-feature_drafterpy) |
| 10 | `LintFixHandler` / `ValidateTestsHandler.execute()` | `flow/handlers.py` | Unit | [§ 5.3](#53-handlerspy) |

**Graduation queue** (promote when a slot opens):
- C04 / C05 isolated unit tests (`validation/rules/`)
- Selectors integration with real topology (`graph/selectors.py`)
- `sw review` with topology context injected (`cli/review.py`)
- `sw draft` user feedback mid-draft + interrupt handling (`cli/review.py`)
- `_apply_specweaverignore()` / `_git_ls_files()` (`standards/discovery.py`)
- Prompt with constitution + standards + topology all combined (`llm/prompt_builder.py`)
- Concurrent DB access (`config/database.py`)
- `ContextInferrer` edge cases — empty dirs, `__init__.py` only (`context/inferrer.py`)
- Display with PARKED status / 10+ step pipeline (`flow/display.py`)
- `migrate_legacy_config()` (`config/settings.py`)

---

## 1 · CLI (`cli/`)

### 1.1 `_core.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `get_db()` singleton creation | ❌ | ⚪ | ⚪ | ⚪ | Thin wiring, used by all commands |
| `_require_active_project()` error path | ❌ | ✅ | ⚪ | ⚪ | Indirectly via CLI |
| `_version_callback()` | ❌ | ❌ | ❌ | ⚪ | Never tested |

### 1.2 `_helpers.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `_display_results()` console formatting | ✅ | ✅ | ⚪ | ⚪ | — |
| `_print_summary()` pass/fail/warn counts | ✅ | ✅ | ⚪ | ⚪ | — |
| `_require_llm_adapter()` loads adapter | ✅ | ✅ | ⚪ | ⚪ | — |
| `_load_topology()` loads graph | ✅ | ✅ | ⚪ | ⚪ | — |
| `_get_selector_map()` selector dispatch | ✅ | ❌ | ⚪ | ⚪ | No integ for wiring |
| `_select_topology_contexts()` neighbor selection | ✅ | ❌ | ⚪ | ⚪ | No integ for injection |
| `_load_constitution_content()` reads file | ✅ | ✅ | ⚪ | ⚪ | — |
| `_load_standards_content()` reads from DB | ✅ | ❌ | ⚪ | ⚪ | No integ for DB read |

### 1.3 `config.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `config_set` / `config_get` / `config_list` / `config_reset` | ✅ | ✅ | ✅ | ⚪ | — |
| `config_set_log_level` / `config_get_log_level` | ✅ | ✅ | ⚪ | ⚪ | — |
| `config_*_constitution_max_size` | ✅ | ✅ | ✅ | ⚪ | — |
| `config_profiles` / `config_show_profile` | ✅ | ✅ | ✅ | ⚪ | — |
| `config_set_profile` / `config_get_profile` / `config_reset_profile` | ✅ | ✅ | ✅ | ⚪ | — |

### 1.4 `constitution.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `constitution_show` / `constitution_check` / `constitution_init` | ✅ | ✅ | ✅ | ⚪ | — |

### 1.5 `implement.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `implement()` LLM call + file write | ✅ | ✅ | ✅ | ⚪ | — |

### 1.6 `pipelines.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `_get_state_store()` lazy factory | ❌ | ⚪ | ⚪ | ⚪ | Thin wiring |
| `_resolve_spec_path()` path resolution | ✅ | ✅ | ⚪ | ⚪ | — |
| `_create_display()` backend selection | ✅ | ✅ | ⚪ | ⚪ | — |
| `pipelines()` list bundled | ✅ | ✅ | ✅ | ⚪ | — |
| `run_pipeline()` full execution | ✅ | ✅ | ✅ | ⚪ | — |
| `_execute_run()` core run wiring | ❌ | ✅ | ⚪ | ⚪ | Complex but tested via integ |
| `resume()` resume parked/failed | ✅ | ✅ | ✅ | ⚪ | — |
| `sw run new_feature` full cycle | ❌ | ❌ | ❌ | ⚪ | Draft→validate→review→implement |
| `sw run --selector nhop` | ❌ | ❌ | ❌ | ⚪ | Topology selector in run context |
| `sw run` interrupted → state saved | ✅ | ❌ | ❌ | ⚪ | Unit mock only |

### 1.7 `projects.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `init` / `use` / `projects` / `remove` / `update` / `scan` | ✅ | ✅ | ✅ | ⚪ | — |

### 1.8 `review.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `draft()` interactive spec drafting | ✅ | ❌ | ⚪ | ⚪ | No integ for HITL loop |
| `review()` spec/code review | ✅ | ✅ | ✅ | ⚪ | — |
| `_execute_review()` asyncio handling | ✅ | ✅ | ⚪ | ⚪ | — |
| `_display_review_result()` exit codes | ✅ | ✅ | ⚪ | ⚪ | — |
| `sw review` with topology context | ❌ | ❌ | ❌ | ⚪ | Neighbor context in prompt |
| `sw review` with constitution | ✅ | ✅ | ✅ | ⚪ | — |
| `sw draft` user feedback mid-draft | ❌ | ❌ | ❌ | ⚪ | Not tested |
| `sw draft` interrupted → partial discard | ❌ | ❌ | ❌ | ⚪ | Not tested |

### 1.9 `standards.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `standards_scan()` scan project | ✅ | ✅ | ✅ | ⚪ | 7 unit + 5 integ + 3 e2e |
| `standards_show()` display stored | ✅ | ✅ | ✅ | ⚪ | 7 unit + 2 integ + 2 e2e |
| `standards_clear()` clear stored | ✅ | ✅ | ✅ | ⚪ | 5 unit + 2 integ + 1 e2e |
| `_load_standards_content()` formatting | ✅ | ✅ | ✅ | ⚪ | 7 unit + 1 integ + 1 e2e |
| Re-scan overwrites existing standards | ✅ | ✅ | ✅ | ⚪ | Unit + integ + e2e |
| Scan with confidence boundary (exactly 0.3) | ✅ | ⚪ | ⚪ | ⚪ | Boundary tested |
| SyntaxError file graceful degradation | ✅ | ✅ | ⚪ | ⚪ | Skips bad file, still analyzes good ones |
| `.specweaverignore` filtering | ✅ | ✅ | ⚪ | ⚪ | Glob/negation/dir patterns |

### 1.10 `validation.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `_apply_override` / `_load_check_settings` | ✅ | ✅ | ⚪ | ⚪ | — |
| `check()` main entry | ✅ | ✅ | ✅ | ⚪ | — |
| `list_rules()` | ✅ | ✅ | ⚪ | ⚪ | — |

---

## 2 · Config (`config/`)

### 2.1 `database.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| All CRUD (register, get, list, remove, update) | ✅ | ✅ | ⚪ | ⚪ | — |
| All config (log_level, constitution_max_size) | ✅ | ✅ | ⚪ | ⚪ | — |
| All LLM profile (create, get, link) | ✅ | ✅ | ⚪ | ⚪ | — |
| All validation overrides (set, get, list, delete, load) | ✅ | ✅ | ⚪ | ⚪ | — |
| All domain profiles (get, set, clear) | ✅ | ✅ | ⚪ | ⚪ | — |
| All standards (save, get, list, clear, scopes) | ✅ | ✅ | ⚪ | ⚪ | — |
| Concurrent access (two connections) | ❌ | ❌ | ⚪ | ❌ | WAL assumed safe |
| Schema migration on upgrade | ❌ | ❌ | ⚪ | ⚪ | Only initial schema tested |

### 2.2 `profiles.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `DomainProfile` / `get_profile` / `list_profiles` | ✅ | ✅ | ✅ | ⚪ | — |

### 2.3 `settings.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| All Settings models and methods | ✅ | ✅ | ⚪ | ⚪ | — |
| `migrate_legacy_config()` one-time migration | ❌ | ❌ | ⚪ | ⚪ | Not tested |

---

## 3 · Context (`context/`)

### 3.1 `analyzers.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `PythonAnalyzer` detect, extract, infer | ✅ | ✅ | ⚪ | ⚪ | — |
| `AnalyzerFactory.for_directory()` dispatch | ✅ | ❌ | ⚪ | ⚪ | No integ for factory |
| Non-Python project fallback | ❌ | ❌ | ⚪ | ⚪ | Unsupported language |

### 3.2 `hitl_provider.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `HITLProvider` construction + `ask()` | ✅ | ❌ | ⚪ | ⚪ | Used in `sw draft` loop |

### 3.3 `inferrer.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `ContextInferrer.infer_and_write()` | ✅ | ✅ | ⚪ | ⚪ | — |
| `InferredNode` / `InferenceResult` models | ✅ | ⚪ | ⚪ | ⚪ | Data models |
| Infer for dir with no Python files | ❌ | ❌ | ⚪ | ⚪ | Edge case |
| Infer for dir with only `__init__.py` | ❌ | ❌ | ⚪ | ⚪ | Edge case |

### 3.4 `provider.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `ContextProvider` ABC | ⚪ | ⚪ | ⚪ | ⚪ | Abstract — no logic |

---

## 4 · Drafting (`drafting/`)

### 4.1 `decomposition.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `ComponentChange` / `IntegrationSeam` / `DecompositionPlan` | ✅ | ❌ | ⚪ | ⚪ | No integ in pipeline |

### 4.2 `drafter.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `Drafter.__init__()` | ✅ | ❌ | ⚪ | ⚪ | — |
| `Drafter.draft()` full loop with mocked LLM | ❌ | ❌ | ⚪ | ⚪ | Critical gap |
| `Drafter._generate_section()` single section | ❌ | ❌ | ⚪ | ⚪ | Private but critical |
| Draft with 0 sections (empty template) | ❌ | ❌ | ⚪ | ⚪ | Edge case |
| LLM returns empty response for section | ❌ | ❌ | ⚪ | ⚪ | Edge case |
| LLM error mid-draft → partial spec | ❌ | ❌ | ⚪ | ⚪ | Edge case |

### 4.3 `feature_drafter.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `FeatureDrafter.__init__()` | ✅ | ❌ | ⚪ | ⚪ | — |
| `FeatureDrafter.draft()` decomposition + drafting | ❌ | ❌ | ⚪ | ⚪ | Only models tested |
| `FeatureDrafter._generate_section()` | ❌ | ❌ | ⚪ | ⚪ | Not tested |
| Feature draft with multiple components | ❌ | ❌ | ⚪ | ⚪ | Edge case |
| Feature draft with zero integration seams | ❌ | ❌ | ⚪ | ⚪ | Edge case |

---

## 5 · Flow Engine (`flow/`)

### 5.1 `display.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `RichPipelineDisplay` all event handlers | ✅ | ❌ | ⚪ | ⚪ | No integ with real pipeline |
| `JsonPipelineDisplay` NDJSON output | ✅ | ❌ | ⚪ | ⚪ | No integ with real pipeline |
| Display with 10+ step pipeline | ❌ | ❌ | ⚪ | ⚪ | Only 2-step tested |
| Display with PARKED status (HITL gate) | ❌ | ❌ | ⚪ | ⚪ | Not tested |

### 5.2 `gates.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `evaluate()` / `passes()` | ✅ | ✅ | ⚪ | ⚪ | — |
| `find_step_index()` | ✅ | ✅ | ⚪ | ⚪ | — |
| `inject_feedback()` | ✅ | ✅ | ⚪ | ⚪ | — |
| `_handle_retry` / `_handle_loop_back` | ✅ | ✅ | ⚪ | ⚪ | — |
| Gate with `max_retries=0` | ❌ | ❌ | ⚪ | ⚪ | Immediate failure |
| LOOP_BACK to nonexistent target | ❌ | ❌ | ⚪ | ⚪ | Error handling |

### 5.3 `handlers.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `ValidateSpecHandler.execute()` | ✅ | ✅ | ⚪ | ⚪ | — |
| `ValidateCodeHandler.execute()` | ✅ | ❌ | ⚪ | ⚪ | No real file integ |
| `ValidateCodeHandler._find_code_path()` | ❌ | ❌ | ⚪ | ⚪ | Not tested |
| `ReviewSpecHandler.execute()` | ❌ | ❌ | ⚪ | ⚪ | CLI only |
| `ReviewCodeHandler.execute()` | ❌ | ❌ | ⚪ | ⚪ | CLI only |
| `ReviewCodeHandler._find_code_path()` | ❌ | ❌ | ⚪ | ⚪ | Not tested |
| `GenerateCodeHandler.execute()` | ❌ | ❌ | ⚪ | ⚪ | CLI only |
| `GenerateTestsHandler.execute()` | ❌ | ❌ | ⚪ | ⚪ | No test at all |
| `DraftSpecHandler.execute()` | ❌ | ❌ | ⚪ | ⚪ | No test at all |
| `ValidateTestsHandler.execute()` | ❌ | ❌ | ⚪ | ⚪ | No test at all |
| `LintFixHandler.execute()` | ❌ | ❌ | ⚪ | ⚪ | No test at all |
| `LintFixHandler._llm_fix()` | ❌ | ❌ | ⚪ | ⚪ | LLM lint fix |
| `StepHandlerRegistry` get/register | ✅ | ✅ | ⚪ | ⚪ | — |
| `_error_result()` factory | ❌ | ❌ | ⚪ | ⚪ | Not tested |
| Handler raises exception → error result | ❌ | ❌ | ⚪ | ⚪ | Per-handler error propagation |
| Handler with missing LLM adapter | ❌ | ❌ | ⚪ | ⚪ | Per-handler |
| `ValidateTestsHandler` no test file found | ❌ | ❌ | ⚪ | ⚪ | Edge case |

### 5.4 `models.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| All models and enums | ✅ | ✅ | ⚪ | ⚪ | — |
| `PipelineDefinition.validate_flow()` | ✅ | ❌ | ⚪ | ⚪ | No integ in loading context |
| `_validate_loop_back()` | ❌ | ❌ | ⚪ | ⚪ | Not unit-tested |

### 5.5 `parser.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `load_pipeline()` | ✅ | ✅ | ⚪ | ⚪ | — |
| `list_bundled_pipelines()` | ✅ | ✅ | ⚪ | ⚪ | — |
| `_resolve_path()` bundled/project/absolute | ❌ | ❌ | ⚪ | ⚪ | Not isolated |

### 5.6 `runner.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `PipelineRunner.run()` | ✅ | ✅ | ✅ | ⚪ | — |
| `PipelineRunner.resume()` | ✅ | ✅ | ✅ | ⚪ | — |
| `_execute_loop()` / `_persist()` / `_log()` / `_emit()` | ✅ | ✅ | ⚪ | ⚪ | — |
| Runner with no event callback | ❌ | ❌ | ⚪ | ⚪ | — |
| Runner with no store (in-memory only) | ❌ | ❌ | ⚪ | ⚪ | — |

### 5.7 `state.py` + `store.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| All `PipelineRun` methods | ✅ | ✅ | ⚪ | ⚪ | — |
| All `StateStore` methods | ✅ | ✅ | ⚪ | ⚪ | — |
| Store survives process restart (real file) | ❌ | ❌ | ⚪ | ⚪ | In-process only |

---

## 6 · Graph (`graph/`)

### 6.1 `selectors.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `DirectNeighborSelector.select()` | ✅ | ❌ | ⚪ | ⚪ | No integ with real topology |
| `NHopConstraintSelector.select()` | ✅ | ❌ | ⚪ | ⚪ | No integ |
| `ConstraintOnlySelector.select()` | ✅ | ❌ | ⚪ | ⚪ | No integ |
| `ImpactWeightedSelector.select()` | ✅ | ❌ | ⚪ | ⚪ | No integ |
| Selector on graph with cycles | ❌ | ❌ | ⚪ | ⚪ | Edge case |
| Selector on empty graph | ❌ | ❌ | ⚪ | ⚪ | Edge case |

### 6.2 `topology.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `TopologyGraph.from_project()` | ✅ | ✅ | ⚪ | ⚪ | — |
| `consumers_of` / `dependencies_of` / `impact_of` | ✅ | ✅ | ⚪ | ⚪ | — |
| `cycles()` / `constraints_for()` | ✅ | ❌ | ⚪ | ⚪ | No integ in real project |
| `operational_warnings()` | ✅ | ❌ | ⚪ | ⚪ | No integ |
| `format_context_summary()` | ✅ | ❌ | ⚪ | ⚪ | No integ |
| `_auto_infer_missing()` partial context.yaml | ❌ | ❌ | ⚪ | ⚪ | Edge case |

---

## 7 · Implementation (`implementation/`)

### 7.1 `generator.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `Generator.generate_code()` | ❌ | ❌ | ✅ | ⚪ | Via CLI only |
| `Generator.generate_tests()` | ❌ | ❌ | ❌ | ⚪ | Not tested at all |
| `Generator._clean_code_output()` fence stripping | ❌ | ❌ | ✅ | ⚪ | E2E only |
| Generate code with constitution | ❌ | ❌ | ❌ | ⚪ | — |
| Generate code with markdown fences | ✅ | ❌ | ✅ | ⚪ | E2E only |
| Generate tests from spec | ❌ | ❌ | ❌ | ⚪ | — |

---

## 8 · LLM (`llm/`)

### 8.1 `models.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| All models (Role, Message, GenerationConfig, etc.) | ✅ | ⚪ | ⚪ | ⚪ | — |
| `TokenBudget` all methods | ✅ | ⚪ | ⚪ | ⚪ | — |

### 8.2 `errors.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| All 5 exception types + hierarchy | ✅ | ⚪ | ⚪ | ⚪ | — |
| `str(GenerationError)` regression | ✅ | ⚪ | ⚪ | ⚪ | — |

### 8.3 `prompt_builder.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| All builder methods (`add_*`, `build`) | ✅ | ❌ | ⚪ | ⚪ | No integ with adapter |
| `_compute_auto_scale()` | ✅ | ❌ | ⚪ | ⚪ | — |
| `detect_language()` | ✅ | ❌ | ⚪ | ⚪ | — |
| Prompt with constitution + standards + topology combined | ❌ | ❌ | ⚪ | ⚪ | Never combined |
| Prompt exceeds token budget → truncation | ✅ | ❌ | ⚪ | ⚪ | Unit only |

### 8.4 `adapters/base.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `LLMAdapter` ABC | ⚪ | ⚪ | ⚪ | ⚪ | Abstract |

### 8.5 `adapters/gemini.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `GeminiAdapter.__init__()` | ✅ | ❌ | ⚪ | ⚪ | — |
| `GeminiAdapter.available()` | ✅ | ❌ | ⚪ | ⚪ | — |
| `GeminiAdapter.generate()` | ❌ | ❌ | ⚪ | ⚪ | Real API — manual only |
| `GeminiAdapter.generate_stream()` | ❌ | ❌ | ⚪ | ⚪ | Real API — manual only |
| `GeminiAdapter._parse_response()` | ❌ | ❌ | ⚪ | ⚪ | Not isolated |
| `GeminiAdapter.count_tokens()` | ❌ | ❌ | ⚪ | ⚪ | Not tested |
| `GeminiAdapter._handle_error()` API→LLMError mapping | ❌ | ❌ | ⚪ | ⚪ | Not tested |
| `_messages_to_gemini()` format conversion | ❌ | ❌ | ⚪ | ⚪ | Not tested |

---

## 9 · Loom — Atoms / Tools / Commons (`loom/`)

### 9.1 Atoms (base, rule, filesystem, git, test_runner)

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `Atom` ABC + `AtomResult` / `AtomStatus` | ✅ | ⚪ | ⚪ | ⚪ | — |
| `RuleAtom` run | ✅ | ✅ | ⚪ | ⚪ | — |
| `FileSystemAtom` all intents | ✅ | ✅ | ⚪ | ⚪ | — |
| `GitAtom` all intents | ✅ | ⚪ | ⚪ | ⚪ | — |
| `TestRunnerAtom` run/lint/complexity | ✅ | ✅ | ⚪ | ⚪ | — |

### 9.2 Tools (filesystem, git, test_runner)

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `FileSystemTool` all methods + grants | ✅ | ✅ | ⚪ | ⚪ | — |
| `GitTool` all methods + whitelist | ✅ | ⚪ | ⚪ | ⚪ | — |
| `TestRunnerTool` run_tests/run_linter | ✅ | ⚪ | ⚪ | ⚪ | — |
| Role gating (implementer can fix, reviewer cannot) | ✅ | ✅ | ⚪ | ⚪ | — |
| Path traversal prevention | ✅ | ⚪ | ⚪ | ⚪ | — |

### 9.3 Commons (filesystem, git, test_runner)

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `FileExecutor` all methods | ✅ | ⚪ | ⚪ | ⚪ | — |
| `GitExecutor` run + whitelist | ✅ | ⚪ | ⚪ | ⚪ | — |
| `PythonTestRunner` run/lint/complexity | ✅ | ⚪ | ⚪ | ⚪ | — |
| `TestRunnerInterface` ABC | ⚪ | ⚪ | ⚪ | ⚪ | — |

### 9.4 Interfaces (filesystem, git, test_runner)

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| All role-specific interfaces | ✅ | ⚪ | ⚪ | ⚪ | — |
| `create_*_interface()` factory functions | ✅ | ⚪ | ⚪ | ⚪ | — |

---

## 10 · Project (`project/`)

### 10.1 `constitution.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `find_constitution()` walk-up, override, BOM | ✅ | ⚪ | ✅ | ⚪ | — |
| `find_all_constitutions()` | ✅ | ⚪ | ⚪ | ⚪ | — |
| `check_constitution()` size limits | ✅ | ⚪ | ✅ | ⚪ | — |
| `generate_constitution()` | ✅ | ⚪ | ✅ | ⚪ | — |

### 10.2 `discovery.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `resolve_project_path()` explicit / env / cwd | ✅ | ⚪ | ✅ | ⚪ | — |
| Nonexistent / file-instead-of-dir | ✅ | ⚪ | ⚪ | ⚪ | — |

### 10.3 `scaffold.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `scaffold_project()` creates dirs + files | ✅ | ⚪ | ✅ | ⚪ | — |
| Scaffold idempotency | ✅ | ⚪ | ✅ | ⚪ | — |

---

## 11 · Review (`review/`)

### 11.1 `reviewer.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `ReviewResult` / `ReviewFinding` / `ReviewVerdict` models | ✅ | ❌ | ⚪ | ⚪ | — |
| `ReviewResult.above_threshold_findings()` | ✅ | ❌ | ⚪ | ⚪ | — |
| `Reviewer.__init__()` | ❌ | ❌ | ⚪ | ⚪ | Not tested |
| `Reviewer.review_spec()` with mocked LLM | ❌ | ❌ | ⚪ | ⚪ | CLI only |
| `Reviewer.review_code()` with mocked LLM | ❌ | ❌ | ⚪ | ⚪ | CLI only |
| `Reviewer._execute_review()` | ❌ | ❌ | ⚪ | ⚪ | CLI only |
| `Reviewer._parse_response()` | ✅ | ❌ | ⚪ | ⚪ | — |
| `Reviewer._extract_confidence()` | ✅ | ❌ | ⚪ | ⚪ | — |
| Reviewer with mocked LLM → full cycle | ❌ | ❌ | ⚪ | ⚪ | — |
| Reviewer with topology context in prompt | ❌ | ❌ | ⚪ | ⚪ | — |
| Reviewer with standards in prompt | ❌ | ❌ | ⚪ | ⚪ | — |
| LLM error during review → ERROR verdict | ✅ | ❌ | ✅ | ⚪ | E2E only |

---

## 12 · Standards (`standards/`)

### 12.1 `analyzer.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `StandardsAnalyzer` ABC | ✅ | ❌ | ⚪ | ⚪ | No integ |

### 12.2 `discovery.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `discover_files()` | ✅ | ❌ | ⚪ | ⚪ | No integ on real project |
| `_git_ls_files()` | ❌ | ❌ | ⚪ | ⚪ | Not tested |
| `_walk_with_skips()` | ✅ | ❌ | ⚪ | ⚪ | — |
| `_apply_specweaverignore()` | ❌ | ❌ | ⚪ | ⚪ | Not tested |
| Discovery with `.specweaverignore` | ❌ | ❌ | ⚪ | ⚪ | — |
| Discovery with `git ls-files` | ❌ | ❌ | ⚪ | ⚪ | — |
| Discovery on non-git directory | ❌ | ❌ | ⚪ | ⚪ | — |

### 12.3 `python_analyzer.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| All 6 extraction categories | ✅ | ❌ | ⚪ | ⚪ | No integ scanning project |
| `_classify_name()` | ✅ | ❌ | ⚪ | ⚪ | — |
| `_detect_test_framework()` | ✅ | ❌ | ⚪ | ⚪ | — |
| `_parse_file()` / `_file_weight()` / `_compute_confidence()` | ✅ | ❌ | ⚪ | ⚪ | — |
| Analyze project with 100+ files | ❌ | ❌ | ⚪ | ❌ | Performance |
| Analyze project with no Python files | ❌ | ❌ | ⚪ | ⚪ | — |

### 12.4 `recency.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `recency_weight()` / `compute_half_life()` | ✅ | ❌ | ⚪ | ⚪ | — |
| `_find_oldest_source_mtime()` | ❌ | ❌ | ⚪ | ⚪ | Not tested |

---

## 13 · Validation (`validation/`)

### 13.1 Rules S01–S11 (spec rules)

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| S01 One-Sentence pass/fail/edge | ✅ | ✅ | ⚪ | ⚪ | — |
| S02 Single Setup pass/fail | ✅ | ✅ | ⚪ | ⚪ | — |
| S03 Stranger Test pass/fail | ✅ | ✅ | ⚪ | ⚪ | — |
| S04 Dependency Direction pass/fail | ✅ | ✅ | ⚪ | ⚪ | — |
| S05 Day Test pass/fail | ✅ | ✅ | ⚪ | ⚪ | — |
| S06 Concrete Example pass/fail | ✅ | ✅ | ⚪ | ⚪ | — |
| S07 Test-First extraction/scoring/thresholds | ✅ | ✅ | ⚪ | ⚪ | — |
| S08 Ambiguity pass/warn/fail | ✅ | ✅ | ⚪ | ⚪ | — |
| S09 Error Path keywords/policy/empty | ✅ | ✅ | ⚪ | ⚪ | — |
| S10 Done Definition pass/fail | ✅ | ✅ | ⚪ | ⚪ | — |
| S11 Terminology casing/undefined | ✅ | ✅ | ⚪ | ⚪ | — |

### 13.2 Rules C01–C08 (code rules)

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| C01 Syntax Valid | ✅ | ✅ | ⚪ | ⚪ | — |
| C02 Tests Exist | ✅ | ✅ | ⚪ | ⚪ | — |
| C03 Tests Pass (mocked) | ✅ | ✅ | ⚪ | ⚪ | — |
| C04 Coverage threshold check | ❌ | ✅ | ⚪ | ⚪ | No isolated unit |
| C04 0% coverage edge case | ❌ | ❌ | ⚪ | ⚪ | — |
| C04 Boundary at exact threshold | ❌ | ❌ | ⚪ | ⚪ | — |
| C04 Custom threshold constructor | ❌ | ❌ | ⚪ | ⚪ | — |
| C05 Import Direction layer violations | ❌ | ✅ | ⚪ | ⚪ | No isolated unit |
| C05 Circular imports | ❌ | ❌ | ⚪ | ⚪ | — |
| C05 Intra-layer imports only | ❌ | ❌ | ⚪ | ⚪ | — |
| C05 `typing` imports ignored | ❌ | ❌ | ⚪ | ⚪ | — |
| C06 No Bare Except | ✅ | ✅ | ⚪ | ⚪ | — |
| C07 No Orphan TODO | ✅ | ✅ | ⚪ | ⚪ | — |
| C08 Type Hints | ✅ | ✅ | ⚪ | ⚪ | — |

### 13.3 Infrastructure (executor, loader, registry, runner, etc.)

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `execute_validation_pipeline()` | ✅ | ✅ | ⚪ | ⚪ | — |
| `apply_settings_to_pipeline()` | ✅ | ✅ | ⚪ | ⚪ | — |
| `resolve_pipeline()` inheritance | ✅ | ⚪ | ⚪ | ⚪ | — |
| `_validate_loop_back()` | ❌ | ❌ | ⚪ | ⚪ | — |
| Pipeline loader YAML | ✅ | ✅ | ⚪ | ⚪ | — |
| Rule registry | ✅ | ✅ | ⚪ | ⚪ | — |
| Custom D-prefix rule loading | ✅ | ⚪ | ⚪ | ⚪ | — |
| Sub-pipeline `extends` circular guard | ✅ | ⚪ | ⚪ | ⚪ | — |

### 13.4 `logging.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `get_log_path()` | ✅ | ❌ | ⚪ | ⚪ | — |
| `setup_logging()` | ✅ | ❌ | ⚪ | ⚪ | No integ for file output |
| `teardown_logging()` | ✅ | ❌ | ⚪ | ⚪ | — |

---

## Proposed New E2E Tests

### `test_new_feature_e2e.py` — Full Factory Workflow

| # | Test Name | Story Covered |
|---|-----------|--------------|
| 1 | `test_new_feature_full_cycle` | Draft→validate→review→implement with mocked LLM |
| 2 | `test_new_feature_review_denied_loops_back` | DENIED → loop back → re-review → ACCEPTED |
| 3 | `test_new_feature_validation_fails_stops` | Spec fails validation → stops before review |
| 4 | `test_new_feature_hitl_parks_and_resumes` | HITL gate parks → `sw resume` completes |
| 5 | `test_new_feature_llm_error_mid_pipeline` | LLM error during implement → FAILED |
| 6 | `test_new_feature_with_constitution` | Constitution injected into prompts |
| 7 | `test_new_feature_with_topology` | Topology context injected |

### `test_multi_project_e2e.py` — Cross-Project Workflows

| # | Test Name | Story Covered |
|---|-----------|--------------|
| 8 | `test_two_projects_switch_and_operate` | Init P1+P2 → switch → no contamination |
| 9 | `test_remove_project_operations_on_remaining` | Remove P1 → P2 still works |
| 10 | `test_update_project_path_uses_new` | `sw update path` → subsequent ops use new path |

### `test_standards_e2e.py` — Standards Discovery Workflow

| # | Test Name | Story Covered |
|---|-----------|--------------|
| 11 | `test_scan_standards_stores_results` | `sw standards-scan` → DB populated |
| 12 | `test_show_standards_after_scan` | `sw standards-show` displays results |
| 13 | `test_clear_standards` | `sw standards-clear` removes data |
| 14 | `test_standards_injected_into_review` | Scan → review prompt includes standards |

### `test_validation_pipeline_e2e.py` — Pipeline Variants

| # | Test Name | Story Covered |
|---|-----------|--------------|
| 15 | `test_validate_only_all_rules_fire` | All 11 spec rules execute |
| 16 | `test_validate_only_with_profile_override` | Profile → fewer rules |
| 17 | `test_validate_only_with_disable_override` | Disable S01 → S01 skipped |
| 18 | `test_code_validation_pipeline` | C01–C08 fire on Python file |

### `test_topology_e2e.py` — Context/Topology Integration

| # | Test Name | Story Covered |
|---|-----------|--------------|
| 19 | `test_scan_generates_context_yaml` | `sw scan` auto-generates context |
| 20 | `test_review_with_nhop_selector` | `--selector nhop` → neighbors in prompt |
| 21 | `test_review_with_impact_selector` | `--selector impact` → weighted contexts |
| 22 | `test_review_with_no_topology` | No context.yaml → review still works |
