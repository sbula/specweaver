# Implementation Plan: Unified Runner Architecture & Universal Logging [SF-03: Logging Rollout]
- **Feature ID**: 3.13a
- **Sub-Feature**: SF-03 — Logging Rollout
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/D-FLOW-04/D-FLOW-04_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/D-FLOW-04/D-FLOW-04_sf03_implementation_plan.md
- **Status**: APPROVED

## Goal Description

Instrument every module in `src/specweaver/` with structured logging calls. SF-01 (committed) established the logging infrastructure: `RichHandler` for colorized console output (WARNING+) and `JSONFormatter` with `RotatingFileHandler` for persistent DEBUG-level JSON logs to `~/.specweaver/logs/<project>/specweaver.log`. SF-03 rolls out actual `logger.debug()`, `logger.info()`, `logger.warning()`, and `logger.error()` calls across every class and public method in the codebase.

> [!NOTE]
> **Research Notes Synthesis**
> - ~47 modules already have `logger = logging.getLogger(__name__)` AND active log calls (e.g., `core/flow/runner.py`, `context/inferrer.py`, `config/database.py`). These need an **audit pass** — verify their logging is comprehensive (method entry, error paths, key decisions).
> - ~10 modules have `logger = logging.getLogger(__name__)` declared but minimal/no actual log calls. These need log calls **added**.
> - ~30+ modules have neither `import logging` nor a logger declaration. These need the full treatment (import, declaration, and calls).
> - The logging infrastructure is in `src/specweaver/telemetry_logger.py`. All modules under the `specweaver` namespace automatically route to this infrastructure via Python's logger hierarchy (`logging.getLogger(__name__)` → `specweaver.core.config.settings` → propagates to root `specweaver` logger).

## Resolved Design Decisions

> [!IMPORTANT]
> **All design decisions below were HITL-approved on 2026-03-29. A new agent MUST follow them exactly — no re-opening these decisions.**

| # | Decision | Resolution |
|---|----------|------------|
| D1 | **Logging granularity** | Public methods + error paths + key decision points ONLY. Private helper methods are logged ONLY if they contain non-trivial branching logic (rule of thumb: if it has 3+ branches or a try/except, log it). Do NOT log trivial getters, property access, or simple delegation. |
| D2 | **Batch size** | 4 commit boundaries, one per architectural layer (config/context/project → domain → infrastructure/llm/core/flow/sandbox → interfaces/cli/api). |
| D3 | **Test strategy** | A single `tests/unit/test_logging_rollout.py` spot-checking 5-6 representative modules. No per-module logging tests. Existing behavioral tests validate that logging additions don't break functionality. |
| D4 | **Exclusions** | Pure data models and `__init__.py` files are EXCLUDED. See explicit list below. |
| D5 | **CLI logging** | Add operational DEBUG logging alongside existing `console.print()`. Do NOT replace Rich console output. Logging captures command entry, project resolution, error paths — for the log file, not for the terminal user. |

## Explicit Exclusion List

> [!WARNING]
> **Do NOT add logging to these files.** They contain no behavior worth logging (pure data models, constants, type definitions, re-exports):

