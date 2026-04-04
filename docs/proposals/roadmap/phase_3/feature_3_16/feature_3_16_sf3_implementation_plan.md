# Implementation Plan: Unified Runner Architecture & Universal Logging [SF-3: Logging Rollout]
- **Feature ID**: 3.13a
- **Sub-Feature**: SF-3 — Logging Rollout
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3_16/feature_3_16_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-3
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_16/feature_3_16_sf3_implementation_plan.md
- **Status**: APPROVED

## Goal Description

Instrument every module in `src/specweaver/` with structured logging calls. SF-1 (committed) established the logging infrastructure: `RichHandler` for colorized console output (WARNING+) and `JSONFormatter` with `RotatingFileHandler` for persistent DEBUG-level JSON logs to `~/.specweaver/logs/<project>/specweaver.log`. SF-3 rolls out actual `logger.debug()`, `logger.info()`, `logger.warning()`, and `logger.error()` calls across every class and public method in the codebase.

> [!NOTE]
> **Research Notes Synthesis**
> - ~47 modules already have `logger = logging.getLogger(__name__)` AND active log calls (e.g., `flow/runner.py`, `context/inferrer.py`, `config/database.py`). These need an **audit pass** — verify their logging is comprehensive (method entry, error paths, key decisions).
> - ~10 modules have `logger = logging.getLogger(__name__)` declared but minimal/no actual log calls. These need log calls **added**.
> - ~30+ modules have neither `import logging` nor a logger declaration. These need the full treatment (import, declaration, and calls).
> - The logging infrastructure is in `src/specweaver/logging.py`. All modules under the `specweaver` namespace automatically route to this infrastructure via Python's logger hierarchy (`logging.getLogger(__name__)` → `specweaver.config.settings` → propagates to root `specweaver` logger).

## Resolved Design Decisions

> [!IMPORTANT]
> **All design decisions below were HITL-approved on 2026-03-29. A new agent MUST follow them exactly — no re-opening these decisions.**

| # | Decision | Resolution |
|---|----------|------------|
| D1 | **Logging granularity** | Public methods + error paths + key decision points ONLY. Private helper methods are logged ONLY if they contain non-trivial branching logic (rule of thumb: if it has 3+ branches or a try/except, log it). Do NOT log trivial getters, property access, or simple delegation. |
| D2 | **Batch size** | 4 commit boundaries, one per architectural layer (config/context/project → domain → llm/flow/loom → cli/api). |
| D3 | **Test strategy** | A single `tests/unit/test_logging_rollout.py` spot-checking 5-6 representative modules. No per-module logging tests. Existing behavioral tests validate that logging additions don't break functionality. |
| D4 | **Exclusions** | Pure data models and `__init__.py` files are EXCLUDED. See explicit list below. |
| D5 | **CLI logging** | Add operational DEBUG logging alongside existing `console.print()`. Do NOT replace Rich console output. Logging captures command entry, project resolution, error paths — for the log file, not for the terminal user. |

## Explicit Exclusion List

> [!WARNING]
> **Do NOT add logging to these files.** They contain no behavior worth logging (pure data models, constants, type definitions, re-exports):

- `src/specweaver/__init__.py` (and ALL `__init__.py` files except `llm/adapters/__init__.py` which has auto-discovery logic)
- `src/specweaver/flow/models.py` — pure Pydantic data models
- `src/specweaver/flow/state.py` — pure Pydantic data models
- `src/specweaver/llm/models.py` — pure Pydantic data models
- `src/specweaver/llm/errors.py` — pure exception definitions
- `src/specweaver/llm/_prompt_constants.py` — pure string constants
- `src/specweaver/validation/models.py` — pure Pydantic data models
- `src/specweaver/planning/models.py` — pure Pydantic data models
- `src/specweaver/project/_templates.py` — pure string templates
- `src/specweaver/loom/tools/*/definitions.py` — pure tool definition constants
- `src/specweaver/loom/tools/*/interfaces.py` — thin delegation facades (no logic)
- `src/specweaver/loom/atoms/base.py` — abstract base class with no concrete behavior
- `src/specweaver/context/provider.py` — pure Protocol/interface definition
- `src/specweaver/flow/handlers.py` — registry class (already has handler-level logging in individual handlers)
- `src/specweaver/validation/rules/spec/*.py` — pure validation functions (input→finding), too granular for logging
- `src/specweaver/validation/rules/code/*.py` — pure validation functions (input→finding), too granular for logging

