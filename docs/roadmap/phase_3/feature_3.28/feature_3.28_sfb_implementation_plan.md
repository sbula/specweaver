# Implementation Plan: Scenario Testing — Independent Verification [SF-B: Scenario Pipeline — Generate + Convert + Wire]

- **Feature ID**: 3.28
- **Sub-Feature**: SF-B — Scenario Pipeline: Generate + Convert + Wire
- **Design Document**: docs/roadmap/phase_3/feature_3.28/feature_3.28_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-B
- **Implementation Plan**: docs/roadmap/phase_3/feature_3.28/feature_3.28_sfb_implementation_plan.md
- **Status**: COMPLETED_AND_VERIFIED (Phase 1-5 executed successfully. SF-B pipeline wired and functional. 4012 tests passing.)

## Deviations from Original Plan
- During Phase 5 code complexity checks, `_generation.py` exceeded the 600 line threshold limit due to the addition of scenario handlers. To maintain clean architecture, `GenerateScenarioHandler` and `ConvertScenarioHandler` were refactored into a dedicated `_scenario.py` file, which was then exported via `handlers.py`.
- We extracted `test_integration_physical_io_join_locks` from `test_planning_integration.py` to `test_orchestration_integration.py` to keep integration testing limits below the mandatory 900 line warning threshold.
- `runner.py`'s `fan_out()` logic was relocated to `runner_utils.py` to drop the runner line count below the 600 line limit safely.

## Scope

SF-B builds the complete scenario pipeline atop SF-A's foundation (S07 enforcement + contract generation):

1. **FR-3 (Scenario generation)**: LLM-driven atom that takes spec + API contract → structured YAML scenarios. Each scenario maps to a `req_id` from the spec.
2. **FR-4 (Scenario → pytest)**: Mechanical (non-LLM) converter that transforms YAML scenarios into parametrized pytest files with `# @trace(FR-X)` tags for C09 compatibility.
3. **FR-5a (Scenario agent isolation)**: New `scenario_agent` role in `ROLE_INTENTS` with constrained filesystem grants: `specs/` (read), `contracts/` (read), `scenarios/` (read-write).
4. **FR-5b (Coding agent opacity)**: Total information opacity — the coding agent MUST NOT know the scenario pipeline exists. Zero `scenarios/` grants, zero scenario vocabulary in prompts/feedback.
5. **FR-6 (Scenario validation pipeline)**: New `scenario_validation.yaml` pipeline: `generate_contract → generate_scenarios → convert_to_pytest`.
6. **FR-7 (Dual-pipeline parallel execution)**: Wire both pipelines for parallel execution via `OrchestrateComponentsHandler` + `GateType.JOIN`. **Note**: The JOIN gate mechanism is already 100% implemented from Feature 3.27.

> [!IMPORTANT]
> **NFR Coverage:**
> - NFR-1 (YAML not Gherkin): Enforced by ScenarioSet Pydantic model + YAML serialization
> - NFR-2 (non-LLM conversion): ScenarioConverter is pure-logic, zero LLM
> - NFR-3 (logging): All handlers log via `logger.info` for every key event
> - NFR-4 (no test collision): FolderGrant enforcement — scenario agent writes to `scenarios/` only
> - NFR-6 (zero @trace dependency): Tags are comments, not imports
> - NFR-7 (backward compatibility): All changes are additive; enum count assertions updated
> - NFR-8 (total opacity): Coding agent's WorkspaceBoundary excludes `scenarios/`; no scenario vocabulary in any prompt or feedback; FR-5b enforcement is architectural (no code change needed in existing coding pipeline)

### What's In Scope
- `ScenarioGenerator` class (LLM-based, in `workflows/scenarios/`)
- `ScenarioDefinition` Pydantic model (standalone, in `workflows/scenarios/`)
- `GenerateScenarioHandler` in `flow/_generation.py`
- `ScenarioConverter` pure-logic class (YAML → pytest, in `workflows/scenarios/`)
- `ConvertScenarioHandler` in `flow/_generation.py`
- New `StepTarget.SCENARIO` enum value + `StepAction.CONVERT` enum value
- New `VALID_STEP_COMBINATIONS` entries
- Handler registrations in `StepHandlerRegistry`
- `scenario_agent` role in `ROLE_INTENTS`
- `scenario_validation.yaml` pipeline definition
- New `workflows/scenarios/` package with `context.yaml`
- `tach.toml` registration for new `workflows.scenarios` module
- `flow/context.yaml` updated to consume `specweaver/scenarios`
- Tests for all of the above

