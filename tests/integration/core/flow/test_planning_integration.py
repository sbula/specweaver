# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for the planning feature (Feature 3.6a).

Tests the seams between:
- Planner → renderer
- PlanArtifact → YAML/JSON serialization round-trip
- PromptBuilder.add_plan → build → <plan> in output
- Generator with plan kwarg → plan in final prompt
- PlanSpecHandler → filesystem → loadable PlanArtifact
- RunContext.plan → GenerateCodeHandler/GenerateTestsHandler → plan reaches Generator
- StepHandlerRegistry with (PLAN, SPEC) → PlanSpecHandler
- _render_files integration with full _render pipeline
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.handlers import (
    GenerateCodeHandler,
    GenerateTestsHandler,
    PlanSpecHandler,
    RunContext,
    StepHandlerRegistry,
)
from specweaver.core.flow.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.state import StepStatus
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder
from specweaver.workflows.planning.models import PlanArtifact
from specweaver.workflows.planning.renderer import render_plan_markdown

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeResponse:
    text: str


class FakeLLM:
    """Fake LLM for integration tests."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._call_count = 0
        self.messages_log: list[Any] = []

    async def generate(self, messages: Any, config: Any = None) -> _FakeResponse:
        self.messages_log.append(messages)
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return _FakeResponse(text=self._responses[idx])


def _valid_plan_json() -> str:
    return json.dumps(
        {
            "spec_path": "specs/login_spec.md",
            "spec_name": "Login",
            "spec_hash": "ignored",
            "timestamp": "2026-03-22T10:00:00Z",
            "file_layout": [
                {"path": "src/login.py", "action": "create", "purpose": "Login handler"},
            ],
            "architecture": {
                "module_layout": "flat",
                "dependency_direction": "downward",
                "archetype": "adapter",
            },
            "reasoning": "Simple adapter pattern.",
            "confidence": 80,
        }
    )


# ---------------------------------------------------------------------------
# I1: Planner output → render_plan_markdown
# ---------------------------------------------------------------------------


class TestPlannerToRenderer:
    """I1: Planner output feeds directly into the renderer."""

    @pytest.mark.asyncio()
    async def test_planner_output_renders_to_markdown(self) -> None:
        llm = FakeLLM([_valid_plan_json()])
        from specweaver.workflows.planning.planner import Planner

        planner = Planner(llm, max_retries=1)
        plan = await planner.generate_plan(
            spec_content="# Login Spec\nHandle login.",
            spec_path="specs/login_spec.md",
            spec_name="Login",
        )

        md = render_plan_markdown(plan)
        assert "# Plan: Login" in md
        assert "src/login.py" in md
        assert "adapter" in md


# ---------------------------------------------------------------------------
# I2-I3: PlanArtifact → YAML/JSON serialization round-trip
# ---------------------------------------------------------------------------


class TestPlanArtifactSerialization:
    """I2/I3: PlanArtifact survives YAML and JSON round-trip."""

    def _make_plan(self) -> PlanArtifact:
        return PlanArtifact(
            spec_path="specs/auth.md",
            spec_name="Auth",
            spec_hash="abc123",
            file_layout=[
                {"path": "src/auth.py", "action": "create", "purpose": "Auth handler"},
            ],
            timestamp="2026-03-22T10:00:00Z",
            confidence=90,
        )

    def test_yaml_round_trip(self) -> None:
        """I2: dump to YAML → load → model_validate."""
        import io

        from ruamel.yaml import YAML

        yaml = YAML()
        yaml.default_flow_style = False
        plan = self._make_plan()
        buf = io.StringIO()
        yaml.dump(plan.model_dump(), buf)
        loaded = YAML().load(buf.getvalue())
        restored = PlanArtifact.model_validate(loaded)
        assert restored.spec_name == plan.spec_name
        assert restored.confidence == plan.confidence
        assert len(restored.file_layout) == len(plan.file_layout)

    def test_json_round_trip(self) -> None:
        """I3: dump to JSON → load → model_validate."""
        plan = self._make_plan()
        dumped = plan.model_dump_json()
        loaded = json.loads(dumped)
        restored = PlanArtifact.model_validate(loaded)
        assert restored.spec_path == plan.spec_path
        assert restored.spec_hash == plan.spec_hash


# ---------------------------------------------------------------------------
# I4-I5: PromptBuilder.add_plan → build → <plan> in output + ordering
# ---------------------------------------------------------------------------


class TestPromptBuilderPlanIntegration:
    """I4/I5: add_plan → build produces <plan> tags, correctly positioned."""

    def test_add_plan_then_build_has_plan_tags(self) -> None:
        """I4: PromptBuilder.add_plan() → build() → <plan> in output."""
        result = PromptBuilder().add_plan("## Tasks\n1. Create module").build()
        assert "<plan>" in result
        assert "Create module" in result
        assert "</plan>" in result

    def test_plan_between_standards_and_topology(self) -> None:
        """I5: Plan positioned between <standards> and <topology> in built prompt."""
        from specweaver.assurance.graph.topology import TopologyContext

        ctx = [
            TopologyContext(
                name="svc",
                purpose="A service.",
                archetype="pure-logic",
                relationship="direct dependency",
            )
        ]
        result = (
            PromptBuilder()
            .add_instructions("Instruction")
            .add_standards("Follow PEP 8")
            .add_plan("Plan content")
            .add_topology(ctx)
            .build()
        )
        assert result.index("<standards>") < result.index("<plan>") < result.index("<topology>")


# ---------------------------------------------------------------------------
# I6-I7: Generator with plan → plan in final prompt
# ---------------------------------------------------------------------------


class TestGeneratorPlanIntegration:
    """I6/I7: Generator.generate_code/tests with plan= includes plan in prompt."""

    @pytest.fixture()
    def mock_llm(self):
        llm = AsyncMock()
        llm.generate = AsyncMock(
            return_value=MagicMock(text="def hello():\n    pass\n"),
        )
        return llm

    @pytest.mark.asyncio()
    async def test_generate_code_plan_in_prompt(self, tmp_path: Path, mock_llm) -> None:
        """I6: Generator.generate_code(plan=...) → plan in final prompt."""
        from specweaver.workflows.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_code(spec, output, plan="## File Layout\n- src/auth.py")

        prompt = mock_llm.generate.call_args[0][0][-1].content
        assert "<plan>" in prompt
        assert "auth.py" in prompt

    @pytest.mark.asyncio()
    async def test_generate_tests_plan_in_prompt(self, tmp_path: Path, mock_llm) -> None:
        """I7: Generator.generate_tests(plan=...) → plan in final prompt."""
        from specweaver.workflows.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "test_out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_tests(spec, output, plan="## Test Expectations\n- test_login")

        prompt = mock_llm.generate.call_args[0][0][-1].content
        assert "<plan>" in prompt
        assert "test_login" in prompt


# ---------------------------------------------------------------------------
# I8: PlanSpecHandler → filesystem → loadable PlanArtifact
# ---------------------------------------------------------------------------


class TestPlanSpecHandlerFileSystem:
    """I8: PlanSpecHandler saves a YAML file that loads as PlanArtifact."""

    @pytest.mark.asyncio()
    async def test_handler_creates_loadable_plan_yaml(self, tmp_path: Path) -> None:
        spec = tmp_path / "component_spec.md"
        spec.write_text("# Component\n## 1. Purpose\nDoes things.\n", encoding="utf-8")

        llm = FakeLLM([_valid_plan_json()])
        ctx = RunContext(project_path=tmp_path, spec_path=spec, llm=llm)
        step = PipelineStep(name="plan", action=StepAction.PLAN, target=StepTarget.SPEC)

        handler = PlanSpecHandler()
        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.PASSED
        plan_path_str = result.output["plan_path"]
        from pathlib import Path

        plan_path = Path(plan_path_str)
        assert plan_path.exists()

        from ruamel.yaml import YAML

        loaded = YAML().load(plan_path.read_text(encoding="utf-8"))
        restored = PlanArtifact.model_validate(loaded)
        assert restored.confidence == 80
        assert len(restored.file_layout) >= 1

    @pytest.mark.asyncio()
    async def test_handler_passes_stitch_mode_from_settings(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """I8b: Handler accurately passes extracted mode & api key to Planner."""
        spec = tmp_path / "spec.md"
        spec.write_text("## Protocol\n\nUI content", encoding="utf-8")

        mock_planner_called_with = {}

        from specweaver.workflows.planning.models import PlanArtifact
        from specweaver.workflows.planning.planner import Planner

        async def mock_generate_plan(self, **kwargs):
            mock_planner_called_with.update(kwargs)
            return PlanArtifact(
                spec_path="x",
                spec_name="y",
                spec_hash="z",
                file_layout=[],
                timestamp="t",
                confidence=0,
            )

        monkeypatch.setattr(Planner, "generate_plan", mock_generate_plan)

        class MockLlmSettings:
            model = "mock-model"
            max_output_tokens = 4096

        class MockStitchSettings:
            mode = "auto"
            api_key = "fake_key"

        class MockSettings:
            stitch = MockStitchSettings()
            llm = MockLlmSettings()

        ctx = RunContext(
            project_path=tmp_path, spec_path=spec, llm=FakeLLM([]), config=MockSettings()
        )
        step = PipelineStep(name="plan", action=StepAction.PLAN, target=StepTarget.SPEC)

        handler = PlanSpecHandler()
        await handler.execute(step, ctx)

        assert mock_planner_called_with.get("stitch_mode") == "auto"
        assert mock_planner_called_with.get("stitch_api_key") == "fake_key"

    @pytest.mark.asyncio()
    async def test_handler_valueerror_fallback(self, tmp_path: Path, monkeypatch) -> None:
        """I8c: Handler gracefully falls back if load_settings raises ValueError."""
        spec = tmp_path / "spec.md"
        spec.write_text("## Protocol\n\nUI content", encoding="utf-8")

        mock_planner_called_with = {}

        from specweaver.workflows.planning.models import PlanArtifact
        from specweaver.workflows.planning.planner import Planner

        async def mock_generate_plan(self, **kwargs):
            mock_planner_called_with.update(kwargs)
            return PlanArtifact(
                spec_path="x",
                spec_name="y",
                spec_hash="z",
                file_layout=[],
                timestamp="t",
                confidence=0,
            )

        monkeypatch.setattr(Planner, "generate_plan", mock_generate_plan)

        # Just test the fallback case: config is missing or lacks stitch
        ctx = RunContext(project_path=tmp_path, spec_path=spec, llm=FakeLLM([]), config=None)
        step = PipelineStep(name="plan", action=StepAction.PLAN, target=StepTarget.SPEC)

        handler = PlanSpecHandler()
        await handler.execute(step, ctx)

        assert mock_planner_called_with.get("stitch_mode") == "off"
        assert mock_planner_called_with.get("stitch_api_key") == ""

    @pytest.mark.asyncio()
    async def test_handler_saves_mockup_to_yaml_when_stitch_auto(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """I8d: E2E Pipeline (Stitch Auto) saving YAML to disk with mockups."""
        spec = tmp_path / "spec.md"
        spec.write_text("## Protocol\n\nUI component with a button", encoding="utf-8")

        class MockLlmSettings:
            model = "mock-model"
            max_output_tokens = 4096

        class MockStitchSettings:
            mode = "auto"
            api_key = "fake_key"

        class MockSettings:
            stitch = MockStitchSettings()
            llm = MockLlmSettings()

        llm = FakeLLM([_valid_plan_json()])
        ctx = RunContext(project_path=tmp_path, spec_path=spec, llm=llm, config=MockSettings())
        step = PipelineStep(name="plan", action=StepAction.PLAN, target=StepTarget.SPEC)

        handler = PlanSpecHandler()
        result = await handler.execute(step, ctx)

        plan_path = Path(result.output["plan_path"])
        yaml_content = plan_path.read_text(encoding="utf-8")

        assert "mockups" in yaml_content
        assert "placeholder" in yaml_content
        assert "Generated UI" in yaml_content

    @pytest.mark.asyncio()
    async def test_handler_saves_no_mockup_to_yaml_when_stitch_off(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """I8e: E2E Pipeline (Stitch Off) saving YAML to disk omits mockups."""
        spec = tmp_path / "spec.md"
        spec.write_text("## Protocol\n\nUI component", encoding="utf-8")

        class MockLlmSettings:
            model = "mock-model"
            max_output_tokens = 4096

        class MockStitchSettings:
            mode = "off"
            api_key = ""

        class MockSettings:
            stitch = MockStitchSettings()
            llm = MockLlmSettings()

        llm = FakeLLM([_valid_plan_json()])
        ctx = RunContext(project_path=tmp_path, spec_path=spec, llm=llm, config=MockSettings())
        step = PipelineStep(name="plan", action=StepAction.PLAN, target=StepTarget.SPEC)

        handler = PlanSpecHandler()
        result = await handler.execute(step, ctx)

        plan_path = Path(result.output["plan_path"])
        yaml_content = plan_path.read_text(encoding="utf-8")

        assert "mockups: []" in yaml_content


# ---------------------------------------------------------------------------
# I9-I10: RunContext.plan → GenerateCodeHandler/GenerateTestsHandler
# ---------------------------------------------------------------------------


class TestRunContextPlanFlowsToGenerator:
    """I9/I10: RunContext(plan=...) → Generate handlers → plan reaches Generator."""

    @pytest.mark.asyncio()
    async def test_generate_code_handler_passes_plan(self, tmp_path: Path) -> None:
        """I9: RunContext.plan flows to GenerateCodeHandler → Generator."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n", encoding="utf-8")
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value=MagicMock(text="x = 1\n", finish_reason=1, parsed=None),
        )
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=spec,
            output_dir=src_dir,
            llm=mock_llm,
            plan="## File Layout\n- src/test.py: main module",
        )
        step = PipelineStep(name="gen", action=StepAction.GENERATE, target=StepTarget.CODE)
        handler = GenerateCodeHandler()
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.PASSED

        # Verify plan was injected into the final prompt
        prompt = mock_llm.generate.call_args[0][0][-1].content
        assert "<plan>" in prompt
        assert "main module" in prompt

    @pytest.mark.asyncio()
    async def test_generate_tests_handler_passes_plan(self, tmp_path: Path) -> None:
        """I10: RunContext.plan flows to GenerateTestsHandler → Generator."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n", encoding="utf-8")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(
            return_value=MagicMock(text="def test_x(): pass\n", finish_reason=1, parsed=None),
        )
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=spec,
            output_dir=tests_dir,
            llm=mock_llm,
            plan="## Test Expectations\n- test_login: Check login flow",
        )
        step = PipelineStep(name="gen_tests", action=StepAction.GENERATE, target=StepTarget.TESTS)
        handler = GenerateTestsHandler()
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.PASSED

        prompt = mock_llm.generate.call_args[0][0][-1].content
        assert "<plan>" in prompt
        assert "test_login" in prompt


# ---------------------------------------------------------------------------
# I11: StepHandlerRegistry[(PLAN, SPEC)] → PlanSpecHandler
# ---------------------------------------------------------------------------


class TestRegistryPlanSpec:
    """I11: Registry maps (PLAN, SPEC) to PlanSpecHandler."""

    def test_registry_has_plan_spec(self) -> None:
        registry = StepHandlerRegistry()
        handler = registry.get(StepAction.PLAN, StepTarget.SPEC)
        assert handler is not None
        assert isinstance(handler, PlanSpecHandler)


# ---------------------------------------------------------------------------
# I12: _render_files integration with full _render pipeline
# ---------------------------------------------------------------------------


class TestRenderFilesInPipeline:
    """I12: _render_files integrates correctly in the full render pipeline."""

    def test_files_in_full_render_pipeline(self, tmp_path: Path) -> None:
        """File blocks appear in correct position within full rendered output."""
        f = tmp_path / "auth.py"
        f.write_text("class Auth: pass", encoding="utf-8")

        result = (
            PromptBuilder()
            .add_instructions("Review this code")
            .add_constitution("Be strict")
            .add_standards("Follow PEP 8")
            .add_plan("## Tasks\n1. Review auth")
            .add_file(f, priority=1, role="target")
            .build()
        )

        # Verify order: instructions → constitution → standards → plan → files
        assert result.index("<instructions>") < result.index("<constitution>")
        assert result.index("<constitution>") < result.index("<standards>")
        assert result.index("<standards>") < result.index("<plan>")
        assert result.index("<plan>") < result.index("<file_contents>")
        assert 'role="target"' in result
        assert "class Auth" in result


# ---------------------------------------------------------------------------
# I13: Planner + constitution + standards via refactored render pipeline
# ---------------------------------------------------------------------------


class TestPlannerWithConstitutionAndStandards:
    """I13: Planner passes constitution+standards through PromptBuilder
    which now renders standards via _render_tagged_blocks."""

    @pytest.mark.asyncio()
    async def test_planner_constitution_and_standards_in_prompt(self) -> None:
        """Planner with constitution+standards → both appear in prompt."""
        llm = FakeLLM([_valid_plan_json()])
        from specweaver.workflows.planning.planner import Planner

        planner = Planner(llm, max_retries=1)
        plan = await planner.generate_plan(
            spec_content="# Login Spec\nHandle login.",
            spec_path="specs/login_spec.md",
            spec_name="Login",
            constitution="Always follow security best practices.",
            standards="Use PEP 8 naming conventions.",
        )

        # Verify the plan was generated correctly
        assert plan.spec_name == "Login"
        assert plan.confidence == 80

        # Verify the prompt sent to the LLM contained both sections
        # (inspect messages_log from the fake LLM)
        prompt = llm.messages_log[0][-1].content
        assert "<constitution>" in prompt
        assert "security best practices" in prompt
        assert "<standards>" in prompt
        assert "PEP 8 naming" in prompt


# ---------------------------------------------------------------------------
# I14: render_blocks assembly order preserved after helper extraction
# ---------------------------------------------------------------------------


class TestRenderBlocksOrderPreserved:
    """I14: render_blocks still produces correct section ordering
    after extracting _render_tagged_blocks and _render_mentioned."""

    def test_full_render_order_with_all_block_types(self, tmp_path: Path) -> None:
        """All block types rendered in correct architectural order."""
        from specweaver.assurance.graph.topology import TopologyContext

        f = tmp_path / "code.py"
        f.write_text("x = 1", encoding="utf-8")
        ctx = [
            TopologyContext(
                name="mod",
                purpose="A module.",
                archetype="pure-logic",
                relationship="direct consumer",
            )
        ]

        result = (
            PromptBuilder()
            .add_instructions("Review code")
            .add_constitution("Be safe")
            .add_standards("Follow PEP 8")
            .add_plan("## Tasks\n1. Review")
            .add_topology(ctx)
            .add_file(f)
            .add_context("Extra info", "ctx_label")
            .add_reminder("Don't forget quality")
            .build()
        )

        # Verify strict rendering order
        positions = {
            "instructions": result.index("<instructions>"),
            "constitution": result.index("<constitution>"),
            "standards": result.index("<standards>"),
            "plan": result.index("<plan>"),
            "topology": result.index("<topology>"),
            "files": result.index("<file_contents>"),
            "context": result.index("<context "),
            "reminder": result.index("<reminder>"),
        }
        order = sorted(positions.keys(), key=lambda k: positions[k])
        assert order == [
            "instructions",
            "constitution",
            "standards",
            "plan",
            "topology",
            "files",
            "context",
            "reminder",
        ]


# ---------------------------------------------------------------------------
# I15: Planner retry flow with refactored _clean_json
# ---------------------------------------------------------------------------


class TestPlannerRetryWithCleanJson:
    """I15: Planner retry uses refactored _clean_json (removeprefix/removesuffix)
    end-to-end."""

    @pytest.mark.asyncio()
    async def test_retry_with_markdown_fenced_json(self) -> None:
        """LLM returns markdown-fenced JSON on first attempt → cleaned and parsed."""
        fenced = f"```json\n{_valid_plan_json()}\n```"
        llm = FakeLLM([fenced])
        from specweaver.workflows.planning.planner import Planner

        planner = Planner(llm, max_retries=1)
        plan = await planner.generate_plan(
            spec_content="# Spec\nContent.",
            spec_path="specs/test.md",
            spec_name="Test",
        )

        assert plan.spec_name == "Test"
        assert plan.confidence == 80


# ---------------------------------------------------------------------------
# DAG Orchestrator Dynamic Pipeline Fan-Out (Integration)
# ---------------------------------------------------------------------------


class TestDagOrchestratorIntegration:
    """Tests the interaction between OrchestrateComponentsHandler, TopologyGraph, and dynamically spawned PipelineRunners."""

    @pytest.mark.asyncio()
    async def test_integration_starvation_and_dependency_bubble_up(self, tmp_path: Path) -> None:
        """Integration Story 2: Failures in dynamic sub-pipelines properly starve dependents and bubble."""
        from specweaver.core.flow._decompose import OrchestrateComponentsHandler
        from specweaver.core.flow.handlers import StepHandlerRegistry
        from specweaver.core.flow.models import PipelineDefinition
        from specweaver.core.flow.runner import PipelineRunner

        ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        ctx.run_id = "parent_run"

        # Two components: A and B. B depends on A.
        plan_dict = {
            "components": [
                {"component": "service_a", "dependencies": [], "target_modules": ["auth"]},
                {
                    "component": "service_b",
                    "dependencies": ["service_a"],
                    "target_modules": ["api"],
                },
            ]
        }
        ctx.plan = json.dumps(plan_dict)

        # We need a PipelineRunner with a registry. We will mock the runner to fail on 'service_a'
        pipe = PipelineDefinition.model_validate_json(json.dumps({"name": "test", "steps": []}))
        registry = StepHandlerRegistry()
        ctx.pipeline_runner = PipelineRunner(pipe, ctx, registry=registry, store=MagicMock())

        # Mock PipelineRunner.run() so we don't actually trigger deep LLM calls

        async def mocked_run(self_runner, parent_run_id=None):
            # If this is service_a, fail it!
            if self_runner._pipeline.name == "auto_service_a":
                return MagicMock(status=StepStatus.FAILED)
            return MagicMock(status=StepStatus.PASSED)

        with patch("specweaver.core.flow.runner.PipelineRunner.run", new=mocked_run):
            handler = OrchestrateComponentsHandler()
            step_def = PipelineStep(
                name="orch", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
            )

            result = await handler.execute(step_def, ctx)

            # Since auto_service_a failed, B must be starved.
            # The parent orchestration must FAIL with a cascading failure message.
            assert result.status == StepStatus.FAILED, "Handler should bubble up failures."
            assert "Cascading failure" in result.error_message
            assert "Ran 1 total pipelines" in result.error_message, (
                "Only Service A should have run!"
            )

    @pytest.mark.asyncio()
    async def test_integration_topological_collision_deferment(self, tmp_path: Path) -> None:
        """Integration Story 1: DAG Orchestrator physically blocks overlapping impact chains."""
        import asyncio

        from specweaver.assurance.graph.topology import TopologyGraph
        from specweaver.core.flow._decompose import OrchestrateComponentsHandler
        from specweaver.core.flow.models import PipelineDefinition
        from specweaver.core.flow.runner import PipelineRunner

        ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        ctx.run_id = "parent_run"

        # Parallel components logically, no logical strictly defined dependency!
        # BUT they share a target module "auth"
        plan_dict = {
            "components": [
                {"component": "service_a", "dependencies": [], "target_modules": ["auth"]},
                {"component": "service_b", "dependencies": [], "target_modules": ["auth"]},
            ]
        }
        ctx.plan = json.dumps(plan_dict)

        # Mock topology showing collision
        mock_topo = MagicMock(spec=TopologyGraph)
        mock_topo.impact_of.return_value = {"auth"}
        ctx.topology = mock_topo

        pipe = PipelineDefinition.model_validate_json(json.dumps({"name": "test", "steps": []}))
        ctx.pipeline_runner = PipelineRunner(pipe, ctx, registry=MagicMock(), store=MagicMock())

        # We need custom run() locking to prove they don't run *at the same time*.
        running_tasks = set()
        max_concurrent = 0

        async def mocked_run(self_runner, parent_run_id=None):
            nonlocal max_concurrent
            running_tasks.add(self_runner._pipeline.name)
            max_concurrent = max(max_concurrent, len(running_tasks))
            # Sleep briefly to ensure overlap if the engine didn't lock it
            await asyncio.sleep(0.1)
            running_tasks.remove(self_runner._pipeline.name)
            return MagicMock(status=StepStatus.PASSED, run_id="child_run_id")

        with patch("specweaver.core.flow.runner.PipelineRunner.run", new=mocked_run):
            handler = OrchestrateComponentsHandler()
            step_def = PipelineStep(
                name="orch", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
            )

            result = await handler.execute(step_def, ctx)

            # Both should have run successfully
            assert result.status == StepStatus.PASSED
            assert len(result.output["sub_runs"]) == 2

            # The maximum observed concurrency MUST be 1 due to the topology conflict!
            assert max_concurrent == 1, (
                "Topological collision guard failed, tasks ran concurrently!"
            )


@pytest.mark.asyncio
async def test_integration_topological_join_wave_n_deferred() -> None:
    """
    Verifies that OrchestrateComponentsHandler correctly strips `gate: join` steps
    prior to running parallel fan_out pipelines, and correctly executes them identically
    at the end via a synchronised Wave N runner execution.
    """
    from pathlib import Path

    from specweaver.core.flow._base import RunContext
    from specweaver.core.flow._decompose import OrchestrateComponentsHandler
    from specweaver.core.flow.runner import PipelineRunner
    from specweaver.core.flow.state import StepStatus

    ctx = RunContext(project_path=Path("/tmp/path"), spec_path=Path("/tmp/path/spec.md"))
    ctx.run_id = "parent_run"

    # 1. Provide a plan indicating 2 entirely disconnected components.
    mock_plan = json.dumps(
        {
            "components": [
                {"component": "AlphaFeature", "dependencies": []},
                {"component": "BetaFeature", "dependencies": []},
            ]
        }
    )
    ctx.plan = mock_plan

    import importlib.resources

    import yaml

    files = importlib.resources.files("specweaver.workflows.pipelines")
    resource = files.joinpath("new_feature.yaml")
    base_yaml = yaml.safe_load(resource.read_text(encoding="utf-8"))

    # Force the last step to be a `join` Gate
    base_yaml["steps"][-1]["gate"] = {"type": "join"}
    custom_yaml_text = yaml.dump(base_yaml)

    handler = OrchestrateComponentsHandler()
    runner = PipelineRunner(
        pipeline=MagicMock(),
        context=ctx,
        registry=MagicMock(),
        store=MagicMock(),
        on_event=MagicMock(),
    )
    ctx.pipeline_runner = runner

    original_init = PipelineRunner.__init__
    created_pipelines = []

    def spy_init(self: Any, pipeline: Any, *args: Any, **kwargs: Any) -> None:
        created_pipelines.append(pipeline)
        return original_init(self, pipeline, *args, **kwargs)

    with (
        patch.multiple(
            "specweaver.core.flow.runner.PipelineRunner",
            __init__=spy_init,
            run=AsyncMock(return_value=MagicMock(status=StepStatus.PASSED, run_id="mock-run")),
        ),
        patch.object(importlib.resources, "files") as mock_files,
    ):
        mock_resource = MagicMock()
        mock_resource.joinpath.return_value.read_text.return_value = custom_yaml_text
        mock_files.return_value = mock_resource

        step_def = PipelineStep(
            name="orch", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
        )
        res = await handler.execute(step_def, ctx)

    assert res.status == StepStatus.PASSED

    assert len(created_pipelines) == 3

    pipe_alpha = next(p for p in created_pipelines if p.name == "auto_AlphaFeature")
    pipe_beta = next(p for p in created_pipelines if p.name == "auto_BetaFeature")
    pipe_join = next(p for p in created_pipelines if "wave_n" in p.name)

    assert len(pipe_alpha.steps) == len(base_yaml["steps"]) - 1
    assert len(pipe_beta.steps) == len(base_yaml["steps"]) - 1

    assert len(pipe_join.steps) == 2
    assert pipe_join.steps[0].params["component"] in ["AlphaFeature", "BetaFeature"]
    assert pipe_join.steps[1].params["component"] in ["AlphaFeature", "BetaFeature"]
    assert pipe_join.steps[0].params["component"] != pipe_join.steps[1].params["component"]


