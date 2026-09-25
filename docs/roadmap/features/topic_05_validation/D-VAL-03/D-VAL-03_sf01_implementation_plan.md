# D-VAL-03 SF-01 — Core Interface, Compilers & Python/TS Handlers

**Status**: APPROVED · **FRs owned**: FR-1, FR-2, FR-3, FR-7 (recorded 2026-08-17 under
`specweaver-dev` §3.2c, from `INT-US-03-SF01-MIG`) · **Depends on**: none · Design:
[D-VAL-03_design.md](D-VAL-03_design.md) §Sub-Feature Breakdown → SF-01 · Feature ID 3.19

FR-1's data-model clause is struck in the design: `stacktrace` and `rule_uri` are declared and
never written. The interface clause stands — its mutant fails 228 tests.

## Goal

Extend `atoms`, `tools` and `interface` to broker compile, debug, lint and test for any language.
Compiler output follows SARIF, debug output follows DAP. Implement the Python and TS runners, and
let LLM agents trigger these actions themselves.

## Changes

### 1. Interface & data models — `src/specweaver/loom/commons/qa_runner/interface.py` [MODIFY]

- `TestFailure` gains `stacktrace: str = ""` and `rule_uri: str = ""`; `LintError` gains
  `rule_uri: str = ""`.
- New `CompileError` (SARIF-inspired: standard lines, columns, messages):
  `file: str`, `line: int`, `column: int = 0`, `code: str`, `message: str`, `is_warning: bool`
- New `CompileRunResult`: `error_count: int`, `warning_count: int`, `errors: list[CompileError]`
- New `OutputEvent` (DAP OutputEvent): `category: str` (stdout, stderr, console), `output: str`,
  `file: str = ""`, `line: int = 0`
- New `DebugRunResult`: `exit_code: int`, `duration_seconds: float`, `events: list[OutputEvent]`
- `QARunnerInterface` gains:
  - `@abstractmethod def run_compiler(self, target: str) -> CompileRunResult:`
  - `@abstractmethod def run_debugger(self, target: str, entrypoint: str) -> DebugRunResult:`

### 2. Intent routing — agent down to the interface

- `src/specweaver/loom/atoms/qa_runner/atom.py` [MODIFY]
  - `_intent_run_compiler` (context `target`) → `AtomResult` with `CompileRunResult.errors`.
  - `_intent_run_debugger` (context `target`, `entrypoint`) → `AtomResult` with `DebugRunResult.events`.
- `src/specweaver/loom/tools/qa_runner/tool.py` [MODIFY]
  - `ROLE_INTENTS`: add `"run_compiler"` and `"run_debugger"` to the `implementer` and `reviewer` roles.
  - `def run_compiler(self, target: str) -> ToolResult:` — requires the `run_compiler` intent.
  - `def run_debugger(self, target: str, entrypoint: str) -> ToolResult:` — requires the
    `run_debugger` intent.

### 3. Runners

- `src/specweaver/loom/commons/qa_runner/__init__.py` [MODIFY] — expose `CompileRunResult`,
  `CompileError`, `DebugRunResult`, `OutputEvent`; `_resolve_runner` routes to `TypeScriptRunner`
  when `package.json` is traced.
- `src/specweaver/loom/commons/qa_runner/python.py` [MODIFY]
  - `run_compiler()` stub returning 0 errors (Python is interpreted: a no-op, or a `py_compile`
    trace if needed).
  - `run_debugger()` via `subprocess.run()`, stdout/stderr mapped to DAP `OutputEvent` fields.
- `src/specweaver/loom/commons/qa_runner/typescript.py` [NEW] — `TypeScriptRunner(QARunnerInterface)`
  - `run_compiler()`: `tsc --noEmit`; regex
    `<file>(<line>,<col>): error TS<code>: <msg>` → `CompileError` (tsc JSON output is non-standard
    outside tsc-watch).
  - `run_debugger()`: `node <entrypoint>` → `OutputEvent` list.

> [!CAUTION]
> Adding @abstractmethod breaks the master branch unless we implement stubs in PythonQARunner immediately.

### 4. Dependencies — `pyproject.toml` [MODIFY]

`junitparser>=3.1.2` and `sarif-tools>=1.0.0` under `dependencies`.

### 5. Docs — `docs/architecture/architecture_reference.md` [MODIFY]

New section 'Updating 3rd Party Software and Protocols within SpecWeaver': the Adapter Pattern that
insulates internal models (`CompileError`, `OutputEvent`) from schema breaks in DAP and SARIF.

## Tests

1. Unit tests across the Atom and Tool intent paths: permissions do not block implementers.
2. The TypeScript fallback regex extracts TS syntax errors.

## Decisions

- **SARIF** is the standard JSON target for compiler output (GCC 13+, MSVC, Clang); `CompileError`
  follows its diagnostic block.
- **DAP** `OutputEvent` streams logs back to agents; `category` covers stdout, stderr and exception
  boundaries.
- Deferred: native SARIF compile parsing for C++/GCC targets, once standard parsers support it.
