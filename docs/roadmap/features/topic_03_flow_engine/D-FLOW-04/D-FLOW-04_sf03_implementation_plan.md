# D-FLOW-04 SF-03 — Logging Rollout

**Status**: APPROVED · **FRs owned**: FR-6 · **Depends on**: SF-01 · **Feature ID**: 3.13a ·
Design: [D-FLOW-04_design.md](D-FLOW-04_design.md) §Sub-features → SF-03

## Goal

Add `logger.debug()`, `logger.info()`, `logger.warning()` and `logger.error()` calls to every class
and public method in `src/specweaver/`. SF-01 built the infrastructure: `RichHandler` on the console
(WARNING+), `JSONFormatter` + `RotatingFileHandler` writing DEBUG JSON logs to
`~/.specweaver/logs/<project>/specweaver.log`.

## Where it plugs in

State as of 2026-03-29:

- ~47 modules have `logger = logging.getLogger(__name__)` AND active log calls (e.g.,
  `core/flow/runner.py`, `context/inferrer.py`, `config/database.py`) → **audit pass** (method entry,
  error paths, key decisions).
- ~10 modules declare `logger = logging.getLogger(__name__)` with minimal/no log calls → **add calls**.
- ~30+ modules have neither `import logging` nor a logger → import, declaration and calls.
- Infrastructure: `src/specweaver/telemetry_logger.py`. Every module in the `specweaver` namespace
  reaches it through the logger hierarchy (`logging.getLogger(__name__)` →
  `specweaver.core.config.settings` → propagates to root `specweaver` logger).

The "Has logger" / "Missing logger" notes below reflect 2026-03-29. `/dev` re-reads each file before
editing; verify the actual state — a file may have been refactored since.

## Decisions (HITL-approved 2026-03-29 — not to be reopened)

| # | Decision | Resolution |
|---|----------|------------|
| D1 | **Logging granularity** | Public methods + error paths + key decision points ONLY. Private helpers only with non-trivial branching (3+ branches or a try/except). No trivial getters, property access, simple delegation. |
| D2 | **Batch size** | 4 commit boundaries, one per architectural layer (config/context/project → domain → infrastructure/llm/core/flow/sandbox → interfaces/cli/api). |
| D3 | **Test strategy** | A single `tests/unit/test_logging_rollout.py` spot-checking 5-6 representative modules. No per-module logging tests. Existing behavioral tests prove nothing broke. |
| D4 | **Exclusions** | Pure data models and `__init__.py` files are EXCLUDED. See the list below. |
| D5 | **CLI logging** | Operational DEBUG logging alongside existing `console.print()`, never replacing Rich output. Logs command entry, project resolution, error paths — for the log file, not the terminal. |

### Excluded files

No behavior worth logging (data models, constants, type definitions, re-exports):

- `src/specweaver/__init__.py` (and ALL `__init__.py` files except `infrastructure/llm/adapters/__init__.py`, which has
  auto-discovery logic)
- `src/specweaver/core/flow/engine/models.py`, `src/specweaver/core/flow/engine/state.py`,
  `src/specweaver/infrastructure/llm/models.py`, `src/specweaver/assurance/validation/models.py`,
  `src/specweaver/workflows/planning/models.py` — pure Pydantic data models
- `src/specweaver/infrastructure/llm/errors.py` — pure exception definitions
- `src/specweaver/infrastructure/llm/_prompt_constants.py` — pure string constants
- `src/specweaver/workspace/project/_templates.py` — pure string templates
- `src/specweaver/sandbox/*/interfaces/definitions.py` — pure tool definition constants
- `src/specweaver/sandbox/*/interfaces/facades.py` — thin delegation facades (no logic)
- `src/specweaver/workspace/context/provider.py` — pure Protocol/interface definition
- `src/specweaver/assurance/validation/rules/spec/*.py`, `src/specweaver/assurance/validation/rules/code/*.py` — pure
  validation functions (input→finding), too granular for logging

Rule: a file with ONLY Pydantic `BaseModel` classes, `TypedDict`, `Enum`, `Protocol` definitions, string
constants, `ToolDefinition` lists or `@abstractmethod` stubs is excluded. ANY method with real control
flow (if/else, try/except, loops, function calls) → included.

### Audit checklist ("Has logger" files)

For EVERY public method (no leading `_`), not just "a logger exists":

