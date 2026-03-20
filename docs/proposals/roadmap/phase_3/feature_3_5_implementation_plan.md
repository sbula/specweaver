# Feature 3.5 — Auto-Discover Standards from Codebase

Extract coding conventions per scope × language from existing code → HITL document review → store centrally → auto-inject into LLM prompts.

> **Scope**: Phase 3.5a = AST extraction + conditional LLM comparison + HITL review + DB + auto-injection.
> **Deferred**: Phase 3.5b = deeper interactive tribal-knowledge extraction (`sw discover-standards`).
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

Each scope can have different conventions — and that's correct. The user-service uses Google docstrings while payment-service uses NumPy. Both are valid within their scope.

---

## Design Decisions

| # | Decision | Choice |
|---|---|---|
| 1 | **Storage** | DB (`project_standards` table, schema v6). Scoped by project × scope × language × category. |
| 2 | **Scope detection** | Top-level directories with their own source code. `context.yaml` boundaries when available. |
| 3 | **File discovery** | `git ls-files` (respects `.gitignore` automatically, works in all git repos). |
| 4 | **Language detection** | By file extension. Each `StandardsAnalyzer` declares which extensions it handles. |
| 5 | **Categories** | **Dynamic per language**. Each analyzer registers its own categories. No fixed ABC methods. |
| 6 | **Recency** | Exponential decay on `mtime`. Variable half-life auto-computed from project age. |
| 7 | **Conflicting practices** | Majority vote + confidence score. HITL reviews as structured document. |
| 8 | **LLM comparison** | Conditional: only when confidence < 90%. Uses existing `LLMAdapter` (review profile). No new infra. |
| 9 | **HITL** | **Structured document review** (Rich table with per-category actions: accept/edit/reject). Not a simple yes/no. |
| 10 | **Re-scan** | Present diff to HITL. HITL decides per category: keep existing, accept new, or edit. |
| 11 | **Injection** | Auto-load via `PromptBuilder.add_standards()`, scoped to current spec's directory. |
| 12 | **Constitution bootstrap** | Draft `CONSTITUTION.md` from confirmed standards + project metadata. |
| 13 | **JS/TS parsing** | `tree-sitter` (full AST, pre-built wheels). Extensible to other languages. |
| 14 | **`sw standards show`** | Rich table grouped by scope → language → category. |

---

## Workflow

```
sw scan --standards [--compare]
    │
    ├── 1. File Discovery
    │       git ls-files → group by scope (top-level dirs)
    │       → group by language (file extensions)
    │
    ├── 2. AST Analysis (per scope × language)
    │       Python: stdlib ast  |  JS/TS: tree-sitter
    │       → CategoryResult per category (dominant, confidence, alternatives, conflicts)
    │       → recency-weighted via mtime (variable half-life)
    │
    ├── 3. Conditional LLM Comparison (only if --compare OR confidence < 90%)
    │       Uses existing LLMAdapter (review profile)
    │       "Compare these patterns with community best practices"
    │       → enriched findings with community context
    │
    ├── 4. HITL Document Review (Rich structured report)
    │       Present per-scope, per-language report
    │       User reviews each category: [A]ccept / [E]dit / [R]eject / [S]kip scope
    │       On re-scan: show diff vs stored, HITL decides what to keep
    │
    ├── 5. Store confirmed standards → DB
    │
    └── 6. Constitution bootstrap (if no CONSTITUTION.md exists)
            Draft from confirmed conventions + project metadata
```

---

## Proposed Changes

### DB Layer (`config/`)

#### [MODIFY] [database.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/database.py)

Schema v6 migration:

```sql
CREATE TABLE IF NOT EXISTS project_standards (
    project_name TEXT NOT NULL REFERENCES projects(name) ON DELETE CASCADE,
    scope        TEXT NOT NULL,     -- 'user-service', 'frontend', '.' (root)
    language     TEXT NOT NULL,     -- 'python', 'javascript', 'typescript'
    category     TEXT NOT NULL,     -- language-specific: 'naming', 'docstrings', 'jsdoc', etc.
    data         TEXT NOT NULL,     -- JSON blob with findings
    confidence   REAL NOT NULL,     -- 0.0–1.0
    confirmed_by TEXT DEFAULT NULL, -- 'hitl' or NULL
    scanned_at   TEXT NOT NULL,
    PRIMARY KEY (project_name, scope, language, category)
);
```

New methods:
- `save_standard(project_name, scope, language, category, data, confidence)` — upsert
- `get_standards(project_name, *, scope=None, language=None)` → `list[dict]` — filtered
- `get_standard(project_name, scope, language, category)` → `dict | None`
- `clear_standards(project_name, *, scope=None)` — scoped delete
- `list_scopes(project_name)` → `list[str]`

---

### Standards Extraction (`context/`)

#### [NEW] [standards_analyzer.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/standards_analyzer.py)

Dynamic-category ABC:

