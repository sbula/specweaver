# B-FLOW-01 SF-B — Scenario Pipeline: Generate + Convert + Wire

**Status**: COMPLETED_AND_VERIFIED — SF-B pipeline wired and functional; 4012 tests passing. ·
**FRs owned**: FR-3, FR-4, FR-5a, FR-5b, FR-6, FR-7 · **Depends on**: SF-A · **Feature ID**: 3.28
(3.28c–h) · Design: [B-FLOW-01_design.md](B-FLOW-01_design.md) §Sub-features → SF-B

## Goal

The scenario pipeline on top of SF-A (S07 enforcement + contract generation):

1. **FR-3 (Scenario generation)**: LLM-driven atom: spec + API contract → structured YAML scenarios,
   each mapped to a `req_id` from the spec.
2. **FR-4 (Scenario → pytest)**: mechanical (non-LLM) converter to parametrized pytest files with
   `# @trace(FR-X)` tags for C09 compatibility.
3. **FR-5a (Scenario agent isolation)**: `scenario_agent` role in `ROLE_INTENTS`; grants `specs/`
   (read), `contracts/` (read), `scenarios/` (read-write).
4. **FR-5b (Coding agent opacity)**: the coding agent MUST NOT know the scenario pipeline exists —
   zero `scenarios/` grants, zero scenario vocabulary in prompts/feedback.
5. **FR-6 (Scenario validation pipeline)**: `scenario_validation.yaml`:
   `generate_contract → generate_scenarios → convert_to_pytest`.
6. **FR-7 (Dual-pipeline parallel execution)**: both pipelines run in parallel via
   `OrchestrateComponentsHandler` + `GateType.JOIN`; the JOIN gate already exists (3.27).

NFR coverage:
- NFR-1 (YAML not Gherkin): ScenarioSet Pydantic model + YAML serialization
- NFR-2 (non-LLM conversion): ScenarioConverter is pure-logic, zero LLM
- NFR-3 (logging): all handlers `logger.info` every key event
- NFR-4 (no test collision): FolderGrant — the scenario agent writes to `scenarios/` only
- NFR-6 (zero @trace dependency): tags are comments, not imports
- NFR-7 (backward compatibility): all changes additive; enum count assertions updated
- NFR-8 (total opacity): the coding agent's WorkspaceBoundary excludes `scenarios/`; no scenario
  vocabulary in any prompt or feedback; FR-5b is enforced by architecture (no change to the coding
  pipeline)

Out of scope (SF-C): arbiter and error attribution (FR-8); post-JOIN scenario test execution
against coding output (AD-10); filtered feedback loop (FR-9); HITL escalation on spec ambiguity
(FR-10); NFR-5 (bounded arbiter retries).

## Where it plugs in

- **`Planner`** (`workflows/planning/planner.py`) is the pattern `ScenarioGenerator` clones,
  producing `ScenarioSet` instead of `PlanArtifact`: constructor
  `__init__(self, llm, *, config, max_retries, tool_dispatcher)`; main method
  `async def generate_plan(...)` → structured Pydantic model; retry loop JSON parse → Pydantic
  validate → retry with the error message; static `_clean_json()` strips markdown fences.
- **C09** at `c09_traceability.py:132-147` extracts `@trace` tags from AST comment nodes:
```python
re.findall(r"@trace\((?:N)?FR-\d+\)", text)
```
  Generated pytest files MUST use exactly `# @trace(FR-1)` as a comment on the test function line.
- **`flow/context.yaml`** consumes `specweaver/planning`, `specweaver/loom/dispatcher`,
  `specweaver/loom/security`; this SF adds `specweaver/scenarios`. Then `ScenarioGenerator`,
  `ScenarioConverter`, `ScenarioDefinition` from `workflows/scenarios/` ✅; `WorkspaceBoundary`,
  `FolderGrant` from `loom/security` ✅; `ToolDispatcher.create_standard_set()` from
  `loom/dispatcher` ✅.
- **FR-5b needs no code.** The coding pipeline uses `new_feature.yaml` (NO scenario steps); its
  `RunContext` has no `scenarios/` in `workspace_roots` or `api_contract_paths`; its
  `WorkspaceBoundary` has only `src/`, `tests/` roots + `specs/`, `contracts/` api_paths. This holds
  because `OrchestrateComponentsHandler` creates an isolated `RunContext` per sub-pipeline.

