# B-FLOW-01 SF-A — Foundation: Spec Enforcement + Contract Generation

**Status**: COMPLETED · **FRs owned**: FR-1, FR-2 · **Depends on**: none · **Feature ID**: 3.28
(3.28a + 3.28b) · Design: [B-FLOW-01_design.md](B-FLOW-01_design.md) §Sub-features → SF-A

## Goal

The two inputs the scenario pipeline needs:

1. **FR-1 (Spec Template Enforcement)**: S07 `TestFirstRule` also checks that the spec has a
   `## Scenarios` section with structured YAML.
2. **FR-2 (API Contract Generation)**: new `GenerateContractHandler` extracts a Python `Protocol`
   class from the spec's `## Contract` section and writes it to `contracts/api_contract.py`.

In scope: S07 enhancement (`_extract_scenarios()` + `_validate_scenario_yaml()`);
`GenerateContractHandler` in `flow/_generation.py`; `StepTarget.CONTRACT`; `VALID_STEP_COMBINATIONS`
entry `(GENERATE, CONTRACT)`; registration in `StepHandlerRegistry.__init__()`; re-export in
`handlers.py` + `__all__`; tests. Out of scope: scenario generation, pipeline YAML wiring and agent
isolation (SF-B); arbiter (SF-C). Binding decisions: AD-2 (handler lives in `flow/`), AD-6
(`StepAction.GENERATE` + `StepTarget.CONTRACT`).

## Where it plugs in

- The project uses `ruamel.yaml>=0.18` (not `pyyaml`) everywhere, e.g. `PlanSpecHandler` at
  `_generation.py:299`. S07 YAML validation uses `ruamel.yaml.YAML(typ="safe")`, NOT
  `yaml.safe_load()`.
- S07 has its own `_extract_contract()` at line 203-219; its regex differs from S06's.
  `_extract_scenarios()` follows S07's pattern (returns `str | None`, `re.MULTILINE |
  re.IGNORECASE`), not S06's (returns `str`, `re.DOTALL`).
- `GenerateCodeHandler` uses `Generator` from `implementation/`. Contract generation does NOT: it is
  **pure-logic** extraction (read spec → extract `## Contract` → parse code blocks for Python
  signatures → template a Protocol class). No LLM, adapter or config.
- `StepHandler` at `_base.py:135-138` is a `@runtime_checkable Protocol` with one method, `async def
  execute(self, step: PipelineStep, context: RunContext) -> StepResult`. The new handler MUST match
  it exactly.
- `RunContext.api_contract_paths` already exists: `_base.py:57` has `api_contract_paths: list[str] |
  None = None` (for neighbouring API surfaces). The handler MUST append the generated contract path
  so SF-B's `ScenarioGenerator` can consume it.
- `validation/context.yaml` declares `archetype: pure-logic`. `ruamel.yaml.YAML(typ="safe").load()`
  parses an in-memory string (no file I/O), and `validation/` already consumes `config/` (pydantic),
  so it is allowed.
- `tests/unit/assurance/validation/rules/test_s07_test_first.py`: 192 lines, 5 test classes
  (`TestExtractContract`, `TestAnalyseContract`, `TestTestabilityScore`, `TestTestFirstRuleCheck`),
  string fixtures (`_GOOD_CONTRACT`, `_NO_CONTRACT_SPEC`, …). New tests follow this pattern.

**Scenario YAML schema** — the contract between SF-A and SF-B. Follows the `TestExpectation` model
(`workflows/planning/models.py:133-152`); SF-B adds `req_id`. SF-A checks required keys so garbage
YAML never reaches SF-B's generator:
```yaml
- name: "happy_path_login"          # required, str
  function_under_test: "login"      # required, str
  input_summary: "valid credentials" # required, str
  expected_behavior: "returns token" # required, str
  category: "happy"                  # optional, one of: happy|error|boundary
```

FR-2 asks for typed signatures **and docstrings**, so `_render_protocol()` extracts docstrings from
Contract code blocks into the Protocol stubs.

### Reused infrastructure (all SFs; line refs as of the design)

