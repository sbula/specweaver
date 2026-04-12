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

**Goal**: Multi-language support, single-pass AST execution, and Pydantic-structured LLM enrichment.

| Component | What |
|---|---|
| `pyproject.toml` | Add `tree-sitter>=0.22.0`, `tree-sitter-javascript`, `tree-sitter-typescript` dependencies. |
| `standards/analyzer.py` | Refactor base `StandardsAnalyzer` to `extract_all(files) -> list[CategoryResult]` to enforce single-pass AST parsing. Retain independent category extractor methods for isolation. |
| `standards/languages/` | Move `python_analyzer.py` here. Add `tree_sitter_base.py` interface. Add `javascript/analyzer.py` and `typescript/analyzer.py`. |
| `standards/scanner.py` | `StandardsScanner`: Orchestrate file discovery, auto-detect language by extension, and execute mapped analyzers. |
| `standards/enricher.py` | `StandardsEnricher`: Async LLM comparison (`asyncio.gather`). Requests Pydantic JSON structure. Only fires for confidence < 90% or `--compare` flag. |
| `cli/standards.py` | `--compare` flag. Color-coded UI warnings for LLM deviations in HITL report. |

**Tests**: ~60-80 tests. tree-sitter fixtures, LLM component mocking.
**Deliverable**: Scan a project with Python backend + TypeScript frontend, each gets auto-detected language-appropriate standards with LLM enrichment.

---

### Phase 3.5a-4: Constitution Bootstrap + Polish

**Goal**: Auto-generate `CONSTITUTION.md` from confirmed standards, finalize edge cases, update documentation.

**Resolved design decisions** (from discussion):

| # | Decision | Resolution |
|---|---|---|
| 1 | Where to implement bootstrap | Option A — `generate_constitution_from_standards()` in `project/constitution.py`. Constitution generators stay together; standards data passed as plain `list[dict]`. |
| 2 | Auto-trigger | **Separate step**. `sw init` prints hint for existing projects: *"Existing code detected. Run `sw standards scan` to discover conventions."* After `sw standards scan`, HITL hint: *"Run `sw constitution bootstrap` to generate CONSTITUTION.md."* |
| 3 | Config values | `auto_bootstrap_constitution` column: `'off'` \| `'prompt'` (default) \| `'auto'`. |
| 4 | Schema migration | v7: only `auto_bootstrap_constitution`. Skip `rescan_mode` until needed. |
| 5 | CLI command | `sw constitution bootstrap` (grouped by output artifact, not input source). |
| 6 | Overwrite behavior | Option B — detect unmodified starter template (check for TODO markers) and auto-replace. User-edited constitutions require `--force`. |

| Component | What |
|---|---|
| `config/database.py` | Schema v7: `ALTER TABLE projects ADD COLUMN auto_bootstrap_constitution TEXT DEFAULT 'prompt'`. Methods: `get_auto_bootstrap()`, `set_auto_bootstrap()`. |
| `project/constitution.py` | New `generate_constitution_from_standards(project_path, project_name, standards, languages)` → pre-fills sections 1 (Identity), 2 (Tech Stack), 4 (Coding Standards) from confirmed data. New `_STANDARDS_TEMPLATE` alongside existing `_STARTER_TEMPLATE`. Idempotent. |
| `cli/constitution.py` | New `sw constitution bootstrap` command: loads confirmed standards from DB, calls `generate_constitution_from_standards()`, supports `--force`. |
| `cli/standards.py` | After successful scan (line ~156): print HITL hint *"Run `sw constitution bootstrap`..."* when no `CONSTITUTION.md` exists. Respect `auto_bootstrap` config: `'auto'` → bootstrap silently, `'prompt'` → Rich prompt, `'off'` → just hint. |
| `cli/projects.py` | After `sw init` scaffold (line ~59): if existing source files detected, print hint: *"Existing code detected. Run `sw standards scan` to discover coding conventions."* |
| `cli/config.py` | New `sw config set-auto-bootstrap` / `sw config get-auto-bootstrap` commands. |
| Edge cases (scan + bootstrap) | Empty project, single-file, all-below-threshold, project with no git, mixed languages in one scope — test both scan path and bootstrap path. |
| Documentation | `README.md` (constitution bootstrap bullet + CLI table), `docs/quickstart.md` (scan→bootstrap flow), `docs/developer_guide.html` (if applicable), `docs/roadmap/phase_3_feature_expansion.md` (mark 3.5 ✅). |

**Tests**: ~20-30 tests.
- **Unit** (~12): `generate_constitution_from_standards()` variations (Python-only, multi-lang, empty standards, idempotent, `--force`), schema v7 migration, get/set auto_bootstrap.
- **Integration** (~8): scan→bootstrap flow, `sw init` hint for existing project, `sw constitution bootstrap` CLI, config round-trip.
- **Edge cases** (~8): empty project scan, single-file scan, all-below-threshold scan, no-git fallback, mixed-languages-in-scope scan, bootstrap with zero standards, bootstrap with existing `CONSTITUTION.md`, bootstrap after `--force`.
- **Verification**: `/pre-commit-test-gap` workflow after implementation.

**Deliverable**: Feature 3.5a complete. All tests passing, documentation updated, roadmap marked ✅.

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
    def extract_all(self, files: list[Path], half_life_days: float) -> list[CategoryResult]: ...
