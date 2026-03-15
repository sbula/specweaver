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

from pydantic import BaseModel, ConfigDict, Field

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
    feedback: dict[str, Any] = Field(default_factory=dict)


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
# Validate tests handler
# ---------------------------------------------------------------------------


class ValidateTestsHandler:
    """Runs tests via the TestRunnerAtom.

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

        atom = self._get_atom(context)
        result = atom.run({
            "intent": "run_tests",
            "target": step.params.get("target", "tests/"),
            "kind": step.params.get("kind", "unit"),
            "scope": step.params.get("scope", ""),
            "timeout": step.params.get("timeout", 120),
            "coverage": step.params.get("coverage", False),
            "coverage_threshold": step.params.get("coverage_threshold", 70),
        })

        if result.status.value == "SUCCESS":
            return StepResult(
                status=StepStatus.PASSED,
                output=result.exports,
                started_at=started,
                completed_at=_now_iso(),
            )

        return StepResult(
            status=StepStatus.FAILED,
            output=result.exports,
            error_message=result.message,
            started_at=started,
            completed_at=_now_iso(),
        )

    def _get_atom(self, context: RunContext):
        """Lazily create a TestRunnerAtom for the project."""
        from specweaver.loom.atoms.test_runner.atom import TestRunnerAtom
        return TestRunnerAtom(cwd=context.project_path)


# ---------------------------------------------------------------------------
# Lint-fix reflection loop
# ---------------------------------------------------------------------------


class LintFixHandler:
    """Handler for lint_fix+code — lint-fix reflection loop.

    Runs the linter on generated code. If errors are found, feeds them
    to the LLM to generate fixes, then re-lints. Repeats up to
    ``max_reflections`` times (from ``step.params``).

    Inspired by Aider's ``max_reflections`` pattern.

    Step params:
        target: str — file or directory to lint (default: "src/").
        max_reflections: int — max fix cycles (default: 3).
    """

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        max_reflections: int = step.params.get("max_reflections", 3)
        target: str = step.params.get("target", "src/")

        atom = self._get_atom(context)
        reflections_used = 0
        last_error_count = 0

        # Initial lint
        lint_result = atom.run({"intent": "run_linter", "target": target})
        last_error_count = lint_result.exports.get("error_count", 0) if lint_result.exports else 0

        # Clean on first run → done
        if last_error_count == 0:
            return StepResult(
                status=StepStatus.PASSED,
                output={
                    "reflections_used": 0,
                    "lint_errors_remaining": 0,
                    "auto_fixed": False,
                },
                started_at=started,
                completed_at=_now_iso(),
            )

        # Phase 1: Try ruff auto-fix first (cheaper than LLM)
        atom.run({
            "intent": "run_linter",
            "target": target,
            "fix": True,
        })
        # Re-lint to see what remains after auto-fix
        lint_result = atom.run({"intent": "run_linter", "target": target})
        last_error_count = (
            lint_result.exports.get("error_count", 0)
            if lint_result.exports else 0
        )

        if last_error_count == 0:
            return StepResult(
                status=StepStatus.PASSED,
                output={
                    "reflections_used": 0,
                    "lint_errors_remaining": 0,
                    "auto_fixed": True,
                },
                started_at=started,
                completed_at=_now_iso(),
            )

        # Phase 2: LLM reflection loop for remaining errors
        for _ in range(max_reflections):
            # No LLM → can't fix
            if context.llm is None:
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message="Lint errors found but no LLM configured for auto-fix",
                    output={
                        "reflections_used": reflections_used,
                        "lint_errors_remaining": last_error_count,
                    },
                    started_at=started,
                    completed_at=_now_iso(),
                )

            # Find code to fix
            code_files = self._find_code_files(context)
            if not code_files:
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message="No code files found to fix",
                    output={
                        "reflections_used": reflections_used,
                        "lint_errors_remaining": last_error_count,
                    },
                    started_at=started,
                    completed_at=_now_iso(),
                )

            # Ask LLM to fix
            try:
                await self._llm_fix(
                    context.llm,
                    code_files[0],
                    lint_result.exports.get("errors", []) if lint_result.exports else [],
                )
            except Exception as exc:
                return StepResult(
                    status=StepStatus.ERROR,
                    error_message=str(exc),
                    output={
                        "reflections_used": reflections_used,
                        "lint_errors_remaining": last_error_count,
                    },
                    started_at=started,
                    completed_at=_now_iso(),
                )

            reflections_used += 1

            # Re-lint
            lint_result = atom.run({"intent": "run_linter", "target": target})
            last_error_count = (
                lint_result.exports.get("error_count", 0)
                if lint_result.exports else 0
            )

            if last_error_count == 0:
                return StepResult(
                    status=StepStatus.PASSED,
                    output={
                        "reflections_used": reflections_used,
                        "lint_errors_remaining": 0,
                    },
                    started_at=started,
                    completed_at=_now_iso(),
                )

        # Exhausted
        return StepResult(
            status=StepStatus.FAILED,
            output={
                "reflections_used": reflections_used,
                "lint_errors_remaining": last_error_count,
            },
            error_message=f"Lint-fix exhausted after {reflections_used} reflections, "
                          f"{last_error_count} errors remain",
            started_at=started,
            completed_at=_now_iso(),
        )

    def _get_atom(self, context: RunContext):
        """Lazily create a TestRunnerAtom for the project."""
        from specweaver.loom.atoms.test_runner.atom import TestRunnerAtom
        return TestRunnerAtom(cwd=context.project_path)

    def _find_code_files(self, context: RunContext) -> list[Path]:
        """Find Python files in the output directory."""
        if context.output_dir and context.output_dir.exists():
            return list(context.output_dir.glob("*.py"))
        return []

    async def _llm_fix(
        self,
        llm: Any,
        code_path: Path,
        lint_errors: list[dict],
    ) -> None:
        """Ask the LLM to fix lint errors in the given file."""
        code = code_path.read_text(encoding="utf-8")
        error_summary = "\n".join(
            f"- {e.get('file', '?')}:{e.get('line', '?')} [{e.get('code', '?')}] {e.get('message', '')}"
            for e in lint_errors
        )

        prompt = (
            f"Fix the following lint errors in this Python file.\n\n"
            f"## Lint Errors\n{error_summary}\n\n"
            f"## Current Code\n```python\n{code}\n```\n\n"
            f"Return ONLY the fixed Python code, no explanations."
        )

        response = await llm.generate(prompt)

        fixed_code = response.text.strip()
        # Strip markdown fences if present
        if fixed_code.startswith("```"):
            lines = fixed_code.split("\n")
            lines = [line for line in lines if not line.startswith("```")]
            fixed_code = "\n".join(lines)

        code_path.write_text(fixed_code + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class StepHandlerRegistry:
    """Maps (action, target) pairs to handler instances.

    Pre-populates with all valid step combinations.
    """

    def __init__(self) -> None:
        self._handlers: dict[tuple[StepAction, StepTarget], StepHandler] = {
            (StepAction.DRAFT, StepTarget.SPEC): DraftSpecHandler(),
            (StepAction.VALIDATE, StepTarget.SPEC): ValidateSpecHandler(),
            (StepAction.VALIDATE, StepTarget.CODE): ValidateCodeHandler(),
            (StepAction.VALIDATE, StepTarget.TESTS): ValidateTestsHandler(),
            (StepAction.REVIEW, StepTarget.SPEC): ReviewSpecHandler(),
            (StepAction.REVIEW, StepTarget.CODE): ReviewCodeHandler(),
            (StepAction.GENERATE, StepTarget.CODE): GenerateCodeHandler(),
            (StepAction.GENERATE, StepTarget.TESTS): GenerateTestsHandler(),
            (StepAction.LINT_FIX, StepTarget.CODE): LintFixHandler(),
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