| Component | Location | Feature | Status |
|-----------|----------|---------|--------|
| `GateType.JOIN` | `flow/models.py:60` | 3.27 | ✅ Complete |
| JOIN step stripping + Wave N deferred execution | `flow/_decompose.py:190-278` | 3.27 | ✅ Complete |
| `AsyncRateLimiterAdapter` global semaphore pool | `llm/adapters/_rate_limit.py` | 3.27 | ✅ Complete |
| `OrchestrateComponentsHandler` DAG scheduling | `flow/_decompose.py:77-291` | 3.27 | ✅ Complete |
| `FolderGrant(path, mode, recursive)` | `loom/security.py:38-49` | 3.26 | ✅ Complete |
| `AccessMode` enum (READ/WRITE/FULL) | `loom/security.py:20-26` | 3.26 | ✅ Complete |
| `WorkspaceBoundary` with `api_paths` read-only support | `loom/security.py:56-127` | 3.26 | ✅ Complete |
| `ToolDispatcher.create_standard_set(boundary, role)` | `loom/dispatcher.py:98-161` | 3.11a | ✅ Complete |
| Role-gated `FileSystemTool` with grants | `loom/tools/filesystem/tool.py` | Phase 2 | ✅ Complete |
| S07 Test-First rule (Contract section validation) | `validation/rules/spec/s07_test_first.py` | Phase 1 | ✅ Complete |
| C09 Traceability Matrix (scans `@trace` tags) | `validation/rules/code/c09_traceability.py` | 3.8 | ✅ Complete |
| `TestExpectation` model (precursor to scenarios) | `workflows/planning/models.py:133-152` | 3.6 | ✅ Complete |
| `StepHandlerRegistry` with `register()` | `flow/handlers.py:103-110` | Phase 2 | ✅ Complete |
| Pipeline runner `fan_out()` | `flow/runner.py:162-188` | 3.24 | ✅ Complete |
| `PipelineRunner` worktree sandbox execution | `flow/runner.py:287-353` | 3.26 | ✅ Complete |
| Pipeline YAML definitions (data-only) | `workflows/pipelines/*.yaml` | Phase 2 | ✅ Complete |

### SF-A reuse

| Component | Status | Source | Method |
|-----------|--------|--------|--------|
| `_extract_contract()` regex (S06) | 🟡 Adapt | `validation/rules/spec/s06_concrete_example.py:17-24` | Clone as `_extract_section(spec_text, heading)` — change regex from `Contract` to `Scenarios`. Same module, no boundary issues |
| S07 scoring system (`warn_score`/`fail_score`) | 🟢 Reuse | `validation/rules/spec/s07_test_first.py:55-66` | Add new check to existing `check()` method. Scoring + Finding infrastructure 100% reusable |
| Protocol/Contract section regex | 🟢 Reuse | `workflows/planning/ui_extractor.py:18-21` | `_SECTION_RE` already extracts `## Protocol` / `## Contract` sections. Production-tested regex |
| `GenerateCodeHandler` pattern | 🟢 Reuse | `flow/_generation.py:93-164` | Clone: same `_resolve_generation_routing()`, same `_extract_prompt_feedback()`, same `StepResult` with `generated_path`, same artifact UUID tracking |
| `CodeStructureAtom` (tree-sitter) | 🟡 Adapt | `loom/atoms/code_structure/atom.py` | Can extract function signatures from Contract code blocks. `flow/` consumes `loom/atoms/*` ✅ |
| YAML structure validation | 🔴 New | — | ~30 lines: parse `## Scenarios` section content, validate it's valid YAML with expected keys |
| Contract file generator | 🔴 New | — | ~60 lines: template that produces `contracts/api_contract.py` with typed Protocol class |

## Changes

### 1. S07 enhancement (FR-1) · [s07_test_first.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/rules/spec/s07_test_first.py)

0. Add `Any` to existing imports (line 15):
   ```python
   from typing import TYPE_CHECKING, Any, ClassVar
   ```

1. Add `_extract_scenarios(text: str) -> str | None` function (follows `_extract_contract` pattern
   at line 203-219):
   ```python
   def _extract_scenarios(text: str) -> str | None:
       """Extract the Scenarios section content from a spec."""
       pattern = re.compile(
           r"^##\s+(?:\d+\.\s+)?Scenarios\s*$",
           re.MULTILINE | re.IGNORECASE,
       )
       match = pattern.search(text)
       if not match:
           return None
       start = match.end()
       next_header = re.search(r"^##\s+", text[start:], re.MULTILINE)
       if next_header:
           return text[start : start + next_header.start()]
       return text[start:]
   ```

