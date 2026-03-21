# Test Coverage Matrix

> **2 893 collected** · 2 884 passed · 9 skipped · 96 source modules · 128 test files
> **Last updated**: 2026-03-22

Legend: ✅ covered · ❌ missing · ⚪ n/a

> 💡 **Tip:** Need help running these tests? See the [Testing Guide](testing_guide.md).

---

## Summary

| Metric | Count |
|--------|------:|
| Total stories / use cases catalogued | 185 |
| Fully covered (✅ at all applicable layers) | 69 |
| Missing **unit** tests | 49 |
| Missing **integration** tests | 64 |
| Missing **both** unit + integration | 37 |
| Missing **e2e** tests | 4 |
| Missing **performance** tests | 3 |

---

## Module Inventory

> Counts from `pytest --collect-only` per directory. E2E tests are holistic;
> attribution is by primary source package under test.
> Integration subdirs: `cli/`→94, `config/`→20, `constitution/`→10 (→project), `context/`→8, `flow/`→22, `loom/`→14, `validation/`→49.

| Package | Src Files | Unit | Integ | E2E | Total |
|---------|----------:|-----:|------:|----:|------:|
| `cli/` | 10 | 253 | 94 | 38 | 385 |
| `config/` | 3 | 228 | 20 | 0 | 248 |
| `context/` | 4 | 53 | 8 | 7 | 68 |
| `drafting/` | 3 | 113 | 0 | 0 | 113 |
| `flow/` | 8 | 263 | 22 | 13 | 298 |
| `graph/` | 2 | 88 | 0 | 0 | 88 |
| `implementation/` | 1 | 6 | 0 | 0 | 6 |
| `llm/` | 5 | 150 | 0 | 0 | 150 |
| `loom/` | 15 | 571 | 14 | 0 | 585 |
| `project/` | 3 | 90 | 10 | 18 | 118 |
| `review/` | 1 | 30 | 0 | 0 | 30 |
| `standards/` | 11 | 172 | 0 | 4 | 176 |
| `validation/` | 24 | 562 | 49 | 5 | 616 |
| `logging.py` | 1 | 22 | 0 | 0 | 22 |
| **Total** | **96** | **2 601** | **217** | **76** | **2 893** |


---

## Next Stories to Fix Test Gap

> **Rule**: one story per commit. After each commit, mark the story ✅ and promote
> the next story from the detailed tables below. Keep this section at exactly 10 items.

