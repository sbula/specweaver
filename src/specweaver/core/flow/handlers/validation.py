# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Validation step handlers — spec, code, and test validation."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.assurance.validation.models import Status as RuleStatus
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import _error_result, _now_iso

if TYPE_CHECKING:
    from specweaver.assurance.validation.models import RuleResult
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.run_context import RunContext
    from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

logger = logging.getLogger(__name__)


async def _resolve_merged_settings(context: RunContext, target_path: Path) -> Any:
    """Resolve DAL for the target and overlay validation constraints over settings."""
    from specweaver.commons.enums.dal import DALLevel
    from specweaver.core.config.dal_resolver import DALResolver
    from specweaver.core.config.settings import SpecWeaverSettings, deep_merge_dict

    dal_resolver = DALResolver(context.project_path)
    dal_str = dal_resolver.resolve(target_path)

    if not dal_str and context.db:
        try:
            from specweaver.workspace.store import WorkspaceRepository

            async with context.db.async_session_scope() as session:
                dal_raw = await WorkspaceRepository(session).get_default_dal(
                    context.project_path.name
                )
            if dal_raw:
                try:
                    dal_str = DALLevel(dal_raw)
                except ValueError:
                    dal_str = None
        except Exception as e:
            logger.error("Exception in _resolve_merged_settings: %s", e)
            dal_str = None

    merged_settings = context.settings
    if dal_str and merged_settings and hasattr(merged_settings, "dal_matrix"):
        try:
            dal = dal_str
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
        from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom

        archetype = None
        if project_path:
            resolver = ArchetypeResolver(project_path)
            archetype = resolver.resolve(spec_path)

        # Map kind to pipeline name
        pipeline_name = "validation_spec_default"
        if kind_str == "feature":
            pipeline_name = "validation_spec_feature"

        # Pass project_dir so the documented project-local override
        # ({project}/.specweaver/pipelines/) applies on the flow-handler path; without it the
        # loader searches packaged pipelines only and the override is silently ignored.
        if archetype:
            try:
                pipeline = load_pipeline_yaml(
                    f"{pipeline_name}_{archetype}", project_dir=project_path
                )
            except Exception:
                pipeline = load_pipeline_yaml(pipeline_name, project_dir=project_path)
        else:
            pipeline = load_pipeline_yaml(pipeline_name, project_dir=project_path)

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
            )
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
            except ValueError:
                return None  # target escapes the project root — reject
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
    ) -> list[RuleResult]:
        """Run code validation via sub-pipeline (called in thread)."""
        # Trigger auto-registration of built-in rules
        import specweaver.assurance.validation.rules.code  # noqa: F401
        from specweaver.assurance.validation.executor import (
            apply_settings_to_pipeline,
        )
        from specweaver.assurance.validation.models import (
            RuleResult,  # noqa: F401 — for type narrowing
        )
        from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml
        from specweaver.core.config.archetype_resolver import ArchetypeResolver
        from specweaver.core.flow.handlers.validation_hydrator import execute_validation_flow
        from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom

        archetype = None
        if project_path:
            resolver = ArchetypeResolver(project_path)
            archetype = resolver.resolve(code_path)

        pipeline_name = f"validation_code_{archetype}" if archetype else "validation_code_default"
        # Pass project_dir so project-local pipeline overrides resolve, as on the spec-validation
        # path above; without it the loader silently uses packaged defaults.
        try:
            pipeline = load_pipeline_yaml(pipeline_name, project_dir=project_path)
        except Exception:
            pipeline = load_pipeline_yaml("validation_code_default", project_dir=project_path)

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
        return execute_validation_flow(
            pipeline,
            content,
            spec_path,
            project_root=project_path,
            dal_level=dal_level,
            context={"analyzer_factory": analyzer_factory} if analyzer_factory else None,
        )


def _test_dir_for(module_dir: Path, src_dir: Path, project_path: Path, kind: str) -> str:
    """The test directory mirroring one source module, e.g. `specweaver/core/flow` ->
    `tests/unit/core/flow`.

    Falls back to the tier root (`tests/<kind>`) when the module sits directly under `src/`, when
    the mirrored directory does not exist yet, or when the module is not under `src/` at all —
    three distinct reasons that all mean "run the whole tier rather than nothing".
    """
    tier_root = str(Path("tests") / kind)
    try:
        parts = module_dir.relative_to(src_dir).parts
    except ValueError:
        return tier_root
    if len(parts) <= 1:
        return tier_root
    mirrored = Path("tests") / kind / Path(*parts[1:])
    return str(mirrored) if (project_path / mirrored).exists() else tier_root


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
        target = step.params.get("target")
        if not target:
            from specweaver.sandbox.language.core.scenario_converter_factory import (
                create_scenario_converter,
            )

            converter = create_scenario_converter(context.project_path)
            stem = context.spec_path.stem.replace("_spec", "")
            target_path = converter.output_path(stem, context.project_path)
            target = str(target_path)

        kind = step.params.get("kind", "unit")
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
        _one_generated_file = bool(target) and str(target).endswith(".py")
        atom_kind = "" if (kind == "scenario" or _one_generated_file) else kind

        atom = self._get_atom(context)
        result = atom.run(
            {
                "intent": "run_tests",
                "target": target,
                "targets": targets,
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
        if kind == "scenario":
            context.feedback["scenario_test_failures"] = result.exports

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
                output=result.exports,
                error_message=msg,
                started_at=started,
                completed_at=_now_iso(),
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
        """Lazily create a QARunnerAtom for the project.

        ``run_tests`` (pytest) executes LLM-authored test code, so under
        worktree isolation the runner sets ``execution_root`` to the worktree source
        tree; bind the QA-runner cwd there so tests run worktree-bounded. Falls back to
        ``project_path`` when not isolated. ``sandbox_settings`` is threaded unchanged.
        """
        from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

        sandbox_settings = context.model.config.sandbox if context.model.config else None
        cwd = context.isolation.execution_root or context.project_path
        return QARunnerAtom(cwd=cwd, sandbox_settings=sandbox_settings)

    def _resolve_targets(self, context: RunContext, target: str, kind: str) -> list[str]:
        """Resolve precise test directories from TopologyGraph stale nodes."""
        stale_nodes = context.graph.stale_nodes
        if stale_nodes is None or target not in {".", "", "src", "src/", "tests", "tests/"}:
            return [target]

        if len(stale_nodes) == 0:
            return []  # All nodes pristine, trigger short-circuit

        try:
            from specweaver.assurance.graph.topology import TopologyGraph
            from specweaver.graph.topology.engine import TopologyEngine

            engine = TopologyEngine()
            graph = TopologyGraph.from_project(context.project_path, engine, auto_infer=False)

            src_dir = context.project_path / "src"
            resolved = {
                _test_dir_for(node.yaml_path.parent, src_dir, context.project_path, kind)
                for node_name in stale_nodes
                if (node := graph.nodes.get(node_name)) and node.yaml_path
            }
            return sorted(resolved) if resolved else [target]
        except Exception as exc:
            logger.warning("ValidateTestsHandler: failed to resolve topology targets: %s", exc)
            return [target]
