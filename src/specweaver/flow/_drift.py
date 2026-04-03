# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Drift check step handler — structural validation with AST and LLM root-cause."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.flow._base import RunContext, _error_result, _now_iso
from specweaver.flow.state import StepResult, StepStatus

if TYPE_CHECKING:
    from specweaver.flow.models import PipelineStep

logger = logging.getLogger(__name__)


def _load_plan(plan_path: str) -> Any:
    """Load the PlanArtifact via ruamel.yaml or json."""
    p = Path(plan_path)
    if not p.exists():
        raise FileNotFoundError(f"Plan file not found: {plan_path}")
    content = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        import ruamel.yaml

        y = ruamel.yaml.YAML(typ="safe")
        data = y.load(content)
    else:
        data = json.loads(content)

    from specweaver.planning.models import PlanArtifact

    return PlanArtifact.model_validate(data)


class DriftCheckHandler:
    """Handler for detect+drift — checks AST drift against PlanArtifact."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        """Execute the drift check."""
        started = _now_iso()

        target_path_str = step.params.get("target_path")
        if not target_path_str:
            return _error_result("Missing 'target_path' in step params.", started)

        plan_path_str = step.params.get("plan_path")
        if not plan_path_str:
            return _error_result("Missing 'plan_path' in step params.", started)

        target_path = Path(target_path_str)
        if not target_path.exists():
            return _error_result(f"Target file not found: {target_path}", started)

        try:
            plan = _load_plan(plan_path_str)
        except Exception as exc:
            return _error_result(f"Failed to load PlanArtifact: {exc}", started)

        try:
            content = target_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return _error_result("Target file is not valid UTF-8.", started)

        try:
            import tree_sitter
            import tree_sitter_python

            parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_python.language()))
            tree = parser.parse(content.encode("utf-8"))
        except Exception as exc:
            return _error_result(f"Failed to parse AST: {exc}", started)

        try:
            rel_path = target_path.relative_to(context.project_path)
            file_path_str = str(rel_path).replace("\\", "/")
        except ValueError:
            file_path_str = target_path.name

        from specweaver.validation.drift_detector import detect_drift

        report = detect_drift(file_ast=tree, plan=plan, file_path=file_path_str)

        # Optional LLM Analysis
        analyze = step.params.get("analyze", False)
        llm_analysis = None

        if analyze and report.is_drifted and context.llm:
            llm_analysis = await self._analyze_drift(context, report, target_path_str)

        output = {
            "is_drifted": report.is_drifted,
            "drift_count": len(report.findings),
            "findings": [f.__dict__ for f in report.findings],
        }
        if llm_analysis:
            output["llm_root_cause"] = llm_analysis

        status = StepStatus.PASSED if not report.is_drifted else StepStatus.FAILED

        return StepResult(
            status=status,
            output=output,
            started_at=started,
            completed_at=_now_iso(),
            error_message="Drift detected" if report.is_drifted else "",
        )

    async def _analyze_drift(self, context: RunContext, report: Any, file_path: str) -> str:
        """Invoke LLM to determine drift root cause."""
        from specweaver.llm.models import Message, Role

        prompt = (
            f"You are investigating architectural drift in {file_path}.\n"
            f"The AST Drift Engine found {len(report.findings)} violations:\n"
        )
        for f in report.findings:
            prompt += f"- {f.severity.name}: {f.description}\n"
        prompt += "\nExplain the root cause of these discrepancies concisely."

        messages = [
            Message(
                role=Role.SYSTEM, content="You are a code architecture expert diagnosing AST drift."
            ),
            Message(role=Role.USER, content=prompt),
        ]

        try:
            # Check for config (we don't strictly require context.config for test harnesses)
            from specweaver.llm.models import GenerationConfig

            config = (
                context.config.llm
                if getattr(context, "config", None) and hasattr(context.config, "llm")
                else GenerationConfig(model="gemini-3-flash-preview")
            )
            response = await context.llm.generate(messages, config)
            return str(response.text)
        except Exception as exc:
            logger.exception("DriftCheckHandler: Failed LLM root-cause analysis.")
            return f"LLM analysis failed: {exc}"
