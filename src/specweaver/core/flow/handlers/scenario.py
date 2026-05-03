# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Scenario pipeline handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import RunContext, _error_result, _now_iso
from specweaver.core.flow.handlers.generation import _resolve_generation_routing

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep

logger = logging.getLogger(__name__)


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

            if not context.spec_path.exists():
                return _error_result(f"Spec file not found: {context.spec_path}", started)
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
                len(scenario_set.scenarios),
                output_path,
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


class ConvertScenarioHandler:
    """Handler for convert+scenario — mechanical YAML to language-native test conversion.

    Language-agnostic: delegates all path decisions to the language-specific
    ``ScenarioConverterInterface.output_path()`` method. Zero language branching here.
    """

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        try:
            from ruamel.yaml import YAML

            from specweaver.workflows.scenarios.scenario_models import ScenarioSet

            # Find scenario YAML from previous step
            scenarios_dir = context.project_path / "scenarios" / "definitions"
            stem = context.spec_path.stem.replace("_spec", "")
            scenario_yaml_path = scenarios_dir / f"{stem}_scenarios.yaml"

            if not scenario_yaml_path.exists():
                return _error_result(f"Scenario YAML not found: {scenario_yaml_path}", started)

            yaml = YAML(typ="safe")
            data = yaml.load(scenario_yaml_path.read_text(encoding="utf-8"))
            scenario_set = ScenarioSet.model_validate(data)

            # Language-agnostic: Atom proxy picks the right converter
            from specweaver.sandbox.language.core.atom import LanguageAtom

            atom = LanguageAtom(cwd=context.project_path)
            res = atom.run(
                {
                    "intent": "convert_scenario",
                    "stem": stem,
                    "scenario_set": scenario_set,
                }
            )
            if res.status == "failed":
                raise ValueError(res.message)

            exports = res.exports or {}
            test_content = exports.get("content", "")
            output_path_str = exports.get("output_path", "")
            if not output_path_str:
                raise ValueError("Atom did not return output path")

            from pathlib import Path

            output_path = Path(output_path_str)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(test_content, encoding="utf-8")

            # Store path in feedback so SF-C arbiter can locate the test file
            context.feedback["scenario_test_path"] = str(output_path)

            logger.info(
                "ConvertScenarioHandler: test file written to '%s'",
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
