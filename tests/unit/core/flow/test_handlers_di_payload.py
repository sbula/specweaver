# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specweaver.assurance.validation.models import Status
from specweaver.core.flow._validation import ValidateCodeHandler, ValidateSpecHandler
from specweaver.core.flow.handlers import RunContext
from specweaver.core.flow.models import PipelineStep, StepAction, StepTarget


@pytest.mark.asyncio
async def test_validate_code_handler_injects_ast_payload(tmp_path: Path) -> None:
    # Arrange
    project_root = tmp_path

    # Setup context.yaml to hit spring-boot
    context_file = project_root / "context.yaml"
    context_file.write_text("archetype: spring-boot")

    code_file = project_root / "foo.py"
    code_file.write_text("print('hello')")

    spec_file = project_root / "foo_spec.md"
    spec_file.write_text("spec")

    context = RunContext(
        project_path=project_root,
        spec_path=spec_file,
        output_dir=project_root,
        llm=MagicMock(),
    )

    step = PipelineStep(
        name="test_step", action=StepAction.VALIDATE, target=StepTarget.CODE, params={}
    )

    handler = ValidateCodeHandler()

    # We mock _resolve_merged_settings to just return None
    with (
        patch("specweaver.core.flow._validation._resolve_merged_settings", return_value=None),
        patch("specweaver.core.config.archetype_resolver.ArchetypeResolver") as mock_resolver_cls,
        patch("specweaver.core.loom.atoms.code_structure.atom.CodeStructureAtom") as mock_atom_cls,
        patch("specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml") as mock_load,
        patch("specweaver.assurance.validation.executor.execute_validation_pipeline") as mock_exec,
    ):
        # Setup ArchetypeResolver
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = "spring-boot"
        mock_resolver_cls.return_value = mock_resolver

        # Setup CodeStructureAtom
        mock_atom = MagicMock()

        def run_side_effect(payload):
            res = MagicMock()
            res.status.value = "SUCCESS"
            if payload["intent"] == "read_file_structure":
                res.exports = {"ast": {"type": "module"}}
            else:
                res.exports = {"markers": {"Foo": {"decorators": ["actix"]}}}
            return res

        mock_atom.run.side_effect = run_side_effect
        mock_atom_cls.return_value = mock_atom

        # Setup Pipeline
        mock_pipeline = MagicMock()
        mock_step = MagicMock()
        mock_step.params = {}
        mock_pipeline.steps = [mock_step]
        mock_load.return_value = mock_pipeline

        # Setup executor
        dummy_result = MagicMock()
        dummy_result.status = Status.PASS
        mock_exec.return_value = [dummy_result]

        # Act
        await handler.execute(step, context)

        # Assert
        # 1. Pipeline loaded correctly
        mock_load.assert_called_once_with("validation_code_spring-boot")

        # 2. Rule step was injected
        assert mock_step.params["ast_payload"] == {
            "ast": {"type": "module"},
            "framework_markers": {"Foo": {"decorators": ["actix"]}},
        }

        # 3. CodeStructureAtom was executed twice
        assert mock_atom.run.call_count == 2
        mock_atom.run.assert_any_call({"intent": "read_file_structure", "path": str(code_file)})
        mock_atom.run.assert_any_call(
            {"intent": "extract_framework_markers", "path": str(code_file)}
        )


@pytest.mark.asyncio
async def test_validate_spec_handler_loads_archetype(tmp_path: Path) -> None:
    project_root = tmp_path

    spec_file = project_root / "foo_spec.md"
    spec_file.write_text("spec")

    context = RunContext(
        project_path=project_root,
        spec_path=spec_file,
        output_dir=project_root,
        llm=MagicMock(),
    )

    step = PipelineStep(
        name="test_step", action=StepAction.VALIDATE, target=StepTarget.SPEC, params={}
    )

    handler = ValidateSpecHandler()

    with (
        patch("specweaver.core.flow._validation._resolve_merged_settings", return_value=None),
        patch("specweaver.core.config.archetype_resolver.ArchetypeResolver") as mock_resolver_cls,
        patch("specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml") as mock_load,
        patch("specweaver.assurance.validation.executor.execute_validation_pipeline") as mock_exec,
    ):
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = "spring-boot"
        mock_resolver_cls.return_value = mock_resolver

        mock_pipeline = MagicMock()
        mock_pipeline.steps = []
        mock_load.return_value = mock_pipeline

        mock_exec.return_value = []

        await handler.execute(step, context)

        mock_load.assert_called_once_with("validation_spec_default_spring-boot")


