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
| 3 | **File discovery** | Priority chain: (1) `git ls-files` if `.git/` exists, (2) `.specweaverignore` always checked, (3) `os.walk` + hardcoded skip as fallback. |
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
| `standards/analyzer.py` | `StandardsAnalyzer` ABC, `CategoryResult`, `ScopeReport` dataclasses. |
| `standards/python_analyzer.py` | `PythonStandardsAnalyzer`: naming, error_handling, type_hints, docstrings, test_patterns, import_patterns. Single-pass AST optimization. |
| `standards/recency.py` | `recency_weight()`, `compute_half_life()`. |
| `llm/prompt_builder.py` | `add_standards()` method. Insert `kind="standards"` block directly in `_render()` between constitution and topology (minimal diff, no refactor). |
| `standards/discovery.py` | `discover_files()`, `_git_ls_files()`, `_walk_with_skips()`, `_apply_specweaverignore()`. |
| `cli.py` | `sw standards scan` (separate command, single scope, auto-store, no HITL). `sw standards show`. `sw standards clear`. |
| `flow/handlers.py` | `standards: str | None = None` on `RunContext`. |

**Tests**: ~80-100 unit + integration tests.
**Deliverable**: `sw standards scan` works on SpecWeaver itself, `sw standards show` renders a Rich table, `sw review` includes `<standards>` in the prompt.

---

### Phase 3.5a-2: Multi-Scope + HITL Document Review

**Goal**: Monorepo support (2-level scopes), interactive HITL review, scoped injection with token cap, re-scan diff.

**Resolved decisions**: 2-level scopes (not just top-level). HITL on by default (one combined review, not per-file). Edit = JSON dict editing. Re-scan diff mode = configurable (`sw config set-rescan-mode approve|inform`, default: `inform`). Token cap = 2000 chars (scope-specific prioritized over root). Scope inheritance: merge scope-specific + root `"."`, HITL for conflicts unless already resolved.

| Component | What |
|---|---|
| `standards/scope_detector.py` | `detect_scopes()` — 2-level deep, `_has_source_files()`, imports `_SKIP_DIRS_WALK` from `discovery.py`. `_resolve_scope(target_path, project_path, known_scopes)` — walk-up longest-prefix match for injection. |
| `standards/reviewer.py` | `StandardsReviewer`: Rich table, combined review (all scopes at once), per-category Accept/Edit(JSON)/Reject, Accept-All, Skip-scope. Re-scan diff display. |
| `cli/standards.py` | Multi-scope scan (`--scope X`, `--no-review`). `sw standards scopes` (summary table). |
| `cli/_helpers.py` | Scope-aware `_load_standards_content(project_path, target_path, max_chars=2000)`. Pass `target_path` at 4 call sites. |
| `cli/config.py` | `sw config set-rescan-mode approve|inform`. |
| `config/database.py` | `set_rescan_mode()` / `get_rescan_mode()` (follows `set_log_level` pattern). |

**Backlog** (noted, not implemented now): configurable multi-stage reviews; force re-evaluation of previous HITL decisions.

**Tests**: ~40-50 tests. Synthetic monorepo fixtures, mocked Rich prompts, re-scan diff.
**Deliverable**: `sw standards scan` on a monorepo produces per-scope standards, HITL reviews, `sw review` injects scope-specific standards with token cap.

---

### Phase 3.5a-3: JS/TS (tree-sitter) + Conditional LLM

**Goal**: Multi-language support, LLM-enriched findings.

| Component | What |
|---|---|
| `standards/js_analyzer.py` | `JSStandardsAnalyzer`: naming, error_handling, typescript_types, jsdoc, test_patterns, import_patterns, async_patterns. Uses tree-sitter. |
| `pyproject.toml` | Add `tree-sitter`, `tree-sitter-javascript`, `tree-sitter-typescript` dependencies. |
| `standards/inferrer.py` | Conditional LLM comparison (`compare_with_best_practices()`). Only fires for confidence < 90% or `--compare` flag. |
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

### Standards Module (`standards/`)

> **New module**: `specweaver/standards/` — self-contained orchestrator for codebase analysis.
> Consumes `specweaver/config` (DB). Forbidden: `specweaver/loom/*`.

#### [NEW] [analyzer.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/analyzer.py)

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

