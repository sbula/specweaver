# SpecWeaver MVP — Implementation Roadmap

> **Status**: 📜 HISTORICAL — This document reflects the original implementation plan from March 2026. The actual codebase has evolved significantly. For current architecture, see [README.md](../../README.md).
> **Date**: 2026-03-08 (updated 2026-03-10 — loom layer implemented)
> **Purpose**: Technical implementation plan for the SpecWeaver MVP. Covers source reuse from flowManager, framework decisions, architecture decisions, module-by-module build plan, and verification strategy.

---

## 1. Source Reuse from FlowManager

### 1.1 Directly Reusable (Copy + Adapt)

These modules are production-quality, well-tested, and map directly to SpecWeaver's MVP needs.

| flowManager Source | SW Target | LOC | Modifications Needed |
|:---|:---|---:|:---|
| `src/flow/llm/provider.py` | `src/specweaver/llm/adapter.py` | 170 | Rewrite to new async `LLMAdapter` ABC (see §2.4). Use as reference for lifecycle patterns. |
| `src/flow/llm/errors.py` | `src/specweaver/llm/errors.py` | 88 | Keep as-is. Remove `ProfileNotFoundError`, `FactoryClosedError`, `MissingDependencyError` (factory-pattern-specific). Keep 5 core errors. |
| `src/flow/llm/adapters/gemini_adapter.py` | `src/specweaver/llm/gemini_adapter.py` | 515 | Rewrite against latest `google-genai` SDK. Implement new async `LLMAdapter` interface. Keep API key + ADC auth. Remove Vertex AI, keyring, `embed()`. |
| `src/flow/engine/security.py` | `src/specweaver/project/safepath.py` | 73 | Remove `from flow.engine.models import SecurityError` → use local exception. Otherwise as-is. |
| `src/flow/security/redactor.py` | `src/specweaver/llm/redactor.py` | 97 | As-is. Used to sanitize LLM prompts/responses containing project secrets. |

**Total reusable**: ~943 LOC source code.

**Tests also reusable**:

| flowManager Tests | SW Target | Size | Notes |
|:---|:---|---:|:---|
| `tests/unit/llm/test_gemini_adapter.py` | `tests/unit/llm/test_gemini_adapter.py` | 13KB | Adapt imports, remove embed tests |
| `tests/unit/llm/test_provider_lifecycle.py` | `tests/unit/llm/test_adapter_lifecycle.py` | 10KB | Rename references |
| `tests/unit/llm/test_input_validation.py` | `tests/unit/llm/test_input_validation.py` | 17KB | Adapt imports |
| `tests/unit/llm/test_auth.py` | `tests/unit/llm/test_auth.py` | 13KB | Remove keyring/Vertex tests |
| `tests/unit/llm/test_error_retry.py` | `tests/unit/llm/test_error_retry.py` | 18KB | Adapt |
| `tests/unit/llm/conftest.py` | `tests/unit/llm/conftest.py` | 13KB | Adapt |

**Total reusable tests**: ~84KB (~6 files). This is a significant head start on the LLM layer test coverage.

---

### 1.2 Partially Reusable (Ideas/Patterns, Rewrite Needed)

| flowManager Source | Useful Pattern | Why Rewrite |
|:---|:---|:---|
| `src/flow/llm/factory.py` (244 LOC) | Thread-safe caching, lazy loading | SW MVP needs only one adapter (Gemini). A factory is overkill. Replace with a simple `create_adapter(config)` function. Post-MVP can upgrade to factory pattern. |
| `src/flow/engine/loom.py` (97 LOC) | Surgical file editing with SafePath + optimistic locking | SW's `implementation/generator.py` writes NEW files (not edit existing ones). Loom is post-MVP — relevant when SW edits existing code. |
| `pyproject.toml` | Dependency structure, tool config (pytest, black, isort) | Different package name, different deps, different structure. Use as template. |
| `tests/unit/llm/test_factory.py` (17KB) | Factory lifecycle tests | Not needed for MVP (no factory). |
| `tests/unit/llm/test_contract_and_edge_cases.py` (17KB) | Edge case patterns | Cherry-pick relevant patterns, not whole-file copy. |

---

### 1.3 NOT Reusable (FlowManager-Specific)