@pytest.mark.asyncio
async def test_validate_code_handler_falls_back_when_no_archetype(tmp_path: Path) -> None:
    project_root = tmp_path

    code_file = project_root / "foo.py"
    code_file.write_text("print('hello')")

    spec_file = project_root / "foo_spec.md"
    spec_file.write_text("spec")

    context = RunContext(
        project_path=project_root,
        spec_path=spec_file,
        output_dir=project_root,
        llm=MagicMock(),
    )

    step = PipelineStep(
        name="test_step", action=StepAction.VALIDATE, target=StepTarget.CODE, params={}
    )

    handler = ValidateCodeHandler()

    with (
        patch("specweaver.core.flow._validation._resolve_merged_settings", return_value=None),
        patch("specweaver.core.config.archetype_resolver.ArchetypeResolver") as mock_resolver_cls,
        patch("specweaver.core.loom.atoms.code_structure.atom.CodeStructureAtom") as mock_atom_cls,
        patch("specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml") as mock_load,
        patch("specweaver.assurance.validation.executor.execute_validation_pipeline") as mock_exec,
    ):
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = None  # Force None
        mock_resolver_cls.return_value = mock_resolver

        mock_atom = MagicMock()

        def run_side_effect(payload):
            res = MagicMock()
            res.status.value = "SUCCESS"
            if payload["intent"] == "read_file_structure":
                res.exports = {"ast": {"type": "module"}}
            else:
                res.exports = {"markers": {"Foo": {"decorators": ["actix"]}}}
            return res

        mock_atom.run.side_effect = run_side_effect
        mock_atom_cls.return_value = mock_atom

        mock_pipeline = MagicMock()
        mock_step = MagicMock()
        mock_step.params = {}
        mock_pipeline.steps = [mock_step]
        mock_load.return_value = mock_pipeline

        dummy_result = MagicMock()
        dummy_result.status = Status.PASS
        mock_exec.return_value = [dummy_result]

        await handler.execute(step, context)

        mock_load.assert_called_once_with("validation_code_default")
        assert mock_atom.run.call_count == 2
        mock_atom.run.assert_any_call({"intent": "read_file_structure", "path": str(code_file)})
        mock_atom.run.assert_any_call(
            {"intent": "extract_framework_markers", "path": str(code_file)}
        )


@pytest.mark.asyncio
async def test_validate_spec_handler_falls_back_when_no_archetype(tmp_path: Path) -> None:
    project_root = tmp_path

    spec_file = project_root / "foo_spec.md"
    spec_file.write_text("spec")

    context = RunContext(
        project_path=project_root,
        spec_path=spec_file,
        output_dir=project_root,
        llm=MagicMock(),
    )

    step = PipelineStep(
        name="test_step", action=StepAction.VALIDATE, target=StepTarget.SPEC, params={}
    )

    handler = ValidateSpecHandler()

    with (
        patch("specweaver.core.flow._validation._resolve_merged_settings", return_value=None),
        patch("specweaver.core.config.archetype_resolver.ArchetypeResolver") as mock_resolver_cls,
        patch("specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml") as mock_load,
        patch("specweaver.assurance.validation.executor.execute_validation_pipeline") as mock_exec,
    ):
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = None  # Force None
        mock_resolver_cls.return_value = mock_resolver

        mock_pipeline = MagicMock()
        mock_pipeline.steps = []
        mock_load.return_value = mock_pipeline

        mock_exec.return_value = []

        await handler.execute(step, context)

        mock_load.assert_called_once_with("validation_spec_default")

