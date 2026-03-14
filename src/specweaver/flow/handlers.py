# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Step handlers — bridge between pipeline steps and existing modules.

Each handler adapts a ``(action, target)`` pair to the corresponding
SpecWeaver module (Drafter, Reviewer, Generator, validation runner).
Handlers are thin wrappers: they build the right arguments, call the
module, and translate the result into a ``StepResult``.

Sync modules (validation) are wrapped in ``asyncio.to_thread()`` to
avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003 — Pydantic needs Path at runtime
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from specweaver.flow.models import PipelineStep, StepAction, StepTarget
from specweaver.flow.state import StepResult, StepStatus
from specweaver.validation.models import Status as RuleStatus

# ---------------------------------------------------------------------------
# RunContext — everything a handler needs
# ---------------------------------------------------------------------------


class RunContext(BaseModel):
    """Execution context passed to every step handler.

    Attributes:
        project_path: Root directory of the target project.
        spec_path: Path to the spec being processed.
        llm: LLM adapter (None for validate-only pipelines).
        context_provider: For HITL-interactive steps (draft).
        topology: Project graph topology context.
        settings: Per-project validation settings/overrides.
        output_dir: Output directory for generated code/tests.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    project_path: Path
    spec_path: Path
    llm: Any = None  # LLMAdapter | None — Any to avoid import issues
    context_provider: Any = None  # ContextProvider | None
    topology: Any = None  # TopologyContext | None
    settings: Any = None  # ValidationSettings | None
    output_dir: Path | None = None


# ---------------------------------------------------------------------------
# Handler protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class StepHandler(Protocol):
    """Protocol for step execution handlers."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _error_result(message: str, started_at: str) -> StepResult:
    return StepResult(
        status=StepStatus.ERROR,
        error_message=message,
        started_at=started_at,
        completed_at=_now_iso(),
    )


# ---------------------------------------------------------------------------
# Validate handlers
# ---------------------------------------------------------------------------


class ValidateSpecHandler:
    """Handler for validate+spec — runs spec validation rules."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if not context.spec_path.exists():
            return _error_result(
                f"Spec file not found: {context.spec_path}",
                started,
            )

        try:
            results = await asyncio.to_thread(
                self._run_validation,
                context.spec_path,
                context.settings,
            )
            failed = [r for r in results if r.status == RuleStatus.FAIL]
            all_passed = len(failed) == 0
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
            return _error_result(str(exc), started)

    def _run_validation(
        self,
        spec_path: Path,
        settings: Any,
    ) -> list:
        """Run spec validation rules (called in thread)."""
        from specweaver.validation.runner import get_spec_rules, run_rules

        rules = get_spec_rules(include_llm=False, settings=settings)
        content = spec_path.read_text(encoding="utf-8")
        return run_rules(rules, content)


class ValidateCodeHandler:
    """Handler for validate+code — runs code validation rules."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()

        code_path = self._find_code_path(step, context)
        if code_path is None or not code_path.exists():
            return _error_result(
                "No code file found to validate",
                started,
            )

        try:
            results = await asyncio.to_thread(
                self._run_validation,
                code_path,
                context.spec_path,
                context.settings,
            )
            failed = [r for r in results if r.status == RuleStatus.FAIL]
            all_passed = len(failed) == 0
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
    ) -> list:
        """Run code validation rules (called in thread)."""
        from specweaver.validation.runner import get_code_rules, run_rules

        rules = get_code_rules(include_subprocess=False, settings=settings)
        content = code_path.read_text(encoding="utf-8")
        return run_rules(rules, content, spec_path=spec_path)


# ---------------------------------------------------------------------------
# Review handlers
# ---------------------------------------------------------------------------