> [!NOTE]
> **How to determine if a file should be excluded**: Open the file. If it contains ONLY: Pydantic `BaseModel` classes, `TypedDict` definitions, `Enum` definitions, `Protocol` definitions, string constants, `ToolDefinition` lists, or `@abstractmethod` stubs — it is excluded. If it has ANY method with real control flow (if/else, try/except, loops, function calls), it is included.

## What "Audit Existing Logging" Means — Concrete Checklist

> [!IMPORTANT]
> **When a file is marked "Has logger" with "Audit" instructions, follow this checklist for EVERY public method in the file.** Do NOT just check that a logger exists and move on. The goal is to verify that every public method has adequate logging coverage.

For each public method (no leading `_`) in the file, verify:

1. **Entry log exists?** — Is there a `logger.debug("method_name called ...")` at or near the top of the method? If not → add one.
2. **Error paths logged?** — For every `raise` statement: is there a `logger.error()` or `logger.warning()` before it? For every `except` clause: is there a `logger.warning()`, `logger.error()`, or `logger.exception()`? If not → add one.
3. **Key decision points logged?** — For if/else branches that choose between fundamentally different behaviors (e.g., fallback to default, skip vs. process): is there a `logger.info()` or `logger.debug()` on the chosen branch? If not → add one.
4. **Result/exit log exists?** — For methods that return a meaningful result (not `None`): is there a `logger.debug("method_name completed ...")` near the return? This is OPTIONAL — add only if the method is complex (5+ lines of logic). Simple methods need only an entry log.

If all 4 checks pass → the file needs no changes. Mark it as audited and move on.
If any check fails → add the missing log call(s).

> [!NOTE]
> **Staleness warning**: The "Has logger" / "Missing logger" annotations in this plan reflect the codebase state as of 2026-03-29. The `/dev` workflow mandates re-reading each file before editing. Always verify the actual file state — do NOT trust these annotations blindly. A file marked "Has logger" might have been refactored since this plan was written.

## Scope Boundaries

> [!CAUTION]
> **IN scope for SF-3**:
> - Adding `import logging` and `logger = logging.getLogger(__name__)` to modules that lack them
> - Adding `logger.debug()` / `logger.info()` / `logger.warning()` / `logger.error()` calls to public methods and error paths
> - Auditing existing log calls in already-instrumented modules for completeness (using the checklist above)
>
> **OUT of scope for SF-3** (absolutely do NOT do these):
> - Changing any function signatures, return types, or behavioral logic
> - Adding new dependencies (logging is stdlib)
> - Modifying the logging infrastructure itself (`src/specweaver/logging.py`) — that was SF-1
> - Replacing `console.print()` calls with `logger.info()` — CLI output and logging are separate concerns
> - Adding structured/typed log records or log event schemas — out of scope
> - Changing exception handling patterns (e.g., adding try/except where none exists)

## Proposed Changes

The rollout is divided into 4 batches by architectural layer. Each batch is a commit boundary.

---

### Batch 1: Core Infrastructure (config/, context/, project/)

**Commit Boundary 1 of 4** — After completing all files in this batch, run full test suite + `/pre-commit`.

Modules that are leaf-level or near-leaf in the dependency graph. Adding logging here first ensures the foundational layers are instrumented before their consumers.

#### [MODIFY] [settings.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/settings.py)
- **Currently missing**: `import logging` + logger declaration
- Add `import logging` at top of imports block
- Add `logger = logging.getLogger(__name__)` after imports
- `load_settings()`: log entry with project_name/role at DEBUG, log resolved provider at DEBUG, log profile fallback at INFO
- `load_settings_for_active()`: log entry at DEBUG, log active project name at DEBUG
- `migrate_legacy_config()`: log entry at DEBUG, log result ("migrated" vs "no config.yaml found") at INFO