- `src/specweaver/__init__.py` (and ALL `__init__.py` files except `infrastructure/llm/adapters/__init__.py` which has auto-discovery logic)
- `src/specweaver/core/flow/engine/models.py` — pure Pydantic data models
- `src/specweaver/core/flow/engine/state.py` — pure Pydantic data models
- `src/specweaver/infrastructure/llm/models.py` — pure Pydantic data models
- `src/specweaver/infrastructure/llm/errors.py` — pure exception definitions
- `src/specweaver/infrastructure/llm/_prompt_constants.py` — pure string constants
- `src/specweaver/assurance/validation/models.py` — pure Pydantic data models
- `src/specweaver/workflows/planning/models.py` — pure Pydantic data models
- `src/specweaver/workspace/project/_templates.py` — pure string templates
- `src/specweaver/sandbox/*/interfaces/definitions.py` — pure tool definition constants
- `src/specweaver/sandbox/*/interfaces/facades.py` — thin delegation facades (no logic)
- `src/specweaver/workspace/context/provider.py` — pure Protocol/interface definition
- `src/specweaver/assurance/validation/rules/spec/*.py` — pure validation functions (input→finding), too granular for logging
- `src/specweaver/assurance/validation/rules/code/*.py` — pure validation functions (input→finding), too granular for logging

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
> **IN scope for SF-03**:
> - Adding `import logging` and `logger = logging.getLogger(__name__)` to modules that lack them
> - Adding `logger.debug()` / `logger.info()` / `logger.warning()` / `logger.error()` calls to public methods and error paths
> - Auditing existing log calls in already-instrumented modules for completeness (using the checklist above)
>
> **OUT of scope for SF-03** (absolutely do NOT do these):
> - Changing any function signatures, return types, or behavioral logic
> - Adding new dependencies (logging is stdlib)
> - Modifying the logging infrastructure itself (`src/specweaver/telemetry_logger.py`) — that was SF-01
> - Replacing `console.print()` calls with `logger.info()` — CLI output and logging are separate concerns
> - Adding structured/typed log records or log event schemas — out of scope
> - Changing exception handling patterns (e.g., adding try/except where none exists)

## Proposed Changes

The rollout is divided into 4 batches by architectural layer. Each batch is a commit boundary.

---

### Batch 1: Core Infrastructure (config/, context/, project/)

**Commit Boundary 1 of 4** — After completing all files in this batch, run full test suite + `/pre-commit`.

Modules that are leaf-level or near-leaf in the dependency graph. Adding logging here first ensures the foundational layers are instrumented before their consumers.

#### [MODIFY] [settings.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/config/settings.py)
- **Currently missing**: `import logging` + logger declaration
- Add `import logging` at top of imports block
- Add `logger = logging.getLogger(__name__)` after imports
- `load_settings()`: log entry with project_name/role at DEBUG, log resolved provider at DEBUG, log profile fallback at INFO
- `load_settings_for_active()`: log entry at DEBUG, log active project name at DEBUG
- `migrate_legacy_config()`: log entry at DEBUG, log result ("migrated" vs "no config.yaml found") at INFO

#### [MODIFY] [paths.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/config/paths.py)
- Add logger if missing. Log path resolution results at DEBUG level.

- Add logger if missing. Log schema migration steps (version transitions) at INFO level.

- Add logger if missing. Log profile CRUD operations at DEBUG level.

#### [MODIFY] [profiles.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/config/profiles.py)
- **Has logger**: Audit existing logging. Add log calls for profile resolution/lookup at DEBUG level if insufficient.

#### [MODIFY] [database.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/config/database.py)
- **Has logger**: Audit existing logging. Ensure project registration, profile linking, and migration emit at least DEBUG-level logs. Add any missing entry/exit logs.

- **Has logger**: Audit existing logging. Ensure config read/write ops log at DEBUG.

- **Has logger**: Audit existing logging. Ensure extension discovery logs at DEBUG.

- **Has logger**: Audit existing logging. Ensure telemetry flush/read logs at DEBUG.

#### [MODIFY] [inferrer.py](file:///c:/development/pitbula/specweaver/src/specweaver/workspace/context/inferrer.py)
- **Has logger + active calls**: Audit only — verify comprehensive coverage. Add only if missing.

- Add logger if missing. Log analyzer factory dispatch and analysis results at DEBUG.

#### [MODIFY] [hitl_provider.py](file:///c:/development/pitbula/specweaver/src/specweaver/workspace/context/hitl_provider.py)
- Add logger if missing. Log question prompts and user response lengths at DEBUG (do NOT log response content — could be sensitive).

#### [MODIFY] [scaffold.py](file:///c:/development/pitbula/specweaver/src/specweaver/workspace/project/scaffold.py)
- **Has logger**: Audit existing logging. Ensure scaffold creation steps log at INFO.