```python
@dataclass
class CategoryResult:
    category: str           # e.g. "naming", "docstrings", "jsdoc"
    dominant: dict           # e.g. {"style": "snake_case", "class_style": "PascalCase"}
    confidence: float        # 0.0–1.0, recency-weighted
    sample_size: int
    alternatives: dict       # minority patterns with locations
    conflicts: list[str]     # human-readable conflict notes

@dataclass
class ScopeReport:
    scope: str               # directory name or "."
    language: str            # "python", "javascript", "typescript"
    categories: list[CategoryResult]

class StandardsAnalyzer(ABC):
    """Extract coding standards from source files of one language."""

    @abstractmethod
    def language_name(self) -> str: ...

    @abstractmethod
    def file_extensions(self) -> set[str]:
        """Extensions this analyzer handles (e.g. {'.py'})."""

    @abstractmethod
    def supported_categories(self) -> list[str]:
        """Language-specific categories (e.g. ['naming', 'docstrings', 'type_hints'])."""

    @abstractmethod
    def extract(self, category: str, files: list[Path], half_life_days: float) -> CategoryResult:
        """Extract one category from files with recency weighting."""
```

#### [NEW] [python_standards.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/python_standards.py)

`PythonStandardsAnalyzer(StandardsAnalyzer)` — stdlib `ast`:

| Category | What it extracts |
|---|---|
| `naming` | snake_case/CamelCase, constant pattern, private prefix, test file naming |
| `error_handling` | Custom exceptions, bare except count, try/except patterns |
| `type_hints` | % annotated, return types, PEP 604 vs Optional |
| `docstrings` | Google/NumPy/reST style, coverage % |
| `test_patterns` | pytest/unittest, fixtures, assertion style |
| `import_patterns` | Ordering, TYPE_CHECKING, layer structure |
| `async_patterns` | async/await usage, asyncio vs trio |

#### [NEW] [js_standards.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/js_standards.py)

`JSStandardsAnalyzer(StandardsAnalyzer)` — `tree-sitter`:

| Category | What it extracts |
|---|---|
| `naming` | camelCase, PascalCase (components), UPPER_SNAKE (constants) |
| `error_handling` | try/catch, Promise rejection, custom Error classes |
| `typescript_types` | TS vs JS ratio, strict mode, type coverage |
| `jsdoc` | JSDoc presence, style, coverage |
| `test_patterns` | jest/vitest/mocha, describe/it, test file naming |
| `import_patterns` | ESM vs CJS, import grouping, barrel exports |
| `async_patterns` | async/await, callback vs Promise style |

#### [NEW] [standards_inferrer.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/standards_inferrer.py)

Orchestrator:

```python
class StandardsInferrer:
    def __init__(self, analyzers: list[StandardsAnalyzer] | None = None):
        """Default analyzers: PythonStandardsAnalyzer + JSStandardsAnalyzer."""

    def scan_project(self, project_path: Path) -> list[ScopeReport]:
        """
        1. git ls-files → group by scope → group by language
        2. Run analyzers per scope × language
        3. Compute variable half-life from project age
        4. Return list of ScopeReports
        """

    def detect_scopes(self, project_path: Path) -> list[str]:
        """Detect scope boundaries from directory structure / context.yaml."""

    def compare_with_best_practices(
        self, reports: list[ScopeReport], llm: LLMAdapter
    ) -> list[ScopeReport]:
        """Conditional LLM call: only for categories with confidence < 90%."""

    def format_for_prompt(self, project_name: str, scope: str) -> str:
        """Load from DB, format as concise text for <standards> block.
        Filters to given scope + cross-cutting (scope='.')."""

    def _compute_half_life(self, project_path: Path) -> float:
        """Variable half-life from project age."""
```

#### [NEW] [recency.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/recency.py)

```python
def recency_weight(file_mtime: float, half_life_days: float) -> float:
    """Exponential decay: weight = 2^(-age_days / half_life_days)."""

def compute_half_life(project_path: Path) -> float:
    """Auto from project age. Young=180d, mid=~600d, legacy=730d cap."""
```

---

### HITL Review (`review/`)

#### [NEW] [standards_reviewer.py](file:///c:/development/pitbula/specweaver/src/specweaver/review/standards_reviewer.py)

Reusable HITL document review module (used by 3.5, extendable by 3.5b, 3.6):

```python
class StandardsReviewer:
    """Rich interactive review of standards reports."""

    def review(self, reports: list[ScopeReport], existing: list[dict] | None = None) -> list[dict]:
        """
        Present structured Rich table per scope.
        On re-scan: show diff vs existing, highlight changes.
        User actions per category: [A]ccept / [E]dit / [R]eject
        User actions per scope: [A]ccept all / [S]kip
        Returns list of confirmed standards (ready for DB).
        """

    def _render_scope_table(self, report: ScopeReport) -> Table: ...
    def _render_diff(self, old: dict, new: CategoryResult) -> Panel: ...
    def _prompt_category(self, result: CategoryResult, existing: dict | None) -> str | None: ...
```