#### [MODIFY] [paths.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/paths.py)
- Add logger if missing. Log path resolution results at DEBUG level.

#### [MODIFY] [_schema.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/_schema.py)
- Add logger if missing. Log schema migration steps (version transitions) at INFO level.

#### [MODIFY] [_db_llm_mixin.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/_db_llm_mixin.py)
- Add logger if missing. Log profile CRUD operations at DEBUG level.

#### [MODIFY] [profiles.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/profiles.py)
- **Has logger**: Audit existing logging. Add log calls for profile resolution/lookup at DEBUG level if insufficient.

#### [MODIFY] [database.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/database.py)
- **Has logger**: Audit existing logging. Ensure project registration, profile linking, and migration emit at least DEBUG-level logs. Add any missing entry/exit logs.

#### [MODIFY] [_db_config_mixin.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/_db_config_mixin.py)
- **Has logger**: Audit existing logging. Ensure config read/write ops log at DEBUG.

#### [MODIFY] [_db_extensions_mixin.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/_db_extensions_mixin.py)
- **Has logger**: Audit existing logging. Ensure extension discovery logs at DEBUG.

#### [MODIFY] [_db_telemetry_mixin.py](file:///c:/development/pitbula/specweaver/src/specweaver/config/_db_telemetry_mixin.py)
- **Has logger**: Audit existing logging. Ensure telemetry flush/read logs at DEBUG.

#### [MODIFY] [inferrer.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/inferrer.py)
- **Has logger + active calls**: Audit only — verify comprehensive coverage. Add only if missing.

#### [MODIFY] [analyzers.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/analyzers.py)
- Add logger if missing. Log analyzer factory dispatch and analysis results at DEBUG.

#### [MODIFY] [hitl_provider.py](file:///c:/development/pitbula/specweaver/src/specweaver/context/hitl_provider.py)
- Add logger if missing. Log question prompts and user response lengths at DEBUG (do NOT log response content — could be sensitive).

#### [MODIFY] [scaffold.py](file:///c:/development/pitbula/specweaver/src/specweaver/project/scaffold.py)
- **Has logger**: Audit existing logging. Ensure scaffold creation steps log at INFO.

#### [MODIFY] [constitution.py](file:///c:/development/pitbula/specweaver/src/specweaver/project/constitution.py)
- **Has logger**: Audit existing logging. Ensure discovery and validation log at DEBUG.

#### [MODIFY] [discovery.py](file:///c:/development/pitbula/specweaver/src/specweaver/project/discovery.py)
- Add logger if missing. Log project discovery at DEBUG level.

#### [MODIFY] [_helpers.py](file:///c:/development/pitbula/specweaver/src/specweaver/project/_helpers.py)
- **Has logger**: Audit existing logging. Ensure helper functions log at DEBUG.

---

### Batch 2: Domain Logic (validation/, standards/, graph/, planning/, review/, drafting/, implementation/)

**Commit Boundary 2 of 4** — After completing all files in this batch, run full test suite + `/pre-commit`.

Core domain modules that perform business logic.

#### validation/ (6 files — audit existing, add missing)
- `executor.py` — **Has logger**. Audit: ensure rule execution start/result log at DEBUG.
- `runner.py` — **Has logger**. Audit: ensure batch run entry/exit and per-rule results log at DEBUG.
- `registry.py` — **Has logger**. Audit: ensure rule registration/discovery logs at DEBUG.
- `inheritance.py` — **Has logger**. Audit: ensure pipeline inheritance resolution logs at DEBUG.
- `loader.py` — **Has logger**. Audit: ensure spec loading/parsing logs at DEBUG.
- `pipeline_loader.py` — **Has logger**. Audit: ensure pipeline YAML loading logs at DEBUG.
- `pipeline.py` — Add logger. Log pipeline execution at DEBUG.
- `spec_kind.py` — Add logger if it has control flow. Log spec kind detection at DEBUG.