2. Add `_SCENARIO_REQUIRED_KEYS` constant and `_validate_scenario_yaml(scenarios_text: str) ->
   list[Finding]` function:
   ```python
   _SCENARIO_REQUIRED_KEYS = frozenset({"name", "function_under_test", "input_summary", "expected_behavior"})
   _SCENARIO_VALID_CATEGORIES = frozenset({"happy", "error", "boundary"})

   def _validate_scenario_yaml(scenarios_text: str) -> list[Finding]:
       """Validate that the Scenarios section contains valid YAML with expected schema.

       Expected schema per item (aligned with TestExpectation model):
         - name: str (required)
         - function_under_test: str (required)
         - input_summary: str (required)
         - expected_behavior: str (required)
         - category: str (optional, one of: happy|error|boundary)
       """
       from ruamel.yaml import YAML, YAMLError

       yaml = YAML(typ="safe")
       findings: list[Finding] = []

       # Extract YAML from code blocks
       code_blocks = re.findall(r"```(?:ya?ml)?\s*\n(.*?)```", scenarios_text, re.DOTALL)
       if not code_blocks:
           findings.append(Finding(
               message="Scenarios section has no YAML code blocks",
               severity=Severity.ERROR,
               suggestion="Add at least one ```yaml code block with scenario definitions.",
           ))
           return findings

       for block in code_blocks:
           try:
               data = yaml.load(block)
               if isinstance(data, list):
                   for i, item in enumerate(data):
                       findings.extend(_validate_scenario_item(item, i))
               elif isinstance(data, dict):
                   findings.extend(_validate_scenario_item(data, 0))
               else:
                   findings.append(Finding(
                       message=f"Scenario YAML must be a list or mapping, got: {type(data).__name__}",
                       severity=Severity.ERROR,
                   ))
           except YAMLError as exc:
               findings.append(Finding(
                   message=f"Invalid YAML in Scenarios section: {exc}",
                   severity=Severity.ERROR,
                   suggestion="Fix the YAML syntax in the scenario code block.",
               ))
       return findings

   def _validate_scenario_item(item: Any, index: int) -> list[Finding]:
       """Validate a single scenario item against the expected schema."""
       findings: list[Finding] = []
       if not isinstance(item, dict):
           findings.append(Finding(
               message=f"Scenario item {index} must be a mapping, got: {type(item).__name__}",
               severity=Severity.ERROR,
           ))
           return findings

       missing = _SCENARIO_REQUIRED_KEYS - set(item.keys())
       if missing:
           findings.append(Finding(
               message=f"Scenario item {index} missing required keys: {sorted(missing)}",
               severity=Severity.ERROR,
               suggestion=f"Each scenario must have: {sorted(_SCENARIO_REQUIRED_KEYS)}",
           ))

       category = item.get("category")
       if category is not None and category not in _SCENARIO_VALID_CATEGORIES:
           findings.append(Finding(
               message=f"Scenario item {index} has invalid category '{category}'",
               severity=Severity.WARNING,
               suggestion=f"category must be one of: {sorted(_SCENARIO_VALID_CATEGORIES)}",
           ))
       return findings
   ```

3. Modify `TestFirstRule.check()` to add scenario validation after the existing contract scoring
   logic (line 81-120). Insert after the final `return self._pass(...)`:

   > [!CAUTION]
   > The scenario check is **additive** — it runs AFTER the existing contract scoring. A spec can
   > pass the contract check but fail the scenario check. The scenario check returns its own
   > findings independent of the contract score.

   ```python
   # After existing contract scoring (before the final return):
   scenarios = _extract_scenarios(spec_text)
   if scenarios is None:
       return self._warn(
           f"Contract testability score: {testability_score}/12. "
           "No Scenarios section found — scenario generation will be skipped.",
           findings + [Finding(
               message="Missing '## Scenarios' section",
               severity=Severity.WARNING,
               suggestion="Add a '## Scenarios' section with YAML scenario definitions.",
           )],
       )

   scenario_findings = _validate_scenario_yaml(scenarios)
   if scenario_findings:
       return self._warn(
           f"Contract testability score: {testability_score}/12. "
           "Scenarios section has structural issues.",
           findings + scenario_findings,
       )
   ```

> [!NOTE]
> A missing `## Scenarios` section is a WARNING, not FAIL, for backward compatibility: existing
> specs without scenarios still pass S07. Only malformed YAML in an existing section produces
> ERROR-level findings.

### 2. Contract generation handler (FR-2)

[models.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/models.py) — new
`StepTarget` value (after line 51):
```python
CONTRACT = "contract"
```

`VALID_STEP_COMBINATIONS` (after line 106):
```python
(StepAction.GENERATE, StepTarget.CONTRACT),
```

[_generation.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_generation.py)
— `GenerateContractHandler` after `GenerateTestsHandler` (after line 238):