### SF-B reuse (line refs as of the design)

| Component | Status | Source | Method |
|-----------|--------|--------|--------|
| `TestExpectation` model | 🟢 Reuse | `workflows/planning/models.py:133-152` | Already has `function_under_test`, `input_summary`, `expected_behavior`, `category: happy\|error\|boundary`. Extend with `req_id` for C09 traceability. `flow/` consumes `planning/` ✅ |
| `PlanSpecHandler` + `Planner` pattern | 🟡 Adapt | `flow/_generation.py:241-418` + `workflows/planning/planner.py` | `ScenarioGenerator` follows same pattern: structured prompt → LLM → parse structured response → validate with Pydantic → save as YAML. ~70% boilerplate reusable |
| `_extract_prompt_feedback()` | 🟢 Reuse | `flow/_generation.py:72-90` | Scenario generation handler uses identical feedback extraction for loop-back |
| C09 `@trace` tag format | 🟢 Reuse | `validation/rules/code/c09_traceability.py` | Use same `# @trace(FR-X)` comment format. C09 automatically picks up scenario-generated tags. Zero changes to C09 |
| `WorkspaceBoundary` | 🟢 Reuse | `loom/security.py:56-127` | Direct use — pass different constructor args per agent. `flow/` consumes `loom/security` ✅ |
| `FolderGrant` + `AccessMode` | 🟢 Reuse | `loom/security.py:20-49` | Direct use — different grants per agent. Same import ✅ |
| `ROLE_INTENTS` dict | 🟢 Reuse | `loom/tools/filesystem/models.py:48-78` | Add 1 entry: `"scenario_agent"`. Same module, additive only |
| `ToolDispatcher.create_standard_set()` | 🟢 Reuse | `loom/dispatcher.py:98-161` | Direct call with different args. `flow/` consumes `loom/dispatcher` ✅ |
| `OrchestrateComponentsHandler` + Wave N | 🟢 Reuse | `flow/_decompose.py:77-291` | Unchanged. Post-JOIN steps use existing deferred-joins mechanism |
| `GateType.JOIN` | 🟢 Reuse | `flow/models.py:60` | Unchanged. Already exists from 3.27 |
| Pipeline YAML | 🟢 Reuse | `workflows/pipelines/new_feature.yaml` | Clone format for `scenario_validation.yaml` |
| `ScenarioGenerator` class | 🔴 New | — | ~100 lines: LLM prompt + response parsing (but follows `Planner` pattern) |
| YAML → pytest mechanical converter | 🔴 New | — | ~150 lines: template-based conversion, parametrized pytest with `@trace` tags |
| `scenario_validation.yaml` | 🔴 New | — | ~20 lines: declarative YAML, data-only |

## Changes

### 1. Enum values · [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/models.py)

`StepAction` (after line 39):
```python
CONVERT = "convert"
```

`StepTarget` (after line 52):
```python
SCENARIO = "scenario"
```

`VALID_STEP_COMBINATIONS` (after line 122):
```python
# Scenario pipeline combos (Feature 3.28 SF-B)
(StepAction.GENERATE, StepTarget.SCENARIO),
(StepAction.CONVERT, StepTarget.SCENARIO),
```

### 2. New `workflows/scenarios/` package

[__init__.py](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/scenarios/__init__.py)
— empty.

[context.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/scenarios/context.yaml)
— own boundary: `consumes` `specweaver/llm`, `specweaver/config`; `forbids` `specweaver/loom/*`,
`specweaver/implementation`, `specweaver/review`; `archetype`: `orchestrator`.

```yaml
name: scenarios
level: module
purpose: >
  LLM-driven scenario generation and mechanical YAML-to-pytest conversion
  for independent verification of spec requirements (Feature 3.28).

archetype: orchestrator

consumes:
  - specweaver/llm
  - specweaver/config

forbids:
  - specweaver/loom/*  # Scenario logic must not bypass the flow engine
  - specweaver/implementation  # Total information opacity from coding pipeline
  - specweaver/review  # Scenario pipeline is independent from review

exposes:
  - ScenarioGenerator
  - ScenarioConverter
  - ScenarioDefinition
  - ScenarioSet

operational:
  async_ready: true
  concurrency_model: none
```

