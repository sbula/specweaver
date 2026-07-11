# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the validation hydrator — QA context bridge."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from specweaver.assurance.validation.pipeline import ValidationPipeline, ValidationStep
from specweaver.core.flow.handlers.validation_hydrator import (
    _serialize_atom_result,
    execute_validation_flow,
    hydrate_code_validation_context,
)
from specweaver.sandbox.base import AtomResult, AtomStatus

if TYPE_CHECKING:
    from pathlib import Path

# Patch targets: QARunnerAtom and execute_validation_pipeline are lazy-imported
# inside functions, so we must patch at the SOURCE module, not the hydrator.
_PATCH_ATOM = "specweaver.sandbox.qa_runner.core.atom.QARunnerAtom"
_PATCH_EXEC = "specweaver.assurance.validation.executor.execute_validation_pipeline"


def _make_pipeline(rule_ids: list[str]) -> ValidationPipeline:
    """Create a minimal pipeline with the given rule IDs."""
    return ValidationPipeline(
        name="test",
        steps=[
            ValidationStep(name=f"step_{rid}", rule=rid)
            for rid in rule_ids
        ],
    )


def _make_atom_result(
    status: AtomStatus = AtomStatus.SUCCESS,
    message: str = "OK",
    exports: dict[str, Any] | None = None,
) -> AtomResult:
    return AtomResult(status=status, message=message, exports=exports or {})


class TestSerializeAtomResult:
    """Tests for _serialize_atom_result — Story #1 and #2."""

    def test_serialize_with_none_exports(self) -> None:
        """[Boundary] None exports should serialize to empty dict."""
        result = AtomResult(status=AtomStatus.SUCCESS, message="OK", exports=None)
        serialized = _serialize_atom_result(result)
        assert serialized["exports"] == {}

    def test_serialize_with_none_message(self) -> None:
        """[Boundary] None message should serialize to empty string."""
        result = AtomResult(status=AtomStatus.SUCCESS, message=None, exports={"a": 1})
        serialized = _serialize_atom_result(result)
        assert serialized["message"] == ""

    def test_serialize_preserves_status_value(self) -> None:
        """[Happy Path] Status enum value is serialized as string."""
        result = _make_atom_result(status=AtomStatus.FAILED)
        serialized = _serialize_atom_result(result)
        assert serialized["status"] == "FAILED"

    def test_serialize_preserves_exports_dict(self) -> None:
        """[Happy Path] Exports dict is passed through unchanged."""
        result = _make_atom_result(exports={"key": "value", "nested": [1, 2]})
        serialized = _serialize_atom_result(result)
        assert serialized["exports"] == {"key": "value", "nested": [1, 2]}