### What's Out of Scope (deferred to SF-C)
- Arbiter agent and error attribution (FR-8)
- Post-JOIN scenario test execution against coding output (AD-10)
- Filtered feedback loop (FR-9)
- HITL escalation on spec ambiguity (FR-10)
- NFR-5 (bounded arbiter retries)

## Research Notes

### RN-1: `StepAction.CONVERT` — new enum, HITL-approved
The design doc AD-7 defines `GENERATE + SCENARIO` for scenario generation. The YAML→pytest conversion is a distinct action (mechanical, not LLM). HITL approved adding `StepAction.CONVERT` for clear semantics: `(GENERATE, SCENARIO)` = LLM generation, `(CONVERT, SCENARIO)` = mechanical conversion.

### RN-2: `ScenarioGenerator` follows `Planner` pattern exactly
The `Planner` class at `workflows/planning/planner.py` is the canonical pattern:
- Constructor: `__init__(self, llm, *, config, max_retries, tool_dispatcher)`
- Main method: `async def generate_plan(...)` → structured Pydantic model
- Retry loop: JSON parse → Pydantic validate → retry with error message on failure
- Static helper: `_clean_json()` for markdown fence stripping

`ScenarioGenerator` will clone this exact structure, producing `ScenarioSet` instead of `PlanArtifact`.

### RN-3: `ScenarioDefinition` — standalone model, HITL-approved
`ScenarioDefinition` is a standalone Pydantic model in `workflows/scenarios/scenario_models.py`. It does NOT subclass `TestExpectation` from `planning/models.py`. This avoids coupling the scenario pipeline to the planning module. The 5 shared fields (`name`, `description`, `function_under_test`, `input_summary`, `expected_behavior`) are duplicated intentionally.

### RN-4: `ScenarioConverter` output format — C09 compatible
C09 at `c09_traceability.py:132-147` extracts `@trace` tags from AST comment nodes using:
```python
re.findall(r"@trace\((?:N)?FR-\d+\)", text)
```
Generated pytest files MUST use the exact format: `# @trace(FR-1)` as a comment on the test function line.

### RN-5: `ROLE_INTENTS` — `scenario_agent` entry
Design doc §New ROLE_INTENTS Entry defines:
```python
"scenario_agent": frozenset({
    "read_file", "write_file", "create_file",
    "list_directory", "grep", "find_files",
})
```
This is additive — no existing roles are modified.

### RN-6: Package location — `workflows/scenarios/`, HITL-approved
HITL decided that scenario generation is NOT planning — it's a separate domain. New `workflows/scenarios/` package created with:
- Own `context.yaml` declaring `consumes` and `forbids`
- `tach.toml` registration as `src.specweaver.workflows.scenarios`
- `flow/context.yaml` updated to consume `specweaver/scenarios`

### RN-7: `flow/context.yaml` import legality
`flow/` currently consumes: `specweaver/planning`, `specweaver/loom/dispatcher`, `specweaver/loom/security`.
After this change, `flow/` will also consume `specweaver/scenarios` (new entry).
- `ScenarioGenerator`, `ScenarioConverter`, `ScenarioDefinition` from `workflows/scenarios/` ✅
- `WorkspaceBoundary`, `FolderGrant` from `loom/security` ✅
- `ToolDispatcher.create_standard_set()` from `loom/dispatcher` ✅

### RN-8: FR-5b coding agent opacity — NO code changes needed
FR-5b says the coding agent must have zero awareness of the scenario pipeline. This is achieved architecturally:
- The coding pipeline uses `new_feature.yaml` which has NO scenario steps
- `RunContext` for the coding agent has no `scenarios/` in `workspace_roots` or `api_contract_paths`
- The coding agent's `WorkspaceBoundary` only has `src/`, `tests/` roots + `specs/`, `contracts/` api_paths
- No code change required — this is enforced by how `OrchestrateComponentsHandler` creates isolated `RunContext` per sub-pipeline