[scenario_models.py](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/scenarios/scenario_models.py)

```python
"""Scenario models — structured scenario definitions for independent verification.

These models define the machine-readable scenario artifacts that bridge
spec validation and scenario-based testing (Feature 3.28).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ScenarioDefinition(BaseModel):
    """A structured test scenario derived from spec + API contract.

    Standalone model — does NOT subclass TestExpectation to avoid
    coupling the scenario pipeline to the planning module.

    Attributes:
        name: Unique scenario identifier.
        description: What this scenario verifies.
        function_under_test: Target function/method name.
        req_id: Requirement ID from the spec (e.g., "FR-1", "NFR-3").
        category: One of "happy", "error", "boundary".
        preconditions: Setup state descriptions.
        input_summary: Human-readable input description.
        inputs: Concrete input values for parametrize.
        expected_behavior: Human-readable expected outcome.
        expected_output: Concrete expected value for assertion.
    """

    __test__ = False  # Prevent pytest collection

    name: str
    description: str
    function_under_test: str
    req_id: str
    category: str = "happy"
    preconditions: list[str] = Field(default_factory=list)
    input_summary: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_behavior: str = ""
    expected_output: Any = None


class ScenarioSet(BaseModel):
    """Collection of scenarios generated from a single spec.

    Attributes:
        spec_path: Path to the source spec.
        contract_path: Path to the API contract used.
        scenarios: List of generated scenario definitions.
        reasoning: LLM chain-of-thought (stored, not exposed).
    """

    __test__ = False

    spec_path: str
    contract_path: str
    scenarios: list[ScenarioDefinition]
    reasoning: str = ""
```

### 3. ScenarioGenerator — LLM-driven (FR-3) · [scenario_generator.py](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/scenarios/scenario_generator.py)

Follows the `Planner` pattern. Differs in:
- Input: spec `## Contract` + `## Scenarios` + `## Functional Requirements` + `## Non-Functional
  Requirements` sections + contract file content + req_id list
- Output: `ScenarioSet` (Pydantic model)
- Prompt: "Generate ≥1 scenario per public method covering happy, error, and boundary paths. Each
  scenario MUST reference a `req_id` from the spec. Map each FR/NFR to at least one scenario."

```python
"""ScenarioGenerator — LLM-driven scenario generation from spec + contract.

Reads a spec and its API contract, generates structured YAML scenarios via LLM,
and validates output with Pydantic + reflection retry.

Follows the Planner pattern (prompt → LLM → parse → validate → retry).
"""
class ScenarioGenerator:
    def __init__(self, llm, *, config=None, max_retries=3, tool_dispatcher=None): ...

    async def generate_scenarios(
        self,
        spec_content: str,
        contract_content: str,
        req_ids: list[str],
        *,
        constitution: str | None = None,
        project_metadata: Any = None,
    ) -> ScenarioSet: ...

    @staticmethod
    def _extract_req_ids(spec_content: str) -> list[str]:
        """Extract FR-X and NFR-X tags from spec text.

        Uses same regex as C09: r"\\b(?:N)?FR-\\d+\\b"
        """
        ...

    @staticmethod
    def _extract_section(spec_text: str, heading: str) -> str | None:
        """Extract a ## section from spec text by heading name.

        Returns content between the heading and the next ## heading, or None.
        """
        ...

    @staticmethod
    def _clean_json(text: str) -> str:
        """Remove markdown code fences if present."""
        ...
```

> [!CAUTION]
> `_extract_req_ids` uses the same regex as C09: `r"\b(?:N)?FR-\d+\b"`, so the generator's req_id
> list is identical to what C09 validates against.

### 4. ScenarioConverter — mechanical YAML → pytest (FR-4) · [scenario_converter.py](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/scenarios/scenario_converter.py)

Pure-logic (no LLM, no I/O of its own). Takes a `ScenarioSet`, returns a pytest file string.