| Module | Why |
|:---|:---|
| `src/flow/domain/` (parser, models, persister — 34KB) | Status domain model specific to flowManager workflows |
| `src/flow/engine/core.py` (28KB) | Flow execution engine — completely different from SW |
| `src/flow/atoms/` (27KB) | Workflow atoms — not applicable |
| `src/flow/skills/` (33KB) | Agent skills — not applicable |
| `src/flow/tools/` (14 files) | Shell/file/knowledge tools — patterns partially reused in loom layer |
| `src/flow/workflows/` | Workflow definitions — not applicable |
| `src/flow/engine/events.py` | Event bus — not applicable |
| `src/flow/engine/redactor.py` | Simpler redactor (1KB) — use `security/redactor.py` instead |

---

## 2. Frameworks & Dependencies

> [!NOTE]
> All choices below are based on web research conducted March 2026, comparing current community recommendations, latest stable versions, and ecosystem trends.

### 2.1 Build System: **uv** (replaces Poetry)

| | Poetry (flowManager used) | **uv** (recommended) |
|:---|:---|:---|
| Speed | Slow dependency resolution | **10-100x faster** (Rust-based) |
| Scope | All-in-one project manager | All-in-one: replaces pip, pip-tools, pyenv, virtualenv, poetry |
| Lockfile | `poetry.lock` | `uv.lock` (human-readable TOML, cross-platform) |
| `pyproject.toml` | Custom `[tool.poetry]` keys | **PEP 621 native** (`[project]` section) |
| Version | Mature but slower | v0.10.9 (March 2026), rapidly adopted |
| Community | Still widely used | **2026 community favorite** for new projects |

**Decision: `uv`**. Faster, standards-compliant, actively gaining adoption. `uv init`, `uv add`, `uv run` cover all MVP needs.

### 2.2 Production Dependencies

| Package | Purpose | Version | Why This One |
|:---|:---|:---|:---|
| **typer[all]** | CLI framework (includes Rich + Click) | `^0.21` | Community consensus: best for new Python CLIs. Type-hint-based, minimal boilerplate, automatic help/completions. FM already uses it. |
| **rich** | Terminal formatting, progress bars, tables | Bundled with typer[all] | — |
| **google-genai** | Gemini API SDK (latest) | `^1.0.0` | **GA since May 2025**. Replaces deprecated `google-generativeai`. Must use latest version. |
| **pydantic** | Data models for RuleResult, config, findings + `BaseSettings` for config loading | `^2.12` | v2 Rust backend. `BaseSettings` auto-resolves env vars + `.env` files for type-safe config. |
| **pydantic-settings** | `BaseSettings` support (separate package since Pydantic v2) | `^2.0` | Required for env var + `.env` auto-loading. |
| **python-dotenv** | `.env` file loading for API keys | `^1.0` | Community standard for local dev. Keys in `.env`, NOT in config.yaml. |
| **ruamel.yaml** | `.specweaver/config.yaml` parsing | `^0.18` | **Replaces PyYAML**. YAML 1.2, preserves comments in round-trip edits. |
| **jinja2** | Template rendering for spec templates & LLM prompts | `^3.1` | Still the standard for LLM prompt templating. |

> [!NOTE]
> **No chromadb, tree-sitter, numpy** — those were flowManager-specific (RAG, AST parsing). SW MVP doesn't need them. Keeps the dependency footprint small.

### 2.3 Dev Dependencies

| Package | Purpose | Why |
|:---|:---|:---|
| **pytest** | Test runner | Industry standard, no alternative needed |
| **pytest-cov** | Coverage measurement (target: 70-90%) | Standard pytest plugin |
| **ruff** | Linting **AND** formatting | **Replaces flake8 + black + isort** as a single tool. Rust-based, 500+ rules, adopted by FastAPI/pandas/Pydantic. The 2026 community standard. |
| **mypy** | Type checking | Still the leading type checker for Python |

---

### 2.4 Common LLM Adapter Interface (Research-Backed)

> [!NOTE]
> Designed to cover Google Gemini, OpenAI, Anthropic, Mistral, Ollama, vLLM, and Qwen. MVP implements Gemini only; other adapters are drop-in additions.

```python
# src/specweaver/llm/models.py
class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class GenerationConfig(BaseModel):
    model: str
    temperature: float = 0.7
    max_output_tokens: int = 4096
    response_format: Literal["text", "json"] = "text"
    # Future: tools, top_p, stop_sequences

class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class LLMResponse(BaseModel):
    text: str
    model: str
    usage: TokenUsage
    finish_reason: str  # "stop", "max_tokens", "error"

# src/specweaver/llm/adapter.py
class LLMAdapter(ABC):
    @abstractmethod
    async def generate(self, messages: list[Message], config: GenerationConfig) -> LLMResponse: ...

    @abstractmethod
    async def generate_stream(self, messages: list[Message], config: GenerationConfig) -> AsyncIterator[str]: ...

    @abstractmethod
    def available(self) -> bool: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...
```

