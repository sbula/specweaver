# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Validation step handlers — spec, code, and test validation."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from specweaver.assurance.validation.models import Status as RuleStatus
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import RunContext, _error_result, _now_iso

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.assurance.validation.models import RuleResult
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.loom.atoms.qa_runner.atom import QARunnerAtom

logger = logging.getLogger(__name__)


def _resolve_merged_settings(context: RunContext, target_path: Path) -> Any:
    """Resolve DAL for the target and overlay validation constraints over settings."""
    from specweaver.commons.enums.dal import DALLevel
    from specweaver.core.config.dal_resolver import DALResolver
    from specweaver.core.config.settings import SpecWeaverSettings, deep_merge_dict

    dal_resolver = DALResolver(context.project_path)
    dal_str = dal_resolver.resolve(target_path)

    if not dal_str and context.db:
        try:
            dal_str = context.db.get_default_dal(context.project_path.name)
        except Exception:
            dal_str = None

    merged_settings = context.settings
    if dal_str and merged_settings and hasattr(merged_settings, "dal_matrix"):
        try:
            dal = DALLevel(dal_str)
            matrix_dict = merged_settings.dal_matrix.matrix
            dal_constraints = matrix_dict.get(dal)
            if dal_constraints:
                base_dict = merged_settings.model_dump()
                constraint_dict = {"validation": dal_constraints.model_dump(exclude_unset=True)}
                merged_dict = deep_merge_dict(base_dict, constraint_dict)
                merged_settings = SpecWeaverSettings.model_validate(merged_dict)
        except Exception as exc:
            logger.warning("Failed to merge DAL '%s' constraints: %s", dal_str, exc)

    return merged_settings