#### [NEW] [python_analyzer.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/python_analyzer.py)

7 categories: naming, error_handling, type_hints, docstrings, test_patterns, import_patterns, async_patterns.

#### [NEW] [js_analyzer.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/js_analyzer.py)

7 categories: naming, error_handling, typescript_types, jsdoc, test_patterns, import_patterns, async_patterns.

#### [NEW] [inferrer.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/inferrer.py)

`scan_project()`, `detect_scopes()`, `compare_with_best_practices()`, `format_for_prompt()`, `_compute_half_life()`.

#### [NEW] [recency.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/recency.py)

#### [NEW] [reviewer.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/reviewer.py)

#### [NEW] [discovery.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/discovery.py)

---

### PromptBuilder

#### [MODIFY] [prompt_builder.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/prompt_builder.py)

- New `add_standards(text)` method → `_ContentBlock(kind="standards", priority=1)`
- Insert standards rendering directly in `_render()` (L462-515) between constitution (L476) and topology (L479) — 5 lines added, no existing logic refactored:

```python
# Standards (after constitution, before topology)
standards = [b for b in blocks if b.kind == "standards"]
if standards:
    text = "\n\n".join(b.text for b in standards)
    marker = "\n[truncated]" if any(b.truncated for b in standards) else ""
    parts.append(f"<standards>\n{text}{marker}\n</standards>")
```

Minimal diff, no risk to existing tests. Data-driven `_RENDER_ORDER` refactoring deferred to a future cleanup.

---

### CLI

#### [MODIFY] [cli.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli.py)

- `sw standards scan [--compare]` — **separate command** (not a flag on `sw scan`). Orchestrate scan → HITL → store.
- `sw standards show [--scope X]` — Rich table grouped by scope → language → category
- `sw standards clear [--scope X]` — scoped delete
- `sw standards scopes` — list detected scopes
- `_load_standards_content(project_path, target_path)` — resolves project_name from DB by matching `project_path`, resolves scope via walk-up, loads + formats for prompt
- Auto-injection: call `_load_standards_content()` alongside `_load_constitution_content()` at all 4 call sites (L951, L1082, L1797, L1950)
- Constitution bootstrap moved to `sw standards scan` (not `sw scan`)

---

### Flow Engine

#### [MODIFY] [handlers.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/handlers.py)

Add `standards: str | None = None` to `RunContext` (after L59, alongside `constitution`).

---

## File Discovery Strategy

```
Priority chain:
├── If .git/ exists:
│   ├── Run: git ls-files --cached --others --exclude-standard
│   │   (tracked + untracked but not ignored)
│   ├── Also check .specweaverignore for additional excludes
│   └── If git command fails → fall through to os.walk
│
└── If no .git/:
    ├── os.walk with hardcoded skips:
    │   .git, __pycache__, node_modules, venv, .venv,
    │   .tox, .mypy_cache, .pytest_cache, dist, build, .eggs
    ├── Also check .specweaverignore
    └── Log warning: "Not a git repo — using basic file discovery."
```

`.specweaverignore` lives in project root (user-controlled config, not SpecWeaver-generated). Uses `pathspec` library for `.gitignore`-compatible pattern matching.

#### [NEW] [discovery.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/discovery.py)

```python
def discover_files(project_path: Path) -> list[Path]:
    """Discover analyzable files using the priority chain."""

def _git_ls_files(project_path: Path) -> list[Path] | None:
    """Try git ls-files. Returns None if git unavailable or not a repo."""

def _walk_with_skips(project_path: Path) -> list[Path]:
    """Fallback: os.walk with hardcoded skip patterns."""

def _apply_specweaverignore(files: list[Path], project_path: Path) -> list[Path]:
    """Filter files through .specweaverignore patterns (pathspec library)."""
```

---

## Scope Resolution Algorithm

DB-backed walk-up resolution for injection:

```python
def _resolve_scope(target_path: Path, project_path: Path, known_scopes: list[str]) -> str:
    """
    Walk up from target_path toward project_path.
    At each level, check if relative path matches a known scope in DB.
    Longest-prefix match wins. If no match → '.' (root scope).

    Examples:
      target:  /proj/user-service/src/auth/login.py
      scopes:  ['user-service', 'frontend', '.']
      Walk up: 'user-service/src/auth' → 'user-service/src' → 'user-service' → MATCH!
      Result:  'user-service'

      target:  /proj/src/specweaver/cli.py
      scopes:  ['user-service', 'frontend', '.']
      Walk up: 'src/specweaver' → 'src' → no match
      Result:  '.' (root scope)
    """
```