| # | Story | Module | Tests to Write | Ref |
|---|-------|--------|---------------|-----|
| 1 | `Reviewer.review_spec()` / `review_code()` — full cycle with mocked LLM | `review/reviewer.py` | Unit + Integration | [§ 11.1](#111-reviewerpy) |
| 2 | `Drafter.draft()` — full section loop with mocked LLM | `drafting/drafter.py` | Unit + Integration | [§ 4.2](#42-drafterpy) |
| 3 | ~~`sw run new_feature` — Draft→validate→review→implement cycle~~ ✅ | `cli/pipelines.py` | ~~E2E~~ | [§ 1.6](#16-pipelinespy) |
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
- `_apply_specweaverignore()` / `_git_ls_files()` ✅ (6 + 4 unit tests added)
- `sw review` with topology context injected ✅ (nhop/impact E2E)
- `sw draft` user feedback mid-draft + interrupt handling (`cli/review.py`)
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
| `_load_topology()` loads graph | ✅ | ✅ | ✅ | ⚪ | E2E via topology/nhop/impact selector tests |
| `_get_selector_map()` selector dispatch | ✅ | ❌ | ✅ | ⚪ | E2E via review --selector tests |
| `_select_topology_contexts()` neighbor selection | ✅ | ❌ | ✅ | ⚪ | E2E via nhop/impact/no-topology tests |
| `_load_constitution_content()` reads file | ✅ | ✅ | ⚪ | ⚪ | — |
| `_load_standards_content()` reads from DB | ✅ | ✅ | ✅ | ⚪ | Scope-aware w/ target_path, token cap |
| `_load_standards_content()` scope-aware load | ✅ | ❌ | ⚪ | ⚪ | 9 unit tests (scope resolve, cap, priority) |
| `_load_standards_content()` token cap truncation | ✅ | ❌ | ⚪ | ⚪ | Truncation + below-limit tested |

### 1.3 `config.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `config_set` / `config_get` / `config_list` / `config_reset` | ✅ | ✅ | ✅ | ⚪ | — |
| `config_set_log_level` / `config_get_log_level` | ✅ | ✅ | ⚪ | ⚪ | — |
| `config_*_constitution_max_size` | ✅ | ✅ | ✅ | ⚪ | — |
| `config_profiles` / `config_show_profile` | ✅ | ✅ | ✅ | ⚪ | — |
| `config_set_profile` / `config_get_profile` / `config_reset_profile` | ✅ | ✅ | ✅ | ⚪ | — |
| `config_set_auto_bootstrap` / `config_get_auto_bootstrap` | ✅ | ⚪ | ⚪ | ⚪ | 4 unit (prompt/auto/off/invalid) |

### 1.4 `constitution.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `constitution_show` / `constitution_check` / `constitution_init` | ✅ | ✅ | ✅ | ⚪ | — |
| `constitution_bootstrap` generates from standards | ✅ | ⚪ | ⚪ | ⚪ | Happy path |
| `constitution_bootstrap` no standards → error | ✅ | ⚪ | ⚪ | ⚪ | Empty DB |
| `constitution_bootstrap` user-edited → requires `--force` | ✅ | ⚪ | ⚪ | ⚪ | Modified detection |
| `constitution_bootstrap --force` overwrites | ✅ | ⚪ | ⚪ | ⚪ | Force flag |
| `_maybe_bootstrap_constitution()` auto mode | ✅ | ⚪ | ⚪ | ⚪ | auto_bootstrap='auto' |
| `_maybe_bootstrap_constitution()` prompt mode | ✅ | ⚪ | ⚪ | ⚪ | auto_bootstrap='prompt' |

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
| `sw run new_feature` full cycle | ❌ | ❌ | ✅ | ⚪ | Pipeline start + abort + constitution E2E |
| `sw run --selector nhop` | ❌ | ❌ | ✅ | ⚪ | Topology selectors via review E2E |
| `sw run` interrupted → state saved | ✅ | ❌ | ❌ | ⚪ | Unit mock only |

### 1.7 `projects.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `init` / `use` / `projects` / `remove` / `update` / `scan` | ✅ | ✅ | ✅ | ⚪ | — |
| `sw init` existing project → scan hint | ✅ | ⚪ | ⚪ | ⚪ | Prints `sw standards scan` hint |
| `sw init` new project → no scan hint | ✅ | ⚪ | ⚪ | ⚪ | Clean init |
| `sw init` scan hint respects `--no-hints` | ✅ | ⚪ | ⚪ | ⚪ | Suppression flag |
| `sw init` scan hint console output | ✅ | ⚪ | ⚪ | ⚪ | Rich text check |

### 1.8 `review.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `draft()` interactive spec drafting | ✅ | ❌ | ⚪ | ⚪ | No integ for HITL loop |
| `review()` spec/code review | ✅ | ✅ | ✅ | ⚪ | — |
| `_execute_review()` asyncio handling | ✅ | ✅ | ⚪ | ⚪ | — |
| `_display_review_result()` exit codes | ✅ | ✅ | ⚪ | ⚪ | — |
| `sw review` with topology context | ❌ | ❌ | ✅ | ⚪ | nhop/impact/no-topology E2E tests |
| `sw review` with constitution | ✅ | ✅ | ✅ | ⚪ | — |
| `sw draft` user feedback mid-draft | ❌ | ❌ | ❌ | ⚪ | Not tested |
| `sw draft` interrupted → partial discard | ❌ | ❌ | ❌ | ⚪ | Not tested |

### 1.9 `standards.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `standards_scan()` scan project | ✅ | ✅ | ✅ | ⚪ | Multi-scope + HITL, --no-review |
| `standards_show()` display stored | ✅ | ✅ | ✅ | ⚪ | 7 unit + 2 integ + 2 e2e |
| `standards_clear()` clear stored | ✅ | ✅ | ✅ | ⚪ | 5 unit + 2 integ + 1 e2e |
| `standards_scopes()` summary table | ✅ | ❌ | ⚪ | ⚪ | 5 unit tests |
| `_file_in_scope()` scope filter | ✅ | ❌ | ⚪ | ⚪ | 5 unit tests |
| `_load_standards_content()` formatting | ✅ | ✅ | ✅ | ⚪ | 7 unit + 1 integ + 1 e2e |
| `scan --scope` single-scope scan | ✅ | ❌ | ⚪ | ⚪ | 1 unit test |
| `scan` confirmed_by='hitl' / None | ✅ | ❌ | ⚪ | ⚪ | 1 unit test |
| Re-scan overwrites existing standards | ✅ | ✅ | ✅ | ⚪ | Unit + integ + e2e |
| Scan with confidence boundary (exactly 0.3) | ✅ | ⚪ | ⚪ | ⚪ | Boundary tested |
| SyntaxError file graceful degradation | ✅ | ✅ | ⚪ | ⚪ | Skips bad file, still analyzes good ones |
| `.specweaverignore` filtering | ✅ | ✅ | ⚪ | ⚪ | Glob/negation/dir patterns |
| `_save_accepted_standards()` writes to DB | ✅ | ⚪ | ⚪ | ⚪ | 3 unit (save, scope, overwrite) |
| `_save_accepted_standards()` confirmed_by field | ✅ | ⚪ | ⚪ | ⚪ | hitl vs None |
| `_maybe_bootstrap_constitution()` hint after scan | ✅ | ⚪ | ⚪ | ⚪ | Prints bootstrap cmd |
| Scan end-to-end with auto-bootstrap | ✅ | ⚪ | ⚪ | ⚪ | auto mode triggers bootstrap |

### 1.10 `validation.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `_apply_override` / `_load_check_settings` | ✅ | ✅ | ⚪ | ⚪ | — |
| `_resolve_pipeline_name` — all precedence branches | ✅ | ✅ | ✅ | ⚪ | Profile-override E2E: set-profile then check |
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
| Schema v6→v7 migration (`auto_bootstrap_constitution`) | ✅ | ⚪ | ⚪ | ⚪ | Column exists, default 'prompt' |

### 2.2 `profiles.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `DomainProfile` / `get_profile` / `list_profiles` | ✅ | ✅ | ✅ | ⚪ | — |
| `_extract_description()` missing field / OSError | ✅ | ⚪ | ⚪ | ⚪ | Feature 3.5b |
| `profile_exists` / `profile_to_pipeline_name` | ✅ | ⚪ | ⚪ | ⚪ | — |
| Custom profile overrides built-in in listing | ✅ | ⚪ | ⚪ | ⚪ | Feature 3.5b |

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
| `ContextInferrer.infer_and_write()` | ✅ | ✅ | ✅ | ⚪ | E2E via sw scan → context.yaml generated |
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
| `RichPipelineDisplay.on_event` unknown event | ✅ | ❌ | ❌ | ⚪ | Graceful ignore |
| `RichPipelineDisplay` run_started missing `total_steps` | ✅ | ❌ | ❌ | ⚪ | Graceful default |
| `RichPipelineDisplay` loop_back missing step target in history | ✅ | ❌ | ❌ | ⚪ | Edge case |
| `RichPipelineDisplay` gate_result logs (advance/stop/etc) | ✅ | ✅ | ❌ | ⚪ | Visual feedback |
| `JsonPipelineDisplay.on_event` serialization error | ✅ | ❌ | ❌ | ⚪ | Unhandled object safety |
| Display with 10+ step pipeline | ❌ | ❌ | ⚪ | ⚪ | Only 2-step tested |
| Display with PARKED status (HITL gate) | ❌ | ✅ | ⚪ | ⚪ | Integration tested |

### 5.2 `gates.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| HITL passed (result == PASSED) | ✅ | ✅ | ❌ | ⚪ | Gate advance |
| HITL failed (result == FAILED) | ✅ | ✅ | ❌ | ⚪ | Gate on_fail |
| AUTO / ACCEPTED `output` missing verdict | ✅ | ✅ | ❌ | ⚪ | Graceful fallback |
| `on_fail` RETRY limits | ✅ | ✅ | ❌ | ⚪ | Escalate to stop |
| `on_fail` LOOP_BACK limits | ✅ | ✅ | ❌ | ⚪ | Max loops boundary |
| `inject_feedback` missing loop target | ✅ | ✅ | ❌ | ⚪ | Prevents crash |
| Graceful fallback on unmapped or missing gate data | ✅ | ✅ | ❌ | ⚪ | Enums/Missing steps |

### 5.3 `handlers.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `ValidateSpecHandler` normal execute | ✅ | ✅ | ✅ | ⚪ | Core function |
| `ValidateSpecHandler` atom run exception catch | ✅ | ✅ | ❌ | ⚪ | Prevents runner crash |
| `ValidateCodeHandler` no `output_dir` or files | ✅ | ✅ | ❌ | ⚪ | Skips/fails code val |
| `ValidateCodeHandler` atom run exception catch | ✅ | ✅ | ❌ | ⚪ | Prevents runner crash |
| `ReviewSpecHandler.execute()` mock LLM review | ❌ | ❌ | ✅ | ⚪ | Tested in CLI E2E + new_feature E2E |
| `ReviewCodeHandler.execute()` mock LLM review | ❌ | ❌ | ✅ | ⚪ | Tested in CLI E2E |
| `GenerateCodeHandler.execute()` mock LLM prompt | ❌ | ✅ | ✅ | ⚪ | Tested in CLI E2E |
| `GenerateTestsHandler.execute()` mock LLM tests | ❌ | ❌ | ❌ | ⚪ | Missing coverage entirely |
| `ValidateTestsHandler` tests fail / exception | ✅ | ❌ | ❌ | ⚪ | Fallback / crash prevent |
| `LintFixHandler` exhaustion of reflections | ✅ | ❌ | ❌ | ⚪ | Reflections max hit |
| `LintFixHandler` LLM exception during reflection | ✅ | ❌ | ❌ | ⚪ | Fails step cleanly |
| `DraftSpecHandler` spec exists | ✅ | ❌ | ❌ | ⚪ | Skips execution |

### 5.4 `models.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| All models and enums | ✅ | ✅ | ⚪ | ⚪ | — |
| `PipelineDefinition.validate_flow()` combos | ✅ | ❌ | ❌ | ⚪ | Target limits |
| Gate `loop_target` validation | ✅ | ❌ | ❌ | ⚪ | Infinite loop guard |

### 5.5 `parser.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `load_pipeline()` normal parsing | ✅ | ✅ | ✅ | ⚪ | — |
| `list_bundled_pipelines()` | ✅ | ✅ | ⚪ | ⚪ | — |
| `load_pipeline()` invalid YAML syntax | ✅ | ✅ | ❌ | ⚪ | Parser errors cleanly |
| Pipeline native ModuleNotFoundError interception | ✅ | ✅ | ❌ | ⚪ | Bundled template missing |

### 5.6 `runner.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `PipelineRunner.run()` general path | ✅ | ✅ | ✅ | ⚪ | — |
| `PipelineRunner.run()` empty pipeline | ✅ | ✅ | ✅ | ⚪ | Immediate complete |
| handler `.execute()` throws exception externally | ✅ | ✅ | ❌ | ⚪ | Captures unknown errors |
| runner evaluating AUTO gate `stop`/`retry` | ✅ | ✅ | ✅ | ⚪ | — |
| runner evaluating gate HITL `park` | ✅ | ✅ | ✅ | ⚪ | — |
| runner evaluating gate `loop_back` | ✅ | ✅ | ✅ | ⚪ | — |

### 5.7 `state.py` + `store.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `PipelineRun.complete_current_step` past end | ✅ | ✅ | ❌ | ⚪ | No-op bounds check |
| `StateStore.get_latest_run` without existing | ✅ | ✅ | ❌ | ⚪ | Returns None |
| `StateStore.load_run` corrupt JSON load | ✅ | ❌ | ❌ | ⚪ | Unhandled JSON decoder error |
| Store survives process restart (real file) | ❌ | ✅ | ✅ | ⚪ | Tested in Integ/E2E via SQLite |

---

## 6 · Graph (`graph/`)

### 6.1 `selectors.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `DirectNeighborSelector.select()` | ✅ | ❌ | ✅ | ⚪ | E2E via --selector direct |
| `NHopConstraintSelector.select()` | ✅ | ❌ | ✅ | ⚪ | E2E via --selector nhop |
| `ConstraintOnlySelector.select()` | ✅ | ❌ | ✅ | ⚪ | E2E via --selector constraint |
| `ImpactWeightedSelector.select()` | ✅ | ❌ | ✅ | ⚪ | E2E via --selector impact |
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
| `_auto_infer_missing()` partial context.yaml | ✅ | ❌ | ⚪ | ⚪ | 4 unit tests (skips hidden, all-covered, mixed, no-python) |

---

## 7 · Implementation (`implementation/`)

### 7.1 `generator.py`

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `Generator.generate_code()` — happy path | ✅ | ❌ | ✅ | ⚪ | Unit via standards injection test; E2E via lifecycle |
| `Generator.generate_code()` — with standards injected | ✅ | ❌ | ⚪ | ⚪ | `tests/unit/implementation/test_generator_standards.py` |
| `Generator.generate_code()` — without standards | ✅ | ❌ | ⚪ | ⚪ | Same file |
| `Generator.generate_tests()` — with standards | ✅ | ❌ | ❌ | ⚪ | Same file |
| `Generator.generate_tests()` — without standards | ✅ | ❌ | ❌ | ⚪ | Same file |
| `Generator` — standards + constitution both injected | ✅ | ❌ | ❌ | ⚪ | Same file |
| `Generator` — output file still written | ✅ | ❌ | ❌ | ⚪ | Same file |
| `Generator._clean_code_output()` fence stripping | ❌ | ❌ | ✅ | ⚪ | E2E only |
| Generate code with constitution (standalone) | ❌ | ❌ | ❌ | ⚪ | Not tested in isolation |
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
| `find_constitution()` walk-up, override, BOM | ✅ | ✅ | ✅ | ⚪ | Unit + integ/constitution + E2E |
| `find_all_constitutions()` | ✅ | ✅ | ⚪ | ⚪ | 4 integ tests (scaffold, walk-up) |
| `check_constitution()` size limits | ✅ | ✅ | ✅ | ⚪ | Unit + `test_db_max_size_controls_check` |
| `generate_constitution()` | ✅ | ✅ | ✅ | ⚪ | Scaffold integration tests |
| `generate_constitution_from_standards()` happy path | ✅ | ⚪ | ⚪ | ⚪ | Multi-language standards |
| `generate_constitution_from_standards()` empty standards | ✅ | ⚪ | ⚪ | ⚪ | Raises ValueError |
| `generate_constitution_from_standards()` OSError on write | ✅ | ⚪ | ⚪ | ⚪ | Read-only dir handling |
| `_build_tech_stack_rows()` language-to-row map | ✅ | ⚪ | ⚪ | ⚪ | Python/JS/TS rows |
| `_build_tech_stack_rows()` empty standards | ✅ | ⚪ | ⚪ | ⚪ | Returns empty |
| `_build_standards_section()` formatting | ✅ | ⚪ | ⚪ | ⚪ | Category grouping |
| `_build_standards_section()` special chars in values | ✅ | ⚪ | ⚪ | ⚪ | Pipe/backslash escaping |
| `is_unmodified_template()` TODO marker check | ✅ | ⚪ | ⚪ | ⚪ | Detects starter template |
| Logging: find/generate/oversize | ✅ | ✅ | ⚪ | ⚪ | 4 tests in `TestConstitutionLogging` |

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
| Reviewer with topology context in prompt | ❌ | ❌ | ✅ | ⚪ | E2E via nhop/impact selector tests |
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
| `_git_ls_files()` | ✅ | ❌ | ⚪ | ⚪ | 6 unit tests via monkeypatch (nonzero, timeout, OSError, deleted file, blank lines, success) |
| `_walk_with_skips()` | ✅ | ❌ | ⚪ | ⚪ | — |
| `_apply_specweaverignore()` | ✅ | ❌ | ⚪ | ⚪ | 4 unit tests (not-installed, external file, dir pattern, negation pattern) |
| Discovery with `.specweaverignore` | ✅ | ❌ | ⚪ | ⚪ | 3 unit tests (pattern, glob, missing file) |
| Discovery with `git ls-files` | ✅ | ❌ | ⚪ | ⚪ | gitignore respect + fallback tested |
| Discovery on non-git directory | ✅ | ❌ | ⚪ | ⚪ | TestWalkWithSkips covers all cases |

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

### 12.5 `scope_detector.py` *(Feature 3.5a-2)*

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `detect_scopes()` — empty/flat/L1/L2 | ✅ | ⚪ | ⚪ | ⚪ | 12 unit tests |
| `detect_scopes()` — skip dirs + hidden dirs | ✅ | ⚪ | ⚪ | ⚪ | — |
| `detect_scopes()` — depth cap at 2 levels | ✅ | ⚪ | ⚪ | ⚪ | — |
| `detect_scopes()` — sorted output | ✅ | ⚪ | ⚪ | ⚪ | — |
| `detect_scopes()` — PermissionError handling | ✅ | ⚪ | ⚪ | ⚪ | 1 unit test (mocked) |
| `_has_source_files()` all extensions + edge | ✅ | ⚪ | ⚪ | ⚪ | 7 unit tests |
| `_has_source_files()` — PermissionError | ✅ | ⚪ | ⚪ | ⚪ | 1 unit test |
| `_resolve_scope()` — all paths | ✅ | ⚪ | ⚪ | ⚪ | 8 unit tests |
| `_resolve_scope()` — target outside project | ✅ | ⚪ | ⚪ | ⚪ | ValueError path tested |
| L2 hidden/skip dirs filtering | ✅ | ⚪ | ⚪ | ⚪ | 2 unit tests |
| Mixed L1-only + L1/L2 layouts | ✅ | ⚪ | ⚪ | ⚪ | 2 unit tests |
| Multi-scope detect on monorepo | ⚪ | ❌ | ❌ | ⚪ | End-to-end path |

### 12.6 `reviewer.py` *(Feature 3.5a-2)*

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| Accept/Reject/Edit/AcceptAll/SkipScope | ✅ | ⚪ | ⚪ | ⚪ | 6 unit tests |
| Multi-scope combined review | ✅ | ⚪ | ⚪ | ⚪ | — |
| Empty results → empty dict | ✅ | ⚪ | ⚪ | ⚪ | — |
| Re-scan diff shown | ✅ | ⚪ | ⚪ | ⚪ | — |
| Auto-accept unchanged HITL-confirmed | ✅ | ⚪ | ⚪ | ⚪ | — |
| Edit with non-dict JSON → retry | ✅ | ⚪ | ⚪ | ⚪ | 1 unit test |
| HITL confirmed but data changed → prompt | ✅ | ⚪ | ⚪ | ⚪ | 1 unit test |
| Accept All on first/last category | ✅ | ⚪ | ⚪ | ⚪ | 2 unit tests |
| Skip scope then next scope proceeds | ✅ | ⚪ | ⚪ | ⚪ | 1 unit test |
| Scope review order is sorted | ✅ | ⚪ | ⚪ | ⚪ | 1 unit test |
| Show methods render without crash | ✅ | ⚪ | ⚪ | ⚪ | 3 unit tests |
| Existing category not in results | ✅ | ⚪ | ⚪ | ⚪ | 1 unit test |

### 12.7 `scanner.py` *(Feature 3.5a-3)*

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `StandardsScanner.scan()` empty files | ✅ | ⚪ | ⚪ | ⚪ | 1 unit test |
| `StandardsScanner.scan()` groups by extension | ✅ | ⚪ | ⚪ | ⚪ | 1 unit test |
| `StandardsScanner.scan()` skips unknown | ✅ | ⚪ | ⚪ | ⚪ | 1 unit test |

### 12.8 `enricher.py` *(Feature 3.5a-3)*

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `enrich()` filters by confidence | ✅ | ⚪ | ⚪ | ⚪ | LLM conditionally triggered |
| `enrich()` handles LLM invalid JSON | ✅ | ⚪ | ⚪ | ⚪ | Fallback correctly |
| `enrich()` with force_compare | ✅ | ⚪ | ⚪ | ⚪ | 1 unit test |

### 12.9 `tree_sitter_base.py` *(Feature 3.5a-3)*

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `extract_all()` loops and yields single pass | ✅ | ⚪ | ⚪ | ⚪ | 1 unit test |
| `extract_all()` tolerates extractor unhandled exception | ✅ | ⚪ | ⚪ | ⚪ | 1 unit test |

### 12.10 `languages/javascript/analyzer.py` & `languages/typescript/analyzer.py` *(Feature 3.5a-3)*

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| Detects async functions, promises, await | ✅ | ⚪ | ⚪ | ⚪ | Unit tests in both JS/TS |
| Detects naming paradigms (camelCase/PascalCase) | ✅ | ⚪ | ⚪ | ⚪ | Unit tests in both JS/TS |
| Detects JSDoc / TSDoc | ✅ | ⚪ | ⚪ | ⚪ | Unit tests |

---

## 13 · Validation (`validation/`)

### 13.1 Rules S01–S11 (spec rules)

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| S01 One-Sentence pass/fail/edge | ✅ | ✅ | ✅ | ⚪ | All rules fire E2E in test_validation_pipeline_e2e |
| S02 Single Setup pass/fail | ✅ | ✅ | ✅ | ⚪ | — |
| S03 Stranger Test pass/fail | ✅ | ✅ | ✅ | ⚪ | — |
| S04 Dependency Direction pass/fail | ✅ | ✅ | ✅ | ⚪ | — |
| S05 Day Test pass/fail | ✅ | ✅ | ✅ | ⚪ | — |
| S06 Concrete Example pass/fail | ✅ | ✅ | ✅ | ⚪ | — |
| S07 Test-First extraction/scoring/thresholds | ✅ | ✅ | ✅ | ⚪ | — |
| S08 Ambiguity pass/warn/fail | ✅ | ✅ | ✅ | ⚪ | — |
| S09 Error Path keywords/policy/empty | ✅ | ✅ | ✅ | ⚪ | — |
| S10 Done Definition pass/fail | ✅ | ✅ | ✅ | ⚪ | — |
| S11 Terminology casing/undefined | ✅ | ✅ | ✅ | ⚪ | — |

### 13.2 Rules C01–C08 (code rules)

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| C01 Syntax Valid | ✅ | ✅ | ✅ | ⚪ | E2E via test_code_validation_pipeline |
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
| C06 No Bare Except | ✅ | ✅ | ✅ | ⚪ | E2E: violations detected in test_code_validation_pipeline |
| C07 No Orphan TODO | ✅ | ✅ | ✅ | ⚪ | E2E: violations detected in test_code_validation_pipeline |
| C08 Type Hints | ✅ | ✅ | ✅ | ⚪ | E2E via test_code_validation_pipeline |

### 13.3 Infrastructure (executor, loader, registry, runner, etc.)

| Story | Unit | Integ | E2E | Perf | Notes |
|-------|:----:|:-----:|:---:|:----:|-------|
| `execute_validation_pipeline()` | ✅ | ✅ | ⚪ | ⚪ | — |
| `apply_settings_to_pipeline()` | ✅ | ✅ | ⚪ | ⚪ | — |
| `resolve_pipeline()` inheritance | ✅ | ⚪ | ⚪ | ⚪ | — |
| `_validate_loop_back()` | ❌ | ❌ | ⚪ | ⚪ | — |
| `_build_rule_kwargs()` — all kwargs scenarios | ✅ | ⚪ | ⚪ | ⚪ | 12+ unit tests (Feature 3.5b) |
| `_build_rule_kwargs()` — None settings / empty PARAM_MAP | ✅ | ⚪ | ⚪ | ⚪ | Feature 3.5b |
| `_get_rule_id_from_cls()` — all 9 configurable rules | ✅ | ⚪ | ⚪ | ⚪ | Feature 3.5b |
| `Rule.PARAM_MAP` ABC default + per-rule contracts (9 rules) | ✅ | ⚪ | ⚪ | ⚪ | Feature 3.5b |
| Removed legacy `get_spec_rules/get_code_rules` (negative) | ✅ | ⚪ | ⚪ | ⚪ | Feature 3.5b |
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

## Implemented E2E Tests (2026-03-22 additions)

### `test_new_feature_e2e.py` — Flow Engine Pipeline (4 tests)

| # | Test Name | Story Covered | Status |
|---|-----------|--------------|--------|
| 1 | `test_new_feature_validate_spec_step_runs` | Pipeline starts, first step executes without crash | ✅ |
| 3 | `test_new_feature_validation_fails_stops` | Spec fails validation → pipeline aborts (exit 1) | ✅ |
| 5 | `test_new_feature_llm_error_mid_pipeline` | LLM raises GenerationError → clean ERROR verdict | ✅ |
| 6 | `test_new_feature_with_constitution` | CONSTITUTION.md injected into review prompt | ✅ |
| 2 | ~~`test_new_feature_review_denied_loops_back`~~ | Requires real HITL session — covered at integration level | ⚪ |
| 4 | ~~`test_new_feature_hitl_parks_and_resumes`~~ | Requires real HITL session — covered at integration level | ⚪ |
| 7 | `test_new_feature_with_topology` | Topology context with selectors — see `test_topology_e2e.py` | ✅ |

### `test_multi_project_e2e.py` — Cross-Project Workflows (3 tests)

| # | Test Name | Story Covered | Status |
|---|-----------|--------------|--------|
| 8 | `test_two_projects_switch_and_operate` | Init P1+P2 → switch → no contamination | ✅ |
| 9 | `test_remove_project_operations_on_remaining` | Remove P1 → P2 still works | ✅ |
| 10 | `test_update_project_path_uses_new` | `sw update NAME path VALUE` → subsequent ops use new path | ✅ |

### `test_standards_e2e.py` — Standards Discovery Workflow (4 tests — already existed)

| # | Test Name | Story Covered | Status |
|---|-----------|--------------|--------|
| 11 | `test_full_lifecycle_scan_show_clear` | `sw standards scan → show → clear → show (empty)` | ✅ |
| 12 | `test_scan_discovers_expected_patterns` | Scan detects snake_case + PascalCase | ✅ |
| 13 | `test_standards_reach_load_standards_content` | Standards content available via `_load_standards_content()` | ✅ |
| 14 | `test_rescan_after_code_change` | Re-scan after code change — upsert works | ✅ |

### `test_validation_pipeline_e2e.py` — Pipeline Variants (5 tests)

| # | Test Name | Story Covered | Status |
|---|-----------|--------------|--------|
| 15 | `test_validate_only_all_rules_fire` | All 11 spec rules (S01–S11) appear in output | ✅ |
| 16 | `test_validate_only_with_profile_override` | `web-app` profile → sw check adapts to profile pipeline | ✅ |
| 17 | `test_validate_only_with_disable_override` | `--set S01.enabled=false` → S01 absent from output | ✅ |
| 18 | `test_code_validation_pipeline` | C01/C06/C07/C08 fire on Python file | ✅ |
| +  | `test_code_validation_detects_violations` | C06/C07 report FAIL on known-bad code | ✅ |

### `test_topology_e2e.py` — Context/Topology Integration (7 tests)

| # | Test Name | Story Covered | Status |
|---|-----------|--------------|--------|
| 19 | `test_scan_generates_context_yaml` | `sw scan` auto-generates context.yaml per module | ✅ |
| +  | `test_scan_skips_modules_with_existing_context` | Existing context.yaml not overwritten | ✅ |
| 20 | `test_review_with_nhop_selector` | `--selector nhop` → proceeds without crash | ✅ |
| 21 | `test_review_with_impact_selector` | `--selector impact` → proceeds without crash | ✅ |
| 22 | `test_review_with_no_topology` | No context.yaml → review works (graceful degradation) | ✅ |
| +  | `test_review_with_all_selector_types_no_topology` | All 4 selectors work when no topology present | ✅ |

### `test_flow_engine_e2e.py` — Flow Engine Seam (Deferred)

| # | Test Name | Story Covered | Status |
|---|-----------|--------------|--------|
| 23 | ~~`test_sw_run_new_feature_hitl_interaction`~~ | Requires live HITL driver at CLI level — deferred | ⚪ |
| 24 | ~~`test_sw_run_loop_back_reflection`~~ | Covered at integration/flow/ level — deferred | ⚪ |
| 25 | ~~`test_cli_to_runner_integration`~~ | Covered by `test_pipeline_e2e.py` — deferred | ⚪ |