class ReviewSpecHandler:
    """Handler for review+spec — LLM-based spec review."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if context.llm is None:
            return _error_result("LLM adapter required for review steps", started)

        try:
            from specweaver.review.reviewer import Reviewer

            reviewer = Reviewer(context.llm)
            result = await reviewer.review_spec(
                context.spec_path,
                topology_contexts=([context.topology] if context.topology else None),
            )
            return StepResult(
                status=StepStatus.PASSED
                if result.verdict.value == "accepted"
                else StepStatus.FAILED,
                output={
                    "verdict": result.verdict.value,
                    "summary": result.summary,
                    "findings_count": len(result.findings),
                },
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            return _error_result(str(exc), started)


class ReviewCodeHandler:
    """Handler for review+code — LLM-based code review."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if context.llm is None:
            return _error_result("LLM adapter required for review steps", started)

        try:
            from specweaver.review.reviewer import Reviewer

            code_path = self._find_code_path(context)
            if code_path is None:
                return _error_result("No code file found for review", started)

            reviewer = Reviewer(context.llm)
            result = await reviewer.review_code(
                code_path,
                context.spec_path,
                topology_contexts=([context.topology] if context.topology else None),
            )
            return StepResult(
                status=StepStatus.PASSED
                if result.verdict.value == "accepted"
                else StepStatus.FAILED,
                output={
                    "verdict": result.verdict.value,
                    "summary": result.summary,
                    "findings_count": len(result.findings),
                },
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            return _error_result(str(exc), started)

    def _find_code_path(self, context: RunContext) -> Path | None:
        if context.output_dir and context.output_dir.exists():
            py_files = list(context.output_dir.glob("*.py"))
            if py_files:
                return py_files[0]
        return None


# ---------------------------------------------------------------------------
# Generate handlers
# ---------------------------------------------------------------------------


class GenerateCodeHandler:
    """Handler for generate+code — LLM code generation."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if context.llm is None:
            return _error_result("LLM adapter required for generate steps", started)

        try:
            from specweaver.implementation.generator import Generator

            generator = Generator(context.llm)
            output_dir = context.output_dir or context.project_path / "src"
            output_path = output_dir / f"{context.spec_path.stem.replace('_spec', '')}.py"

            generated = await generator.generate_code(
                context.spec_path,
                output_path,
                topology_contexts=([context.topology] if context.topology else None),
            )
            return StepResult(
                status=StepStatus.PASSED,
                output={"generated_path": str(generated)},
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            return _error_result(str(exc), started)


class GenerateTestsHandler:
    """Handler for generate+tests — LLM test generation."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if context.llm is None:
            return _error_result("LLM adapter required for generate steps", started)

        try:
            from specweaver.implementation.generator import Generator

            generator = Generator(context.llm)
            output_dir = context.output_dir or context.project_path / "tests"
            output_path = output_dir / f"test_{context.spec_path.stem.replace('_spec', '')}.py"

            generated = await generator.generate_tests(
                context.spec_path,
                output_path,
                topology_contexts=([context.topology] if context.topology else None),
            )
            return StepResult(
                status=StepStatus.PASSED,
                output={"generated_path": str(generated)},
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            return _error_result(str(exc), started)


# ---------------------------------------------------------------------------
# Draft handler (HITL parking)
# ---------------------------------------------------------------------------


class DraftSpecHandler:
    """Handler for draft+spec — parks if spec doesn't exist yet."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()

        # If spec already exists, consider the draft step pre-completed
        if context.spec_path.exists():
            return StepResult(
                status=StepStatus.PASSED,
                output={"message": f"Spec already exists: {context.spec_path}"},
                started_at=started,
                completed_at=_now_iso(),
            )

        # Spec doesn't exist — park and tell the user
        return StepResult(
            status=StepStatus.WAITING_FOR_INPUT,
            output={
                "message": (
                    f"Spec file not found: {context.spec_path}. "
                    "Please create it using 'sw draft' and then resume with 'sw run --resume'."
                ),
            },
            started_at=started,
            completed_at=_now_iso(),
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class StepHandlerRegistry:
    """Maps (action, target) pairs to handler instances.

    Pre-populates with all 7 valid step combinations.
    """

    def __init__(self) -> None:
        self._handlers: dict[tuple[StepAction, StepTarget], StepHandler] = {
            (StepAction.DRAFT, StepTarget.SPEC): DraftSpecHandler(),
            (StepAction.VALIDATE, StepTarget.SPEC): ValidateSpecHandler(),
            (StepAction.VALIDATE, StepTarget.CODE): ValidateCodeHandler(),
            (StepAction.REVIEW, StepTarget.SPEC): ReviewSpecHandler(),
            (StepAction.REVIEW, StepTarget.CODE): ReviewCodeHandler(),
            (StepAction.GENERATE, StepTarget.CODE): GenerateCodeHandler(),
            (StepAction.GENERATE, StepTarget.TESTS): GenerateTestsHandler(),
        }

    def get(
        self,
        action: StepAction,
        target: StepTarget,
    ) -> StepHandler | None:
        """Get the handler for a given action+target, or None."""
        return self._handlers.get((action, target))

    def register(
        self,
        action: StepAction,
        target: StepTarget,
        handler: StepHandler,
    ) -> None:
        """Register a custom handler (for testing or extensions)."""
        self._handlers[(action, target)] = handler
