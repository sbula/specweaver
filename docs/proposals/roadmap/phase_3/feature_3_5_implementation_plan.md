# Feature 3.5 — Auto-Discover Standards from Codebase

Extract coding conventions per scope × language from existing code → HITL document review → store centrally → auto-inject into LLM prompts.

> **Languages**: Python (stdlib `ast`) + JS/TS (`tree-sitter`). Architecture supports adding Kotlin, Rust, Go.
> **Inspired by**: [Agent OS v3](https://github.com/buildermethods/agent-os)

---

## Core Concept: Scoped Standards

Standards are **per-scope, per-language** — not per-project. A monorepo with 3 microservices produces 3+ sets of standards:

```
monorepo/
├── user-service/        → scope="user-service",     lang=python
├── payment-service/     → scope="payment-service",  lang=python
├── frontend/            → scope="frontend",         lang=typescript
└── (project root)       → scope=".",                lang=* (cross-cutting)
```

---

## Design Decisions

| # | Decision | Choice |
|---|---|---|
| 1 | **Storage** | DB (`project_standards` table, schema v6). Keyed by project × scope × language × category. |
| 2 | **Scope detection** | Top-level directories with their own source code. `context.yaml` boundaries when available. |
| 3 | **File discovery** | `git ls-files` (respects `.gitignore`). Fallback: `os.walk` with hardcoded skip patterns. |
| 4 | **Language detection** | By file extension. Each `StandardsAnalyzer` declares handled extensions. |
| 5 | **Categories** | **Dynamic per language**. Each analyzer registers its own list. |
| 6 | **Recency** | Exponential decay on `mtime`. Variable half-life auto-computed from project age. |
| 7 | **Conflicting practices** | Majority vote + confidence score + conflict report → HITL reviews. |
| 8 | **LLM comparison** | Conditional: only when confidence < 90% or `--compare` flag. Uses existing `LLMAdapter` (review profile). |
| 9 | **HITL** | **Structured document review** (Rich table with per-category Accept/Edit/Reject). |
| 10 | **Re-scan** | Present diff vs stored → HITL decides per category: keep existing, accept new, or edit. |
| 11 | **Injection** | Auto-load via `PromptBuilder.add_standards()`, scoped to spec's directory. |
| 12 | **Constitution bootstrap** | Draft `CONSTITUTION.md` from confirmed standards + project metadata. |
| 13 | **JS/TS parsing** | `tree-sitter` (full AST, pre-built wheels). |
| 14 | **`sw standards show`** | Rich table grouped by scope → language → category. |

---

## Sub-Phases

### Phase 3.5a-1: Foundation (DB + Python Analyzer + Basic CLI)

**Goal**: End-to-end flow working for a single-scope Python project. No LLM, no HITL, no JS/TS.

| Component | What |
|---|---|
| `config/database.py` | Schema v6 migration: `project_standards` table. CRUD methods. |
| `context/standards_analyzer.py` | `StandardsAnalyzer` ABC, `CategoryResult`, `ScopeReport` dataclasses. |
| `context/python_standards.py` | `PythonStandardsAnalyzer`: naming, error_handling, type_hints, docstrings, test_patterns, import_patterns. |
| `context/recency.py` | `recency_weight()`, `compute_half_life()`. |
| `llm/prompt_builder.py` | `add_standards()` method, `kind="standards"` block in `_render()` between constitution and topology. |
| `cli.py` | `sw scan --standards` (single scope, auto-store, no HITL). `sw standards show`. `sw standards clear`. |
| `flow/handlers.py` | `standards: str | None = None` on `RunContext`. |

**Tests**: ~80-100 unit + integration tests.
**Deliverable**: `sw scan --standards` works on SpecWeaver itself, `sw standards show` renders a Rich table, `sw review` includes `<standards>` in the prompt.

---

### Phase 3.5a-2: Multi-Scope + HITL Document Review

**Goal**: Monorepo support, interactive review, re-scan diff.

| Component | What |
|---|---|
| `context/standards_inferrer.py` | `StandardsInferrer`: scope detection, `git ls-files`, multi-scope grouping, file-per-language grouping. |
| `review/standards_reviewer.py` | `StandardsReviewer`: Rich structured report, per-category Accept/Edit/Reject, per-scope Accept All/Skip, re-scan diff display. |
| `cli.py` | Interactive HITL flow in `sw scan --standards`. `sw standards show --scope X`. `sw standards scopes`. Scope resolution for auto-injection. |
| Scope resolution | `_resolve_scope(target_path, project_path)` — walk up from spec to find matching scope. Merge scope-specific + cross-cutting (scope=`.`). |

**Tests**: ~40-60 tests. Multi-scope fixtures, mocked Rich prompts, re-scan diff.
**Deliverable**: `sw scan --standards` on a monorepo produces per-service standards, HITL reviews each scope, re-scan shows diff.

---

### Phase 3.5a-3: JS/TS (tree-sitter) + Conditional LLM

**Goal**: Multi-language support, LLM-enriched findings.

| Component | What |
|---|---|
| `context/js_standards.py` | `JSStandardsAnalyzer`: naming, error_handling, typescript_types, jsdoc, test_patterns, import_patterns, async_patterns. Uses tree-sitter. |
| `pyproject.toml` | Add `tree-sitter`, `tree-sitter-javascript`, `tree-sitter-typescript` dependencies. |
| `context/standards_inferrer.py` | Conditional LLM comparison (`compare_with_best_practices()`). Only fires for confidence < 90% or `--compare` flag. |
| `cli.py` | `--compare` flag. LLM enrichment in HITL report. |

**Tests**: ~40-50 tests. tree-sitter fixtures, LLM mocking.
**Deliverable**: Scan a project with Python backend + TypeScript frontend, each gets language-appropriate standards.

---

### Phase 3.5a-4: Constitution Bootstrap + Polish

**Goal**: Auto-generate `CONSTITUTION.md` from confirmed standards, finalize edge cases.

| Component | What |
|---|---|
| `cli.py` | Constitution bootstrap: when `sw scan --standards` completes and no `CONSTITUTION.md` exists, generate draft from confirmed standards + project metadata (name, languages, layers). |
| Edge cases | Empty project, single-file, all-below-threshold, project with no git, mixed languages in one scope. |
| Documentation | Update `README.md`, roadmap, developer guide. |

**Tests**: ~20-30 tests.
**Deliverable**: Feature 3.5a complete. All tests passing, documentation updated.

---

## Proposed Changes (detailed)

### DB Layer

#### [MODIFY] [database.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/database.py)

Schema v6:

```sql
CREATE TABLE IF NOT EXISTS project_standards (
    project_name TEXT NOT NULL REFERENCES projects(name) ON DELETE CASCADE,
    scope        TEXT NOT NULL,
    language     TEXT NOT NULL,
    category     TEXT NOT NULL,
    data         TEXT NOT NULL,     -- JSON blob
    confidence   REAL NOT NULL,     -- 0.0–1.0
    confirmed_by TEXT DEFAULT NULL, -- 'hitl' or NULL
    scanned_at   TEXT NOT NULL,
    PRIMARY KEY (project_name, scope, language, category)
);
```

Methods: `save_standard()`, `get_standards()`, `get_standard()`, `clear_standards()`, `list_scopes()`.

---

### Standards Extraction

#### [NEW] [standards_analyzer.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/standards_analyzer.py)

```python
@dataclass
class CategoryResult:
    category: str
    dominant: dict
    confidence: float        # recency-weighted
    sample_size: int
    alternatives: dict       # minority patterns + locations
    conflicts: list[str]

@dataclass
class ScopeReport:
    scope: str
    language: str
    categories: list[CategoryResult]

class StandardsAnalyzer(ABC):
    @abstractmethod
    def language_name(self) -> str: ...
    @abstractmethod
    def file_extensions(self) -> set[str]: ...
    @abstractmethod
    def supported_categories(self) -> list[str]: ...
    @abstractmethod
    def extract(self, category: str, files: list[Path], half_life_days: float) -> CategoryResult: ...
```

#### [NEW] [python_standards.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/python_standards.py)

7 categories: naming, error_handling, type_hints, docstrings, test_patterns, import_patterns, async_patterns.

#### [NEW] [js_standards.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/js_standards.py)

7 categories: naming, error_handling, typescript_types, jsdoc, test_patterns, import_patterns, async_patterns.

#### [NEW] [standards_inferrer.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/standards_inferrer.py)

`scan_project()`, `detect_scopes()`, `compare_with_best_practices()`, `format_for_prompt()`, `_compute_half_life()`.

#### [NEW] [recency.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/recency.py)

#### [NEW] [standards_reviewer.py](file:///c:/development/pitbula/specweaver/src/specweaver/review/standards_reviewer.py)

---

### PromptBuilder

#### [MODIFY] [prompt_builder.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/prompt_builder.py)

- New `add_standards(text)` method → `_ContentBlock(kind="standards", priority=1)`
- In `_render()` (L462-515): add `standards` rendering between `constitution` (L473) and `topology` (L479)

---

### CLI

#### [MODIFY] [cli.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli.py)

- `sw scan --standards [--compare]` — orchestrate scan → HITL → store
- `_load_standards_content(project_name, scope)` — load from DB, format
- Auto-injection: `_resolve_scope()` in `review()` (L921), `_execute_review()` (L958), etc.
- `sw standards show/clear/scopes` — new subcommand group
- Constitution bootstrap

---

### Flow Engine

#### [MODIFY] [handlers.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/handlers.py)

Add `standards: str | None = None` to `RunContext` (after L59, alongside `constitution`).

---

## Remaining Implementation Concerns

### ⚠️ Issues to resolve during implementation

| # | Issue | Details | When |
|---|---|---|---|
| 1 | **`AnalyzerFactory` pattern mismatch** | Existing `AnalyzerFactory.for_directory()` returns first match only. Standards needs ALL matching analyzers for mixed-language dirs (e.g., `.py` + `.ts` in same scope). `StandardsInferrer` should group files by extension, then match to analyzers — NOT use `AnalyzerFactory`. | 3.5a-1 |
| 2 | **`git ls-files` subprocess** | Need graceful fallback when (a) git not installed, (b) project not a git repo. Fallback = `os.walk` with hardcoded skips (`.git`, `__pycache__`, `node_modules`, `venv`, `.venv`). | 3.5a-1 |
| 3 | **Scope detection heuristic** | "Top-level directories with source code" is vague. What if the project structure is `src/services/user-service/`? Need recursive scope detection, not just top-level. Proposal: detect scopes from `context.yaml` locations first, fall back to first-level dirs with source files. | 3.5a-2 |
| 4 | **`_render()` modification requires test surgery** | `_render()` has exact-match assertion tests in `test_prompt_builder.py`. Adding `<standards>` between `<constitution>` and `<topology>` will break them. Must update ALL existing render-order tests. | 3.5a-1 |
| 5 | **How `_resolve_scope()` handles nested paths** | For `user-service/src/auth/login.py`, scope = `user-service`. But for `src/specweaver/context/analyzers.py` (no top-level service dir), scope = `.`. Need clear resolution: walk up from file, check DB for known scopes, first match wins. | 3.5a-2 |
| 6 | **Rich interactive prompts in tests** | `StandardsReviewer` uses Rich `Prompt.ask()` for HITL. Tests need `monkeypatch` / `unittest.mock.patch` on `rich.prompt.Prompt.ask` — verify this works cross-platform (Windows terminal quirks). | 3.5a-2 |
| 7 | **tree-sitter API version** | `tree-sitter` Python bindings changed API significantly between v0.21 and v0.23. Must verify exact API: `Language()`, `Parser()`, `tree.root_node`, `node.children`. Pin version in `pyproject.toml`. | 3.5a-3 |
| 8 | **LLM prompt for best-practice comparison** | Need to design the exact prompt template: what goes in, what comes out, how is the response parsed? Structured output (JSON) or free-text that gets injected into HITL report? | 3.5a-3 |
| 9 | **Token budget impact** | Standards block at priority 1 means it competes with files (priority 2) and topology (priority 2). If standards are verbose (e.g., 6 categories × 100 tokens = 600 tokens), that's fine. But for a monorepo with 5 scopes × 2 languages × 7 categories — could be 4,000+ tokens. Need max-size guard. | 3.5a-2 |
| 10 | **Constitution bootstrap template** | Need a concrete template for the auto-generated `CONSTITUTION.md`. What sections? What format? How much comes from standards vs metadata? | 3.5a-4 |
| 11 | **`PythonStandardsAnalyzer` complexity** | 7 categories × AST walking = potentially 7 full passes over every `.py` file. Optimization: single AST pass collecting all data, then split into categories. Critical for large projects (10K+ files). | 3.5a-1 |
| 12 | **Windows `mtime` precision** | Windows NTFS has ~100ns `mtime` resolution but Python's `os.stat().st_mtime` returns a float that may lose precision. Shouldn't matter for our half-life scale (days), but verify. Also: `git clone` on Windows may reset all `mtime` to clone time — need testing. | 3.5a-1 |

### ✅ Non-issues (verified against code)

| Item | Why it's fine |
|---|---|
| `RunContext.standards` field | Clean addition alongside existing `constitution` field (L59 in handlers.py). Same Pydantic pattern. |
| `PromptBuilder.add_standards()` | Follows exact pattern of `add_constitution()`. Priority 1, new `kind="standards"`. |
| DB schema v6 | Follows existing migration pattern (v1→v5). `_SCHEMA_V6` string + `_ensure_schema()` block. |
| Auto-injection in CLI callers | Same pattern as `_load_constitution_content()`. Add `_load_standards_content()` and call in same places. |
| tree-sitter Windows wheels | Pre-built wheels available for Windows, no C compiler needed. |

---

## Verification Plan

**Total: ~180-240 tests across 4 sub-phases.**

| Sub-phase | Unit | Integration | Edge |
|---|---|---|---|
| 3.5a-1 | ~60 | ~15 | ~10 |
| 3.5a-2 | ~30 | ~20 | ~10 |
| 3.5a-3 | ~30 | ~15 | ~5 |
| 3.5a-4 | ~10 | ~10 | ~10 |

```
uv run pytest tests/ -x -q
uv run ruff check src/ tests/
```