#### standards/ (12 files — audit existing, add missing)
- `analyzer.py` — Add logger if missing. Log analysis entry/results at DEBUG.
- `discovery.py` — **Has logger**. Audit for comprehensive coverage.
- `enricher.py` — **Has logger**. Audit for comprehensive coverage.
- `loader.py` — **Has logger**. Audit for comprehensive coverage.
- `recency.py` — Add logger if missing. Log recency checks at DEBUG.
- `reviewer.py` — **Has logger**. Audit for comprehensive coverage.
- `scanner.py` — **Has logger**. Audit for comprehensive coverage.
- `scope_detector.py` — **Has logger**. Audit for comprehensive coverage.
- `tree_sitter_base.py` — **Has logger**. Audit for comprehensive coverage.
- `languages/python/analyzer.py` — **Has logger**. Audit for comprehensive coverage.
- `languages/javascript/analyzer.py` — **Has logger**. Audit for comprehensive coverage.
- `languages/typescript/analyzer.py` — **Has logger**. Audit for comprehensive coverage.

#### graph/ (2 files)
- `topology.py` — **Has logger**. Audit: ensure graph building, cycle detection, impact analysis log at DEBUG.
- `selectors.py` — Add logger. Log selector queries at DEBUG.

#### planning/ (4 files — audit + add)
- `planner.py` — **Has logger**. Audit for comprehensive coverage.
- `renderer.py` — Add logger. Log rendering steps at DEBUG.
- `stitch.py` — **Has logger**. Audit for comprehensive coverage.
- `ui_extractor.py` — Add logger. Log extraction steps at DEBUG.

#### review/ (1 file)
- `reviewer.py` — **Has logger**. Audit: ensure review invocation, LLM call, verdict parsing log at DEBUG/INFO.

#### drafting/ (3 files)
- `drafter.py` — **Missing logger entirely**. Add `import logging` + `logger = logging.getLogger(__name__)`. Add: `draft()` entry with component name at DEBUG, section iteration at DEBUG, file write at INFO. `_generate_section()` LLM call at DEBUG.
- `decomposition.py` — Add logger. Log decomposition steps at DEBUG.
- `feature_drafter.py` — Add logger. Log feature drafting steps at DEBUG.

#### implementation/ (1 file)
- `generator.py` — **Has logger**. Audit: ensure code generation and test generation steps log at DEBUG/INFO.

---

### Batch 3: LLM & Flow Engine (llm/, flow/, loom/)

**Commit Boundary 3 of 4** — After completing all files in this batch, run full test suite + `/pre-commit`.

#### llm/ (8 files + adapters)
- `prompt_builder.py` — Add logger. Log block assembly at DEBUG (block name, priority).
- `router.py` — **Has logger**. Audit for comprehensive coverage.
- `factory.py` — **Has logger**. Audit for comprehensive coverage.
- `collector.py` — **Has logger**. Audit for comprehensive coverage.
- `telemetry.py` — Add logger. Log cost estimation at DEBUG.
- `_prompt_render.py` — Add logger if it has render functions with control flow. Log rendering at DEBUG.
- `mention_scanner/scanner.py` — Add logger. Log mention scanning at DEBUG.
- `mention_scanner/models.py` — Skip (pure data models).

#### llm/adapters/ (6 files)
- `__init__.py` — **Has logger**. Audit: ensure auto-discovery scanning logs at DEBUG.
- `base.py` — Add logger for base class methods if they have concrete behavior.
- `gemini.py` — **Has logger**. Audit: ensure API call entry/exit, error paths log at DEBUG/WARNING.
- `openai.py` — Add logger. Log API call entry/exit at DEBUG, errors at WARNING.
- `anthropic.py` — Add logger. Log API call entry/exit at DEBUG, errors at WARNING.
- `mistral.py` — Add logger. Log API call entry/exit at DEBUG, errors at WARNING.
- `qwen.py` — Add logger. Log API call entry/exit at DEBUG, errors at WARNING.