1. **Entry log?** `logger.debug("method_name called ...")` at or near the top. Missing → add.
2. **Error paths?** A `logger.error()` or `logger.warning()` before every `raise`; a `logger.warning()`,
   `logger.error()` or `logger.exception()` in every `except`. Missing → add.
3. **Key decisions?** A `logger.info()` or `logger.debug()` on branches that pick fundamentally
   different behavior (fallback to default, skip vs. process). Missing → add.
4. **Result log?** `logger.debug("method_name completed ...")` near a meaningful (non-`None`) return —
   OPTIONAL, only for methods with 5+ lines of logic.

All 4 pass → no change; mark audited.

### Scope

- **In**: `import logging` + `logger = logging.getLogger(__name__)` where missing;
  `logger.debug()` / `logger.info()` / `logger.warning()` / `logger.error()` calls in public methods and
  error paths; auditing already-instrumented modules with the checklist.
- **Out** (absolutely not): changing function signatures, return types or behavioral logic; new
  dependencies (logging is stdlib); modifying the infrastructure (`src/specweaver/telemetry_logger.py`
  — SF-01); replacing `console.print()` with `logger.info()`; structured/typed log records or event
  schemas; changing exception handling (e.g., adding try/except where none exists).

## Changes

4 batches by architectural layer; each is a commit boundary followed by the full test suite +
`/pre-commit`.

### Batch 1 — Core Infrastructure (config/, context/, project/) · Commit Boundary 1 of 4

Leaf-level modules first, so foundations are instrumented before their consumers.

| File | Work |
|---|---|
| `core/config/settings.py` | **Missing** `import logging` + logger — details below the table |
| `core/config/paths.py` | add logger if missing; path resolution results (DEBUG) |
| `core/config/profiles.py` | **Has logger**: audit; profile resolution/lookup (DEBUG) if insufficient |
| `core/config/database.py` | **Has logger**: audit; project registration, profile linking, migration at least DEBUG; missing entry/exit logs |
| `workspace/context/inferrer.py` | **Has logger + active calls**: audit only |
| `workspace/context/hitl_provider.py` | add logger if missing; question prompts and user response *lengths* (DEBUG) — never response content (may be sensitive) |
| `workspace/project/scaffold.py` | **Has logger**: audit; scaffold creation steps (INFO) |
| `workspace/project/constitution.py` | **Has logger**: audit; discovery and validation (DEBUG) |
| `workspace/ast/` (all parsers + base modules) | add logger if missing; parser initialization and parsing steps (DEBUG) |
| `workspace/project/discovery.py` | add logger if missing; project discovery (DEBUG) |
| `workspace/project/_helpers.py` | **Has logger**: audit; helper functions (DEBUG) |

`settings.py`: `load_settings()` — entry with project_name/role (DEBUG), resolved provider (DEBUG),
profile fallback (INFO). `load_settings_for_active()` — entry + active project name (DEBUG).
`migrate_legacy_config()` — entry (DEBUG), result "migrated" vs "no config.yaml found" (INFO).

Orphan entries in the approved plan (their file heading was lost in an earlier edit): add logger if
missing, log schema migration steps (version transitions, INFO); add logger if missing, log profile CRUD
(DEBUG); audit — config read/write ops (DEBUG); audit — extension discovery (DEBUG); audit — telemetry
flush/read (DEBUG); add logger if missing — analyzer factory dispatch and analysis results (DEBUG).

### Batch 2 — Domain Logic · Commit Boundary 2 of 4

assurance/validation/, assurance/standards/, graph/, workflows/planning/, workflows/review/,
workflows/drafting/, workflows/implementation/.

"Audit" = **Has logger**, run the checklist. "Add" = add a logger (if missing) and the calls.

- **`assurance/validation/` (6 files)** — audit, all DEBUG: `executor.py` rule execution
  start/result · `runner.py` batch entry/exit + per-rule results · `registry.py` rule
  registration/discovery · `inheritance.py` pipeline inheritance resolution · `loader.py` spec
  loading/parsing · `pipeline_loader.py` pipeline YAML loading. Add: `pipeline.py` pipeline execution
  (DEBUG); `spec_kind.py` if it has control flow, spec kind detection (DEBUG).
- **`assurance/standards/` (12 files)** — audit: `discovery.py`, `enricher.py`, `loader.py`,
  `reviewer.py`, `scanner.py`, `scope_detector.py`, `tree_sitter_base.py`,
  `languages/python/analyzer.py`, `languages/javascript/analyzer.py`,
  `languages/typescript/analyzer.py`. Add: `analyzer.py` analysis entry/results, `recency.py` recency
  checks (DEBUG).