### RN-9: FR-7 dual-pipeline — standalone scenario pipeline, HITL-approved
SF-B delivers `scenario_validation.yaml` as a standalone pipeline that runs independently (generate_contract → generate_scenarios → convert_to_pytest). The dual-pipeline wiring (parent pipeline that spawns both coding + scenario sub-pipelines with JOIN gate) is deferred to SF-C, which owns the post-JOIN flow.

### RN-10: LLM prompt injection — HITL-approved: include FRs/NFRs
The ScenarioGenerator prompt MUST inject:
1. `## Contract` section from spec (API surface)
2. `## Scenarios` section from spec (scenario hints)
3. `## Functional Requirements` section from spec (FR definitions)
4. `## Non-Functional Requirements` section from spec (NFR definitions)
5. `req_id` list extracted from spec (for explicit mapping)
6. Contract file content (Protocol class from SF-A)

> [!IMPORTANT]
> FRs and NFRs are NOT part of the contract file. They must be extracted from the spec separately. The contract file only contains typed method signatures (Protocol class). The LLM needs both the behavioral requirements (FRs/NFRs) AND the API surface (contract) to generate meaningful scenarios.

### RN-11: Scenario tests do NOT import contracts at runtime
HITL-approved: generated pytest files do NOT import from `contracts/`. The contract is a *generation-time* artifact used by the ScenarioGenerator to understand the API surface. Generated tests use concrete inputs/outputs. The `# @trace` tag provides the traceability link. This keeps scenario tests zero-dependency.

### RN-12: `context.yaml` for `workflows/scenarios/`
A new `context.yaml` is required for the `workflows/scenarios/` package because it's a new module with its own boundary:
- `consumes`: `specweaver/llm`, `specweaver/config`
- `forbids`: `specweaver/loom/*`, `specweaver/implementation`, `specweaver/review`
- `archetype`: `orchestrator`

## Proposed Changes

### Component 1: Data Model — New Enum Values

#### [MODIFY] [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/models.py)

Add new `StepAction` enum value (after line 39):
```python
CONVERT = "convert"
```

Add new `StepTarget` enum value (after line 52):
```python
SCENARIO = "scenario"
```

Add to `VALID_STEP_COMBINATIONS` (after line 122):
```python
# Scenario pipeline combos (Feature 3.28 SF-B)
(StepAction.GENERATE, StepTarget.SCENARIO),
(StepAction.CONVERT, StepTarget.SCENARIO),
```

---

### Component 2: New `workflows/scenarios/` Package

#### [NEW] [__init__.py](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/scenarios/__init__.py)

Empty `__init__.py` for package initialization.

#### [NEW] [context.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/scenarios/context.yaml)

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

#### [NEW] [scenario_models.py](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/scenarios/scenario_models.py)

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

---

### Component 3: ScenarioGenerator — LLM-driven (FR-3)

#### [NEW] [scenario_generator.py](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/scenarios/scenario_generator.py)

Follows the `Planner` pattern. Key differences from Planner:
- Input: spec `## Contract` + `## Scenarios` + `## Functional Requirements` + `## Non-Functional Requirements` sections + contract file content + req_id list
- Output: `ScenarioSet` (Pydantic model)
- Prompt: "Generate ≥1 scenario per public method covering happy, error, and boundary paths. Each scenario MUST reference a `req_id` from the spec. Map each FR/NFR to at least one scenario."

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

> [!IMPORTANT]
> **Prompt injection includes FRs and NFRs** (HITL decision):
> The `_extract_section()` helper extracts `## Functional Requirements` and `## Non-Functional Requirements`
> in addition to `## Contract` and `## Scenarios`. All four sections are injected into the LLM prompt.
> FRs/NFRs are NOT part of the contract file — they must be extracted from the spec separately.

> [!CAUTION]
> The `_extract_req_ids` method uses the same regex as C09: `r"\b(?:N)?FR-\d+\b"`. This ensures the scenario generator's req_id list is identical to what C09 will validate against.

---