```

#### [NEW] [python_analyzer.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/python_analyzer.py)

7 categories: naming, error_handling, type_hints, docstrings, test_patterns, import_patterns, async_patterns.

#### [NEW] [tree_sitter_base.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/tree_sitter_base.py)

Base class for `TreeSitterAnalyzer` to establish tree-sitter bindings.

#### [NEW] [languages/javascript/analyzer.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/languages/javascript/analyzer.py)
#### [NEW] [languages/typescript/analyzer.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/languages/typescript/analyzer.py)

Implements language-specific AST node traversal categories (`typescript_types` for TS, `jsdoc`/`tsdoc`, etc.).

#### [NEW] [scanner.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/scanner.py)

Contains `StandardsScanner` which handles orchestration: detecting scopes, mapping languages, and iterating analyzers.

#### [NEW] [enricher.py](file:///c:/development/pitbula/specweaver/src/specweaver/standards/enricher.py)

Contains `StandardsEnricher` which handles async LLM comparison loops via Pydantic output parsing.

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

---

## Phase 3.5b: Validation Override Consolidation

**Goal**: Eliminate duplicated threshold definitions between `profiles.py` Python dicts and YAML pipeline files. Establish a clean, well-documented separation: YAML = structure, DB = runtime tuning.

### Design Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Overall approach | DB overrides as runtime layer on top of YAML |
| 2 | Legacy functions | Remove `get_spec_rules()`/`get_code_rules()` immediately |
| 3 | Profile mechanism | Profile just selects YAML pipeline, no DB override writes |
| 4 | Pipeline conflict | `--pipeline` explicitly overrides profile |
| 5 | Custom profiles | Supported via `.specweaver/pipelines/validation_spec_*.yaml` |
| 6 | `_THRESHOLD_PARAMS` | Fix now: rules self-declare `PARAM_MAP` |
| 7 | Feature-level + profiles | Independent — `--level feature` always uses `validation_spec_feature.yaml` |

### Validation Override Cascade (The Contract)

```
Precedence: YAML base < extends < DB overrides < --set flags

Layer 1: YAML Pipeline (STRUCTURE)
├─ Which rules run, in what order, with what base params
├─ Profile-specific tuning via extends/override/remove/add
├─ Auto-selected via: active profile OR --pipeline flag
└─ Files: specweaver/pipelines/validation_spec_*.yaml
         .specweaver/pipelines/validation_spec_*.yaml (custom)

Layer 2: DB Overrides (RUNTIME TUNING)
├─ Per-project, per-rule enable/disable + threshold tweaks
├─ Written by: sw config set <rule> --warn/--fail/--enabled
├─ NOT written by sw config set-profile (profile = YAML only)
└─ Storage: validation_overrides table in specweaver.db

Layer 3: CLI --set Flags (EPHEMERAL)
├─ One-off, session-only override. Highest precedence.
└─ Example: sw check --set S08.fail_threshold=2
```

### Architecture Validation

| Module | Archetype | Boundary Respected? |
|--------|-----------|---------------------|
| `validation/` | pure-logic, consumes `config/` | ✅ `_THRESHOLD_PARAMS` moves within module |
| `config/` | pure-logic, leaf | ✅ `profiles.py` stays here, `database.py` simplified |
| `cli/` | orchestrator | ✅ Profile→pipeline selection logic is CLI concern |
| `pipelines/` | data | ✅ No code changes, YAML files only |

### Sub-Phase B-1: Profiles Select YAML Pipelines

| Component | What |
|---|---|
| `config/profiles.py` | Remove `PROFILES` dict and `DomainProfile` class. `list_profiles()` scans YAML files. `get_profile_description(name)` loads YAML description. |
| `config/database.py` | `set_domain_profile()` simplified: only stores name, no bulk-write to `validation_overrides`. `clear_domain_profile()` only clears name, keeps per-rule tweaks. |
| `cli/validation.py` | `check()`: auto-select `validation_spec_{profile_name}.yaml` when profile active. Precedence: `--pipeline` > `--level` > active profile > default. `--level feature` always uses `validation_spec_feature.yaml`. |
| `cli/config.py` | `config_set_profile()` simplified. `config_show_profile()` sources from YAML. `config_reset_profile()` only clears profile name. |

### Sub-Phase B-2: Remove Legacy + Self-Declaring Rules

| Component | What |
|---|---|
| `validation/models.py` | Add `PARAM_MAP: ClassVar[dict[str, str]] = {}` to `Rule` ABC. Maps DB-column-like names to constructor kwargs. |
| 8 configurable rules | Add `PARAM_MAP` to S01, S03, S04, S05, S07, S08, S11, C04. Each rule self-declares its param mapping. |
| `validation/executor.py` | Move `_build_rule_kwargs` here, rewrite to use `rule_cls.PARAM_MAP` instead of hardcoded `_THRESHOLD_PARAMS`. |
| `validation/runner.py` | Remove: `get_spec_rules()`, `get_code_rules()`, `_build_rule_kwargs()`, `_THRESHOLD_PARAMS`. Keep: `run_rules()`, `count_by_status()`, `all_passed()`. |
| 4 test files (~45 calls) | Rewrite to use pipeline executor path instead of removed functions. |

### Sub-Phase B-3: Documentation

| Component | What |
|---|---|
| `README.md` | Add "Validation Override Cascade" section |
| `docs/quickstart.md` | Update profile behavior documentation |
| `validation_spec_default.yaml` | Add cascade comment block |
| `context.yaml` (validation, pipelines) | Update descriptions |


### Tests

- **Unit** (~15): Profile YAML listing, profile-to-pipeline selection, `PARAM_MAP` self-declaration, `set_domain_profile()` simplified behavior, `clear_domain_profile()` preserves overrides
- **Integration** (~10): `sw config set-profile` → pipeline selection, `sw check` with active profile, `--pipeline` overrides profile, `--level feature` ignores profile, DB override on top of profile pipeline
- **Edge cases** (~5): Custom profile from `.specweaver/`, reset-profile keeps tweaks, unknown profile error, profile + `--set` combined

**Verification**: `/pre-commit-test-gap` workflow (5 phases).

