# C-EXEC-01 SF-07 — Target Rule C05 Subsumption (Tach)

**Status**: COMPLETED · **FRs owned**: FR-4 · **Feature ID**: 3.20a · Design:
[C-EXEC-01_design.md](C-EXEC-01_design.md) §Sub-features → SF-07

FR-4: rule C05 turns a tach boundary violation in an *analysed* project into an ERROR `Finding` a
reviewer can act on — the product-facing half of the capability, as against the repo's own hygiene.
Recorded 2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-01-SF02-MIG`. Mutant: the
no-violations branch forced true — 4 fail across three tiers.

**Since moved** (2026-07-10, `f74f5844`, TECH-01b SF-04): C05 no longer builds a `PythonQARunner`;
it reads `self.context["qa_architecture_result"]`, filled by the flow layer's validation hydrator.
`loom/commons/qa_runner/` is now `sandbox/qa_runner/core/` (interface) and
`sandbox/language/core/<lang>/runner.py`; `run_architecture_check` gained a `dal_level` argument
and runs tach through the executor. Paths below are as of the plan's date.

## Goal

Replace the hardcoded AST parser in `c05_import_direction.py` with an architecture boundary check
on the target project. C05 delegates to `QARunnerInterface` rather than running `tach` itself, so
it stays polyglot. This extends the L4/L5 QA Runner and fixes existing L2 Architectural DMZ
violations.

## Changes

1. **`src/specweaver/loom/commons/qa_runner/interface.py`**
   - New dataclasses `ArchitectureViolation` (file, code, message, rule_uri) and
     `ArchitectureRunResult` (violation_count, violations).
   - New abstract method `run_architecture_check(self, target: str) -> ArchitectureRunResult` on
     `QARunnerInterface`.
2. **`python/runner.py`** — `run_architecture_check(...)` runs
   `uv run tach check --output json` (or `tach check`) via `subprocess.run`, pointed strictly at
   `self._cwd` (the target workspace). Handles `subprocess.CalledProcessError` and parses Tach's
   JSON array (`UndeclaredDependency`). Returns an empty result if parsing fails/hangs or no
   boundary metadata is found.
3. **`typescript/runner.py`, `java/runner.py`, `kotlin/runner.py`, `rust/runner.py`** — the new
   abstract method forces every adapter to implement it; without this exact stub test orchestration
   crashes:
   ```python
   def run_architecture_check(self, target: str) -> ArchitectureRunResult:
       # Native checks (e.g. ArchUnit/ESLint) deferred to Feature 3.20b
       return ArchitectureRunResult(violation_count=0, violations=[])
   ```
4. **`src/specweaver/loom/atoms/qa_runner/atom.py`** — new intent handler `_intent_run_architecture`
   returning `AtomResult`: reads `target` from the context, calls
   `self._runner.run_architecture_check(target)`, exports `violation_count` and the serialized
   violations, maps to `SUCCESS` or `FAILED`.
5. **`src/specweaver/loom/tools/qa_runner/`**
   - `tool.py` — whitelist `run_architecture` in `ROLE_INTENTS` for `implementer`, `reviewer`,
     `planner`; add `run_architecture_check(self, target: str) -> ToolResult` dispatching the same
     atom intent.
   - `definitions.py` — `INTENT_DEFINITIONS["run_architecture"]` with one string target parameter.
6. **`src/specweaver/validation/context.yaml`** — add `specweaver/loom/commons/qa_runner` to
   `consumes`. Rules C03 (Tests Pass) and C04 (Coverage) already import L4 components past the DMZ
   guards; this makes that explicit without opening broad I/O gaps.
7. **`rules/code/c05_import_direction.py`**
   - Remove `ast.parse` and the static `_FORBIDDEN_RULES` mapping.
   - Resolve the project root (as `c03` does) and create `PythonQARunner(cwd=project_root)`
     (future: dynamic language adapter); call `.run_architecture_check(target)`.
   - Zero violations → `self._pass("All structural architecture boundaries verified")`.
   - Each `ArchitectureViolation` → `Finding(message=..., severity=Severity.ERROR)`.
   - No `tach.toml` in the workspace → detect empty results / fallback exceptions and return
     `self._skip(...)` until SF-08 generates one.

## Traps

- **JSON schema:** Tach nests `Located -> details -> Code -> UndeclaredDependency`. Parse with
  `.get()` defaults so an API bump fails cleanly instead of a `KeyError` inside the workflow engine.
- **Speed:** the AST check took ms. If the subprocess adds > 400ms across unit tests, mock C05 in
  unit runs outside E2E.
- **`tach` must resolve** inside the venv running the code; SpecWeaver ships it as a
  dev-dependency.

## Tests

- `c05_import_direction` skips on invalid target environments and maps Tach errors into a
  `RuleResult` failure holding multiple `Findings`.
- Cross-layer tests from `PythonQARunner` output to the `Validation` interfaces.
- Standard pre-commit workflow.