@pytest.mark.asyncio
async def test_validate_spec_handler_atom_fails_fallback(tmp_path: Path) -> None:
    project_root = tmp_path
    spec_file = project_root / "foo_spec.md"
    spec_file.write_text("spec")
    context = RunContext(project_path=project_root, spec_path=spec_file, output_dir=project_root, llm=MagicMock())
    step = PipelineStep(name="test_step", action=StepAction.VALIDATE, target=StepTarget.SPEC, params={})
    handler = ValidateSpecHandler()

    with (
        patch("specweaver.core.flow._validation._resolve_merged_settings", return_value=None),
        patch("specweaver.core.config.archetype_resolver.ArchetypeResolver") as mock_resolver_cls,
        patch("specweaver.core.loom.atoms.code_structure.atom.CodeStructureAtom") as mock_atom_cls,
        patch("specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml") as mock_load,
        patch("specweaver.assurance.validation.executor.execute_validation_pipeline") as mock_exec,
    ):
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = "spring-boot"
        mock_resolver_cls.return_value = mock_resolver

        mock_atom = MagicMock()
        def run_side_effect(payload):
            res = MagicMock()
            res.status.value = "FAILED"
            return res
        mock_atom.run.side_effect = run_side_effect
        mock_atom_cls.return_value = mock_atom

        mock_pipeline = MagicMock()
        mock_step = MagicMock()
        mock_step.params = {}
        mock_pipeline.steps = [mock_step]
        mock_load.return_value = mock_pipeline
        mock_exec.return_value = []

        await handler.execute(step, context)
        assert mock_step.params["ast_payload"] == {}


@pytest.mark.asyncio
async def test_validate_code_handler_atom_fails_fallback(tmp_path: Path) -> None:
    project_root = tmp_path
    code_file = project_root / "foo.py"
    code_file.write_text("print('hello')")
    spec_file = project_root / "foo_spec.md"
    spec_file.write_text("spec")
    context = RunContext(project_path=project_root, spec_path=spec_file, output_dir=project_root, llm=MagicMock())
    step = PipelineStep(name="test_step", action=StepAction.VALIDATE, target=StepTarget.CODE, params={})
    handler = ValidateCodeHandler()

    with (
        patch("specweaver.core.flow._validation._resolve_merged_settings", return_value=None),
        patch("specweaver.core.config.archetype_resolver.ArchetypeResolver") as mock_resolver_cls,
        patch("specweaver.core.loom.atoms.code_structure.atom.CodeStructureAtom") as mock_atom_cls,
        patch("specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml") as mock_load,
        patch("specweaver.assurance.validation.executor.execute_validation_pipeline") as mock_exec,
    ):
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = "spring-boot"
        mock_resolver_cls.return_value = mock_resolver

        mock_atom = MagicMock()
        def run_side_effect(payload):
            res = MagicMock()
            res.status.value = "FAILED"
            return res
        mock_atom.run.side_effect = run_side_effect
        mock_atom_cls.return_value = mock_atom

        mock_pipeline = MagicMock()
        mock_step = MagicMock()
        mock_step.params = {}
        mock_pipeline.steps = [mock_step]
        mock_load.return_value = mock_pipeline
        mock_exec.return_value = []

        await handler.execute(step, context)
        assert mock_step.params["ast_payload"] == {}


@pytest.mark.asyncio
async def test_validate_spec_handler_load_pipeline_fails_fallback(tmp_path: Path) -> None:
    project_root = tmp_path
    spec_file = project_root / "foo_spec.md"
    spec_file.write_text("spec")
    context = RunContext(project_path=project_root, spec_path=spec_file, output_dir=project_root, llm=MagicMock())
    step = PipelineStep(name="test_step", action=StepAction.VALIDATE, target=StepTarget.SPEC, params={})
    handler = ValidateSpecHandler()

    with (
        patch("specweaver.core.flow._validation._resolve_merged_settings", return_value=None),
        patch("specweaver.core.config.archetype_resolver.ArchetypeResolver") as mock_resolver_cls,
        patch("specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml") as mock_load,
        patch("specweaver.assurance.validation.executor.execute_validation_pipeline") as mock_exec,
    ):
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = "unrecognized_archetype"
        mock_resolver_cls.return_value = mock_resolver

        def mock_load_side_effect(name):
            if name == "validation_spec_default_unrecognized_archetype":
                raise ValueError("File not found")
            mock_pipeline = MagicMock()
            mock_pipeline.steps = []
            return mock_pipeline

        mock_load.side_effect = mock_load_side_effect
        mock_exec.return_value = []

        await handler.execute(step, context)
        # Should have called loading twice
        assert mock_load.call_count == 2
        mock_load.assert_any_call("validation_spec_default")