```python
"""ScenarioConverter — mechanical YAML scenarios to parametrized pytest.

Pure-logic transformer. No LLM involvement (NFR-2).
Produces executable pytest files with # @trace(FR-X) tags for C09 compatibility.
"""
class ScenarioConverter:
    @staticmethod
    def convert(scenario_set: ScenarioSet) -> str:
        """Convert a ScenarioSet to a parametrized pytest file string."""
        ...

    @staticmethod
    def _render_test_function(scenario: ScenarioDefinition) -> str:
        """Render a single test function from a scenario definition."""
        ...

    @staticmethod
    def _render_parametrize_data(scenarios: list[ScenarioDefinition]) -> str:
        """Group scenarios by function_under_test and render @pytest.mark.parametrize."""
        ...
```

**Output format** (example):
```python
"""Auto-generated scenario tests from spec scenarios."""
import pytest


# @trace(FR-1)
@pytest.mark.parametrize("input_data,expected", [
    ({"username": "valid_user", "password": "valid_pass"}, {"token": "..."}),
    ({"username": "", "password": ""}, None),
])
def test_login_scenarios(input_data, expected):  # @trace(FR-1)
    """Scenario: happy_path_login — valid credentials returns token."""
    # Act + Assert placeholder — scenario agent fills implementation
    ...
```

> [!WARNING]
> The `# @trace(FR-X)` tag MUST be an inline comment on the `def test_...` line or a standalone
> comment directly above it. C09's tree-sitter AST parser extracts trace tags from `comment` nodes,
> so the tag MUST be a Python comment (`#`), not a docstring.

### 5. Flow handlers (FR-3, FR-4) · [_generation.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_generation.py)

After `GenerateContractHandler`:

**`GenerateScenarioHandler`** — LLM-driven scenario generation:
```python
class GenerateScenarioHandler:
    """Handler for generate+scenario — LLM scenario generation from spec + contract."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if context.llm is None:
            return _error_result("LLM adapter required for scenario generation", started)
        try:
            from specweaver.workflows.scenarios.scenario_generator import ScenarioGenerator

            adapter, config = _resolve_generation_routing(context, temperature=0.3)
            generator = ScenarioGenerator(llm=adapter, config=config)

            spec_content = context.spec_path.read_text(encoding="utf-8")

            # Read contract content from api_contract_paths
            contract_content = ""
            if context.api_contract_paths:
                from pathlib import Path
                for cp in context.api_contract_paths:
                    p = Path(cp)
                    if p.exists():
                        contract_content += p.read_text(encoding="utf-8")

            req_ids = ScenarioGenerator._extract_req_ids(spec_content)

            scenario_set = await generator.generate_scenarios(
                spec_content=spec_content,
                contract_content=contract_content,
                req_ids=req_ids,
                constitution=context.constitution,
                project_metadata=context.project_metadata,
            )

            # Save scenarios as YAML
            scenarios_dir = context.project_path / "scenarios" / "definitions"
            scenarios_dir.mkdir(parents=True, exist_ok=True)
            stem = context.spec_path.stem.replace("_spec", "")
            output_path = scenarios_dir / f"{stem}_scenarios.yaml"

            import io
            from ruamel.yaml import YAML
            yaml = YAML()
            yaml.default_flow_style = False
            buf = io.StringIO()
            yaml.dump(scenario_set.model_dump(), buf)
            output_path.write_text(buf.getvalue(), encoding="utf-8")

            logger.info(
                "GenerateScenarioHandler: %d scenarios saved to '%s'",
                len(scenario_set.scenarios), output_path,
            )

            return StepResult(
                status=StepStatus.PASSED,
                output={
                    "generated_path": str(output_path),
                    "scenario_count": len(scenario_set.scenarios),
                },
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            logger.exception("GenerateScenarioHandler: unhandled exception")
            return _error_result(str(exc), started)
```

**`ConvertScenarioHandler`** — mechanical YAML → pytest conversion:
```python
class ConvertScenarioHandler:
    """Handler for convert+scenario — mechanical YAML to pytest conversion."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        try:
            from pathlib import Path

            from ruamel.yaml import YAML

            from specweaver.workflows.scenarios.scenario_converter import ScenarioConverter
            from specweaver.workflows.scenarios.scenario_models import ScenarioSet

            # Find scenario YAML from previous step
            scenarios_dir = context.project_path / "scenarios" / "definitions"
            stem = context.spec_path.stem.replace("_spec", "")
            scenario_yaml_path = scenarios_dir / f"{stem}_scenarios.yaml"

            if not scenario_yaml_path.exists():
                return _error_result(
                    f"Scenario YAML not found: {scenario_yaml_path}", started
                )

            yaml = YAML(typ="safe")
            data = yaml.load(scenario_yaml_path.read_text(encoding="utf-8"))
            scenario_set = ScenarioSet.model_validate(data)

            pytest_content = ScenarioConverter.convert(scenario_set)

            output_dir = context.project_path / "scenarios" / "generated"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"test_{stem}_scenarios.py"
            output_path.write_text(pytest_content, encoding="utf-8")

            logger.info(
                "ConvertScenarioHandler: pytest file written to '%s'",
                output_path,
            )

            return StepResult(
                status=StepStatus.PASSED,
                output={"generated_path": str(output_path)},
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            logger.exception("ConvertScenarioHandler: unhandled exception")
            return _error_result(str(exc), started)
```