**Provider coverage** (all share the same Message/Config/Response shape):

| Provider | SDK | Native or OpenAI-compat? |
|:---|:---|:---|
| Google Gemini | `google-genai` | Native (MVP) |
| OpenAI | `openai` | Native |
| Anthropic | `anthropic` | Native |
| Mistral | `mistralai` | Native |
| Ollama | `ollama` | OpenAI-compatible |
| vLLM | `openai` (client) | OpenAI-compatible |
| Qwen | `openai` / `dashscope` | OpenAI-compatible |

### 2.5 API Key Management

| Priority | Source | Tool | Scope |
|:---|:---|:---|:---|
| 1 | Environment variable | `os.environ["GEMINI_API_KEY"]` | Always works |
| 2 | `.env` file | `python-dotenv` (auto-loaded by Pydantic `BaseSettings`) | Local dev convenience |
| 3 | Config file | `.specweaver/config.yaml` | Model name, temperature — **NOT secrets** |
| 4 (post-MVP) | OS keyring | `keyring` library | Encrypted by OS |

---

## 3. Build From Scratch

These modules have no equivalent in flowManager and must be written new.

### 3.1 Project & Config (~200-300 LOC)

| File | What It Does | Complexity |
|:---|:---|:---|
| `project/discovery.py` | Resolve project path from `--project` flag or `SW_PROJECT` env | Low |
| `project/scaffold.py` | Create `.specweaver/`, `specs/` dirs, default `config.yaml` | Low |
| `config/settings.py` | Load `.specweaver/config.yaml`, env vars, defaults | Low |
| `config/layers.py` | Layer config model (rules, thresholds, templates per layer) | Medium |

### 3.2 Validation Engine (~800-1200 LOC)

| File | What It Does | Complexity |
|:---|:---|:---|
| `validation/models.py` | `Rule`, `RuleResult`, `Finding` interfaces (Pydantic). Finding has: message, line, severity, suggestion | Low |
| `validation/runner.py` | Load rules from YAML registry, run all, collect results, format output | Medium |
| `validation/rules.yaml` | Rule registry: maps rule IDs to Python classes, declares LLM requirement | Low |
| **Spec Rules** (10 files, ~50-80 LOC each): | | |
| `s01_one_sentence.py` | Conjunction count in Purpose section | Low |
| `s02_single_setup.py` | H2/H3 section count heuristic | Low |
| `s03_stranger.py` | LLM: summarize from Purpose alone | Medium (LLM) |
| `s04_dependency_dir.py` | Cross-reference direction scan + dead-link detection (traceability) | Medium |
| `s05_day_test.py` | Word/section count complexity score | Low |
| `s06_concrete_example.py` | Code block presence in Contract | Low |
| `s07_test_first.py` | LLM: generate test from Contract alone | Medium (LLM) |
| `s08_ambiguity.py` | Weasel word regex scan | Low |
| `s09_error_path.py` | Error/failure keyword search | Low |
| `s10_done_definition.py` | Verification section check | Low |
| `s11_terminology.py` | Inconsistent casing + undefined domain term detection | Medium |
| **Code Rules** (8 files, ~30-60 LOC each): | | |
| `c01_syntax_valid.py` | `import` check via `ast.parse` | Low |
| `c02_tests_exist.py` | Test file presence check | Low |
| `c03_tests_pass.py` | `pytest` subprocess execution | Medium |
| `c04_coverage.py` | Coverage ≥ threshold via pytest-cov | Medium |
| `c05_import_direction.py` | AST import analysis | Medium |
| `c06_no_bare_except.py` | AST `ExceptHandler` scan | Low |
| `c07_no_orphan_todo.py` | TODO/FIXME grep | Low |
| `c08_type_hints.py` | AST annotation check | Low |

### 3.3 Drafting (~200-300 LOC)

| File | What It Does | Complexity |
|:---|:---|:---|
| `context/provider.py` | `ContextProvider` ABC | Low |
| `context/hitl_provider.py` | Interactive HITL question loop (Rich prompts) | Medium |
| `drafting/drafter.py` | Drives template-based spec drafting with LLM + context providers | High |

### 3.4 Review (~150-200 LOC)

| File | What It Does | Complexity |
|:---|:---|:---|
| `review/reviewer.py` | Unified spec/code reviewer — sends prompt, parses ACCEPTED/DENIED | Medium |
| `review/prompts/spec_review.md` | LLM prompt for spec semantic review | Medium (prompt design) |
| `review/prompts/code_review.md` | LLM prompt for code review vs spec | Medium (prompt design) |