#### [MODIFY] [constitution.py](file:///c:/development/pitbula/specweaver/src/specweaver/workspace/project/constitution.py)
- **Has logger**: Audit existing logging. Ensure discovery and validation log at DEBUG.


#### workspace/ast/ (multiple files)
- All parsers and base modules — Add logger if missing. Log parser initialization and parsing steps at DEBUG.

#### [MODIFY] [discovery.py](file:///c:/development/pitbula/specweaver/src/specweaver/workspace/project/discovery.py)
- Add logger if missing. Log project discovery at DEBUG level.

#### [MODIFY] [_helpers.py](file:///c:/development/pitbula/specweaver/src/specweaver/workspace/project/_helpers.py)
- **Has logger**: Audit existing logging. Ensure helper functions log at DEBUG.

---

### Batch 2: Domain Logic (assurance/validation/, assurance/standards/, graph/, workflows/planning/, workflows/review/, workflows/drafting/, workflows/implementation/)

**Commit Boundary 2 of 4** — After completing all files in this batch, run full test suite + `/pre-commit`.

Core domain modules that perform business logic.

#### assurance/validation/ (6 files — audit existing, add missing)
- `executor.py` — **Has logger**. Audit: ensure rule execution start/result log at DEBUG.
- `runner.py` — **Has logger**. Audit: ensure batch run entry/exit and per-rule results log at DEBUG.
- `registry.py` — **Has logger**. Audit: ensure rule registration/discovery logs at DEBUG.
- `inheritance.py` — **Has logger**. Audit: ensure pipeline inheritance resolution logs at DEBUG.
- `loader.py` — **Has logger**. Audit: ensure spec loading/parsing logs at DEBUG.
- `pipeline_loader.py` — **Has logger**. Audit: ensure pipeline YAML loading logs at DEBUG.
- `pipeline.py` — Add logger. Log pipeline execution at DEBUG.
- `spec_kind.py` — Add logger if it has control flow. Log spec kind detection at DEBUG.

#### assurance/standards/ (12 files — audit existing, add missing)
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


#### workflows/evaluators/ (multiple files)
- All evaluators — Add logger if missing. Log evaluation steps at DEBUG.

#### graph/lineage/ (multiple files)
- All store and domain modules — Add logger if missing. Log lineage events at DEBUG.

#### workflows/planning/ (4 files — audit + add)
- `planner.py` — **Has logger**. Audit for comprehensive coverage.
- `renderer.py` — Add logger. Log rendering steps at DEBUG.
- `stitch.py` — **Has logger**. Audit for comprehensive coverage.
- `ui_extractor.py` — Add logger. Log extraction steps at DEBUG.

#### workflows/review/ (1 file)
- `reviewer.py` — **Has logger**. Audit: ensure review invocation, LLM call, verdict parsing log at DEBUG/INFO.

#### workflows/drafting/ (3 files)
- `drafter.py` — **Missing logger entirely**. Add `import logging` + `logger = logging.getLogger(__name__)`. Add: `draft()` entry with component name at DEBUG, section iteration at DEBUG, file write at INFO. `_generate_section()` LLM call at DEBUG.
- `decomposition.py` — Add logger. Log decomposition steps at DEBUG.
- `feature_drafter.py` — Add logger. Log feature drafting steps at DEBUG.

#### workflows/implementation/ (1 file)
- `generator.py` — **Has logger**. Audit: ensure code generation and test generation steps log at DEBUG/INFO.

---

### Batch 3: LLM & Flow Engine (infrastructure/llm/, core/flow/, sandbox/)

**Commit Boundary 3 of 4** — After completing all files in this batch, run full test suite + `/pre-commit`.