```python
class GenerateContractHandler:
    """Handler for generate+contract — extracts API Protocol from spec Contract section.

    This is a mechanical (non-LLM) extraction. It reads the spec's ## Contract
    section, extracts Python function signatures from code blocks, and generates
    a Protocol class file at contracts/api_contract.py.

    No LLM adapter is required.
    """

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        try:
            spec_text = context.spec_path.read_text(encoding="utf-8")
            contract_section = self._extract_contract(spec_text)
            if contract_section is None:
                return _error_result("No ## Contract section found in spec", started)

            signatures = self._extract_signatures(contract_section)
            if not signatures:
                return _error_result(
                    "No Python function signatures found in Contract code blocks",
                    started,
                )

            docstrings = self._extract_docstrings(contract_section)

            contracts_dir = context.project_path / "contracts"
            contracts_dir.mkdir(parents=True, exist_ok=True)
            output_path = contracts_dir / f"{context.spec_path.stem.replace('_spec', '')}_contract.py"

            protocol_content = self._render_protocol(
                context.spec_path.stem.replace("_spec", "").replace("_", " ").title().replace(" ", ""),
                signatures,
                docstrings,
            )
            output_path.write_text(protocol_content, encoding="utf-8")
            logger.info("GenerateContractHandler: contract written to '%s'", output_path)

            # Wire contract path into RunContext for downstream consumption (SF-B)
            if context.api_contract_paths is None:
                context.api_contract_paths = []
            context.api_contract_paths.append(str(output_path))

            return StepResult(
                status=StepStatus.PASSED,
                output={"generated_path": str(output_path), "signature_count": len(signatures)},
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            logger.exception("GenerateContractHandler: unhandled exception")
            return _error_result(str(exc), started)

    @staticmethod
    def _extract_contract(text: str) -> str | None:
        """Extract the Contract section content from a spec."""
        import re

        pattern = re.compile(
            r"^##\s+(?:\d+\.\s+)?Contract\s*$",
            re.MULTILINE | re.IGNORECASE,
        )
        match = pattern.search(text)
        if not match:
            return None
        start = match.end()
        next_header = re.search(r"^##\s+", text[start:], re.MULTILINE)
        if next_header:
            return text[start : start + next_header.start()]
        return text[start:]

    @staticmethod
    def _extract_signatures(contract_text: str) -> list[str]:
        """Extract Python function/method signatures from code blocks."""
        import re

        code_blocks = re.findall(
            r"```python\s*\n(.*?)```", contract_text, re.DOTALL
        )
        signatures: list[str] = []
        for block in code_blocks:
            # Match def/async def lines
            for match in re.finditer(
                r"^\s*((?:async\s+)?def\s+\w+\(.*?\)(?:\s*->\s*[^\n:]+)?)\s*:",
                block,
                re.MULTILINE | re.DOTALL,
            ):
                signatures.append(match.group(1).strip())
        return signatures

    @staticmethod
    def _extract_docstrings(contract_text: str) -> dict[str, str]:
        """Extract docstrings paired with function names from code blocks.

        Returns a mapping of function_name -> docstring content.
        """
        import re

        code_blocks = re.findall(
            r"```python\s*\n(.*?)```", contract_text, re.DOTALL
        )
        docstrings: dict[str, str] = {}
        for block in code_blocks:
            # Match: def func_name(...): followed by a docstring
            for match in re.finditer(
                r"(?:async\s+)?def\s+(\w+)\(.*?\).*?:\s*\n"
                r'\s+"""(.*?)"""',
                block,
                re.DOTALL,
            ):
                func_name = match.group(1)
                docstring = match.group(2).strip()
                docstrings[func_name] = docstring
        return docstrings

    @staticmethod
    def _render_protocol(
        class_name: str,
        signatures: list[str],
        docstrings: dict[str, str] | None = None,
    ) -> str:
        """Render a Python Protocol class from extracted signatures and docstrings."""
        import re

        docstrings = docstrings or {}
        lines = [
            '"""Auto-generated API contract from spec Contract section."""',
            "",
            "from __future__ import annotations",
            "",
            "from typing import Protocol, runtime_checkable",
            "",
            "",
            "@runtime_checkable",
            f"class {class_name}Protocol(Protocol):",
            f'    """API contract for {class_name}."""',
            "",
        ]
        for sig in signatures:
            lines.append(f"    {sig}:")
            # Extract function name from signature to look up docstring
            func_match = re.search(r"def\s+(\w+)\(", sig)
            func_name = func_match.group(1) if func_match else None
            if func_name and func_name in docstrings:
                lines.append(f'        """{docstrings[func_name]}"""')
            else:
                lines.append("        ...")
            lines.append("")
        return "\n".join(lines) + "\n"
```

