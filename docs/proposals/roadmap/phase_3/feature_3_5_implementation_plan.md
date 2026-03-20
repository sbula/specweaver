# Feature 3.5 — Auto-Discover Standards from Codebase

Extract naming conventions, patterns, error handling, and architectural decisions from existing code → HITL review → store centrally → auto-inject into LLM prompts.

> **Scope**: Phase 3.5a = AST extraction + LLM best-practice comparison + HITL confirmation + DB storage + auto-injection.
> **Deferred**: Phase 3.5b = deeper LLM+HITL `sw discover-standards` (interactive tribal-knowledge extraction loop).
> **Languages**: Python (stdlib `ast`) + JS/TS (`tree-sitter`) from Phase 1.
> **Inspired by**: [Agent OS v3](https://github.com/buildermethods/agent-os) — `/discover-standards` + `/inject-standards`

---

## Design Decisions

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | **Storage** | DB only (`project_standards` table, schema v6) | Strict no SpecWeaver files in project folders. |
| 2 | **Injection** | Auto-load via `PromptBuilder.add_standards()` | No `--with-standards` flag needed. |
| 3 | **Render order** | `<instructions>` → `<constitution>` → `<standards>` → `<topology>` → `<files>` → `<context>` → `<reminder>` | Standards = how; constitution = what. |
| 4 | **Priority** | 1 (high, but truncatable) | Unlike constitution (0), standards compress under token pressure. |
| 5 | **Phase split** | 3.5a: AST + LLM compare + HITL confirm. 3.5b: deeper interactive discovery | Ship a useful workflow fast, add depth later. |
| 6 | **Empty project** | Graceful no-op, no DB rows, skip constitution bootstrap | "Add source files and re-scan" message. |
| 7 | **Conflicting practices** | Majority vote + confidence score + conflict report → **HITL confirms** before storing | User decides what's canonical, not the tool. |
| 8 | **Style evolution** | Recency-weighted analysis (exponential decay on `mtime`) | Surface current conventions, not historical average. |
| 9 | **Half-life** | Variable: shorter for young projects, longer for old stable ones | Auto-computed from project age (oldest file's mtime). |
| 10 | **Scan scope** | Respect `.gitignore` + `.specweaverignore` | Same as `sw scan` today plus explicit ignore support. |
| 11 | **Incremental scan** | Full rescan Phase 1, incremental later | Simplicity first. |
| 12 | **LLM comparison** | Compare findings with known best practices → present alongside findings | Gives HITL context: "your code does X, community recommends Y." |
| 13 | **Constitution bootstrap** | Auto-generate `CONSTITUTION.md` with conventions + project metadata | Name, language, architecture layers, discovered conventions as rules. |
| 14 | **`sw standards show`** | Rich table output | Consistent with other CLI commands. |
| 15 | **JS/TS parsing** | `tree-sitter` (full AST) | Required for accuracy. Extensible to Kotlin, Rust, Go etc. |

---

## Workflow

```
sw scan --standards
    │
    ├── 1. Walk project tree (respect .gitignore/.specweaverignore)
    ├── 2. AST analysis (Python: stdlib ast, JS/TS: tree-sitter)
    │       → naming, error_handling, type_hints, docstrings, test_patterns, imports
    │       → recency-weighted confidence scores per category
    │
    ├── 3. LLM best-practice comparison (Gemini call)
    │       "Given these discovered patterns, compare with current community
    │        best practices. Flag deviations and suggest improvements."
    │       → enriched findings with community context
    │
    ├── 4. HITL review (Rich interactive prompt)
    │       Present findings per category with confidence + LLM notes.
    │       User confirms/edits/rejects each category.
    │       "Your code uses Google-style docstrings (92% confidence).
    │        Community: ✓ Standard practice. Store? [Y/n/edit]"
    │
    ├── 5. Store confirmed standards → DB (project_standards table)
    │
    └── 6. Constitution bootstrap (if no CONSTITUTION.md exists)
            Auto-generate draft from confirmed conventions + project metadata.
```

---

## Proposed Changes

### DB Layer (`config/`)

#### [MODIFY] [database.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/database.py)

Schema v6 migration — new `project_standards` table:

```sql
CREATE TABLE IF NOT EXISTS project_standards (
    project_name   TEXT NOT NULL REFERENCES projects(name) ON DELETE CASCADE,
    category       TEXT NOT NULL,     -- 'naming', 'error_handling', 'type_hints', etc.
    data           TEXT NOT NULL,     -- JSON blob with findings
    confidence     REAL NOT NULL,     -- 0.0–1.0
    confirmed_by   TEXT DEFAULT NULL, -- 'hitl' or NULL (auto-accepted)
    scanned_at     TEXT NOT NULL,     -- ISO timestamp
    PRIMARY KEY (project_name, category)
);
```

New methods:
- `save_standard(project_name, category, data, confidence)` — upsert
- `get_standards(project_name)` → `list[dict]` — all categories
- `get_standard(project_name, category)` → `dict | None`
- `clear_standards(project_name)` — delete all

---

### Standards Extraction (`context/`)

#### [NEW] [standards_analyzer.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/standards_analyzer.py)

`StandardsAnalyzer` ABC — each method returns `CategoryResult(dominant, confidence, alternatives, conflicts)`:

```python
@dataclass
class CategoryResult:
    dominant: dict          # e.g. {"style": "snake_case"}
    confidence: float       # 0.0–1.0, recency-weighted
    sample_size: int
    alternatives: dict      # minority patterns with locations
    conflicts: list[str]    # human-readable conflict notes

class StandardsAnalyzer(ABC):
    @abstractmethod
    def detect(self, directory: Path) -> bool: ...
    @abstractmethod
    def extract_naming(self, files: list[Path]) -> CategoryResult: ...
    @abstractmethod
    def extract_error_handling(self, files: list[Path]) -> CategoryResult: ...
    @abstractmethod
    def extract_type_coverage(self, files: list[Path]) -> CategoryResult: ...
    @abstractmethod
    def extract_docstring_style(self, files: list[Path]) -> CategoryResult: ...
    @abstractmethod
    def extract_test_patterns(self, files: list[Path]) -> CategoryResult: ...
    @abstractmethod
    def extract_import_patterns(self, files: list[Path]) -> CategoryResult: ...
```

#### [NEW] [python_standards.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/python_standards.py)

`PythonStandardsAnalyzer(StandardsAnalyzer)` — stdlib `ast` based. Recency-weighted via `mtime`.

#### [NEW] [js_standards.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/js_standards.py)

`JSStandardsAnalyzer(StandardsAnalyzer)` — `tree-sitter` AST based. Same categories.

#### [NEW] [standards_inferrer.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/standards_inferrer.py)

Orchestrator:

```python
class StandardsInferrer:
    def scan_project(self, project_path: Path) -> StandardsReport:
        """Walk tree (respecting ignores), run analyzers, compute variable half-life."""

    def compare_with_best_practices(self, report: StandardsReport) -> EnrichedReport:
        """LLM call: compare findings with community best practices."""

    def format_for_prompt(self, project_name: str) -> str:
        """Load from DB, format as concise text for <standards> block."""

    def _compute_half_life(self, project_path: Path) -> float:
        """Auto-compute decay half-life from project age (oldest file mtime)."""
```

Variable half-life formula:
```
project_age_years = (now - oldest_file_mtime) / 365
half_life_days = min(730, max(180, project_age_years * 120))
```
- Young project (1 year old): ~180 days half-life (6 months)
- Mid-age project (5 years): ~600 days half-life (~1.6 years)
- Legacy project (30 years): ~730 days half-life (2 years, capped)

#### [NEW] [recency.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/recency.py)

Recency weighting utilities:

```python
def recency_weight(file_mtime: float, half_life_days: float) -> float:
    """Exponential decay weight based on file modification time."""

def compute_half_life(project_path: Path) -> float:
    """Auto-compute from project age."""
```

#### [NEW] [ignore.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/ignore.py)

Ignore-file support:

```python
def load_ignore_patterns(project_path: Path) -> list[str]:
    """Load .gitignore + .specweaverignore patterns."""

def should_skip(path: Path, patterns: list[str]) -> bool:
    """Check if path matches any ignore pattern."""
```

---

### PromptBuilder (`llm/`)

#### [MODIFY] [prompt_builder.py](file:///c:/development/pitbula/specweaver/src/specweaver/llm/prompt_builder.py)

```python
def add_standards(self, text: str) -> PromptBuilder:
    """Add project standards (priority 1, truncatable).
    Rendered after <constitution>, before <topology>, inside <standards> tags.
    """
```

Render order: `<standards>` block added between `<constitution>` and `<topology>` in `_render()`.

---

### CLI (`cli.py`)

#### [MODIFY] [cli.py](file:///c:/development/pitbula/specweaver/src/specweaver/cli.py)

1. **`sw scan --standards`** — Run `StandardsInferrer.scan_project()` → LLM compare → HITL review → store to DB.
2. **`_load_standards_content()`** — Load from DB, format for prompt.
3. **Auto-injection** — `.add_standards()` in all PromptBuilder callers (review, implement, draft, sw run).
4. **Constitution bootstrap** — When `sw scan --standards` runs with no `CONSTITUTION.md`: auto-generate draft including project metadata (name, languages, architecture layers) + confirmed conventions.
5. **`sw standards show`** — Rich table per category (dominant, confidence, alternatives).
6. **`sw standards clear`** — Delete all standards for active project.

---

### Flow Engine (`flow/`)

#### [MODIFY] [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/flow/models.py)

Add `standards: str | None = None` to `RunContext`.

---

### Dependencies (`pyproject.toml`)

#### [MODIFY] [pyproject.toml](file:///c:/development/pitbula/specweaver/pyproject.toml)

Add `tree-sitter` + `tree-sitter-javascript` + `tree-sitter-typescript` to production dependencies.

---

## Verification Plan

### Automated Tests

**Unit tests** (~150-180 tests expected):
- `tests/unit/context/test_python_standards.py` — each category with fixtures
- `tests/unit/context/test_js_standards.py` — tree-sitter based extraction
- `tests/unit/context/test_standards_inferrer.py` — orchestration, half-life, ignores
- `tests/unit/context/test_recency.py` — decay formula, variable half-life
- `tests/unit/context/test_ignore.py` — gitignore + specweaverignore parsing
- `tests/unit/config/test_database_v6.py` — schema migration, CRUD
- `tests/unit/llm/test_prompt_builder_standards.py` — `add_standards()`, render order
- Edge cases: empty project, conflicting practices, single-file project, mixed languages

**Integration tests** (~25-35 tests):
- `tests/integration/context/test_standards_scan.py` — real project scan → DB → prompt
- `tests/integration/cli/test_cli_standards.py` — `sw scan --standards`, `sw standards show/clear`
- `tests/integration/cli/test_cli_constitution_bootstrap.py` — auto-generation from standards

**Commands:**
```
uv run pytest tests/ -x -q
uv run ruff check src/ tests/
```

### Manual Verification
- Run `sw scan --standards` on SpecWeaver's own codebase → HITL flow → verify DB
- Run `sw standards show` → verify Rich table output
- Run `sw review` → verify `<standards>` block in prompt