---

### PromptBuilder (`llm/`)

#### [MODIFY] [prompt_builder.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/prompt_builder.py)

```python
def add_standards(self, text: str) -> PromptBuilder:
    """Priority 1 (truncatable). Rendered after <constitution>, before <topology>."""
```

---

### CLI (`cli.py`)

#### [MODIFY] [cli.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli.py)

1. **`sw scan --standards [--compare]`** — Run scan → conditional LLM → HITL review → store.
   - `--compare` forces LLM comparison even for high-confidence categories
   - Without `--compare`, LLM only fires for confidence < 90%
2. **`_load_standards_content(scope)`** — Load from DB for given scope + cross-cutting (scope=`.`)
3. **Auto-injection** — In all PromptBuilder callers, determine scope from spec path, load standards.
4. **Constitution bootstrap** — Draft `CONSTITUTION.md` from confirmed standards + metadata.
5. **`sw standards show [--scope X]`** — Rich table grouped by scope → language → category.
6. **`sw standards clear [--scope X]`** — Scoped delete.
7. **`sw standards scopes`** — List detected scopes with language stats.

---

### Flow Engine (`flow/`)

#### [MODIFY] [handlers.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/handlers.py)

Add `standards: str | None = None` to `RunContext`.

---

### Dependencies (`pyproject.toml`)

#### [MODIFY] [pyproject.toml](file:///c:/development/pitbula/specweaver/pyproject.toml)

```toml
dependencies = [
    # ... existing ...
    "tree-sitter>=0.23",
    "tree-sitter-javascript>=0.23",
    "tree-sitter-typescript>=0.23",
]
```

---

## Standard Injection: Scope Resolution

When `sw check`, `sw review`, or `sw implement` runs on a file, the system resolves which standards apply:

```
File: user-service/src/auth/login.py

1. Determine scope: walk up from file path → find matching scope ('user-service')
2. Load scope-specific standards from DB (scope='user-service', lang='python')
3. Load cross-cutting standards from DB (scope='.', all languages)
4. Merge: scope-specific overrides cross-cutting
5. format_for_prompt() → concise text
6. PromptBuilder.add_standards(text)
```

---

## Re-Scan: Diff + HITL Merge

```
First scan:  AST → HITL review → store (confirmed_by='hitl')
Second scan: AST → detect changes vs stored → present diff to HITL

┌──────────────────────────────────────────────────────────────┐
│  RE-SCAN DIFF — user-service (Python)                        │
├──────────────┬────────────────────┬──────────────────────────┤
│ Category     │ Stored (confirmed) │ New scan                 │
├──────────────┼────────────────────┼──────────────────────────┤
│ Naming       │ snake_case (94%)   │ snake_case (95%) ✓ same  │
│ Docstrings   │ Google (87%)       │ Google (91%)   ✓ same    │
│ Type Hints   │ PEP 604 (91%)     │ PEP 604 (93%)  ✓ same    │
│ Testing      │ pytest (96%)       │ pytest (94%)   ⚠ dropped │
│ NEW: async   │ —                  │ asyncio (78%)  ★ new     │
├──────────────┴────────────────────┴──────────────────────────┤
│ Actions: [K]eep all stored  [R]eview changes  [A]ccept all   │
└──────────────────────────────────────────────────────────────┘
```

---

## Verification Plan

### Automated Tests (~175-200 tests)

**Unit tests:**
- `test_python_standards.py` — each category with fixtures (naming, docstrings, etc.)
- `test_js_standards.py` — tree-sitter extraction per category
- `test_standards_inferrer.py` — scope detection, half-life, file grouping
- `test_recency.py` — decay formula, variable half-life, edge cases
- `test_standards_reviewer.py` — HITL review (mocked Rich prompts)
- `test_database_v6.py` — schema migration, scoped CRUD
- `test_prompt_builder_standards.py` — `add_standards()`, render order

**Integration tests:**
- `test_standards_scan.py` — real project scan → DB → prompt
- `test_cli_standards.py` — `sw scan --standards`, `sw standards show/clear/scopes`
- `test_standards_scope_resolution.py` — multi-scope injection
- `test_constitution_bootstrap.py` — auto-generation from standards

**Edge cases:**
- Empty project (no source files)
- Single-file project
- Mixed languages in one scope
- Monorepo with 5+ scopes
- Project with no git (fallback to os.walk)
- Re-scan with HITL-confirmed data
- All categories below confidence threshold

**Commands:**
```
uv run pytest tests/ -x -q
uv run ruff check src/ tests/
```

### Manual Verification
- Run `sw scan --standards` on SpecWeaver itself → HITL flow
- Run `sw standards show` → Rich table
- Run `sw standards scopes` → scope listing
- Run `sw review` on a spec → verify `<standards>` in prompt
