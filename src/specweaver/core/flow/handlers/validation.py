# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Validation step handlers — spec, code, and test validation."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from specweaver.assurance.validation.models import Status as RuleStatus
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import _error_result, _now_iso
from specweaver.core.flow.handlers.coder_sandbox import coder_sandbox
from specweaver.core.flow.handlers.qa_targets import (
    WHOLE_PROJECT,
    default_test_target,
    generated_code,
    in_scenarios_mount,
    names_one_file,
    requirement_coverage_of,
    scenarios_root,
)

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.assurance.validation.models import RuleResult
    from specweaver.commons.enums.dal import DALLevel
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.run_context import RunContext
    from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

logger = logging.getLogger(__name__)


def target_dal(context: RunContext, target_path: Path) -> DALLevel:
    """The target's DAL: its nearest `context.yaml`, else its project's default, else `DAL_C`."""
    from specweaver.core.config.dal_resolver import DALResolver
    from specweaver.core.flow.engine.registered import registered
    from specweaver.workspace.store import DEFAULT_DAL, default_dal_at

    dal = DALResolver(context.project_path).resolve(target_path)
    if dal is None:
        dal = registered(context, default_dal_at, "default DAL")
    return dal or DEFAULT_DAL


async def _resolve_merged_settings(context: RunContext, target_path: Path) -> Any:
    """Resolve DAL for the target and overlay validation constraints over settings."""
    from specweaver.core.config.settings import SpecWeaverSettings, deep_merge_dict

    dal_str = target_dal(context, target_path)

    merged_settings = context.settings
    if dal_str and merged_settings and hasattr(merged_settings, "dal_matrix"):
        dal_constraints = merged_settings.dal_matrix.matrix.get(dal_str)
        if dal_constraints:
            base_dict = merged_settings.model_dump()
            constraint_dict = {"validation": dal_constraints.model_dump(exclude_unset=True)}
            try:
                merged_settings = SpecWeaverSettings.model_validate(
                    deep_merge_dict(base_dict, constraint_dict)
                )
            except Exception as exc:
                # Judging the file without its tier's rules would pass what the tier forbids.
                msg = f"cannot apply the {dal_str} rules: {exc}"
                raise ValueError(msg) from exc

    return merged_settings


def _rule_payload(results: list[RuleResult]) -> list[dict[str, Any]]:
    """One dict per rule, carrying its findings **without loss**.

    The rules compute a `Finding` per issue — message, line, severity, suggestion — and a boundary
    that keeps only `rule_id`/`status`/`message` discards every locator and every
    suggestion the rules had just worked out.

    Two things are deliberate:

    * **`severity` is emitted as `.value`** for symmetry with `status` above. `Severity` is a
      `StrEnum`, so while that holds this is cosmetic: `f.severity` and `f.severity.value` are
      indistinguishable to both `json.dumps` and `==`, and a mutant swapping them is **equivalent**.
      It stops being cosmetic the moment `Severity` becomes a plain `Enum`,
      at which point `default=str` writes `"Severity.ERROR"`; the test pins the `StrEnum` so that
      change fails loudly rather than silently corrupting every persisted payload.
    * **`findings` is always present**, empty list included, so a consumer never needs `.get`.

    Shared by both call sites on purpose: they built byte-identical payloads, and wiring one while
    forgetting the other is invisible to a test of this function alone.
    """
    return [
        {
            "rule_id": r.rule_id,
            "status": r.status.value,
            "message": r.message,
            "findings": [
                {
                    "message": f.message,
                    "line": f.line,
                    "severity": f.severity.value,
                    "suggestion": f.suggestion,
                }
                for f in r.findings
            ],
        }
        for r in results
    ]


