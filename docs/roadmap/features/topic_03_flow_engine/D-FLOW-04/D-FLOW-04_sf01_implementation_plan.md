# D-FLOW-04 SF-01 — Universal Logging Reform

**Status**: APPROVED · **FRs owned**: FR-2, FR-3 · **Depends on**: none · **Feature ID**: 3.13a ·
Design: [D-FLOW-04_design.md](D-FLOW-04_design.md) §Sub-features → SF-01

## Goal

Retrofit `src/specweaver/logging.py`: console via `rich.logging.RichHandler` (colorized, WARNING+
only unless `--debug`), plus a stdlib-based `JSONFormatter` writing full DEBUG logs to a local
`specweaver.log` in machine-parseable form.

**Since moved**: the module is `src/specweaver/telemetry_logger.py`; the log file is
`~/.specweaver/logs/<project>/specweaver.log`.

## Decisions

- **Custom JSON `logging.Formatter`, not a 3rd-party dependency** (user-confirmed). A
  `logging.Formatter` subclass running `json.dumps()` on `record.__dict__` needs no
  `python-json-logger`.
- `RichHandler`: the Typer CLI already relies on `Rich`, so no new library.
- Scope: logging inside `logging.py` and its tests only; no overlap with the `PipelineRunner` work
  (SF-02).

## Changes

`logging.py`:

1. `logging.StreamHandler()` → `rich.logging.RichHandler(level=logging.WARNING, rich_tracebacks=True)`,
   with `logging.Formatter("%(message)s", datefmt="[%X]")` so it does not duplicate Rich's own
   timestamp and level columns.
2. New `JSONFormatter(logging.Formatter)`. `format(self, record)` builds a dict:
   `timestamp=self.formatTime(record, self.datefmt)`, `levelname=record.levelname`,
   `name=record.name`, `message=record.getMessage()`, plus the exception trace via
   `self.formatException(record.exc_info)` when `record.exc_info` is set; returns `json.dumps(dict)`.
3. Apply `JSONFormatter` to the `RotatingFileHandler`.

## Tests

- Unit tests for `JSONFormatter` in `tests/`: `logger.debug()` yields valid JSON with all mandatory
  fields.
- Manual: `sw review <existing_spec_path>` — Rich formats logged warnings on standard out; the log
  file (planned as `<project_dir>/logs/specweaver.log`) is valid NDJSON (Newline Delimited JSON).

## As built

In `telemetry_logger.py` the `RichHandler` is built on a stderr `Console` (a bare `RichHandler()`
writes to stdout).