#### flow/ (9 files)
- `runner.py` — **Already well-instrumented**. Audit pass only.
- `gates.py` — **Has logger**. Audit for comprehensive coverage.
- `store.py` — **Has logger**. Audit for comprehensive coverage.
- `_base.py` — **Has logger**. Audit: add entry/exit logging for `execute()` at DEBUG.
- `_draft.py` — **Has logger**. Audit: add entry/exit logging for `execute()` at DEBUG.
- `_review.py` — **Has logger**. Audit: add entry/exit logging for `execute()` at DEBUG.
- `_generation.py` — **Has logger**. Audit: add entry/exit logging for `execute()` at DEBUG.
- `_validation.py` — **Has logger**. Audit: add entry/exit logging for `execute()` at DEBUG.
- `_lint_fix.py` — **Has logger**. Audit: add entry/exit logging for `execute()` at DEBUG.
- `_standards.py` — **Has logger**. Audit: add entry/exit logging for `execute()` at DEBUG.
- `display.py` — Add logger. Log display events at DEBUG.
- `parser.py` — Add logger. Log YAML parsing at DEBUG.

#### loom/ (multiple files)
- `dispatcher.py` — **Has logger**. Audit for comprehensive coverage.
- `security.py` — **Has logger**. Audit for comprehensive coverage.
- `atoms/rule_atom.py` — **Has logger**. Audit for comprehensive coverage.
- `atoms/filesystem/atom.py` — Add logger if missing. Log atom execution at DEBUG.
- `atoms/git/atom.py` — Add logger if missing. Log atom execution at DEBUG.
- `atoms/qa_runner/atom.py` — Add logger if missing. Log atom execution at DEBUG.
- `commons/filesystem/executor.py` — Add logger if missing. Log file ops at DEBUG.
- `commons/filesystem/search.py` — **Has logger**. Audit for comprehensive coverage.
- `commons/git/executor.py` — Add logger if missing. Log git command execution at DEBUG.
- `commons/git/engine_executor.py` — Add logger if missing.
- `commons/qa_runner/python.py` — **Has logger**. Audit for comprehensive coverage.
- `commons/qa_runner/interface.py` — Add logger if missing.
- `tools/filesystem/tool.py` — Add logger if missing. Log tool invocation at DEBUG.
- `tools/git/tool.py` — Add logger if missing. Log tool invocation at DEBUG.
- `tools/qa_runner/tool.py` — Add logger if missing. Log tool invocation at DEBUG.
- `tools/web/tool.py` — **Has logger**. Audit for comprehensive coverage.

---

### Batch 4: Entry Points (cli/, api/)

**Commit Boundary 4 of 4** — After completing all files in this batch, run full test suite + `/pre-commit`.

#### cli/ (14 files)
- `_core.py` — **Has logger**. Audit: ensure main app callbacks log at DEBUG.
- `_helpers.py` — Add logger if missing. Log helper invocations at DEBUG.
- `config.py` — **Has logger**. Audit for comprehensive coverage.
- `config_routing.py` — Add logger if missing. Log routing command entry at DEBUG.
- `constitution.py` — Add logger if missing. Log command entry at DEBUG.
- `cost_commands.py` — Add logger if missing. Log command entry at DEBUG.
- `implement.py` — Add logger if missing. Log command entry at DEBUG.
- `pipelines.py` — Add logger if missing. Log command entry at DEBUG.
- `projects.py` — Add logger if missing. Log command entry at DEBUG.
- `review.py` — Add logger if missing. Log command entry at DEBUG.
- `serve.py` — Add logger if missing. Log server startup at INFO.
- `standards.py` — Add logger if missing. Log command entry at DEBUG.
- `usage_commands.py` — Add logger if missing. Log command entry at DEBUG.
- `validation.py` — Add logger if missing. Log command entry at DEBUG.

> [!NOTE]
> **CLI logging pattern**: CLI modules use `console.print()` for user-facing output (Rich formatted tables, status messages, etc.). The `logger.debug()` calls added here are for the *log file* only — they capture operational state (which command ran, which project was resolved, what error occurred) for post-mortem debugging. They are NOT visible to the terminal user (console handler is WARNING+).