class TestHydrateCodeValidationContext:
    """Tests for hydrate_code_validation_context."""

    def test_hydrates_tests_result_when_c03_active(self, tmp_path: Path) -> None:
        """Pipeline with C03 step → qa_tests_result key populated."""
        pipeline = _make_pipeline(["C03"])
        code_file = tmp_path / "src" / "module.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text("pass\n", encoding="utf-8")
        # Create test file
        test_file = tmp_path / "tests" / "test_module.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("def test(): pass\n", encoding="utf-8")

        mock_result = _make_atom_result(exports={"passed": 1, "failed": 0, "errors": 0})
        with patch(_PATCH_ATOM) as mock_atom_cls:
            mock_atom_cls.return_value.run.return_value = mock_result
            ctx = hydrate_code_validation_context(pipeline, code_file, tmp_path)

        assert "qa_tests_result" in ctx
        assert ctx["qa_tests_result"]["status"] == "SUCCESS"
        assert ctx["qa_tests_result"]["exports"]["passed"] == 1

    def test_hydrates_coverage_result_when_c04_active(self, tmp_path: Path) -> None:
        """Pipeline with C04 step → qa_coverage_result key populated."""
        pipeline = _make_pipeline(["C04"])
        code_file = tmp_path / "src" / "module.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text("pass\n", encoding="utf-8")

        mock_result = _make_atom_result(exports={"coverage_pct": 95.0})
        with patch(_PATCH_ATOM) as mock_atom_cls:
            mock_atom_cls.return_value.run.return_value = mock_result
            ctx = hydrate_code_validation_context(pipeline, code_file, tmp_path)

        assert "qa_coverage_result" in ctx
        assert ctx["qa_coverage_result"]["exports"]["coverage_pct"] == 95.0

    def test_hydrates_architecture_result_when_c05_active(self, tmp_path: Path) -> None:
        """Pipeline with C05 step → qa_architecture_result key populated."""
        pipeline = _make_pipeline(["C05"])
        code_file = tmp_path / "src" / "module.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text("pass\n", encoding="utf-8")

        mock_result = _make_atom_result(exports={"violation_count": 0, "violations": []})
        with patch(_PATCH_ATOM) as mock_atom_cls:
            mock_atom_cls.return_value.run.return_value = mock_result
            ctx = hydrate_code_validation_context(pipeline, code_file, tmp_path)

        assert "qa_architecture_result" in ctx
        assert ctx["qa_architecture_result"]["exports"]["violation_count"] == 0

    def test_skips_all_atoms_when_no_qa_rules_active(self, tmp_path: Path) -> None:
        """Pipeline with only C01/C02 → empty context, QARunnerAtom never instantiated."""
        pipeline = _make_pipeline(["C01", "C02"])
        code_file = tmp_path / "module.py"
        code_file.write_text("pass\n", encoding="utf-8")

        with patch(_PATCH_ATOM) as mock_atom_cls:
            ctx = hydrate_code_validation_context(pipeline, code_file, tmp_path)

        mock_atom_cls.assert_not_called()
        assert ctx == {}

    def test_no_test_file_sets_none_for_c03(self, tmp_path: Path) -> None:
        """C03 active but no test file found → qa_tests_result is None."""
        pipeline = _make_pipeline(["C03"])
        code_file = tmp_path / "src" / "module.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text("pass\n", encoding="utf-8")
        # No tests/ directory at all

        with patch(_PATCH_ATOM) as mock_atom_cls:
            ctx = hydrate_code_validation_context(pipeline, code_file, tmp_path)

        assert ctx["qa_tests_result"] is None
        # Atom was instantiated but run was never called for tests
        mock_atom_cls.return_value.run.assert_not_called()

    def test_atom_exception_produces_error_dict(self, tmp_path: Path) -> None:
        """QARunnerAtom.run() raises → context key is error dict."""
        pipeline = _make_pipeline(["C04"])
        code_file = tmp_path / "src" / "module.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text("pass\n", encoding="utf-8")

        with patch(_PATCH_ATOM) as mock_atom_cls:
            mock_atom_cls.return_value.run.side_effect = RuntimeError("boom")
            ctx = hydrate_code_validation_context(pipeline, code_file, tmp_path)

        assert ctx["qa_coverage_result"]["status"] == "FAILED"
        assert "Hydration error" in ctx["qa_coverage_result"]["message"]

    # --- NEW: Story #3 — Multiple test file matches picks first ---
    def test_multiple_test_files_picks_first_match(self, tmp_path: Path) -> None:
        """[Boundary] Multiple test_module.py matches → first one is used."""
        pipeline = _make_pipeline(["C03"])
        code_file = tmp_path / "src" / "module.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text("pass\n", encoding="utf-8")

        # Create two test files in different subdirs
        test_a = tmp_path / "tests" / "unit" / "test_module.py"
        test_a.parent.mkdir(parents=True, exist_ok=True)
        test_a.write_text("def test_a(): pass\n", encoding="utf-8")
        test_b = tmp_path / "tests" / "integration" / "test_module.py"
        test_b.parent.mkdir(parents=True, exist_ok=True)
        test_b.write_text("def test_b(): pass\n", encoding="utf-8")

        mock_result = _make_atom_result(exports={"passed": 1, "failed": 0, "errors": 0})
        with patch(_PATCH_ATOM) as mock_atom_cls:
            mock_atom_cls.return_value.run.return_value = mock_result
            ctx = hydrate_code_validation_context(pipeline, code_file, tmp_path)

        # Should have called run (first match selected)
        assert ctx["qa_tests_result"] is not None
        assert ctx["qa_tests_result"]["status"] == "SUCCESS"
        mock_atom_cls.return_value.run.assert_called_once()

    # --- NEW: Story #4 — Empty pipeline steps ---
    def test_empty_pipeline_returns_empty_context(self, tmp_path: Path) -> None:
        """[Hostile] Pipeline with no steps at all → empty context, no atoms run."""
        pipeline = _make_pipeline([])
        code_file = tmp_path / "module.py"
        code_file.write_text("pass\n", encoding="utf-8")

        with patch(_PATCH_ATOM) as mock_atom_cls:
            ctx = hydrate_code_validation_context(pipeline, code_file, tmp_path)

        mock_atom_cls.assert_not_called()
        assert ctx == {}