def _validation_output(
    results: list[RuleResult], *, strict: bool = False
) -> tuple[dict[str, Any], int]:
    """The validate payload both handlers return, plus the failure count they both branch on.

    Shared by `ValidateSpecHandler` and `ValidateCodeHandler`, which otherwise repeat the same
    `output` dict and `StepResult` shape — an 11-line clone sitting under the two identical
    `results` comprehensions that `_rule_payload` now owns. Surfaced by removing the layer
    above it.

    Returns the count rather than the failing rules: both callers only ever took `len()` of it, and
    `passed` is then `len(results) - failed` instead of a second pass over the same list.

    `strict` folds WARNs into that count, which is how a module's DAL reaches the step verdict. It is
    the same rule the CLI applies at its summary, so a module marked `DAL_A` fails a pipeline step on
    the findings a `DAL_E` module passes with — instead of the two being judged identically because
    the DAL stopped one call short of here.

    The two callers still differ, deliberately — the spec handler sets `error_message` and the code
    handler does not, because `validate_code` is report-only behind a CONTINUE gate. That
    difference is behaviour, not duplication, so it stays at the call sites.
    """
    failed = sum(1 for r in results if r.status == RuleStatus.FAIL)
    if strict:
        failed += sum(1 for r in results if r.status == RuleStatus.WARN)
    return {
        "results": _rule_payload(results),
        "total": len(results),
        "passed": len(results) - failed,
        "failed": failed,
    }, failed


class ValidateSpecHandler:
    """Handler for validate+spec — runs spec validation rules."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
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
            merged_settings = await _resolve_merged_settings(context, context.spec_path)

            results = await asyncio.to_thread(
                self._run_validation,
                context.spec_path,
                merged_settings,
                kind_str=kind_str,
                project_path=context.project_path,
                analyzer_factory=context.analysis.analyzer_factory,
                parsers=context.analysis.parsers,
                profile=_profile_of(context),
            )
            output, failed = _validation_output(results)
            logger.info(
                "ValidateSpecHandler: %d rules executed, %d passed, %d failed",
                len(results),
                len(results) - failed,
                failed,
            )
            return StepResult(
                status=StepStatus.PASSED if failed == 0 else StepStatus.FAILED,
                output=output,
                error_message="" if failed == 0 else f"{failed} validation rules failed",
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
        profile: str | None = None,
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
        from specweaver.core.flow.handlers.archetype_pipelines import add_payload, spec_pipeline

        pipeline, archetype = spec_pipeline(
            spec_path, project_path, feature=kind_str == "feature", profile=profile
        )
        if settings is not None:
            pipeline = apply_settings_to_pipeline(
                pipeline, getattr(settings, "validation", settings)
            )
        add_payload(pipeline, spec_path, project_path, archetype, parsers=parsers)

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
        logger.debug("Executing %s", self.__class__.__name__)
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
        # Seeded onto the run context by the runner. Read here rather than resolved again, so the
        # step is judged against the same DAL the isolation decisions used.
        dal_level = context.isolation.dal_level
        try:
            merged_settings = await _resolve_merged_settings(context, code_path)
            results = await asyncio.to_thread(
                self._run_validation,
                code_path,
                context.spec_path,
                merged_settings,
                context.project_path,
                analyzer_factory=context.analysis.analyzer_factory,
                parsers=context.analysis.parsers,
                dal_level=dal_level,
                sandbox_settings=coder_sandbox(context),
                language=context.isolation.language,
            )
            if results is None:
                return _no_code_rules(code_path, started)
            output, failed = _validation_output(
                results, strict=bool(dal_level and dal_level.is_strict)
            )
            logger.info(
                "ValidateCodeHandler: %d rules executed, %d passed, %d failed (code=%s)",
                len(results),
                len(results) - failed,
                failed,
                code_path.name,
            )
            return StepResult(
                status=StepStatus.PASSED if failed == 0 else StepStatus.FAILED,
                output=output,
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            logger.exception("ValidateCodeHandler: unhandled exception during code validation")
            return _error_result(str(exc), started)

    def _find_code_path(self, step: PipelineStep, context: RunContext) -> Path | None:
        """Find the code file to validate.

        An explicit ``params["target"]`` is authoritative — it points
        validation at a specific generated file (``src/<stem>.py``) instead of the
        ``output_dir`` glob (which returns an arbitrary first match). The target is
        resolved against ``project_path`` and must stay inside it (no traversal). When
        no target is set, the legacy ``output_dir`` glob behavior is preserved.
        """
        target = step.params.get("target")
        if target and context.project_path:
            base = context.project_path.resolve()
            candidate = (context.project_path / target).resolve()
            try:
                candidate.relative_to(base)
            except ValueError:  # expected: a target outside the project root is refused
                return None
            return candidate if candidate.is_file() else None

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
        dal_level: Any | None = None,
        sandbox_settings: Any | None = None,
        language: str | None = None,
    ) -> list[RuleResult] | None:
        """Run code validation via sub-pipeline (called in thread); None when no rule judges
        the file's language."""
        # Trigger auto-registration of built-in rules
        import specweaver.assurance.validation.rules.code  # noqa: F401
        from specweaver.assurance.validation.executor import (
            apply_settings_to_pipeline,
        )
        from specweaver.assurance.validation.models import (
            RuleResult,  # noqa: F401 — for type narrowing
        )
        from specweaver.core.flow.handlers.archetype_pipelines import (
            add_payload,
            code_pipeline,
            language_of,
        )
        from specweaver.core.flow.handlers.validation_hydrator import execute_validation_flow

        pipeline, archetype = code_pipeline(code_path, project_path)
        if archetype is None and language_of(code_path) != "python":
            # The default rules are Python's and would fail any other language.
            return None
        if settings is not None:
            pipeline = apply_settings_to_pipeline(
                pipeline, getattr(settings, "validation", settings)
            )
        add_payload(pipeline, code_path, project_path, archetype, parsers=parsers, markers=True)

        content = code_path.read_text(encoding="utf-8")
        return execute_validation_flow(
            pipeline,
            content,
            spec_path,
            project_root=project_path,
            dal_level=dal_level,
            context={"analyzer_factory": analyzer_factory} if analyzer_factory else None,
            sandbox_settings=sandbox_settings,
            language=language,
        )