#### api/ (multiple files)
- `app.py` — Add logger if missing. Log app startup/config at INFO.
- `deps.py` — Add logger if missing. Log dependency injection at DEBUG.
- `errors.py` — Add logger if missing. Log error handler invocations at WARNING.
- `event_bridge.py` — **Has logger**. Audit for comprehensive coverage.
- `v1/ws.py` — **Has logger**. Audit for comprehensive coverage.
- `v1/constitution.py` — Add logger if missing. Log endpoint handling at DEBUG.
- `v1/health.py` — Add logger if missing. Log health checks at DEBUG.
- `v1/implement.py` — Add logger if missing. Log endpoint handling at DEBUG.
- `v1/paths.py` — Add logger if missing. Log endpoint handling at DEBUG.
- `v1/pipelines.py` — Add logger if missing. Log endpoint handling at DEBUG.
- `v1/projects.py` — Add logger if missing. Log endpoint handling at DEBUG.
- `v1/review.py` — Add logger if missing. Log endpoint handling at DEBUG.
- `v1/schemas.py` — Skip (pure Pydantic models).
- `v1/standards.py` — Add logger if missing. Log endpoint handling at DEBUG.
- `v1/validation.py` — Add logger if missing. Log endpoint handling at DEBUG.
- `ui/htmx.py` — Add logger if missing. Log page rendering at DEBUG.
- `ui/routes.py` — Add logger if missing. Log route handling at DEBUG.

---

## Logging Pattern Reference

Every instrumented module MUST follow this exact pattern:

```python
# At module level, AFTER all other imports, BEFORE any module-level code:
import logging

logger = logging.getLogger(__name__)
```

> [!CAUTION]
> The `import logging` goes in the standard-library imports section (alphabetically). The `logger = logging.getLogger(__name__)` goes AFTER the last import, BEFORE any constants or class definitions. This is the existing project convention (see `flow/runner.py`, `config/database.py` for reference).

### Log level guidance

| Level | When to use | Example |
|-------|-------------|---------|
| `logger.debug()` | Method entry/exit, intermediate state, variable values | `logger.debug("load_settings called for project=%s, role=%s", name, role)` |
| `logger.info()` | Significant lifecycle events: startup, completion, migration, file writes | `logger.info("Generated spec file at %s", spec_path)` |
| `logger.warning()` | Recoverable failures, fallbacks, missing optional config | `logger.warning("No profile found for %s, using system-default", name)` |
| `logger.error()` | Unrecoverable errors right before raising an exception | `logger.error("Project '%s' not found in database", name)` |
| `logger.exception()` | Caught exceptions where you want the full traceback in the log | `logger.exception("Failed to parse config at %s", path)` |

### Code patterns

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
> **NEVER use f-strings in log calls.** Always use lazy %-style formatting:
> - ✅ `logger.debug("Processing %s", name)`
> - ❌ `logger.debug(f"Processing {name}")`

> [!CAUTION]
> **NEVER log sensitive data.** Do NOT log:
> - API keys, tokens, or secrets
> - Full user input content (log length only if needed)
> - Full file contents (log path only)
> - Full LLM responses (log token count / status only)

---

## TDD Pattern for Logging Additions

> [!IMPORTANT]
> **The `/dev` workflow requires red-green-refactor for every task.** For logging additions, the TDD cycle works as follows:

### Red Phase (write failing test)

Use pytest's built-in `caplog` fixture to assert that a module's logger emits records. The test fails because the module doesn't have logging yet (or doesn't have the specific log call being tested).

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
        from specweaver.config.settings import load_settings

        # We don't need a real DB — we just need to trigger the log call.
        # Use a mock or catch the ValueError and check logs before it.
        with caplog.at_level(logging.DEBUG, logger="specweaver.config.settings"):
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
        """drafting/drafter.py should declare a module-level logger."""
        from specweaver.drafting import drafter

        assert hasattr(drafter, "logger"), "drafter module must have a logger"
        assert isinstance(drafter.logger, logging.Logger)
        assert drafter.logger.name == "specweaver.drafting.drafter"


