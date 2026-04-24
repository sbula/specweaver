# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Lint-fix reflection loop handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import RunContext, _now_iso

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.loom.atoms.qa_runner.atom import QARunnerAtom

logger = logging.getLogger(__name__)


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

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:  # noqa: C901
        started = _now_iso()
        max_reflections: int = step.params.get("max_reflections", 3)
        target: str = step.params.get("target", "src/")
        logger.debug(
            "LintFixHandler: starting lint-fix loop (target=%s, max_reflections=%d)",
            target,
            max_reflections,
        )

        atom = self._get_atom(context)
        reflections_used = 0
        last_error_count = 0

        # Resolve targets topologically if stale_nodes is present
        if context.stale_nodes is not None:
            target_path = (context.project_path / target).resolve()
            all_py = []
            if target_path.is_file():
                all_py = [target_path]
            elif target_path.is_dir():
                all_py = list(target_path.rglob("*.py"))

            resolved_abs = [str(f) for f in all_py if str(f) in context.stale_nodes]
            from pathlib import Path
            resolved_targets = [str(Path(t).relative_to(context.project_path)) for t in resolved_abs]
            run_kwargs: dict[str, Any] = {"intent": "run_linter", "targets": resolved_targets}
        else:
            run_kwargs: dict[str, Any] = {"intent": "run_linter", "target": target}

        # Initial lint
        lint_result = atom.run(run_kwargs)
        last_error_count = lint_result.exports.get("error_count", 0) if lint_result.exports else 0
        logger.debug("LintFixHandler: initial lint found %d errors", last_error_count)

        # Clean on first run → done
        if last_error_count == 0:
            logger.info("LintFixHandler: code is clean — no lint errors")
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
        logger.info("LintFixHandler: attempting ruff auto-fix on %d errors", last_error_count)
        fix_kwargs = dict(run_kwargs)
        fix_kwargs["fix"] = True
        atom.run(fix_kwargs)

        # Re-lint to see what remains after auto-fix
        lint_result = atom.run(run_kwargs)
        last_error_count = lint_result.exports.get("error_count", 0) if lint_result.exports else 0
        logger.debug("LintFixHandler: after auto-fix, %d errors remain", last_error_count)

        if last_error_count == 0:
            logger.info("LintFixHandler: all errors resolved by ruff auto-fix")
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
                logger.debug(
                    "LintFixHandler: LLM reflection %d/%d on '%s'",
                    reflections_used + 1,
                    max_reflections,
                    code_files[0].name,
                )
                await self._llm_fix(
                    context.llm,
                    code_files[0],
                    lint_result.exports.get("errors", []) if lint_result.exports else [],
                    context=context,
                )
            except Exception as exc:
                logger.exception(
                    "LintFixHandler: LLM fix failed on reflection %d", reflections_used + 1
                )
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
            lint_result = atom.run(run_kwargs)
            last_error_count = (
                lint_result.exports.get("error_count", 0) if lint_result.exports else 0
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
        logger.warning(
            "LintFixHandler: exhausted after %d reflections, %d errors remain",
            reflections_used,
            last_error_count,
        )
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

    def _get_atom(self, context: RunContext) -> QARunnerAtom:
        """Lazily create a QARunnerAtom for the project."""
        from specweaver.core.loom.atoms.qa_runner.atom import QARunnerAtom

        return QARunnerAtom(cwd=context.project_path)

    def _find_code_files(self, context: RunContext) -> list[Path]:
        """Find Python files in the output directory."""
        if context.output_dir and context.output_dir.exists():
            return list(context.output_dir.glob("*.py"))
        return []

    async def _llm_fix(
        self,
        llm: Any,
        code_path: Path,
        lint_errors: list[dict[str, object]],
        *,
        context: RunContext,
    ) -> None:
        """Ask the LLM to fix lint errors in the given file."""
        from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role, TaskType

        code = code_path.read_text(encoding="utf-8")
        from specweaver.infrastructure.llm.lineage import extract_artifact_uuid, wrap_artifact_tag

        artifact_uuid = extract_artifact_uuid(code)

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

        if artifact_uuid:
            tag_str = wrap_artifact_tag(artifact_uuid, "python")
            if tag_str:
                prompt += f"\n\nIMPORTANT: You MUST include the exact string '{tag_str}' physically at the very top of your output file."

        messages = [Message(role=Role.USER, content=prompt)]

        # Base config from project default (fallback)
        if context.config is not None:
            base_config = GenerationConfig(
                model=context.config.llm.model,
                temperature=0.1,  # low creativity — fix, not invent
                max_output_tokens=context.config.llm.max_output_tokens,
                task_type=TaskType.CHECK,
                run_id=getattr(context, "run_id", "") or "",
            )
        else:
            base_config = GenerationConfig(
                model="gemini-3-flash-preview",
                temperature=0.1,
                max_output_tokens=4096,
                task_type=TaskType.CHECK,
                run_id=getattr(context, "run_id", "") or "",
            )

        # Routing resolution — same pattern as all other handlers
        routed = (
            context.llm_router.get_for_task(TaskType.CHECK)
            if getattr(context, "llm_router", None)
            else None
        )
        adapter = routed.adapter if routed else llm
        config = (
            GenerationConfig(
                model=routed.model,
                temperature=routed.temperature,
                max_output_tokens=routed.max_output_tokens,
                task_type=TaskType.CHECK,
                run_id=getattr(context, "run_id", "") or "",
            )
            if routed
            else base_config
        )

        response = await adapter.generate(messages, config)

        fixed_code = response.text.strip()
        # Strip markdown fences if present
        if fixed_code.startswith("```"):
            lines = fixed_code.split("\n")
            lines = [line for line in lines if not line.startswith("```")]
            fixed_code = "\n".join(lines)

        # Safety fallback
        if artifact_uuid and not extract_artifact_uuid(fixed_code):
            tag_str = wrap_artifact_tag(artifact_uuid, "python")
            if tag_str:
                fixed_code = tag_str + "\n" + fixed_code

        code_path.write_text(fixed_code + "\n", encoding="utf-8")

        if (
            artifact_uuid
            and getattr(context, "db", None)
            and hasattr(context.db, "log_artifact_event")
        ):
            context.db.log_artifact_event(
                artifact_id=artifact_uuid,
                parent_id=None,
                run_id=getattr(context, "run_id", "") or "",
                event_type="lint_fixed",
                model_id=config.model if config else "unknown",
            )