### Component 4: ScenarioConverter — Mechanical YAML → pytest (FR-4)

#### [NEW] [scenario_converter.py](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/scenarios/scenario_converter.py)

Pure-logic module (no LLM, no I/O operations on its own). Takes a `ScenarioSet` and produces a pytest file string.

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
> The `# @trace(FR-X)` tag MUST appear as an inline comment on the `def test_...` line or as a standalone comment directly above it. C09's tree-sitter AST parser extracts trace tags from `comment` nodes. The tag MUST be a Python comment (`#`), not a docstring.

> [!NOTE]
> Generated pytest files do NOT import from `contracts/` at runtime (HITL decision). The contract
> is a generation-time artifact. Scenario tests use concrete inputs/outputs only.

---

### Component 5: Flow Handlers (FR-3, FR-4)

#### [MODIFY] [_generation.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_generation.py)

Add two new handler classes after `GenerateContractHandler`:

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

**`ConvertScenarioHandler`** — Mechanical YAML → pytest conversion:
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

#### [MODIFY] [handlers.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/handlers.py)

Add imports (update existing `_generation` import block):
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

Add to `__all__`:
```python
"ConvertScenarioHandler",
"GenerateScenarioHandler",
```

Add to `StepHandlerRegistry.__init__()`:
```python
(StepAction.GENERATE, StepTarget.SCENARIO): GenerateScenarioHandler(),
(StepAction.CONVERT, StepTarget.SCENARIO): ConvertScenarioHandler(),
```

---

### Component 6: Security — Scenario Agent Role (FR-5a)

#### [MODIFY] [models.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/tools/filesystem/models.py)

Add `scenario_agent` role to `ROLE_INTENTS` dict (after line 77):
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
> The `scenario_agent` role grants write access to `scenarios/` only. The actual path restriction
> is enforced by the `FolderGrant` configuration in the handler when constructing `WorkspaceBoundary`,
> not by `ROLE_INTENTS` alone. `ROLE_INTENTS` controls *which tool intents* are available,
> while `FolderGrant` controls *which paths* those intents can access.

---

### Component 7: Boundary Configuration

#### [MODIFY] [context.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/context.yaml)

Add `specweaver/scenarios` to the `consumes` list:
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

#### [MODIFY] [tach.toml](file:///c:/development/pitbula/specweaver/tach.toml)

Add new module registration (after line 20):
```toml
{ path = "src.specweaver.workflows.scenarios", depends_on = [] },
```

---

### Component 8: Pipeline YAML (FR-6)

#### [NEW] [scenario_validation.yaml](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/pipelines/scenario_validation.yaml)

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

---

### Component 9: Tests

#### [NEW] [test_scenario_models.py](file:///c:/development/pitbula/specweaver/tests/unit/workflows/scenarios/test_scenario_models.py)

Test class `TestScenarioDefinition`:
- `test_required_fields` — name, description, function_under_test, req_id are required
- `test_defaults` — category defaults to "happy", preconditions/inputs default empty
- `test_req_id_format` — accepts FR-1, NFR-3 formats
- `test_serialization_roundtrip` — model_dump → model_validate roundtrip

Test class `TestScenarioSet`:
- `test_required_fields` — spec_path, contract_path, scenarios are required
- `test_empty_scenarios_valid` — empty list is valid

#### [NEW] [test_scenario_generator.py](file:///c:/development/pitbula/specweaver/tests/unit/workflows/scenarios/test_scenario_generator.py)

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

#### [NEW] [test_scenario_converter.py](file:///c:/development/pitbula/specweaver/tests/unit/workflows/scenarios/test_scenario_converter.py)

Test class `TestScenarioConverter`:
- `test_convert_single_scenario` — produces valid pytest file string
- `test_convert_multiple_scenarios` — groups by function_under_test
- `test_trace_tag_format` — output contains `# @trace(FR-X)` in correct format (C09 regex match)
- `test_parametrize_decorator` — output contains `@pytest.mark.parametrize`
- `test_empty_scenarios` — produces valid but empty test file
- `test_no_contract_import` — output does NOT import from `contracts/` (HITL decision)