class TestBatch3LoggingRollout:
    """Verify Batch 3 modules have logger declarations."""

    def test_prompt_builder_has_logger(self):
        """llm/prompt_builder.py should declare a module-level logger."""
        from specweaver.llm import prompt_builder

        assert hasattr(prompt_builder, "logger"), "prompt_builder module must have a logger"
        assert isinstance(prompt_builder.logger, logging.Logger)


class TestBatch4LoggingRollout:
    """Verify Batch 4 modules have logger declarations."""

    def test_cli_review_has_logger(self):
        """cli/review.py should declare a module-level logger."""
        from specweaver.cli import review

        assert hasattr(review, "logger"), "cli/review module must have a logger"
        assert isinstance(review.logger, logging.Logger)
```

### Green Phase (add logging)

Add the `import logging` + `logger = logging.getLogger(__name__)` + log calls to the module. Re-run the test — it passes.

### Refactor Phase

No refactoring needed for logging additions. Run lint (`ruff check`) and fix any issues.

> [!NOTE]
> **TDD mapping to tasks**: Each task in `task.md` maps to 1-3 closely related files. The test file `test_logging_rollout.py` grows incrementally — add the Red test for the current task batch, then Green the implementation. You do NOT need to write all tests upfront.

---

## Suggested Task Breakdown for `/dev`

> [!IMPORTANT]
> **This section pre-defines the `task.md` structure for the `/dev` workflow.** The implementing agent should use this as-is (adjusting only if files have changed since this plan was written).

Each task is one TDD cycle. Group closely related files (same package, same pattern) into a single task. Each file in a task group follows the identical logging pattern.

### Commit Boundary 1 of 4: Core Infrastructure

```
- [ ] Task 1.1: Instrument config/settings.py + config/paths.py
      Source: src/specweaver/config/settings.py, src/specweaver/config/paths.py
      Test: tests/unit/test_logging_rollout.py::TestBatch1LoggingRollout

- [ ] Task 1.2: Instrument config/_schema.py + config/_db_llm_mixin.py
      Source: src/specweaver/config/_schema.py, src/specweaver/config/_db_llm_mixin.py
      Test: tests/unit/test_logging_rollout.py (extend TestBatch1)

- [ ] Task 1.3: Audit config/profiles.py + config/database.py + config/_db_*_mixin.py (3 files)
      Source: src/specweaver/config/profiles.py, src/specweaver/config/database.py,
              src/specweaver/config/_db_config_mixin.py, src/specweaver/config/_db_extensions_mixin.py,
              src/specweaver/config/_db_telemetry_mixin.py
      Test: Existing tests pass (audit-only — add log calls where missing per checklist)

- [ ] Task 1.4: Instrument + audit context/ modules
      Source: src/specweaver/context/inferrer.py (audit), src/specweaver/context/analyzers.py,
              src/specweaver/context/hitl_provider.py
      Test: tests/unit/test_logging_rollout.py (extend TestBatch1)

- [ ] Task 1.5: Instrument + audit project/ modules
      Source: src/specweaver/project/scaffold.py (audit), src/specweaver/project/constitution.py (audit),
              src/specweaver/project/discovery.py, src/specweaver/project/_helpers.py (audit)
      Test: tests/unit/test_logging_rollout.py (extend TestBatch1)

--- COMMIT BOUNDARY 1 → run full test suite + /pre-commit ---
```

### Commit Boundary 2 of 4: Domain Logic

```
- [ ] Task 2.1: Audit validation/ modules (6 files with existing loggers)
      Source: validation/executor.py, validation/runner.py, validation/registry.py,
              validation/inheritance.py, validation/loader.py, validation/pipeline_loader.py
      Test: Existing tests pass

- [ ] Task 2.2: Instrument validation/pipeline.py + validation/spec_kind.py
      Source: src/specweaver/validation/pipeline.py, src/specweaver/validation/spec_kind.py
      Test: tests/unit/test_logging_rollout.py (extend TestBatch2)

- [ ] Task 2.3: Audit + instrument standards/ modules (12 files)
      Source: All files listed under standards/ in Batch 2
      Test: Existing tests pass

