# Implementation Plan: Scenario Testing — Independent Verification [SF-A: Foundation — Spec Enforcement + Contract Generation]

- **Feature ID**: 3.28
- **Sub-Feature**: SF-A — Foundation: Spec Enforcement + Contract Generation
- **Design Document**: docs/roadmap/phase_3/feature_3.28/feature_3.28_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-A
- **Implementation Plan**: docs/roadmap/phase_3/feature_3.28/feature_3.28_sfa_implementation_plan.md
- **Status**: COMPLETED

## Scope

SF-A establishes the two foundational inputs for the scenario pipeline:

1. **FR-1 (Spec Template Enforcement)**: Enhance S07 `TestFirstRule` to also validate that the spec contains a `## Scenarios` section with structured YAML content.
2. **FR-2 (API Contract Generation)**: New `GenerateContractHandler` that extracts a Python `Protocol` class from a spec's `## Contract` section and writes it to `contracts/api_contract.py`.

### What's In Scope
- S07 enhancement (new `_extract_scenarios()` + `_validate_scenario_yaml()`)
- `GenerateContractHandler` in `flow/_generation.py`
- New `StepTarget.CONTRACT` enum value
- New `VALID_STEP_COMBINATIONS` entry: `(GENERATE, CONTRACT)`
- Handler registration in `StepHandlerRegistry.__init__()`
- Re-export in `handlers.py` + `__all__`
- Tests for all of the above

### What's Out of Scope (deferred to SF-B/SF-C)
- Scenario generation (SF-B)
- Pipeline YAML wiring (SF-B)
- Agent isolation (SF-B)
- Arbiter (SF-C)

## Research Notes

### RN-1: Project uses `ruamel.yaml`, NOT `pyyaml`
The design doc mentions `pyyaml` in External Dependencies, but `pyproject.toml` declares `ruamel.yaml>=0.18`. The codebase uses `ruamel.yaml` everywhere (e.g., `PlanSpecHandler` at `_generation.py:299`). The S07 scenario YAML validation MUST use `ruamel.yaml.YAML(typ="safe")`, NOT `yaml.safe_load()`.

### RN-2: S07 already has `_extract_contract()` (different from S06's)
S07 has its own `_extract_contract()` at line 203-219 with a slightly different regex than S06's version. The new `_extract_scenarios()` should follow S07's pattern (returns `str | None`, uses `re.MULTILINE | re.IGNORECASE`), not S06's (returns `str`, uses `re.DOTALL`).

### RN-3: `GenerateCodeHandler` uses `Generator` from `implementation/`
The contract handler needs a different approach — it's NOT LLM-based code generation. It's mechanical extraction from spec markdown. It should NOT use the `Generator` class. Instead, it should:
1. Read spec text
2. Extract `## Contract` section (reuse `_extract_contract()` pattern)
3. Parse code blocks for Python signatures
4. Template a Protocol class file
This is a **pure-logic** operation, not an LLM call. No adapter/config needed.

### RN-4: `StepHandler` is a `Protocol` (structural typing)
`StepHandler` at `_base.py:135-138` is a `@runtime_checkable Protocol` with a single method: `async def execute(self, step: PipelineStep, context: RunContext) -> StepResult`. The new handler MUST match this signature exactly.

### RN-5: Existing S07 test patterns
`tests/unit/assurance/validation/rules/test_s07_test_first.py` has 192 lines with 5 test classes: `TestExtractContract`, `TestAnalyseContract`, `TestTestabilityScore`, `TestTestFirstRuleCheck`. Each uses string fixtures (`_GOOD_CONTRACT`, `_NO_CONTRACT_SPEC`, etc.). New tests follow this exact pattern.

### RN-6: `RunContext.api_contract_paths` already exists
`_base.py:57` has `api_contract_paths: list[str] | None = None`. This field was designed for neighboring API surfaces. The contract handler MUST append the generated contract path to this list so SF-B's `ScenarioGenerator` can consume it downstream.

### RN-7: Validation module is `pure-logic` archetype
`validation/context.yaml` declares `archetype: pure-logic`. This means S07 MUST NOT import `ruamel.yaml` at module level if it's considered I/O. However, `ruamel.yaml.YAML(typ="safe").load()` is a pure parsing operation (no I/O), and `validation/` already consumes `config/` which uses pydantic. The YAML parsing is acceptable as in-memory string parsing, not file I/O.

### RN-8: Scenario YAML schema (contract between SF-A and SF-B)
The `## Scenarios` YAML must follow the `TestExpectation` model from `workflows/planning/models.py:133-152`. SF-B will extend this with `req_id`. SF-A's validator MUST check for required keys to prevent garbage YAML from reaching SF-B's generator. Expected schema:
```yaml
- name: "happy_path_login"          # required, str
  function_under_test: "login"      # required, str
  input_summary: "valid credentials" # required, str
  expected_behavior: "returns token" # required, str
  category: "happy"                  # optional, one of: happy|error|boundary
```

### RN-9: FR-2 requires docstrings in generated Protocol
FR-2's Outcome column says: "Produces `contracts/api_contract.py` with typed method signatures **and docstrings**." The `_render_protocol()` method must extract docstrings from Contract code blocks and include them in the generated Protocol stubs.

### RN-10: AD-2 and AD-6 govern SF-A directly
- AD-2: "Contract generation handler lives in `flow/` (new handler)"
- AD-6: "New `StepAction.GENERATE` + `StepTarget.CONTRACT` for contract generation"
These are binding architectural decisions — the implementation MUST follow them.