#### infrastructure/llm/ (8 files + adapters)
- `prompt_builder.py` — Add logger. Log block assembly at DEBUG (block name, priority).
- `router.py` — **Has logger**. Audit for comprehensive coverage.
- `factory.py` — **Has logger**. Audit for comprehensive coverage.
- `collector.py` — **Has logger**. Audit for comprehensive coverage.
- `telemetry.py` — Add logger. Log cost estimation at DEBUG.
- `_prompt_render.py` — Add logger if it has render functions with control flow. Log rendering at DEBUG.
- `mention_scanner/scanner.py` — Add logger. Log mention scanning at DEBUG.
- `mention_scanner/models.py` — Skip (pure data models).

#### infrastructure/llm/adapters/ (6 files)
- `__init__.py` — **Has logger**. Audit: ensure auto-discovery scanning logs at DEBUG.
- `base.py` — Add logger for base class methods if they have concrete behavior.
- `gemini.py` — **Has logger**. Audit: ensure API call entry/exit, error paths log at DEBUG/WARNING.
- `openai.py` — Add logger. Log API call entry/exit at DEBUG, errors at WARNING.
- `anthropic.py` — Add logger. Log API call entry/exit at DEBUG, errors at WARNING.
- `mistral.py` — Add logger. Log API call entry/exit at DEBUG, errors at WARNING.
- `qwen.py` — Add logger. Log API call entry/exit at DEBUG, errors at WARNING.

#### core/flow/ (9 files)
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

#### sandbox/ (multiple files)
#### sandbox/language/ (multiple files)
- All language core and interfaces — Add logger if missing. Log execution boundaries at DEBUG.

- mcp/core/executor.py — Add logger if missing.
- mcp/interfaces/tool.py — Add logger if missing.
- protocol/core/atom.py — Add logger if missing.
- protocol/core/factory.py — Add logger if missing.
- protocol/interfaces/tool.py — Add logger if missing.
- qa_runner/core/atom.py — Add logger if missing.
- qa_runner/interfaces/tool.py — Add logger if missing.
- web/interfaces/tool.py — Add logger if missing.

---


### Batch 4: Entry Points (interfaces/cli/, interfaces/api/)

**Commit Boundary 4 of 4** — After completing all files in this batch, run full test suite + `/pre-commit`.

#### Decentralized CLI Interfaces (16 files)
- interfaces/cli/main.py — Add logger.
- interfaces/cli/_core.py — **Has logger**. Audit: ensure main app callbacks log at DEBUG.
- interfaces/cli/routers/serve_router.py — Add logger if missing.
- core/config/interfaces/cli.py — Add logger if missing. Log command entry at DEBUG.
- core/config/cli_db_utils.py — Add logger if missing.
- graph/interfaces/cli.py — Add logger if missing.
- assurance/validation/interfaces/cli.py — Add logger if missing.
- assurance/validation/interfaces/cli_drift.py — Add logger if missing.
- assurance/standards/interfaces/cli.py — Add logger if missing.
- infrastructure/llm/interfaces/cli.py — Add logger if missing.
- workflows/implementation/interfaces/cli.py — Add logger if missing.
- workflows/review/interfaces/cli.py — Add logger if missing.
- workspace/project/interfaces/cli.py — Add logger if missing.
- workspace/project/interfaces/cli_constitution.py — Add logger if missing.
- workspace/project/interfaces/cli_hooks.py — Add logger if missing.
- core/flow/interfaces/cli.py — Add logger if missing.

> [!NOTE]
> **CLI logging pattern**: CLI modules use console.print() for user-facing output. The logger.debug() calls added here capture operational state for post-mortem debugging. They are NOT visible to the terminal user.

#### interfaces/api/ (multiple files)
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
> The `import logging` goes in the standard-library imports section (alphabetically). The `logger = logging.getLogger(__name__)` goes AFTER the last import, BEFORE any constants or class definitions. This is the existing project convention (see `core/flow/runner.py`, `config/database.py` for reference).

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
   - Batch 2: `workflows/drafting/drafter.py` → module-level `logger` attribute exists and is a `logging.Logger`
   - Batch 3: `infrastructure/llm/prompt_builder.py` → module-level `logger` attribute exists
   - Batch 4: `workflows/review/interfaces/cli.py` → module-level `logger` attribute exists
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
