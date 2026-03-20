# Feature 3.5 — Auto-Discover Standards from Codebase

Extract naming conventions, patterns, error handling, and architectural decisions from existing code → store centrally → auto-inject into LLM prompts.

> **Scope**: Phase 3.5a = pure AST + DB storage + auto-injection. Phase 3.5b (LLM+HITL `sw discover-standards`) = deferred.
> **Languages**: Python + JS/TS from Phase 1.
> **Inspired by**: [Agent OS v3](https://github.com/buildermethods/agent-os) — `/discover-standards` + `/inject-standards`

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Storage** | `~/.specweaver/specweaver.db` (`project_standards` table, schema v6) | No SpecWeaver files in project folders. DB already stores per-project config. |
| **Output format** | JSON blobs per category in DB | Structured, queryable, no filesystem pollution. |
| **Injection** | Auto-load via `PromptBuilder.add_standards()` | No `--with-standards` flag needed. Same pattern as constitution. |
| **Priority** | 1 (high, but truncatable) | Unlike constitution (priority 0), standards can be compressed under token pressure. |
| **Render order** | `<instructions>` → `<constitution>` → `<standards>` → `<topology>` → `<files>` → `<context>` → `<reminder>` | Standards are how-to; constitution is what-to. Standards after constitution. |
| **Constitution bootstrap** | `sw scan --standards` auto-generates draft `CONSTITUTION.md` when none exists | Reuses existing `sw constitution init` location (project root). |
| **Standards vs context.yaml** | Separate files, different scope | `context.yaml` = per-module boundaries. Standards = per-project conventions. |
| **Phase split** | 3.5a (AST) now, 3.5b (LLM+HITL) later | Ship fast, add depth later. |

---

## Proposed Changes

### DB Layer (`config/`)

#### [MODIFY] [database.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/database.py)

Schema v6 migration — new `project_standards` table:

```sql
CREATE TABLE IF NOT EXISTS project_standards (
    project_name TEXT NOT NULL REFERENCES projects(name) ON DELETE CASCADE,
    category     TEXT NOT NULL,     -- 'naming', 'error_handling', 'type_hints', etc.
    data         TEXT NOT NULL,     -- JSON blob with category-specific findings
    scanned_at   TEXT NOT NULL,     -- ISO timestamp of last scan
    PRIMARY KEY (project_name, category)
);
```

New methods:
- `save_standards(project_name, category, data)` — upsert
- `get_standards(project_name)` → `list[dict]` — all categories
- `get_standard(project_name, category)` → `dict | None`
- `clear_standards(project_name)` — delete all

---

### Standards Extraction (`context/`)

#### [NEW] [standards_analyzer.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/standards_analyzer.py)

Extends the existing `LanguageAnalyzer` pattern. New `StandardsAnalyzer` ABC:

```python
class StandardsAnalyzer(ABC):
    """Extract coding standards metrics from source files."""

    @abstractmethod
    def extract_naming(self, directory: Path) -> dict: ...
    @abstractmethod
    def extract_error_handling(self, directory: Path) -> dict: ...
    @abstractmethod
    def extract_type_coverage(self, directory: Path) -> dict: ...
    @abstractmethod
    def extract_docstring_style(self, directory: Path) -> dict: ...
    @abstractmethod
    def extract_test_patterns(self, directory: Path) -> dict: ...
    @abstractmethod
    def extract_import_patterns(self, directory: Path) -> dict: ...
```

#### [NEW] [python_standards.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/python_standards.py)

`PythonStandardsAnalyzer(StandardsAnalyzer)` — AST-based extraction:

| Category | What it extracts |
|---|---|
| `naming` | Function/variable style (snake_case), class style (PascalCase), constant pattern, private prefix, test file naming |
| `error_handling` | Custom exception classes, bare except count, try/except patterns, common exception types |
| `type_hints` | % of public functions annotated, return type usage, union style (PEP 604 vs Optional) |
| `docstrings` | Style (google/numpy/rst), coverage %, first-line pattern |
| `test_patterns` | Framework, fixture usage, async style, assertion style, test file naming |
| `import_patterns` | Layer ordering, common dependencies, TYPE_CHECKING usage |

#### [NEW] [js_standards.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/js_standards.py)

`JSStandardsAnalyzer(StandardsAnalyzer)` — regex/heuristic-based (no full JS AST parser):

| Category | What it extracts |
|---|---|
| `naming` | camelCase vs snake_case, component naming (PascalCase), constant pattern |
| `error_handling` | try/catch patterns, Promise error handling, custom error classes |
| `type_hints` | TypeScript usage, JSDoc annotations, `.ts` vs `.js` ratio |
| `import_patterns` | ES modules vs CommonJS, import grouping, barrel exports |
| `test_patterns` | Framework (jest/vitest/mocha), describe/it pattern, test file naming |

#### [NEW] [standards_inferrer.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/standards_inferrer.py)

Orchestrates analysis across directories and writes to DB:

```python
class StandardsInferrer:
    """Scan project, extract standards, store in DB."""

    def scan_project(self, project_path: Path, project_name: str) -> StandardsReport:
        """Walk project dirs, run analyzers, save to DB."""

    def format_for_prompt(self, project_name: str) -> str:
        """Load from DB, format as concise text for PromptBuilder injection."""
```

---

### PromptBuilder (`llm/`)

#### [MODIFY] [prompt_builder.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/prompt_builder.py)

New builder method + render position:

```python
def add_standards(self, text: str) -> PromptBuilder:
    """Add project standards (priority 1 — high priority, truncatable).

    Standards are rendered after constitution, before topology,
    inside <standards> tags.
    """
```

---

### CLI (`cli.py`)

#### [MODIFY] [cli.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli.py)

1. **`sw scan --standards`** — Add `--standards` flag to existing `scan()`. When set, also runs `StandardsInferrer.scan_project()` and stores results in DB.
2. **`_load_standards_content()`** — New helper (parallel to `_load_constitution_content()`). Loads from DB, formats for prompt.
3. **Auto-injection** — Add `.add_standards(standards_content)` call to all PromptBuilder callers (review, implement, draft, sw run).
4. **Constitution bootstrap** — When `sw scan --standards` runs and no `CONSTITUTION.md` exists, auto-generate a draft from discovered conventions.
5. **`sw standards show`** — Display stored standards for the active project.
6. **`sw standards clear`** — Clear stored standards.

---

### Flow Engine (`flow/`)

#### [MODIFY] [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/models.py)

Add `standards: str | None = None` field to `RunContext` for pipeline handler access.

---

### AnalyzerFactory update

#### [MODIFY] [analyzers.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/analyzers.py)

Add `JSAnalyzer` to `AnalyzerFactory._analyzers` for JS/TS file detection.

---

## Verification Plan

### Automated Tests

**Unit tests** (~120-150 tests expected):
- `tests/unit/context/test_python_standards.py` — each extraction category with fixtures
- `tests/unit/context/test_js_standards.py` — JS/TS extraction
- `tests/unit/context/test_standards_inferrer.py` — orchestration, DB interaction
- `tests/unit/config/test_database_v6.py` — schema migration, CRUD
- `tests/unit/llm/test_prompt_builder_standards.py` — `add_standards()`, render order

**Integration tests** (~20-30 tests):
- `tests/integration/context/test_standards_scan.py` — real project scan → DB → prompt
- `tests/integration/cli/test_cli_standards.py` — `sw scan --standards`, `sw standards show/clear`

**Commands:**
```
uv run pytest tests/ -x -q
uv run ruff check src/ tests/
```

### Manual Verification
- Run `sw scan --standards` on SpecWeaver's own codebase → verify DB has entries
- Run `sw standards show` → verify formatted output
- Run `sw review` → verify `<standards>` block appears in prompt (use `--verbose`)