- [ ] Task 2.4: Audit + instrument graph/, planning/ modules
      Source: graph/topology.py (audit), graph/selectors.py, planning/planner.py (audit),
              planning/renderer.py, planning/stitch.py (audit), planning/ui_extractor.py
      Test: tests/unit/test_logging_rollout.py (extend TestBatch2)

- [ ] Task 2.5: Instrument drafting/ + audit review/ + implementation/
      Source: drafting/drafter.py, drafting/decomposition.py, drafting/feature_drafter.py,
              review/reviewer.py (audit), implementation/generator.py (audit)
      Test: tests/unit/test_logging_rollout.py::TestBatch2LoggingRollout

--- COMMIT BOUNDARY 2 → run full test suite + /pre-commit ---
```

### Commit Boundary 3 of 4: LLM & Flow Engine

```
- [ ] Task 3.1: Instrument llm/ core modules
      Source: llm/prompt_builder.py, llm/telemetry.py, llm/_prompt_render.py,
              llm/mention_scanner/scanner.py
      Test: tests/unit/test_logging_rollout.py::TestBatch3LoggingRollout

- [ ] Task 3.2: Audit llm/ existing + instrument adapters
      Source: llm/router.py (audit), llm/factory.py (audit), llm/collector.py (audit),
              llm/adapters/__init__.py (audit), llm/adapters/base.py,
              llm/adapters/gemini.py (audit), llm/adapters/openai.py,
              llm/adapters/anthropic.py, llm/adapters/mistral.py, llm/adapters/qwen.py
      Test: Existing tests pass

- [ ] Task 3.3: Audit + instrument flow/ modules
      Source: flow/runner.py (audit), flow/gates.py (audit), flow/store.py (audit),
              flow/_base.py (audit), flow/_draft.py (audit), flow/_review.py (audit),
              flow/_generation.py (audit), flow/_validation.py (audit),
              flow/_lint_fix.py (audit), flow/_standards.py (audit),
              flow/display.py, flow/parser.py
      Test: Existing tests pass

- [ ] Task 3.4: Audit + instrument loom/ modules
      Source: All files listed under loom/ in Batch 3
      Test: Existing tests pass

--- COMMIT BOUNDARY 3 → run full test suite + /pre-commit ---
```

### Commit Boundary 4 of 4: Entry Points

```
- [ ] Task 4.1: Instrument + audit cli/ modules (14 files)
      Source: All files listed under cli/ in Batch 4
      Test: tests/unit/test_logging_rollout.py::TestBatch4LoggingRollout

- [ ] Task 4.2: Instrument + audit api/ modules
      Source: All files listed under api/ in Batch 4
      Test: Existing tests pass

--- COMMIT BOUNDARY 4 → run full test suite + /pre-commit ---
```

---

## Open Questions

None. All decisions are resolved and documented inline in the plan.

## Verification Plan

### Automated Tests

1. **All existing tests must pass unchanged** — logging additions must not affect behavior:
```
python run_unit_tests.py
python run_integ_tests.py
python run_e2e_tests.py
```

2. **Logging smoke test** — `tests/unit/test_logging_rollout.py` (created incrementally during TDD). Uses pytest `caplog` fixture. Skeleton provided in the "TDD Pattern" section above. Spot-checks from each batch:
   - Batch 1: `config/settings.py` → `load_settings()` emits DEBUG log (via `caplog`)
   - Batch 2: `drafting/drafter.py` → module-level `logger` attribute exists and is a `logging.Logger`
   - Batch 3: `llm/prompt_builder.py` → module-level `logger` attribute exists
   - Batch 4: `cli/review.py` → module-level `logger` attribute exists
```
python -m pytest tests/unit/test_logging_rollout.py -v --tb=short
```

3. **Lint clean**:
```
ruff check src/ tests/
```

### Manual Verification
1. Run `sw review` on a sample spec with `--debug` and verify that DEBUG-level logs from the instrumented modules appear on the console.
2. Inspect `~/.specweaver/logs/<project>/specweaver.log` and verify JSON log entries from multiple modules are present.