[handlers.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/handlers.py) —
update the `_generation` import block:
```python
from specweaver.core.flow._generation import (
    ConvertScenarioHandler,   # NEW
    GenerateCodeHandler,
    GenerateContractHandler,
    GenerateScenarioHandler,  # NEW
    GenerateTestsHandler,
    PlanSpecHandler,
)
```

`__all__`:
```python
"ConvertScenarioHandler",
"GenerateScenarioHandler",
```

`StepHandlerRegistry.__init__()`:
```python
(StepAction.GENERATE, StepTarget.SCENARIO): GenerateScenarioHandler(),
(StepAction.CONVERT, StepTarget.SCENARIO): ConvertScenarioHandler(),
```

### 6. Scenario agent role (FR-5a) · [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/tools/filesystem/models.py)

`scenario_agent` in `ROLE_INTENTS` (after line 77). Additive — no existing role changes:
```python
"scenario_agent": frozenset({
    "read_file",
    "write_file",
    "create_file",
    "list_directory",
    "grep",
    "find_files",
}),
```

> [!NOTE]
> `ROLE_INTENTS` controls *which tool intents* are available; `FolderGrant` controls *which paths*
> they reach. Writes are limited to `scenarios/` by the `FolderGrant` configuration the handler
> builds into `WorkspaceBoundary`, not by `ROLE_INTENTS` alone.

### 7. Boundary configuration

[context.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/context.yaml) —
add `specweaver/scenarios` to `consumes`:
```yaml
consumes:
  - specweaver/config
  - specweaver/llm
  - specweaver/review
  - specweaver/implementation
  - specweaver/planning
  - specweaver/scenarios  # NEW — Feature 3.28 SF-B scenario pipeline
  - specweaver/validation
  - specweaver/loom/atoms/git
  - specweaver/loom/atoms/qa_runner
  - specweaver/loom/dispatcher
  - specweaver/loom/security
```