class TestExecuteValidationFlow:
    """Tests for execute_validation_flow."""

    def test_calls_pipeline_with_merged_context(self, tmp_path: Path) -> None:
        """execute_validation_flow calls execute_validation_pipeline with merged context."""
        pipeline = _make_pipeline(["C01"])  # No QA rules
        code_file = tmp_path / "module.py"
        code_file.write_text("pass\n", encoding="utf-8")

        with patch(_PATCH_EXEC) as mock_exec:
            mock_exec.return_value = []
            result = execute_validation_flow(
                pipeline, "pass\n", spec_path=code_file, project_root=tmp_path
            )

        mock_exec.assert_called_once()
        assert result == []

    def test_merges_extra_context(self, tmp_path: Path) -> None:
        """Extra context arg is merged with hydrated QA context."""
        pipeline = _make_pipeline(["C01"])  # No QA rules
        code_file = tmp_path / "module.py"
        code_file.write_text("pass\n", encoding="utf-8")

        with patch(_PATCH_EXEC) as mock_exec:
            mock_exec.return_value = []
            execute_validation_flow(
                pipeline,
                "pass\n",
                spec_path=code_file,
                project_root=tmp_path,
                context={"analyzer_factory": "mock_factory"},
            )

        call_kwargs = mock_exec.call_args
        passed_context = call_kwargs.kwargs.get("context") or call_kwargs[1].get("context")
        assert passed_context is not None
        assert passed_context["analyzer_factory"] == "mock_factory"

    # --- NEW: Story #5 — spec_path but no project_root skips hydration ---
    def test_spec_path_without_project_root_skips_hydration(self, tmp_path: Path) -> None:
        """[Boundary] spec_path provided but project_root=None → hydration skipped."""
        pipeline = _make_pipeline(["C03"])
        code_file = tmp_path / "module.py"
        code_file.write_text("pass\n", encoding="utf-8")

        with patch(_PATCH_ATOM) as mock_atom_cls, patch(_PATCH_EXEC) as mock_exec:
            mock_exec.return_value = []
            execute_validation_flow(
                pipeline, "pass\n", spec_path=code_file, project_root=None
            )

        # QARunnerAtom should never be instantiated
        mock_atom_cls.assert_not_called()

    # --- NEW: Story #6 — dal_level forwarded to hydrator ---
    def test_dal_level_forwarded_to_hydrator(self, tmp_path: Path) -> None:
        """[Happy Path] dal_level is passed through to hydrate_code_validation_context."""
        pipeline = _make_pipeline(["C05"])
        code_file = tmp_path / "src" / "module.py"
        code_file.parent.mkdir(parents=True, exist_ok=True)
        code_file.write_text("pass\n", encoding="utf-8")

        mock_result = _make_atom_result(exports={"violation_count": 0, "violations": []})
        with patch(_PATCH_ATOM) as mock_atom_cls, patch(_PATCH_EXEC) as mock_exec:
            mock_atom_cls.return_value.run.return_value = mock_result
            mock_exec.return_value = []
            execute_validation_flow(
                pipeline,
                "pass\n",
                spec_path=code_file,
                project_root=tmp_path,
                dal_level="strict",
            )

        # Verify atom.run was called with dal_level
        run_call = mock_atom_cls.return_value.run.call_args
        assert run_call[0][0]["dal_level"] == "strict"