Injection merges scope-specific + cross-cutting (scope=`.`) standards.

---

## Remaining Implementation Concerns

### ⚠️ Open (to resolve during implementation)

| # | Issue | Details | When |
|---|---|---|---|
| 1 | **`AnalyzerFactory` pattern mismatch** | Existing `AnalyzerFactory.for_directory()` returns first match only. Standards needs ALL matching analyzers for mixed-language dirs. `StandardsInferrer` groups files by extension, matches to analyzers — does NOT use `AnalyzerFactory`. | 3.5a-1 |
| 7 | **tree-sitter API version** | Pin exact version in `pyproject.toml`. Verify API: `Language()`, `Parser()`, node traversal. | 3.5a-3 |
| 8 | **LLM prompt template** | Design exact prompt for best-practice comparison. Structured JSON output or free-text for HITL report. | 3.5a-3 |
| 10 | **Constitution bootstrap template** | Concrete template for auto-generated `CONSTITUTION.md`. | 3.5a-4 |
| 11 | **Single-pass AST optimization** | Parse each `.py` file once, collect all category data, split after. Critical for 10K+ file projects. | 3.5a-1 |
| 12 | **Windows `mtime` after `git clone`** | May reset all mtime to clone time. Test and document limitation. | 3.5a-1 |

### ✅ Resolved

| # | Issue | Solution |
|---|---|---|
| 2 | **File discovery** | Priority chain: `git ls-files` → `.specweaverignore` → `os.walk` fallback. Uses `pathspec` library. See File Discovery Strategy above. |
| 3 | **Scope detection heuristic** | 2-level deep detection. L1 dirs with sub-scopes → sub-scopes only (no double-counting). Always includes root `"."`. Implemented in `scope_detector.py`. |
| 4 | **`_render()` test breakage** | Insert standards block directly (5 lines) — no refactor of existing logic, no test breakage. Data-driven `_RENDER_ORDER` deferred. |
| 5 | **Scope resolution** | DB-backed walk-up: query known scopes once, walk up from file path, longest-prefix match. Falls back to `.` (root). See Scope Resolution Algorithm above. |
| 6 | **Rich interactive prompts in tests** | Mock `rich.prompt.Prompt.ask()` via `monkeypatch`. `--no-review` flag for CI. Combined review (one table for all scopes). |
| 9 | **Token budget impact** | 2000-char cap. Scope-specific standards prioritized over root `"."`. Implemented in `_load_standards_content()`. |
| 13 | **`_render()` per-kind logic** | Don't refactor. Insert `<standards>` block directly between constitution and topology. Each kind keeps its own rendering logic. |
| 14 | **`project_name` at call sites** | `_load_standards_content(project_path, target_path)` resolves project_name internally from DB by matching the path. Same function resolves scope via walk-up. |
| 15 | **Command structure** | `sw standards scan` as separate command. `sw scan` stays context.yaml-only. No coupling between the two. |

### ✅ Non-issues (verified against code)

| Item | Why it's fine |
|---|---|
| `RunContext.standards` field | Clean addition alongside existing `constitution` field (L59 in handlers.py). Same Pydantic pattern. |
| `PromptBuilder.add_standards()` | Follows exact pattern of `add_constitution()`. Priority 1, new `kind="standards"`. |
| DB schema v6 | Follows existing migration pattern (v1→v5). `_SCHEMA_V6` string + `_ensure_schema()` block. |
| Auto-injection in CLI callers | Same pattern as `_load_constitution_content()`. Add `_load_standards_content()` and call in same places. |
| tree-sitter Windows wheels | Pre-built wheels available for Windows, no C compiler needed. |

### New Dependencies

| Package | Why |
|---|---|
| `pathspec` | `.gitignore` / `.specweaverignore` pattern matching. Well-maintained, no C extensions. |
| `tree-sitter` + language grammars | JS/TS AST parsing (Phase 3.5a-3). Pre-built wheels. |

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