> [!WARNING]
> `_extract_signatures` handles single-line signatures only. Multi-line signatures are NOT
> supported:
> spec Contract sections use compact single-line signatures. tree-sitter parsing (already available)
> can add multi-line support later.

[handlers.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/handlers.py) —
import (after line 36):
```python
from specweaver.core.flow._generation import (
    GenerateCodeHandler,
    GenerateContractHandler,  # NEW
    GenerateTestsHandler,
    PlanSpecHandler,
)
```

`__all__` (after line 54):
```python
"GenerateContractHandler",
```

`StepHandlerRegistry.__init__()` (after line 86):
```python
(StepAction.GENERATE, StepTarget.CONTRACT): GenerateContractHandler(),
```

### Files

| File | Change |
|---|---|
| `src/specweaver/assurance/validation/rules/spec/s07_test_first.py` | scenario extraction + YAML validation |
| `src/specweaver/core/flow/models.py` | 2-line additive |
| `src/specweaver/core/flow/_generation.py` | ~60 lines added |
| `src/specweaver/core/flow/handlers.py` | 3 lines: import, __all__, registration |
| `tests/unit/assurance/validation/rules/test_s07_test_first.py` | ~80 lines added |
| `tests/unit/core/flow/test_contract_handler.py` | ~100 lines, new file |

Commit: `feat(3.28a,3.28b): add scenario template enforcement and contract generation handler`

## Tests

`tests/unit/assurance/validation/rules/test_s07_test_first.py` (extend existing):

New test class `TestScenarioExtraction`:
- `test_extracts_numbered_header` — `## 3. Scenarios` is found
- `test_extracts_unnumbered_header` — `## Scenarios` is found
- `test_returns_none_when_missing` — spec without Scenarios
- `test_stops_at_next_section` — content ends at next `##`
- `test_end_of_file_scenarios` — section at end of file

New test class `TestScenarioYamlValidation`:
- `test_valid_yaml_list` — YAML list parsed successfully
- `test_valid_yaml_mapping` — YAML mapping parsed successfully
- `test_invalid_yaml_syntax` — malformed YAML produces finding
- `test_no_yaml_code_blocks` — no code blocks → finding
- `test_non_collection_yaml` — scalar YAML value → finding
- `test_missing_required_keys` — item without `name`/`function_under_test` → ERROR finding
- `test_all_required_keys_present` — valid item passes key check
- `test_invalid_category_warns` — `category: "invalid"` → WARNING
- `test_valid_categories_pass` — happy, error, boundary all accepted

New test class `TestScenarioIntegration`:
- `test_good_spec_with_scenarios_passes` — full spec with scenarios passes
- `test_good_spec_without_scenarios_warns` — full spec without scenarios warns (backward compat)
- `test_good_spec_with_malformed_scenarios_warns` — full spec with bad YAML warns
- `test_existing_spec_fixture_backward_compat` — existing `_GOOD_CONTRACT` fixture still PASS
  (NFR-7)

`tests/unit/core/flow/test_contract_handler.py` (new):

Test class `TestGenerateContractHandler`:
- `test_extracts_signatures_from_contract` — verifies `_extract_signatures()` finds defs
- `test_extracts_docstrings_from_contract` — verifies `_extract_docstrings()` finds docstrings
- `test_renders_protocol_class_with_docstrings` — verifies `_render_protocol()` includes docstrings
  (FR-2)
- `test_renders_protocol_class_without_docstrings` — verifies `_render_protocol()` uses `...`
  fallback
- `test_execute_creates_contract_file` — full handler execute with tmp dir
- `test_execute_wires_api_contract_paths` — verifies `context.api_contract_paths` is populated
- `test_execute_no_contract_section_errors` — spec without Contract → ERROR
- `test_execute_no_signatures_errors` — Contract without code blocks → ERROR
- `test_handler_registered_in_registry` — verify `(GENERATE, CONTRACT)` is in registry
- `test_valid_step_combination` — verify `(GENERATE, CONTRACT)` is in `VALID_STEP_COMBINATIONS`

```bash
pytest tests/unit/assurance/validation/rules/test_s07_test_first.py -v
pytest tests/unit/core/flow/test_contract_handler.py -v
pytest tests/ -v --tb=short  # Full test suite regression
python -m tach check          # Boundary compliance
```

Manual: existing specs still pass S07 (backward compatibility); `(GENERATE, CONTRACT)` appears in
`StepHandlerRegistry().get(...)` output.

## As built

**Since moved** (noted 2026-09-25): `GenerateContractHandler` is in
`core/flow/handlers/generation.py`; contract extraction and renderers are in
`core/flow/handlers/contract_renderers.py`. Line refs above are as of the plan's date.