#### [NEW] [test_scenario_handlers.py](file:///c:/development/pitbula/specweaver/tests/unit/core/flow/test_scenario_handlers.py)

Test class `TestGenerateScenarioHandler`:
- `test_execute_creates_scenario_yaml` — handler writes YAML to scenarios/definitions/
- `test_execute_no_llm_errors` — returns error when llm is None
- `test_execute_reads_contract_from_context` — picks up api_contract_paths
- `test_handler_registered` — `(GENERATE, SCENARIO)` in registry

Test class `TestConvertScenarioHandler`:
- `test_execute_converts_yaml_to_pytest` — handler reads YAML and writes pytest
- `test_execute_scenario_yaml_not_found` — returns error if YAML missing
- `test_handler_registered` — `(CONVERT, SCENARIO)` in registry

#### [MODIFY] [test_models.py](file:///c:/development/pitbula/specweaver/tests/unit/core/flow/test_models.py)

Update enum count assertions:
- `StepTarget` count: 8 → 9 (add SCENARIO)
- `StepAction` count: 10 → 11 (add CONVERT)
- `VALID_STEP_COMBINATIONS` count: current → +2

#### [NEW] [test_scenario_pipeline_yaml.py](file:///c:/development/pitbula/specweaver/tests/unit/core/flow/test_scenario_pipeline_yaml.py)

Test class `TestScenarioValidationPipeline`:
- `test_pipeline_loads` — YAML parses to `PipelineDefinition`
- `test_pipeline_validates` — `validate_flow()` returns no errors
- `test_step_count` — exactly 3 steps
- `test_step_actions` — correct action+target pairs

#### [MODIFY] Existing test files for ROLE_INTENTS

- Verify `scenario_agent` is in `ROLE_INTENTS` dict
- Verify intent set matches design doc

---

## Commit Boundary

**Single commit**: `feat(3.28c-f): add scenario generator, converter, agent role, and pipeline YAML`

Files created:
- `src/specweaver/workflows/scenarios/__init__.py` (empty)
- `src/specweaver/workflows/scenarios/context.yaml` (~25 lines)
- `src/specweaver/workflows/scenarios/scenario_models.py` (~60 lines)
- `src/specweaver/workflows/scenarios/scenario_generator.py` (~130 lines)
- `src/specweaver/workflows/scenarios/scenario_converter.py` (~120 lines)
- `src/specweaver/workflows/pipelines/scenario_validation.yaml` (~25 lines)
- `tests/unit/workflows/scenarios/__init__.py` (empty)
- `tests/unit/workflows/scenarios/test_scenario_models.py` (~40 lines)
- `tests/unit/workflows/scenarios/test_scenario_generator.py` (~100 lines)
- `tests/unit/workflows/scenarios/test_scenario_converter.py` (~80 lines)
- `tests/unit/core/flow/test_scenario_handlers.py` (~80 lines)
- `tests/unit/core/flow/test_scenario_pipeline_yaml.py` (~40 lines)

Files modified:
- `src/specweaver/core/flow/models.py` (~4 lines)
- `src/specweaver/core/flow/_generation.py` (~100 lines added)
- `src/specweaver/core/flow/handlers.py` (~6 lines)
- `src/specweaver/core/flow/context.yaml` (~1 line added)
- `src/specweaver/core/loom/tools/filesystem/models.py` (~7 lines)
- `tach.toml` (~1 line added)
- `tests/unit/core/flow/test_models.py` (~4 lines)

## Verification Plan

### Automated Tests
```bash
pytest tests/unit/workflows/scenarios/ -v
pytest tests/unit/core/flow/test_scenario_handlers.py -v
pytest tests/unit/core/flow/test_scenario_pipeline_yaml.py -v
pytest tests/unit/core/flow/test_models.py -v
pytest tests/ -v --tb=short  # Full test suite regression
python -m tach check          # Boundary compliance
ruff check src/ tests/        # Lint check
```

### Manual Verification
- Verify `scenario_validation.yaml` round-trips through `PipelineDefinition`
- Verify `(GENERATE, SCENARIO)` and `(CONVERT, SCENARIO)` appear in registry
- Verify `scenario_agent` in `ROLE_INTENTS`
- Verify `tach check` passes with new module
