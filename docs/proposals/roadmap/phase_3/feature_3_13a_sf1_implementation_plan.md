# Implementation Plan: Universal Logging Reform [SF-1: Universal Logging Reform]
- **Feature ID**: 3.13a
- **Sub-Feature**: SF-1 — Universal Logging Reform
- **Design Document**: docs/proposals/design/phase_3/feature_3_13a_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_13a_sf1_implementation_plan.md
- **Status**: APPROVED

## Goal Description

Execute a project-wide logging reform by retrofitting `src/specweaver/logging.py`. The console output will use `rich.logging.RichHandler` for colorized terminal outputs (WARNING+ only, unless `--debug` is used). Alongside it, a robust standard-library-based `JSONFormatter` will be implemented to write full DEBUG-level logs to a local `specweaver.log` file in a machine-parseable format.

> [!NOTE]
> **Research Notes Synthesis**
> - The Typer CLI heavily relies on `Rich`, so standardizing on `RichHandler` requires no external libraries and guarantees UI cohesion.
> - A standard library `logging.Formatter` subclass can easily execute `json.dumps()` on `record.__dict__` to satisfy the JSON requirement without depending on `python-json-logger`.

## User Review Required (HITL Phase 4 & 5)

> [!WARNING]
> Please review the architectural alignments and provide final **Consistency Check** approval to proceed with SF-1.
> 
> **Phase 5 Consistency Check (Evidence-Backed):**
> 1. **Any unresolved decisions?** No. The user explicitely confirmed using a Custom JSON `logging.Formatter` over a 3rd party dependency.
> 2. **Architecture and future compatibility:** This is fully backwards compatible and aligned. It simply changes the internal formatting behavior and standardizes the handlers inside `src/specweaver/logging.py`, which all modules already use safely.
> 3. **Internal consistency check:** No contradictions exist. The tests for `JSONFormatter` will cleanly match the new `logging.py` implementation.
> 
> **Agent Handoff Risk Evaluation:** Zero risk. A fresh agent jumping into `/dev` will clearly see the scope limited *only* to logging inside `logging.py` and its tests, avoiding any intersection with `PipelineRunner` refactoring (which is isolated to SF-2).

## Proposed Changes

---

### Universal Logging

Reform the current `logging.py` infrastructure to unify terminal output via `Rich` and disk output via simple JSON representation.

#### [MODIFY] [logging.py](file:///c:/development/pitbula/specweaver/src/specweaver/logging.py)
- **Action**: 
  - [x] Change `logging.StreamHandler()` to `rich.logging.RichHandler(level=logging.WARNING, rich_tracebacks=True)`. Explicitly assign it `logging.Formatter("%(message)s", datefmt="[%X]")` so it does not duplicate Rich's native timestamp and level columns.
  - [x] Add a lightweight `JSONFormatter` class inheriting from `logging.Formatter`. Override `format(self, record)` to construct a dictionary containing `timestamp=self.formatTime(record, self.datefmt)`, `levelname=record.levelname`, `name=record.name`, `message=record.getMessage()`, and stringify any exception traces using `self.formatException(record.exc_info)` if `record.exc_info` exists. Finally, return `json.dumps(dict)`.
  - [x] Apply the `JSONFormatter` to the `RotatingFileHandler`.
- **Purpose**: Colorized CLI UX with robust machine-readable log lines underneath.

---

## Open Questions

None. 

## Verification Plan

### Automated Tests
1. **Unit tests for `JSONFormatter`**: Create or update tests in `tests/` directory ensuring `logging.py`'s JSON output strictly outputs valid JSON strings with all mandatory fields on `logger.debug()`.

### Manual Verification
1. Run `sw review <existing_spec_path>` to ensure that Rich formats any logged warnings gracefully on standard out.
2. Inspect the generated `<project_dir>/logs/specweaver.log` file manually to assert it's valid NDJSON (Newline Delimited JSON).