class ValidateSpecHandler:
    """Handler for validate+spec — runs spec validation rules."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        logger.debug("ValidateSpecHandler: validating spec '%s'", context.spec_path.name)
        if not context.spec_path.exists():
            logger.error("ValidateSpecHandler: spec file not found: %s", context.spec_path)
            return _error_result(
                f"Spec file not found: {context.spec_path}",
                started,
            )

        # Resolve spec kind from step params (feature vs component)
        kind_str = step.params.get("kind")

        try:
            merged_settings = _resolve_merged_settings(context, context.spec_path)

            results = await asyncio.to_thread(
                self._run_validation,
                context.spec_path,
                merged_settings,
                kind_str=kind_str,
                project_path=context.project_path,
                analyzer_factory=context.analyzer_factory,
                parsers=context.parsers,
            )
            failed = [r for r in results if r.status == RuleStatus.FAIL]
            all_passed = len(failed) == 0
            logger.info(
                "ValidateSpecHandler: %d rules executed, %d passed, %d failed",
                len(results),
                len(results) - len(failed),
                len(failed),
            )
            return StepResult(
                status=StepStatus.PASSED if all_passed else StepStatus.FAILED,
                output={
                    "results": [
                        {"rule_id": r.rule_id, "status": r.status.value, "message": r.message}
                        for r in results
                    ],
                    "total": len(results),
                    "passed": sum(1 for r in results if r.status != RuleStatus.FAIL),
                    "failed": len(failed),
                },
                error_message="" if all_passed else f"{len(failed)} validation rules failed",
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            logger.exception("ValidateSpecHandler: unhandled exception during spec validation")
            return _error_result(str(exc), started)

    def _run_validation(
        self,
        spec_path: Path,
        settings: Any,
        *,
        kind_str: str | None = None,
        project_path: Path | None = None,
        analyzer_factory: Any | None = None,
        parsers: Any | None = None,
    ) -> list[RuleResult]:
        """Run spec validation via sub-pipeline (called in thread)."""
        # Trigger auto-registration of built-in rules
        import specweaver.assurance.validation.rules.spec  # noqa: F401
        from specweaver.assurance.validation.executor import (
            apply_settings_to_pipeline,
            execute_validation_pipeline,
        )
        from specweaver.assurance.validation.models import (
            RuleResult,  # noqa: F401 — for type narrowing
        )
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
        from specweaver.core.config.archetype_resolver import ArchetypeResolver
        from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom

        archetype = None
        if project_path:
            resolver = ArchetypeResolver(project_path)
            archetype = resolver.resolve(spec_path)

        # Map kind to pipeline name
        pipeline_name = "validation_spec_default"
        if kind_str == "feature":
            pipeline_name = "validation_spec_feature"

        if archetype:
            try:
                pipeline = load_pipeline_yaml(f"{pipeline_name}_{archetype}")
            except Exception:
                pipeline = load_pipeline_yaml(pipeline_name)
        else:
            pipeline = load_pipeline_yaml(pipeline_name)

        if settings is not None:
            pipeline = apply_settings_to_pipeline(
                pipeline, getattr(settings, "validation", settings)
            )

        from specweaver.workflows.evaluators.loader import load_evaluator_schemas

        cwd_path = project_path or spec_path.parent
        schemas = load_evaluator_schemas(project_dir=project_path)
        active_archetype = archetype if archetype else "generic"
        atom = CodeStructureAtom(
            cwd=cwd_path,
            evaluator_schemas=schemas,
            active_archetype=active_archetype,
            parsers=parsers,
        )
        payload_res = atom.run({"intent": "read_file_structure", "path": str(spec_path)})

        ast_payload: dict[str, Any] = {}
        if payload_res.status.value == "SUCCESS":
            ast_payload = payload_res.exports

        for step in pipeline.steps:
            step.params["ast_payload"] = ast_payload

        content = spec_path.read_text(encoding="utf-8")
        return execute_validation_pipeline(
            pipeline,
            content,
            spec_path,
            context={"analyzer_factory": analyzer_factory} if analyzer_factory else None,
        )


class ValidateCodeHandler:
    """Handler for validate+code — runs code validation rules."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        logger.debug("ValidateCodeHandler: looking for code to validate")

        code_path = self._find_code_path(step, context)
        if code_path is None or not code_path.exists():
            logger.warning("ValidateCodeHandler: no code file found to validate")
            return _error_result(
                "No code file found to validate",
                started,
            )

        logger.debug("ValidateCodeHandler: validating code file '%s'", code_path.name)
        try:
            merged_settings = _resolve_merged_settings(context, code_path)
            results = await asyncio.to_thread(
                self._run_validation,
                code_path,
                context.spec_path,
                merged_settings,
                context.project_path,
                analyzer_factory=context.analyzer_factory,
                parsers=context.parsers,
            )
            failed = [r for r in results if r.status == RuleStatus.FAIL]
            all_passed = len(failed) == 0
            logger.info(
                "ValidateCodeHandler: %d rules executed, %d passed, %d failed (code=%s)",
                len(results),
                len(results) - len(failed),
                len(failed),
                code_path.name,
            )
            return StepResult(
                status=StepStatus.PASSED if all_passed else StepStatus.FAILED,
                output={
                    "results": [
                        {"rule_id": r.rule_id, "status": r.status.value, "message": r.message}
                        for r in results
                    ],
                    "total": len(results),
                    "passed": sum(1 for r in results if r.status != RuleStatus.FAIL),
                    "failed": len(failed),
                },
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            logger.exception("ValidateCodeHandler: unhandled exception during code validation")
            return _error_result(str(exc), started)

    def _find_code_path(self, step: PipelineStep, context: RunContext) -> Path | None:
        """Find the code file to validate."""
        if context.output_dir and context.output_dir.exists():
            py_files = list(context.output_dir.glob("*.py"))
            if py_files:
                return py_files[0]
        return None

    def _run_validation(
        self,
        code_path: Path,
        spec_path: Path,
        settings: Any,
        project_path: Path | None = None,
        analyzer_factory: Any | None = None,
        parsers: Any | None = None,
    ) -> list[RuleResult]:
        """Run code validation via sub-pipeline (called in thread)."""
        # Trigger auto-registration of built-in rules
        import specweaver.assurance.validation.rules.code  # noqa: F401
        from specweaver.assurance.validation.executor import (
            apply_settings_to_pipeline,
            execute_validation_pipeline,
        )
        from specweaver.assurance.validation.models import (
            RuleResult,  # noqa: F401 — for type narrowing
        )
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
        from specweaver.core.config.archetype_resolver import ArchetypeResolver
        from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom

        archetype = None
        if project_path:
            resolver = ArchetypeResolver(project_path)
            archetype = resolver.resolve(code_path)

        pipeline_name = f"validation_code_{archetype}" if archetype else "validation_code_default"
        try:
            pipeline = load_pipeline_yaml(pipeline_name)
        except Exception:
            pipeline = load_pipeline_yaml("validation_code_default")

        if settings is not None:
            pipeline = apply_settings_to_pipeline(
                pipeline, getattr(settings, "validation", settings)
            )

        from specweaver.workflows.evaluators.loader import load_evaluator_schemas

        cwd_path = project_path or code_path.parent
        schemas = load_evaluator_schemas(project_dir=project_path)

        # If the pipeline runner natively resolved to an archetype via folder context early out, use it.
        active_arch = archetype if archetype else "generic"
        atom = CodeStructureAtom(
            cwd=cwd_path, evaluator_schemas=schemas, active_archetype=active_arch, parsers=parsers
        )
        payload_res = atom.run({"intent": "read_file_structure", "path": str(code_path)})

        ast_payload: dict[str, Any] = {}
        if payload_res.status.value == "SUCCESS":
            ast_payload = payload_res.exports

        markers_res = atom.run({"intent": "extract_framework_markers", "path": str(code_path)})
        if markers_res.status.value == "SUCCESS" and "markers" in markers_res.exports:
            ast_payload["framework_markers"] = markers_res.exports["markers"]

        for step in pipeline.steps:
            step.params["ast_payload"] = ast_payload

        content = code_path.read_text(encoding="utf-8")
        return execute_validation_pipeline(
            pipeline,
            content,
            spec_path,
            context={"analyzer_factory": analyzer_factory} if analyzer_factory else None,
        )


class ValidateTestsHandler:
    """Runs tests via the QARunnerAtom.

    Step params (optional):
        target: str — test directory (default: "tests/").
        kind: str — "unit", "integration", "e2e" (default: "unit").
        scope: str — module/service filter (default: "").
        timeout: int — seconds (default: 120).
        coverage: bool — measure coverage (default: False).
        coverage_threshold: int — minimum % (default: 70).
    """

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        target = step.params.get("target")
        if not target:
            from specweaver.core.loom.commons.language.scenario_converter_factory import (
                create_scenario_converter,
            )

            converter = create_scenario_converter(context.project_path)
            stem = context.spec_path.stem.replace("_spec", "")
            target_path = converter.output_path(stem, context.project_path)
            target = str(target_path)

        kind = step.params.get("kind", "unit")
        logger.debug("ValidateTestsHandler: running %s tests in '%s'", kind, target)

        atom = self._get_atom(context)
        result = atom.run(
            {
                "intent": "run_tests",
                "target": target,
                "kind": kind,
                "scope": step.params.get("scope", ""),
                "timeout": step.params.get("timeout", 120),
                "coverage": step.params.get("coverage", False),
                "coverage_threshold": step.params.get("coverage_threshold", 70),
                "stale_nodes": context.stale_nodes,
            }
        )

        if result.status.value == "SUCCESS":
            logger.info("ValidateTestsHandler: tests PASSED (kind=%s, target=%s)", kind, target)
            return StepResult(
                status=StepStatus.PASSED,
                output=result.exports,
                started_at=started,
                completed_at=_now_iso(),
            )

        logger.warning(
            "ValidateTestsHandler: tests FAILED (kind=%s, target=%s): %s",
            kind,
            target,
            result.message,
        )
        return StepResult(
            status=StepStatus.FAILED,
            output=result.exports,
            error_message=result.message,
            started_at=started,
            completed_at=_now_iso(),
        )

    def _get_atom(self, context: RunContext) -> QARunnerAtom:
        """Lazily create a QARunnerAtom for the project."""
        from specweaver.core.loom.atoms.qa_runner.atom import QARunnerAtom

        return QARunnerAtom(cwd=context.project_path)
