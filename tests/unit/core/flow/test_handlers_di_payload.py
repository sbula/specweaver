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
        name="test_step",
        action=StepAction.VALIDATE,
        target=StepTarget.CODE,
        params={}
    )

    handler = ValidateCodeHandler()

    # We mock _resolve_merged_settings to just return None
    with patch(
        "specweaver.core.flow._validation._resolve_merged_settings", return_value=None
    ), patch(
        "specweaver.core.config.archetype_resolver.ArchetypeResolver"
    ) as mock_resolver_cls, patch(
        "specweaver.core.loom.atoms.code_structure.atom.CodeStructureAtom"
    ) as mock_atom_cls, patch(
        "specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml"
    ) as mock_load, patch(
        "specweaver.assurance.validation.executor.execute_validation_pipeline"
    ) as mock_exec:

        # Setup ArchetypeResolver
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = "spring-boot"
        mock_resolver_cls.return_value = mock_resolver

        # Setup CodeStructureAtom
        mock_atom = MagicMock()
        def run_side_effect(payload):
            res = MagicMock()
            res.status.value = "SUCCESS"
            if payload["intent"] == "extract_skeleton":
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
        assert mock_step.params["ast_payload"] == {"ast": {"type": "module"}, "framework_markers": {"Foo": {"decorators": ["actix"]}}}

        # 3. CodeStructureAtom was executed twice
        assert mock_atom.run.call_count == 2
        mock_atom.run.assert_any_call({"intent": "extract_skeleton", "path": str(code_file)})
        mock_atom.run.assert_any_call({"intent": "extract_framework_markers", "path": str(code_file)})

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
        name="test_step",
        action=StepAction.VALIDATE,
        target=StepTarget.SPEC,
        params={}
    )

    handler = ValidateSpecHandler()

    with patch(
        "specweaver.core.flow._validation._resolve_merged_settings", return_value=None
    ), patch(
        "specweaver.core.config.archetype_resolver.ArchetypeResolver"
    ) as mock_resolver_cls, patch(
        "specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml"
    ) as mock_load, patch(
        "specweaver.assurance.validation.executor.execute_validation_pipeline"
    ) as mock_exec:

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
        name="test_step",
        action=StepAction.VALIDATE,
        target=StepTarget.CODE,
        params={}
    )

    handler = ValidateCodeHandler()

    with patch(
        "specweaver.core.flow._validation._resolve_merged_settings", return_value=None
    ), patch(
        "specweaver.core.config.archetype_resolver.ArchetypeResolver"
    ) as mock_resolver_cls, patch(
        "specweaver.core.loom.atoms.code_structure.atom.CodeStructureAtom"
    ) as mock_atom_cls, patch(
        "specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml"
    ) as mock_load, patch(
        "specweaver.assurance.validation.executor.execute_validation_pipeline"
    ) as mock_exec:

        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = None  # Force None
        mock_resolver_cls.return_value = mock_resolver

        mock_atom = MagicMock()
        def run_side_effect(payload):
            res = MagicMock()
            res.status.value = "SUCCESS"
            if payload["intent"] == "extract_skeleton":
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
        mock_atom.run.assert_any_call({"intent": "extract_skeleton", "path": str(code_file)})
        mock_atom.run.assert_any_call({"intent": "extract_framework_markers", "path": str(code_file)})

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
        name="test_step",
        action=StepAction.VALIDATE,
        target=StepTarget.SPEC,
        params={}
    )

    handler = ValidateSpecHandler()

    with patch(
        "specweaver.core.flow._validation._resolve_merged_settings", return_value=None
    ), patch(
        "specweaver.core.config.archetype_resolver.ArchetypeResolver"
    ) as mock_resolver_cls, patch(
        "specweaver.assurance.validation.pipeline_loader.load_pipeline_yaml"
    ) as mock_load, patch(
        "specweaver.assurance.validation.executor.execute_validation_pipeline"
    ) as mock_exec:

        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = None  # Force None
        mock_resolver_cls.return_value = mock_resolver

        mock_pipeline = MagicMock()
        mock_pipeline.steps = []
        mock_load.return_value = mock_pipeline

        mock_exec.return_value = []

        await handler.execute(step, context)

        mock_load.assert_called_once_with("validation_spec_default")