@pytest.mark.asyncio
async def test_validate_code_handler_load_pipeline_fails_fallback(tmp_path: Path) -> None:
    project_root = tmp_path
    code_file = project_root / "foo.py"
    code_file.write_text("print('hello')")
    spec_file = project_root / "foo_spec.md"
    spec_file.write_text("spec")
    context = RunContext(project_path=project_root, spec_path=spec_file, output_dir=project_root, llm=MagicMock())
    step = PipelineStep(name="test_step", action=StepAction.VALIDATE, target=StepTarget.CODE, params={})
    handler = ValidateCodeHandler()

    with (
        patch("specweaver.core.flow._validation._resolve_merged_settings", return_value=None),
        patch("specweaver.core.config.archetype_resolver.ArchetypeResolver") as mock_resolver_cls,
        patch("specweaver.core.loom.atoms.code_structure.atom.CodeStructureAtom") as mock_atom_cls,
        patch("specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml") as mock_load,
        patch("specweaver.assurance.validation.executor.execute_validation_pipeline") as mock_exec,
    ):
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = "unrecognized_archetype"
        mock_resolver_cls.return_value = mock_resolver

        # CodeStructureAtom
        mock_atom = MagicMock()
        def run_side_effect(payload):
            res = MagicMock()
            res.status.value = "SUCCESS"
            res.exports = {}
            return res
        mock_atom.run.side_effect = run_side_effect
        mock_atom_cls.return_value = mock_atom

        def mock_load_side_effect(name):
            if name == "validation_code_unrecognized_archetype":
                raise ValueError("File not found")
            mock_pipeline = MagicMock()
            mock_step = MagicMock()
            mock_step.params = {}
            mock_pipeline.steps = [mock_step]
            return mock_pipeline

        mock_load.side_effect = mock_load_side_effect
        mock_exec.return_value = []

        await handler.execute(step, context)

        assert mock_load.call_count == 2
        mock_load.assert_any_call("validation_code_default")


@pytest.mark.asyncio
async def test_validate_spec_handler_e2e_integration(tmp_path: Path) -> None:
    """End to End Integration mimicking the actual pipeline execution with the native execution and S12 check."""
    from specweaver.assurance.validation.rules.spec.s12_archetype_spec_bounds import (
        S12ArchetypeSpecBoundsRule,
    )
    from specweaver.core.flow.state import StepStatus

    project_root = tmp_path
    spec_file = project_root / "foo_spec.md"
    spec_file.write_text("# Main Title\n\n## 1. Purpose\nTest purpose.\n\n## 2. Boundaries\nTest bounds.\n")

    context = RunContext(project_path=project_root, spec_path=spec_file, output_dir=project_root, llm=MagicMock())
    step = PipelineStep(name="test_step", action=StepAction.VALIDATE, target=StepTarget.SPEC, params={})
    handler = ValidateSpecHandler()

    with (
        patch("specweaver.core.flow._validation._resolve_merged_settings", return_value=None),
        patch("specweaver.core.config.archetype_resolver.ArchetypeResolver") as mock_resolver_cls,
        patch("specweaver.core.loom.atoms.code_structure.atom.CodeStructureAtom") as mock_atom_cls,
        patch("specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml") as mock_load,
    ):
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = "spring-boot"
        mock_resolver_cls.return_value = mock_resolver

        mock_atom = MagicMock()
        def run_side_effect(payload):
            res = MagicMock()
            res.status.value = "SUCCESS"
            # It should return a json string for skeleton
            res.exports = {"structure": '{"h1": ["Main Title"], "h2": ["1. Purpose", "2. Boundaries"], "h3": []}'}
            return res
        mock_atom.run.side_effect = run_side_effect
        mock_atom_cls.return_value = mock_atom

        mock_pipeline = PipelineStep(name="1", action=StepAction.VALIDATE, target=StepTarget.SPEC, params={"required_headers": {"h1": ["Main Title"], "h2": ["1. Purpose", "2. Boundaries"]}})
        # create actual S12 rule
        s12_rule = S12ArchetypeSpecBoundsRule(required_headers={"h1": ["Main Title"], "h2": ["1. Purpose", "2. Boundaries"]})

        # Override execution to practically run S12
        def e2e_exec(pipeline, content, spec_path):
            # pipeline step params holds ast_payload
            for step in pipeline.steps:
                s12_rule.context = step.params.get("ast_payload", {})
            return [s12_rule.check(content, spec_path)]

        with patch("specweaver.assurance.validation.executor.execute_validation_pipeline", side_effect=e2e_exec):
            mock_pipeline_obj = MagicMock()
            mock_pipeline_obj.steps = [mock_pipeline]
            mock_load.return_value = mock_pipeline_obj

            # Use real CodeStructureAtom here since we don't mock it!
            result = await handler.execute(step, context)

            assert result.status == StepStatus.PASSED