- **`graph/` (2 files)** — audit `topology.py`: graph building, cycle detection, impact analysis
  (DEBUG). Add `selectors.py`: selector queries (DEBUG).
- **`workflows/evaluators/`** — add to all evaluators: evaluation steps (DEBUG).
- **`graph/lineage/`** — add to all store and domain modules: lineage events (DEBUG).
- **`workflows/planning/` (4 files)** — audit `planner.py`, `stitch.py`. Add `renderer.py` rendering
  steps, `ui_extractor.py` extraction steps (DEBUG).
- **`workflows/review/` (1 file)** — audit `reviewer.py`: review invocation, LLM call, verdict parsing
  (DEBUG/INFO).
- **`workflows/drafting/` (3 files)** — `drafter.py` is **missing a logger entirely**: add
  `import logging` + `logger = logging.getLogger(__name__)`; `draft()` entry with component name
  (DEBUG), section iteration (DEBUG), file write (INFO); `_generate_section()` LLM call (DEBUG). Add
  `decomposition.py` decomposition steps, `feature_drafter.py` feature drafting steps (DEBUG).
- **`workflows/implementation/` (1 file)** — audit `generator.py`: code and test generation steps
  (DEBUG/INFO).

### Batch 3 — LLM & Flow Engine (infrastructure/llm/, core/flow/, sandbox/) · Commit Boundary 3 of 4

- **`infrastructure/llm/` (8 files + adapters)** — audit `router.py`, `factory.py`, `collector.py`.
  Add: `prompt_builder.py` block assembly — block name, priority (DEBUG); `telemetry.py` cost
  estimation (DEBUG); `_prompt_render.py` if its render functions have control flow (DEBUG);
  `mention_scanner/scanner.py` mention scanning (DEBUG). Skip `mention_scanner/models.py` (pure data
  models).
- **`infrastructure/llm/adapters/` (6 files)** — audit `__init__.py` auto-discovery scanning (DEBUG),
  `gemini.py` API call entry/exit, error paths (DEBUG/WARNING). Add: `base.py` if base-class methods
  have concrete behavior; `openai.py`, `anthropic.py`, `mistral.py`, `qwen.py`: API call entry/exit
  (DEBUG), errors (WARNING).
- **`core/flow/` (9 files)** — `runner.py` is **already well-instrumented**: audit pass only. Audit
  `gates.py`, `store.py`. Audit `_base.py`, `_draft.py`, `_review.py`, `_generation.py`,
  `_validation.py`, `_lint_fix.py`, `_standards.py`: entry/exit logging for `execute()` (DEBUG). Add
  `display.py` display events, `parser.py` YAML parsing (DEBUG).
- **`sandbox/language/`** — all language core and interfaces, if missing: execution boundaries
  (DEBUG).
- **`sandbox/`** — add logger if missing: mcp/core/executor.py, mcp/interfaces/tool.py,
  protocol/core/atom.py, protocol/core/factory.py, protocol/interfaces/tool.py, qa_runner/core/atom.py,
  qa_runner/interfaces/tool.py, web/interfaces/tool.py.

### Batch 4 — Entry Points (interfaces/cli/, interfaces/api/) · Commit Boundary 4 of 4

**Decentralized CLI interfaces (16 files)** — add logger (if missing):
interfaces/cli/main.py, interfaces/cli/routers/serve_router.py,
core/config/interfaces/cli.py (command entry at DEBUG), core/config/cli_db_utils.py,
graph/interfaces/cli.py, assurance/validation/interfaces/cli.py,
assurance/validation/interfaces/cli_drift.py, assurance/standards/interfaces/cli.py,
infrastructure/llm/interfaces/cli.py, workflows/implementation/interfaces/cli.py,
workflows/review/interfaces/cli.py, workspace/project/interfaces/cli.py,
workspace/project/interfaces/cli_constitution.py, workspace/project/interfaces/cli_hooks.py,
core/flow/interfaces/cli.py. Audit: interfaces/cli/_core.py (**Has logger** — main app callbacks at
DEBUG).

CLI modules keep console.print() for user-facing output; the added logger.debug() calls record
operational state for post-mortem debugging and are NOT visible to the terminal user.