### 3.5 Implementation (~200-300 LOC)

| File | What It Does | Complexity |
|:---|:---|:---|
| `implementation/generator.py` | Reads spec, generates Python source via LLM | High |
| `implementation/test_generator.py` | Reads spec examples, generates test file via LLM | High |

### 3.6 CLI (~200-300 LOC)

| File | What It Does | Complexity |
|:---|:---|:---|
| `cli.py` | Typer app: `sw init`, `sw check --level=X`, `sw draft`, `sw review`, `sw implement` | Medium |
| `__init__.py` | Package root, version | Low |

### 3.7 Loom: Filesystem Tools & Atoms ✅ COMPLETED (183 tests)

> [!NOTE]
> This section was implemented (2026-03-10) using TDD, achieving complete test coverage across all layers.

| File | What It Does | Status |
|:---|:---|:---|
| `loom/commons/filesystem/executor.py` | `FileExecutor` + `EngineFileExecutor`: Low-level ops (read, write, delete, mkdir, list, exists, stat, move) with path traversal prevention, symlink blocking, protected patterns, atomic writes, Windows ADS blocking | ✅ 54 tests (+6 skipped) |
| `loom/tools/filesystem/tool.py` | `FileSystemTool`: Role-based intent gating, `FolderGrant` boundary enforcement, `find_placement` (keyword MVP), `search_content` (recursive), `_normalize_path` security fix (posixpath.normpath for `../` bypass prevention) | ✅ 66 tests |
| `loom/tools/filesystem/interfaces.py` | 3 role-specific interfaces (`ImplementerFileInterface`, `ReviewerFileInterface`, `DrafterFileInterface`) + `create_filesystem_interface` factory | ✅ 42 tests (+1 skipped) |
| `loom/atoms/filesystem/atom.py` | `FileSystemAtom`: 5 intents — `scaffold`, `backup`, `restore`, `aggregate_context`, `validate_boundaries` (including consumes reference validation) | ✅ 21 tests |
| `context.yaml` | Boundary manifests for both tools and atoms modules | ✅ |

**Architecture:**
```
Agent    ──▶ Interface ──▶ FileSystemTool ──▶ FileExecutor        (commons/)
Engine   ──▶ FileSystemAtom ─────────────────▶ EngineFileExecutor  (commons/)
```

**Total new code**: ~2000 LOC (source + tests)


---

## 4. Implementation Steps

### Step 1: Project Scaffold + CLI Shell (1-2 sessions)

**Create:**
- [x] `pyproject.toml` (uv, PEP 621, core deps)
- [x] `src/specweaver/__init__.py` + `cli.py` (Typer app with stubs)
- [ ] `src/specweaver/config/settings.py` (path resolution)
- [x] `src/specweaver/project/discovery.py` + `scaffold.py` (`sw init`)
- [x] Tests: CLI dispatch, settings, scaffold

**Copy from FM:** Nothing yet.

**Runnable:** `sw --help`, `sw init --project ./test-project`

> [!NOTE]
> CLI uses level-oriented commands: `sw check --level=component spec.md` replaces the earlier `sw validate spec`. MVP supports `--level=component` (spec) and `--level=code` only. Future: `--level=feature`, `--level=class`, `--level=function`, and language-specific code rules.

---

### Step 2: Validation Engine + Static Spec Rules (2-3 sessions)

**Create:**
- `validation/models.py`, `validation/runner.py`
- 8 static spec rules: S01, S02, S05, S06, S08, S09, S10, S11
- Test fixtures: good/bad specs
- Per-rule unit tests + runner integration test

**Copy from FM:** Nothing.

**Runnable:** `sw check --level=component good_spec.md` → all PASS

---

### Step 3: LLM Adapter + Remaining Rules (2-3 sessions)

**Copy from FM:**
- `llm/provider.py` → `llm/adapter.py` (simplified)
- `llm/errors.py` (trimmed)
- `llm/adapters/gemini_adapter.py` → `llm/gemini_adapter.py` (simplified)
- `security/redactor.py` → `llm/redactor.py`
- `engine/security.py` → `project/safepath.py`
- LLM test files (adapted)

**Create:**
- 3 remaining spec rules: S03, S04, S07
- Adapter integration with validation runner

**Runnable:** All 11 spec validation rules operational

---

### Step 4: Spec Drafting + Spec Review (2-3 sessions)