@pytest.mark.asyncio
async def test_validate_spec_handler_e2e_integration_failed_bounds(tmp_path: Path) -> None:
    """End to End Integration simulating the S12 rejection yields failures correctly."""
    from specweaver.assurance.validation.rules.spec.s12_archetype_spec_bounds import (
        S12ArchetypeSpecBoundsRule,
    )
    from specweaver.core.flow.state import StepStatus

    project_root = tmp_path
    spec_file = project_root / "foo_spec.md"
    spec_file.write_text("# Bad Title\n\n## 1. Wrong\nTest purpose.\n")

    context = RunContext(project_path=project_root, spec_path=spec_file, output_dir=project_root, llm=MagicMock())
    step = PipelineStep(name="test_step", action=StepAction.VALIDATE, target=StepTarget.SPEC, params={})
    handler = ValidateSpecHandler()

    with (
        patch("specweaver.core.flow._validation._resolve_merged_settings", return_value=None),
        patch("specweaver.core.config.archetype_resolver.ArchetypeResolver") as mock_resolver_cls,
        patch("specweaver.core.loom.atoms.code_structure.atom.CodeStructureAtom") as mock_atom_cls,
        patch("specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml") as mock_load,
    ):
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = "spring-boot"
        mock_resolver_cls.return_value = mock_resolver

        mock_atom = MagicMock()
        def run_side_effect(payload):
            res = MagicMock()
            res.status.value = "SUCCESS"
            res.exports = {"structure": '{"h1": ["Bad Title"], "h2": ["1. Wrong"], "h3": []}'}
            return res
        mock_atom.run.side_effect = run_side_effect
        mock_atom_cls.return_value = mock_atom

        mock_pipeline = PipelineStep(name="1", action=StepAction.VALIDATE, target=StepTarget.SPEC, params={"required_headers": {"h1": ["Main Title"], "h2": ["1. Purpose"]}})
        s12_rule = S12ArchetypeSpecBoundsRule(required_headers={"h1": ["Main Title"], "h2": ["1. Purpose"]})

        def e2e_exec(pipeline, content, spec_path):
            for step in pipeline.steps:
                s12_rule.context = step.params.get("ast_payload", {})
            return [s12_rule.check(content, spec_path)]

        with patch("specweaver.assurance.validation.executor.execute_validation_pipeline", side_effect=e2e_exec):
            mock_pipeline_obj = MagicMock()
            mock_pipeline_obj.steps = [mock_pipeline]
            mock_load.return_value = mock_pipeline_obj

            result = await handler.execute(step, context)

            assert result.status == StepStatus.FAILED
            assert result.output["failed"] == 1