**interfaces/api/** — add logger if missing:

| Level | Files |
|---|---|
| INFO | `app.py` app startup/config |
| DEBUG | `deps.py` dependency injection · `v1/constitution.py`, `v1/implement.py`, `v1/paths.py`, `v1/pipelines.py`, `v1/projects.py`, `v1/review.py`, `v1/standards.py`, `v1/validation.py` endpoint handling · `v1/health.py` health checks · `ui/htmx.py` page rendering · `ui/routes.py` route handling |
| WARNING | `errors.py` error handler invocations |

Audit: `event_bridge.py`, `v1/ws.py` (**Has logger**). Skip `v1/schemas.py` (pure Pydantic models).

## Logging pattern

Every instrumented module MUST follow this exact pattern:

```python
# At module level, AFTER all other imports, BEFORE any module-level code:
import logging

logger = logging.getLogger(__name__)
```

`import logging` goes in the standard-library imports section (alphabetically);
`logger = logging.getLogger(__name__)` AFTER the last import, BEFORE any constants or class definitions —
the existing convention (see `core/flow/runner.py`, `config/database.py`).

| Level | When to use | Example |
|-------|-------------|---------|
| `logger.debug()` | Method entry/exit, intermediate state, variable values | `logger.debug("load_settings called for project=%s, role=%s", name, role)` |
| `logger.info()` | Significant lifecycle events: startup, completion, migration, file writes | `logger.info("Generated spec file at %s", spec_path)` |
| `logger.warning()` | Recoverable failures, fallbacks, missing optional config | `logger.warning("No profile found for %s, using system-default", name)` |
| `logger.error()` | Unrecoverable errors right before raising an exception | `logger.error("Project '%s' not found in database", name)` |
| `logger.exception()` | Caught exceptions where you want the full traceback in the log | `logger.exception("Failed to parse config at %s", path)` |

```python
# Method entry (DEBUG):
def load_settings(db: Database, project_name: str, *, llm_role: str = "review") -> SpecWeaverSettings:
    logger.debug("load_settings called for project=%s, role=%s", project_name, llm_role)

# Key decision point (INFO or WARNING):
    if not profile:
        logger.info("No profile for project=%s role=%s, falling back to system-default", project_name, llm_role)
        profile = db.get_llm_profile_by_name("system-default")

# Error before raise (ERROR):
    if not proj:
        logger.error("Project '%s' not found in database", project_name)
        raise ValueError(msg)

# Exception with traceback (EXCEPTION):
    try:
        data = yaml.load(config_file)
    except YAMLError:
        logger.exception("Failed to parse legacy config at %s", config_file)
        data = {}
```

> [!CAUTION]
> **NEVER use f-strings in log calls.** Always lazy %-style formatting:
> ✅ `logger.debug("Processing %s", name)` · ❌ `logger.debug(f"Processing {name}")`
>
> **NEVER log sensitive data**: API keys, tokens or secrets; full user input content (length only if
> needed); full file contents (path only); full LLM responses (token count / status only).

## Tests

TDD per task, using pytest's `caplog` fixture. **Red**: assert the module's logger emits records — fails
because the logging is not there yet. **Green**: add `import logging` + `logger = logging.getLogger(__name__)`
+ calls; re-run. **Refactor**: none needed; run `ruff check` and fix.

`test_logging_rollout.py` grows per task batch — add the Red test for the current batch, then Green. Not
all tests upfront. Skeleton:

```python
"""Tests for logging rollout — verifies key modules emit structured log records."""

import logging

import pytest


class TestBatch1LoggingRollout:
    """Verify Batch 1 modules emit log records."""

    def test_load_settings_emits_debug_log(self, caplog, tmp_path, monkeypatch):
        """load_settings() should emit a DEBUG entry log."""
        # This test WILL FAIL (red) before logging is added to settings.py
        # because no logger.debug() call exists in load_settings().
        from specweaver.core.config.settings import load_settings

        # We don't need a real DB — we just need to trigger the log call.
        # Use a mock or catch the ValueError and check logs before it.
        with caplog.at_level(logging.DEBUG, logger="specweaver.core.config.settings"):
            try:
                load_settings(None, "nonexistent")  # type: ignore[arg-type]
            except (ValueError, TypeError, AttributeError):
                pass  # expected — we only care about the log

        assert any(
            "load_settings" in r.message and r.levelno == logging.DEBUG
            for r in caplog.records
        ), "load_settings() should emit a DEBUG-level entry log"


class TestBatch2LoggingRollout:
    """Verify Batch 2 modules have logger declarations."""

    def test_drafter_has_logger(self):
        """workflows/drafting/drafter.py should declare a module-level logger."""
        from specweaver.workflows.drafting import drafter

        assert hasattr(drafter, "logger"), "drafter module must have a logger"
        assert isinstance(drafter.logger, logging.Logger)
        assert drafter.logger.name == "specweaver.workflows.drafting.drafter"


class TestBatch3LoggingRollout:
    """Verify Batch 3 modules have logger declarations."""

    def test_prompt_builder_has_logger(self):
        """infrastructure/llm/prompt_builder.py should declare a module-level logger."""
        from specweaver.infrastructure.llm import prompt_builder

        assert hasattr(prompt_builder, "logger"), "prompt_builder module must have a logger"
        assert isinstance(prompt_builder.logger, logging.Logger)


class TestBatch4LoggingRollout:
    """Verify Batch 4 modules have logger declarations."""

    def test_cli_review_has_logger(self):
        """workflows/review/interfaces/cli.py should declare a module-level logger."""
        from specweaver.workflows.review.interfaces import cli as review_cli

        assert hasattr(review_cli, "logger"), "workflows/review/interfaces/cli module must have a logger"
        assert isinstance(review_cli.logger, logging.Logger)
```

Spot-checks per batch:

- Batch 1: `config/settings.py` → `load_settings()` emits a DEBUG log (via `caplog`)
- Batch 2: `workflows/drafting/drafter.py` → module-level `logger` attribute exists and is a `logging.Logger`
- Batch 3: `infrastructure/llm/prompt_builder.py` → module-level `logger` attribute exists
- Batch 4: `workflows/review/interfaces/cli.py` → module-level `logger` attribute exists

All existing tests must pass unchanged — logging must not change behavior:

```
python run_unit_tests.py
python run_integ_tests.py
python run_e2e_tests.py
```

Logging smoke test:

```
python -m pytest tests/unit/test_logging_rollout.py -v --tb=short
```

Lint clean:

```
ruff check src/ tests/
```

Manual: `sw review` on a sample spec with `--debug` shows DEBUG logs from the instrumented modules on
the console; `~/.specweaver/logs/<project>/specweaver.log` holds JSON entries from multiple modules.

## Task breakdown for `/dev`

Pre-defines the `task.md` structure; use as-is, adjusting only for files changed since. One task = one
TDD cycle; each maps to 1-3 closely related files (same package, same pattern).

### Commit Boundary 1 of 4: Core Infrastructure

```
- [ ] Task 1.1: Instrument config/settings.py + config/paths.py
      Source: src/specweaver/core/config/settings.py, src/specweaver/core/config/paths.py
      Test: tests/unit/test_logging_rollout.py::TestBatch1LoggingRollout

      Test: tests/unit/test_logging_rollout.py (extend TestBatch1)

- [ ] Task 1.3: Audit config/profiles.py + config/database.py + config/_db_*_mixin.py (3 files)
      Source: src/specweaver/core/config/profiles.py, src/specweaver/core/config/database.py,
      Test: Existing tests pass (audit-only — add log calls where missing per checklist)

- [ ] Task 1.4: Instrument + audit context/ modules
              src/specweaver/workspace/context/hitl_provider.py
      Test: tests/unit/test_logging_rollout.py (extend TestBatch1)

- [ ] Task 1.5: Instrument + audit project/ modules
      Source: src/specweaver/workspace/project/scaffold.py (audit), src/specweaver/workspace/project/constitution.py (audit),
              src/specweaver/workspace/project/discovery.py, src/specweaver/workspace/project/_helpers.py (audit)
      Test: tests/unit/test_logging_rollout.py (extend TestBatch1)

- [ ] Task 1.6: Instrument workspace/ast/ parsers
      Source: All python files under workspace/ast/
      Test: Existing tests pass

--- COMMIT BOUNDARY 1 → run full test suite + /pre-commit ---
```

### Commit Boundary 2 of 4: Domain Logic

```
- [ ] Task 2.1: Audit assurance/validation/ modules (6 files with existing loggers)
      Source: assurance/validation/executor.py, assurance/validation/runner.py, assurance/validation/registry.py,
              assurance/validation/inheritance.py, assurance/validation/loader.py, assurance/validation/pipeline_loader.py
      Test: Existing tests pass

- [ ] Task 2.2: Instrument assurance/validation/pipeline.py + assurance/validation/spec_kind.py
      Source: src/specweaver/assurance/validation/pipeline.py, src/specweaver/assurance/validation/spec_kind.py
      Test: tests/unit/test_logging_rollout.py (extend TestBatch2)

- [ ] Task 2.3: Audit + instrument assurance/standards/ modules (12 files)
      Source: All files listed under assurance/standards/ in Batch 2
      Test: Existing tests pass

- [ ] Task 2.4: Audit + instrument graph/, workflows/planning/ modules
      Source: graph/topology.py (audit), graph/selectors.py, workflows/planning/planner.py (audit),
              workflows/planning/renderer.py, workflows/planning/stitch.py (audit), workflows/planning/ui_extractor.py
      Test: tests/unit/test_logging_rollout.py (extend TestBatch2)

- [ ] Task 2.5: Instrument workflows/drafting/ + audit workflows/review/ + workflows/implementation/
      Source: workflows/drafting/drafter.py, workflows/drafting/decomposition.py, workflows/drafting/feature_drafter.py,
              workflows/review/reviewer.py (audit), workflows/implementation/generator.py (audit)
      Test: tests/unit/test_logging_rollout.py::TestBatch2LoggingRollout

- [ ] Task 2.6: Instrument workflows/evaluators/ and graph/lineage/
      Source: All python files under workflows/evaluators/ and graph/lineage/
      Test: Existing tests pass

--- COMMIT BOUNDARY 2 → run full test suite + /pre-commit ---
```

### Commit Boundary 3 of 4: LLM & Flow Engine

```
- [ ] Task 3.1: Instrument infrastructure/llm/ core modules
      Source: infrastructure/llm/prompt_builder.py, infrastructure/llm/telemetry.py, infrastructure/llm/_prompt_render.py,
              infrastructure/llm/mention_scanner/scanner.py
      Test: tests/unit/test_logging_rollout.py::TestBatch3LoggingRollout

- [ ] Task 3.2: Audit infrastructure/llm/ existing + instrument adapters
      Source: infrastructure/llm/router.py (audit), infrastructure/llm/factory.py (audit), infrastructure/llm/collector.py (audit),
              infrastructure/llm/adapters/__init__.py (audit), infrastructure/llm/adapters/base.py,
              infrastructure/llm/adapters/gemini.py (audit), infrastructure/llm/adapters/openai.py,
              infrastructure/llm/adapters/anthropic.py, infrastructure/llm/adapters/mistral.py, infrastructure/llm/adapters/qwen.py
      Test: Existing tests pass

- [ ] Task 3.3: Audit + instrument core/flow/ modules
      Source: core/flow/runner.py (audit), core/flow/gates.py (audit), core/flow/store.py (audit),
              core/flow/_base.py (audit), core/flow/_draft.py (audit), core/flow/_review.py (audit),
              core/flow/_generation.py (audit), core/flow/_validation.py (audit),
              core/flow/_lint_fix.py (audit), core/flow/_standards.py (audit),
              core/flow/display.py, core/flow/parser.py
      Test: Existing tests pass

- [ ] Task 3.4: Audit + instrument sandbox/ modules
      Source: All files listed under sandbox/ in Batch 3
      Test: Existing tests pass

- [ ] Task 3.5: Instrument sandbox/language/ modules
      Source: All python files under sandbox/language/
      Test: Existing tests pass

--- COMMIT BOUNDARY 3 → run full test suite + /pre-commit ---
```

### Commit Boundary 4 of 4: Entry Points

```
- [ ] Task 4.1: Instrument + audit decentralized CLI interfaces (16 files)
      Source: All cli.py and interfaces/cli files listed in Batch 4
      Test: tests/unit/test_logging_rollout.py::TestBatch4LoggingRollout

- [ ] Task 4.2: Instrument + audit interfaces/api/ modules
      Source: All files listed under interfaces/api/ in Batch 4
      Test: Existing tests pass

--- COMMIT BOUNDARY 4 → run full test suite + /pre-commit ---
```

## As built

Committed (`7029da5d`, "complete universal logging rollout" — SF-03). `tests/unit/test_logging_rollout.py`
holds per-batch classes `TestBatch1LoggingRollout` … `TestBatch4LoggingRollout`.

**Since moved**: flow handlers are `src/specweaver/core/flow/handlers/*.py` (no leading underscore:
`draft.py`, `review.py`, `generation.py`, `validation.py`, `lint_fix.py`, `standards.py`). Paths above
are as of the plan's date.
