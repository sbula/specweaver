# Implementation Plan: Polyglot QARunner Interface [SF-1: Core Interface, Compilers & Python/TS Handlers]
- **Feature ID**: 3.19
- **Sub-Feature**: SF-1 — Core Interface, Compilers & Python/TS Handlers
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3_19/feature_3_19_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_19/feature_3_19_sf1_implementation_plan.md
- **Status**: APPROVED

## Goal Description
Expand the engine internals (`atoms`, `tools`, `interface`) to securely broker universal compile, debug, lint, and test execution formats. This foundational sub-feature standardizes compiler outputs via SARIF protocols and debug outputs via DAP standards. It implements the Python and TS runners and explicitly ensures LLM Agents can safely trigger these actions themselves.

## 1. Interface & Data Models (`interface.py`)
Add models to standardize compiler errors (SARIF-inspired) and debug streams (DAP-inspired).

### [MODIFY] `src/specweaver/loom/commons/qa_runner/interface.py`
Add base imports.
Update `TestFailure` to add `stacktrace: str = ""` and `rule_uri: str = ""`.
Update `LintError` to add `rule_uri: str = ""`.

> [!NOTE]
> Standardizing Compiler errors maps nicely to SARIF, which provides standard lines, columns, and message structures. 
Add new `CompileError` data model:
- `file: str`, `line: int`, `column: int = 0`, `code: str`, `message: str`, `is_warning: bool`

Add new `CompileRunResult` data model:
- `error_count: int`, `warning_count: int`, `errors: list[CompileError]`

> [!NOTE]
> Standardizing Debug outputs maps well to DAP (Debug Adapter Protocol) OutputEvents.
Add new `OutputEvent` data model:
- `category: str` (stdout, stderr, console)
- `output: str`
- `file: str = ""`
- `line: int = 0`

Add new `DebugRunResult` data model:
- `exit_code: int`, `duration_seconds: float`, `events: list[OutputEvent]`

Update `QARunnerInterface` class:
- Add `@abstractmethod def run_compiler(self, target: str) -> CompileRunResult:`
- Add `@abstractmethod def run_debugger(self, target: str, entrypoint: str) -> DebugRunResult:`

## 2. Intent Routing (`atom.py` & `tool.py`)
Plumb the new compile and debug hooks from the LLM agent down to the interface.

### [MODIFY] `src/specweaver/loom/atoms/qa_runner/atom.py`
- Add `_intent_run_compiler` handling context `target`. Returns `AtomResult` packaging `CompileRunResult.errors`.
- Add `_intent_run_debugger` handling context `target` and `entrypoint`. Returns `AtomResult` packaging `DebugRunResult.events`.

### [MODIFY] `src/specweaver/loom/tools/qa_runner/tool.py`
- Update `ROLE_INTENTS` dict: Add `"run_compiler"` and `"run_debugger"` to both the `implementer` and `reviewer` roles.
- Add `def run_compiler(self, target: str) -> ToolResult:`. Requires `run_compiler` intent.
- Add `def run_debugger(self, target: str, entrypoint: str) -> ToolResult:`. Requires `run_debugger` intent.

## 3. Runners & Fallbacks (`python.py`, `typescript.py`, `__init__.py`)
Implement the base logic for Python and the new TypeScript handler.

### [MODIFY] `src/specweaver/loom/commons/qa_runner/__init__.py`
- Expose `CompileRunResult`, `CompileError`, `DebugRunResult`, `OutputEvent`.
- Update `_resolve_runner` to route to `TypeScriptRunner` if `package.json` is traced.

### [MODIFY] `src/specweaver/loom/commons/qa_runner/python.py`
> [!CAUTION]
> Adding @abstractmethod breaks the master branch unless we implement stubs in PythonQARunner immediately.
- Implement `run_compiler()` stub returning 0 errors (Since python is interpreted, fallback to a compilation no-op or surface `py_compile` trace if needed).
- Implement `run_debugger()` using `subprocess.run()`, capturing stdout/stderr and mapping to DAP `OutputEvent` fields.

### [NEW] `src/specweaver/loom/commons/qa_runner/typescript.py`
- Build `TypeScriptRunner(QARunnerInterface)`
- `run_compiler()`: runs `tsc --noEmit`. Fallback to Regex parsing `<file>(<line>,<col>): error TS<code>: <msg>` to `CompileError` (since tsc JSON output is non-standard outside of tsc-watch).
- `run_debugger()`: runs `node <entrypoint>`, parses directly to `OutputEvent` arrays.

## 4. Dependencies
### [MODIFY] `pyproject.toml`
- Add `junitparser>=3.1.2` and `sarif-tools>=1.0.0` under standard `dependencies`.

## 5. Documentation
### [MODIFY] `docs/architecture/architecture_reference.md`
- Add a new section titled 'Updating 3rd Party Software and Protocols within SpecWeaver'. Define the Adapter Pattern strategy which explicitly insulates SpecWeaver's internal data models (`CompileError`, `OutputEvent`) from underlying schema breakages in protocols like DAP and SARIF.

## Research Notes
- **SARIF (Static Analysis Results Interchange Format)**: Research confirms this is the industry-standard JSON target for compiler outputs globally (GCC 13+, MSVC, Clang). We molded the `CompileError` tightly around its diagnostic block logic.
- **DAP (Debug Adapter Protocol)**: We adopted the `OutputEvent` from the DAP standard format to uniformly stream logs back to agents (`category` handles stdout, stderr, exception boundaries seamlessly).

## Backlog / Deferred
- Implementation of SARIF compilation parsing natively for C++/GCC targets (handled once standard parsers integrate fully to compiler specs natively).

## Verification Plan
1. Execute unit tests across Atom and Tool intent paths to confirm permissions don't block implementers.
2. Verify TypeScript fallback regex patterns safely extract TS syntax errors.
