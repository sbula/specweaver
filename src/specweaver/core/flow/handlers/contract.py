# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The contract step (`generate+contract`): the spec's Contract section as a file in the run's
language."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.commons.spec_names import module_stem
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.engine.step_outputs import FILES_TOUCHED, touched
from specweaver.core.flow.handlers.base import _error_result, _now_iso
from specweaver.core.flow.run_state.failures import log_step_failure

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.run_state.run_context import RunContext

logger = logging.getLogger(__name__)


class GenerateContractHandler:
    """Handler for generate+contract — extracts API Protocol from spec Contract section.
    This is a mechanical (non-LLM) extraction generating a Protocol class file at contracts/{stem}_contract.py.
    """

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
        """Execute contract generation from spec."""

        started = _now_iso()
        try:
            from specweaver.workflows.implementation.contract_renderers import (
                contract_extension,
                contract_names,
                extract_contract,
                extract_methods,
                render_contract_file,
            )

            spec_text = context.spec_path.read_text(encoding="utf-8")
            contract_section = extract_contract(spec_text)
            if contract_section is None:
                return _error_result("No ## Contract section found in spec", started)

            methods = extract_methods(contract_section)
            if not methods:
                return _error_result(
                    "No Python function signatures found in Contract code blocks",
                    started,
                )

            contracts_dir = context.project_path / "contracts"
            contracts_dir.mkdir(parents=True, exist_ok=True)
            stem = module_stem(context.spec_path)
            class_name = stem.replace("_", " ").title().replace(" ", "")

            from specweaver.core.flow.engine.run_profile import run_task_files

            language = run_task_files(context).language

            contract_content = render_contract_file(language, class_name, methods)
            ext = contract_extension(language)
            output_path = contracts_dir / f"{stem}_contract.{ext}"

            output_path.write_text(contract_content, encoding="utf-8")
            logger.info("GenerateContractHandler: contract written to '%s'", output_path)

            # Wire contract path into RunContext for downstream consumption (SF-B)
            # Frozen, so this is a rebuild-and-replace rather than an append.
            context.graph = context.graph.model_copy(
                update={
                    "api_contract_paths": [
                        *(context.graph.api_contract_paths or []),
                        str(output_path),
                    ]
                }
            )

            return StepResult(
                status=StepStatus.PASSED,
                output={
                    "generated_path": str(output_path),
                    FILES_TOUCHED: touched(output_path, context.project_path),
                    "signature_count": len(methods),
                    "methods": contract_names(methods),
                },
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            log_step_failure(logger, "GenerateContractHandler: unhandled exception")
            return _error_result(str(exc), started)

    @staticmethod
    def _extract_contract(text: str) -> str | None:
        from specweaver.workflows.implementation.contract_renderers import extract_contract

        return extract_contract(text)

    @staticmethod
    def _extract_signatures(contract_text: str) -> list[str]:
        from specweaver.workflows.implementation.contract_renderers import extract_signatures

        return extract_signatures(contract_text)

    @staticmethod
    def _extract_docstrings(contract_text: str) -> dict[str, str]:
        from specweaver.workflows.implementation.contract_renderers import extract_docstrings

        return extract_docstrings(contract_text)