**Create:**
- `context/provider.py`, `context/hitl_provider.py`
- `drafting/drafter.py`
- `config/templates/component_spec.md`
- `review/reviewer.py`, `review/prompts/spec_review.md`
- Tests with mocked LLM

**Copy from FM:** Nothing.

**Runnable:** `sw draft greet_service` → interactive session → spec produced

---

### Step 5: Code Generation + Code Validation + Code Review (3-4 sessions)

**Create:**
- `implementation/generator.py`, `implementation/test_generator.py`
- 8 code rules: C01-C08
- `review/prompts/code_review.md`
- `config/layers.py` (per-layer rule config)
- Integration test: `test_full_loop.py`

**Copy from FM:** Nothing.

**Runnable:** Full core loop F2→F3→F4→F5→F6→F7

---

### Step 6: Dogfooding (1-2 sessions)

**Create:** Nothing new.

**Verify:** Run SpecWeaver on its own specs and on a real target project.

---

## 5. Summary: Effort Breakdown

| Category | Estimated LOC | Sessions |
|:---|---:|---:|
| **Copied from FM** (with modifications) | ~750 | 1 |
| **Copied FM tests** (with modifications) | ~2000 (test LOC) | 1 |
| **New code — from scratch** | ~2000-3000 | 8-12 |
| **New tests — from scratch** | ~1500-2500 | included above |
| **Total** | ~4500-6500 | **10-16 sessions** |

> [!IMPORTANT]
> The LLM layer (adapter, errors, Gemini adapter, ~750 LOC + ~2000 LOC of tests) is the **single biggest time save** from flowManager. Building this from scratch would add 3-4 sessions. The validation rules, drafting, and review modules must be built from scratch — they have no FM equivalent.

---

## 6. Verification Plan

### 6.1 Automated Tests

**Command to run all tests:**
```pwsh
cd c:\development\pitbula\specweaver
uv run pytest tests/ -v --cov=src/specweaver --cov-report=term-missing
```

**Test structure:**
```
tests/
├── unit/
│   ├── test_cli.py                  # CLI dispatch
│   ├── test_settings.py             # Config loading
│   ├── test_scaffold.py             # Init creates dirs
│   ├── test_rule_models.py          # Interface compliance
│   ├── qa_runner.py               # Result collection
│   ├── test_spec_rules/             # S01-S11 per-rule tests
│   ├── test_code_rules/             # C01-C08 per-rule tests
│   ├── test_reviewer.py             # Prompt construction
│   ├── test_drafter.py              # Drafting flow (mocked LLM)
│   ├── test_generator.py            # Code gen (mocked LLM)
│   ├── loom/                        # ✅ IMPLEMENTED
│   │   ├── commons/filesystem/      # FileExecutor tests (54 + 6 skip)
│   │   ├── tools/filesystem/        # FileSystemTool + interfaces (108 + 1 skip)
│   │   └── atoms/filesystem/        # FileSystemAtom tests (21)
│   └── llm/                         # Adapter tests (copied from FM)
├── integration/
│   ├── test_validate_spec.py        # Good/bad specs against runner
│   ├── test_implement_flow.py       # Spec → code
│   └── test_full_loop.py            # F2→F3→F4→F5→F6→F7
└── fixtures/
    ├── good_spec.md
    ├── bad_spec_ambiguous.md
    ├── bad_spec_no_examples.md
    └── bad_spec_too_big.md
```

**Coverage target:** 70-90% as per user rules.

### 6.2 Manual Verification (per step)

| Step | Manual Check |
|:---|:---|
| **Step 1** | Run `sw --help` → see all subcommands. Run `sw init --project ./tmp-test` → verify `.specweaver/` and `specs/` directories created. |
| **Step 2** | Run `sw check --level=component tests/fixtures/good_spec.md` → all PASS. Run `sw check --level=component tests/fixtures/bad_spec_ambiguous.md` → S08 FAIL with findings. |
| **Step 3** | Set `GEMINI_API_KEY` (env var or `.env`), run `sw check --level=component` with a spec needing S03/S07 → LLM rules execute, results displayed. |
| **Step 4** | Run `sw draft greet_service --project ./tmp-test` → interactive session → `greet_service_spec.md` produced in `specs/`. Run `sw review spec specs/greet_service_spec.md` → ACCEPTED or DENIED with structured JSON findings. |
| **Step 5** | Run `sw implement specs/greet_service_spec.md` → `greet_service.py` + `test_greet_service.py` appear in target's `src/` and `tests/`. Run `sw check --level=code src/greet_service.py` → results shown. |
| **Step 6** | Run full loop on SpecWeaver's own docs and on a fresh external project. |