[tach.toml](file:///c:/development/pitbula/specweaver/tach.toml) — register the module as
`src.specweaver.workflows.scenarios` (after line 20):
```toml
{ path = "src.specweaver.workflows.scenarios", depends_on = [] },
```

### 8. Pipeline YAML (FR-6) · [scenario_validation.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/pipelines/scenario_validation.yaml)

```yaml
# Scenario Validation Pipeline — Feature 3.28
# generate_contract → generate_scenarios → convert_to_pytest
# Runs as a sub-pipeline in parallel with the coding pipeline.

name: scenario_validation
description: >
  Scenario-based independent verification pipeline. Generates structured
  YAML scenarios from spec + API contract, then mechanically converts
  them to parametrized pytest files with @trace tags.
version: "1.0"

steps:
  - name: generate_contract
    action: generate
    target: contract
    description: "Extract API Protocol from spec Contract section"

  - name: generate_scenarios
    action: generate
    target: scenario
    description: "LLM-driven scenario generation from spec + contract"
    gate:
      type: auto
      condition: completed
      on_fail: abort

  - name: convert_to_pytest
    action: convert
    target: scenario
    description: "Mechanical YAML to parametrized pytest conversion"
    gate:
      type: auto
      condition: completed
      on_fail: abort
```

### Files

| File | Change |
|---|---|
| `src/specweaver/workflows/scenarios/__init__.py` | new, empty |
| `src/specweaver/workflows/scenarios/context.yaml` | new, ~25 lines |
| `src/specweaver/workflows/scenarios/scenario_models.py` | new, ~60 lines |
| `src/specweaver/workflows/scenarios/scenario_generator.py` | new, ~130 lines |
| `src/specweaver/workflows/scenarios/scenario_converter.py` | new, ~120 lines |
| `src/specweaver/workflows/pipelines/scenario_validation.yaml` | new, ~25 lines |
| `tests/unit/workflows/scenarios/__init__.py` | new, empty |
| `tests/unit/workflows/scenarios/test_scenario_models.py` | new, ~40 lines |
| `tests/unit/workflows/scenarios/test_scenario_generator.py` | new, ~100 lines |
| `tests/unit/workflows/scenarios/test_scenario_converter.py` | new, ~80 lines |
| `tests/unit/core/flow/test_scenario_handlers.py` | new, ~80 lines |
| `tests/unit/core/flow/test_scenario_pipeline_yaml.py` | new, ~40 lines |
| `src/specweaver/core/flow/models.py` | ~4 lines |
| `src/specweaver/core/flow/_generation.py` | ~100 lines added |
| `src/specweaver/core/flow/handlers.py` | ~6 lines |
| `src/specweaver/core/flow/context.yaml` | ~1 line added |
| `src/specweaver/core/loom/tools/filesystem/models.py` | ~7 lines |
| `tach.toml` | ~1 line added |
| `tests/unit/core/flow/test_models.py` | ~4 lines |

Commit: `feat(3.28c-f): add scenario generator, converter, agent role, and pipeline YAML`

## Tests

[test_scenario_models.py](file:///c:/development/pitbula/specweaver/tests/unit/workflows/scenarios/test_scenario_models.py)

Test class `TestScenarioDefinition`:
- `test_required_fields` — name, description, function_under_test, req_id are required
- `test_defaults` — category defaults to "happy", preconditions/inputs default empty
- `test_req_id_format` — accepts FR-1, NFR-3 formats
- `test_serialization_roundtrip` — model_dump → model_validate roundtrip

Test class `TestScenarioSet`:
- `test_required_fields` — spec_path, contract_path, scenarios are required
- `test_empty_scenarios_valid` — empty list is valid

[test_scenario_generator.py](file:///c:/development/pitbula/specweaver/tests/unit/workflows/scenarios/test_scenario_generator.py)

Test class `TestScenarioGenerator`:
- `test_extract_req_ids` — extracts FR-1, FR-2, NFR-1 from spec text
- `test_extract_req_ids_empty` — no req_ids returns empty list
- `test_extract_section_contract` — extracts `## Contract` section
- `test_extract_section_frs` — extracts `## Functional Requirements` section
- `test_extract_section_nfrs` — extracts `## Non-Functional Requirements` section
- `test_extract_section_missing` — returns None if section not found
- `test_clean_json` — strips markdown code fences
- `test_generate_scenarios_happy_path` — mock LLM returns valid JSON → ScenarioSet
- `test_generate_scenarios_retry_on_invalid_json` — invalid JSON triggers retry
- `test_generate_scenarios_exhausts_retries` — raises ValueError after max retries

[test_scenario_converter.py](file:///c:/development/pitbula/specweaver/tests/unit/workflows/scenarios/test_scenario_converter.py)

Test class `TestScenarioConverter`:
- `test_convert_single_scenario` — produces valid pytest file string
- `test_convert_multiple_scenarios` — groups by function_under_test
- `test_trace_tag_format` — output contains `# @trace(FR-X)` in correct format (C09 regex match)
- `test_parametrize_decorator` — output contains `@pytest.mark.parametrize`
- `test_empty_scenarios` — produces valid but empty test file
- `test_no_contract_import` — output does NOT import from `contracts/` (HITL decision)

[test_scenario_handlers.py](file:///c:/development/pitbula/specweaver/tests/unit/core/flow/test_scenario_handlers.py)

Test class `TestGenerateScenarioHandler`:
- `test_execute_creates_scenario_yaml` — handler writes YAML to scenarios/definitions/
- `test_execute_no_llm_errors` — returns error when llm is None
- `test_execute_reads_contract_from_context` — picks up api_contract_paths
- `test_handler_registered` — `(GENERATE, SCENARIO)` in registry

Test class `TestConvertScenarioHandler`:
- `test_execute_converts_yaml_to_pytest` — handler reads YAML and writes pytest
- `test_execute_scenario_yaml_not_found` — returns error if YAML missing
- `test_handler_registered` — `(CONVERT, SCENARIO)` in registry

[test_models.py](file:///c:/development/pitbula/specweaver/tests/unit/core/flow/test_models.py) —
enum count assertions:
- `StepTarget` count: 8 → 9 (add SCENARIO)
- `StepAction` count: 10 → 11 (add CONVERT)
- `VALID_STEP_COMBINATIONS` count: current → +2

[test_scenario_pipeline_yaml.py](file:///c:/development/pitbula/specweaver/tests/unit/core/flow/test_scenario_pipeline_yaml.py)

Test class `TestScenarioValidationPipeline`:
- `test_pipeline_loads` — YAML parses to `PipelineDefinition`
- `test_pipeline_validates` — `validate_flow()` returns no errors
- `test_step_count` — exactly 3 steps
- `test_step_actions` — correct action+target pairs

Existing `ROLE_INTENTS` tests: `scenario_agent` is in the dict; its intent set matches the design.

```bash
pytest tests/unit/workflows/scenarios/ -v
pytest tests/unit/core/flow/test_scenario_handlers.py -v
pytest tests/unit/core/flow/test_scenario_pipeline_yaml.py -v
pytest tests/unit/core/flow/test_models.py -v
pytest tests/ -v --tb=short  # Full test suite regression
python -m tach check          # Boundary compliance
ruff check src/ tests/        # Lint check
```

Manual: `scenario_validation.yaml` round-trips through `PipelineDefinition`; `(GENERATE, SCENARIO)`
and `(CONVERT, SCENARIO)` in the registry; `scenario_agent` in `ROLE_INTENTS`; `tach check` passes
with the new module.

## Decisions (audit, HITL-approved)

| # | Question | Chosen | Why |
|---|---|---|---|
| RN-1 | Action for YAML→pytest? | new `StepAction.CONVERT` | AD-7 defines `GENERATE + SCENARIO` for generation; conversion is distinct (mechanical). `(GENERATE, SCENARIO)` = LLM generation, `(CONVERT, SCENARIO)` = mechanical conversion |
| RN-3 | Scenario model? | standalone `ScenarioDefinition` in `workflows/scenarios/scenario_models.py`; does NOT subclass `TestExpectation` from `planning/models.py` | no coupling to the planning module. The 5 shared fields (`name`, `description`, `function_under_test`, `input_summary`, `expected_behavior`) are duplicated on purpose |
| RN-6 | Package location? | new `workflows/scenarios/` with its own `context.yaml`, registered in `tach.toml`, consumed by `flow/context.yaml` | scenario generation is NOT planning — a separate domain |
| RN-9 | FR-7 wiring? | `scenario_validation.yaml` ships as a standalone pipeline (generate_contract → generate_scenarios → convert_to_pytest); the parent pipeline that spawns both sub-pipelines with the JOIN gate goes to SF-C | SF-C owns the post-JOIN flow |
| RN-10 | What goes into the generator prompt? | 1. `## Contract` (API surface) 2. `## Scenarios` (hints) 3. `## Functional Requirements` 4. `## Non-Functional Requirements` 5. `req_id` list 6. contract file content (Protocol class from SF-A); `_extract_section()` pulls all four sections | FRs/NFRs are NOT in the contract file, which holds only typed signatures. The LLM needs both behaviour (FRs/NFRs) and API surface |
| RN-11 | Do scenario tests import `contracts/`? | No | the contract is a *generation-time* artifact; tests use concrete inputs/outputs; `# @trace` gives the traceability link; tests stay zero-dependency |

## As built

- `GenerateScenarioHandler` and `ConvertScenarioHandler` live in `_scenario.py` (exported via
  `handlers.py`), not `_generation.py`, which would have passed the 600 line threshold.
- `test_integration_physical_io_join_locks` moved from `test_planning_integration.py` to
  `test_orchestration_integration.py` to stay under the 900 line warning threshold.
- `runner.py`'s `fan_out()` moved to `runner_utils.py` to keep the runner under 600 lines.

**Since moved** (noted 2026-09-25): handlers are in `core/flow/handlers/scenario.py`; the Python
converter is `sandbox/language/core/python/scenario_converter.py` (SF-B2). Line refs above are as
of the plan's date.