### RN-11: External Dependencies table error
The design doc's External Dependencies table lists `pyyaml 6.0+` but the project uses `ruamel.yaml>=0.18`. This should be corrected in the design doc.

## Proposed Changes

### Component 1: Validation — S07 Enhancement (FR-1)

#### [MODIFY] [s07_test_first.py](file:///c:/development/pitbula/specweaver/src/specweaver/assurance/validation/rules/spec/s07_test_first.py)

**Changes:**

0. Add `Any` to existing imports (line 15):
   ```python
   from typing import TYPE_CHECKING, Any, ClassVar
   ```

1. Add `_extract_scenarios(text: str) -> str | None` function (follows `_extract_contract` pattern at line 203-219):
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

2. Add `_SCENARIO_REQUIRED_KEYS` constant and `_validate_scenario_yaml(scenarios_text: str) -> list[Finding]` function:
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

3. Modify `TestFirstRule.check()` to add scenario validation after the existing contract scoring logic (line 81-120). Insert after the final `return self._pass(...)`:

   > [!CAUTION]
   > The scenario check is **additive** — it runs AFTER the existing contract scoring. A spec can pass the contract check but fail the scenario check. The scenario check returns its own findings independent of the contract score.

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
> The missing `## Scenarios` section produces a WARNING, not FAIL. This ensures backward compatibility — existing specs without scenarios continue to pass S07 (they already have no scenario section today). Only malformed YAML in an existing section produces ERROR-level findings.

---

### Component 2: Flow — Contract Generation Handler (FR-2)

#### [MODIFY] [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/models.py)

Add new `StepTarget` enum value (after line 51):
```python
CONTRACT = "contract"
```

Add to `VALID_STEP_COMBINATIONS` (after line 106):
```python
(StepAction.GENERATE, StepTarget.CONTRACT),
```

#### [MODIFY] [_generation.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_generation.py)

Add `GenerateContractHandler` class after `GenerateTestsHandler` (after line 238):

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
> The `_extract_signatures` regex handles single-line signatures. Multi-line signatures (with parentheses spanning multiple lines) are NOT supported in this first cut. This is acceptable because spec Contract sections typically use compact single-line signatures. If multi-line support is needed, tree-sitter parsing (already available) can be added in a follow-up.

#### [MODIFY] [handlers.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/handlers.py)

Add import (after line 36):
```python
from specweaver.core.flow._generation import (
    GenerateCodeHandler,
    GenerateContractHandler,  # NEW
    GenerateTestsHandler,
    PlanSpecHandler,
)
```

Add to `__all__` (after line 54):
```python
"GenerateContractHandler",
```

Add to `StepHandlerRegistry.__init__()` (after line 86):
```python
(StepAction.GENERATE, StepTarget.CONTRACT): GenerateContractHandler(),
```

---

### Component 3: Tests

#### [NEW] Tests for S07 Scenario Enhancement

**File**: `tests/unit/assurance/validation/rules/test_s07_test_first.py` (extend existing)

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
- `test_existing_spec_fixture_backward_compat` — existing `_GOOD_CONTRACT` fixture still PASS (NFR-7)

#### [NEW] Tests for GenerateContractHandler

**File**: `tests/unit/core/flow/test_contract_handler.py` (new file)

Test class `TestGenerateContractHandler`:
- `test_extracts_signatures_from_contract` — verifies `_extract_signatures()` finds defs
- `test_extracts_docstrings_from_contract` — verifies `_extract_docstrings()` finds docstrings
- `test_renders_protocol_class_with_docstrings` — verifies `_render_protocol()` includes docstrings (FR-2)
- `test_renders_protocol_class_without_docstrings` — verifies `_render_protocol()` uses `...` fallback
- `test_execute_creates_contract_file` — full handler execute with tmp dir
- `test_execute_wires_api_contract_paths` — verifies `context.api_contract_paths` is populated (RN-6)
- `test_execute_no_contract_section_errors` — spec without Contract → ERROR
- `test_execute_no_signatures_errors` — Contract without code blocks → ERROR
- `test_handler_registered_in_registry` — verify `(GENERATE, CONTRACT)` is in registry
- `test_valid_step_combination` — verify `(GENERATE, CONTRACT)` is in `VALID_STEP_COMBINATIONS`

## Commit Boundary

**Single commit**: `feat(3.28a,3.28b): add scenario template enforcement and contract generation handler`

Files modified:
- `src/specweaver/assurance/validation/rules/spec/s07_test_first.py`
- `src/specweaver/core/flow/models.py` (2-line additive)
- `src/specweaver/core/flow/_generation.py` (~60 lines added)
- `src/specweaver/core/flow/handlers.py` (3 lines: import, __all__, registration)
- `tests/unit/assurance/validation/rules/test_s07_test_first.py` (~80 lines added)
- `tests/unit/core/flow/test_contract_handler.py` (~100 lines, new file)

## Verification Plan

### Automated Tests
```bash
pytest tests/unit/assurance/validation/rules/test_s07_test_first.py -v
pytest tests/unit/core/flow/test_contract_handler.py -v
pytest tests/ -v --tb=short  # Full test suite regression
python -m tach check          # Boundary compliance
```

### Manual Verification
- Verify existing specs still pass S07 (backward compatibility)
- Verify `(GENERATE, CONTRACT)` appears in `StepHandlerRegistry().get(...)` output