def _no_code_rules(code_path: Path, started: str) -> StepResult:
    """A passing step that says no rule judged the file — never a pass that looks judged."""
    from specweaver.core.flow.handlers.archetype_pipelines import language_of

    note = f"no code rules for {language_of(code_path)}"
    logger.info("ValidateCodeHandler: %s (code=%s)", note, code_path.name)
    return StepResult(
        status=StepStatus.PASSED,
        output={"note": note, "total": 0, "passed": 0, "failed": 0, "results": []},
        started_at=started,
        completed_at=_now_iso(),
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
        logger.debug("Executing %s", self.__class__.__name__)
        started = _now_iso()
        kind = step.params.get("kind", "unit")
        if kind == "acceptance":
            from specweaver.core.flow.handlers.acceptance import run_acceptance

            return run_acceptance(context, lambda: self._get_atom(context, "scenario"))
        target = step.params.get("target") or default_test_target(context, kind)
        if kind == "scenario":
            # The container sees the scenario tests only under its /scenarios mount.
            target = in_scenarios_mount(target, scenarios_root(context))
        logger.debug("ValidateTestsHandler: resolving %s test targets for '%s'", kind, target)

        targets = self._resolve_targets(context, target, kind)

        # "scenario" is a flow-level category, not a pytest marker —
        # the generated scenario file carries no such marker, so a `-m scenario` filter
        # would deselect every test and false-green the verification. Suppress the
        # marker at the atom-call site only (_resolve_targets above keeps the original
        # kind for its tests/<kind> fallback paths).
        # ...and the identical reasoning applies to any run that names ONE generated FILE. A marker
        # filter over a single freshly written file can only ever deselect it: `generate_tests`
        # emits no `@pytest.mark.unit`, so `-m unit` collects ZERO from an `sw implement` run and
        # the step reports `0 passed, 0 failed` as a pass. Directory runs keep their filter — that
        # is where a marker is a real selector.
        _one_generated_file = bool(target) and names_one_file(str(target))
        atom_kind = "" if (kind == "scenario" or _one_generated_file) else kind

        atom = self._get_atom(context, kind)
        result = atom.run(
            {
                "intent": "run_tests",
                "target": target,
                "targets": targets,
                "source": generated_code(context),
                "kind": atom_kind,
                "scope": step.params.get("scope", ""),
                "timeout": step.params.get("timeout", 120),
                "coverage": step.params.get("coverage", False),
                "coverage_threshold": step.params.get("coverage_threshold", 70),
            }
        )

        # Scenario runs ALWAYS publish the raw QA export under the
        # reserved key — pass, fail, and zero-collected alike. The arbiter consumes
        # it on verdict; for it, an ABSENT key is a wiring defect (loud ERROR), so
        # publication must be unconditional for this kind.
        output = dict(result.exports)
        if kind == "scenario":
            context.feedback["scenario_test_failures"] = result.exports
            output["requirement_coverage"] = requirement_coverage_of(context)

        # A verification that executed zero tests proves nothing — the atom's total==0 SUCCESS is
        # legitimate only for the pristine incremental paths of the other kinds. Keyed on the same
        # single-file signal as the marker rule above: naming one generated file and collecting
        # nothing means the step verified nothing while the pipeline moved on, reported as
        # `✓ tests: 0 passed, 0 failed`.
        #
        # ORDERING MATTERS. This guard depends on the marker rule above: without it collection is
        # broken everywhere, and the guard turns a false green into a universal red rather than a
        # fix.
        if (kind == "scenario" or _one_generated_file) and result.exports.get("total", 0) == 0:
            _what = "scenario tests" if kind == "scenario" else "tests"
            msg = (
                f"No {_what} executed (target={target}) — nothing was collected; "
                "verification cannot pass on an empty run."
            )
            logger.warning("ValidateTestsHandler: %s", msg)
            return StepResult(
                status=StepStatus.FAILED,
                output=output,
                error_message=msg,
                started_at=started,
                completed_at=_now_iso(),
            )

        if result.status.value == "SUCCESS":
            logger.info("ValidateTestsHandler: tests PASSED (kind=%s, target=%s)", kind, target)
            return StepResult(
                status=StepStatus.PASSED,
                output={**output, "tests_cover_project": target in WHOLE_PROJECT},
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
            output=output,
            error_message=result.message,
            started_at=started,
            completed_at=_now_iso(),
        )

    def _get_atom(self, context: RunContext, kind: str = "unit") -> QARunnerAtom:
        """Lazily create a QARunnerAtom for the project.

        ``run_tests`` (pytest) executes LLM-authored test code, so under
        worktree isolation the runner sets ``execution_root`` to the worktree source
        tree; bind the QA-runner cwd there so tests run worktree-bounded. Falls back to
        ``project_path`` when not isolated. ``sandbox_settings`` is threaded unchanged.
        """
        from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

        cwd = context.isolation.execution_root or context.project_path
        if kind == "scenario":
            # Always in a container, with the scenario tests mounted read-only at /scenarios.
            return QARunnerAtom(
                cwd=cwd,
                language=context.isolation.language,
                scenarios_root=scenarios_root(context),
            )
        return QARunnerAtom(
            cwd=cwd, language=context.isolation.language, sandbox_settings=coder_sandbox(context)
        )

    def _resolve_targets(self, context: RunContext, target: str, kind: str) -> list[str]:
        """The test folders of the modules changed since the last green run; else `target`.

        Only a step over the whole project narrows. Nothing changed, no green run yet, or any
        error: every test runs, so a step never passes having run nothing.
        """
        if target not in WHOLE_PROJECT:
            return [target]
        code_root = context.isolation.execution_root or context.project_path
        try:
            from specweaver.assurance.graph.topology import TopologyGraph
            from specweaver.core.flow.handlers.changed_code import folders_to_test
            from specweaver.graph.topology.engine import TopologyEngine

            graph = TopologyGraph.from_project(code_root, TopologyEngine(), auto_infer=False)
            return folders_to_test(context.project_path, code_root, graph, kind) or [target]
        except Exception as exc:
            logger.warning("ValidateTestsHandler: failed to resolve topology targets: %s", exc)
            return [target]


def _profile_of(context: RunContext) -> str | None:
    """The domain profile of the run's project, read from its registration."""
    from specweaver.core.flow.engine.registered import registered
    from specweaver.workspace.store import domain_profile_at

    return registered(context, domain_profile_at, "domain profile")
