# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Validation hydrator — pre-executes QA atoms for code validation rules.

This module is the bridge between the sandbox layer (QARunnerAtom) and the
assurance/validation layer (pure-logic rules). It:

1. Inspects the pipeline to determine which QA atoms are needed (AD-8: skip
   disabled rules).
2. Executes the atoms and serializes results to plain dicts.
3. Provides `execute_validation_flow` as a single entry point for CLI, API,
   and flow handler (AD-5: unified entry point).

The hydrated context is merged into each rule's `self.context` dict by the
executor, so rules never import from sandbox directly.

Architectural notes:
- This module lives in core.flow which is authorized to import both
  sandbox and assurance.validation (see core/flow/context.yaml).
- Rules must NOT import this module — it flows in one direction only.
"""

from __future__ import annotations

import logging
from pathlib import Path  # noqa: TC003 — used at runtime in function bodies
from typing import Any

logger = logging.getLogger(__name__)

# Context keys used to pass QA results to rules
_KEY_TESTS = "qa_tests_result"
_KEY_COVERAGE = "qa_coverage_result"
_KEY_ARCHITECTURE = "qa_architecture_result"

# Rule IDs that require QA atom execution
_QA_RULE_IDS = frozenset({"C03", "C04", "C05"})


def hydrate_code_validation_context(
    pipeline: Any,
    code_path: Path,
    project_root: Path,
    *,
    dal_level: Any | None = None,
) -> dict[str, Any]:
    """Pre-execute QA atoms and return a context dict for code validation rules.

    Only executes atoms for rules that are active in the pipeline (AD-8).

    Args:
        pipeline: Resolved ValidationPipeline with steps.
        code_path: Path to the code file being validated.
        project_root: Project root directory (for QARunnerAtom cwd).
        dal_level: Optional DALLevel for architecture checks.

    Returns:
        Dict mapping context keys to serialized AtomResult dicts.
        Each value has shape: {"status": str, "message": str, "exports": dict}
    """
    active_rules = {step.rule for step in pipeline.steps}
    qa_rules_active = active_rules & _QA_RULE_IDS

    if not qa_rules_active:
        logger.debug("hydrate_code_validation_context: no QA rules active, skipping hydration")
        return {}

    logger.debug(
        "hydrate_code_validation_context: hydrating for rules %s (code=%s)",
        qa_rules_active,
        code_path.name,
    )

    context: dict[str, Any] = {}

    # Lazy import — only when we actually need to run atoms
    from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

    atom = QARunnerAtom(cwd=project_root)

    # --- C03: Tests Pass ---
    if "C03" in qa_rules_active:
        context[_KEY_TESTS] = _hydrate_tests(atom, code_path, project_root)

    # --- C04: Coverage ---
    if "C04" in qa_rules_active:
        context[_KEY_COVERAGE] = _hydrate_coverage(atom, code_path, project_root)

    # --- C05: Architecture ---
    if "C05" in qa_rules_active:
        context[_KEY_ARCHITECTURE] = _hydrate_architecture(atom, code_path, project_root, dal_level)

    return context


def _hydrate_tests(
    atom: Any,
    code_path: Path,
    project_root: Path,
) -> dict[str, Any] | None:
    """Execute tests atom for C03 and return serialized result."""
    # Derive test file path (same logic as in C03 rule)
    test_name = f"test_{code_path.stem}.py"
    tests_dir = project_root / "tests"
    if not tests_dir.is_dir():
        return None

    matches = list(tests_dir.rglob(test_name))
    if not matches:
        return None

    test_file = matches[0]
    try:
        result = atom.run(
            {
                "intent": "run_tests",
                "target": str(test_file.relative_to(project_root)),
                "kind": "",
                "timeout": 60,
            }
        )
        return _serialize_atom_result(result)
    except Exception as exc:
        logger.warning("Hydration error for C03 tests: %s", exc)
        return {"status": "FAILED", "message": f"Hydration error: {exc}", "exports": {}}


def _hydrate_coverage(
    atom: Any,
    code_path: Path,
    project_root: Path,
) -> dict[str, Any] | None:
    """Execute coverage atom for C04 and return serialized result."""
    try:
        result = atom.run(
            {
                "intent": "run_tests",
                "target": str(code_path.relative_to(project_root)),
                "kind": "",
                "timeout": 120,
                "coverage": True,
            }
        )
        return _serialize_atom_result(result)
    except Exception as exc:
        logger.warning("Hydration error for C04 coverage: %s", exc)
        return {"status": "FAILED", "message": f"Hydration error: {exc}", "exports": {}}


def _hydrate_architecture(
    atom: Any,
    code_path: Path,
    project_root: Path,
    dal_level: Any | None,
) -> dict[str, Any] | None:
    """Execute architecture atom for C05 and return serialized result."""
    try:
        result = atom.run(
            {
                "intent": "run_architecture",
                "target": str(code_path.relative_to(project_root)),
                "dal_level": dal_level,
            }
        )
        return _serialize_atom_result(result)
    except Exception as exc:
        logger.warning("Hydration error for C05 architecture: %s", exc)
        return {"status": "FAILED", "message": f"Hydration error: {exc}", "exports": {}}


def _serialize_atom_result(result: Any) -> dict[str, Any]:
    """Serialize an AtomResult to a plain dict for context injection."""
    return {
        "status": result.status.value,
        "message": result.message or "",
        "exports": result.exports or {},
    }


def execute_validation_flow(
    pipeline: Any,
    spec_text: str,
    spec_path: Path | None = None,
    *,
    project_root: Path | None = None,
    dal_level: Any | None = None,
    context: dict[str, Any] | None = None,
) -> list[Any]:
    """Single entry point for code validation with hydration.

    Combines hydration + pipeline execution (AD-5: unified entry point).

    1. Hydrates QA context (if code_path and project_root are available).
    2. Merges hydrated context with any extra context.
    3. Calls execute_validation_pipeline.

    Args:
        pipeline: Resolved ValidationPipeline.
        spec_text: Content of the file to validate.
        spec_path: Path to the file (used for rule checks and hydration).
        project_root: Project root for QARunnerAtom. If None, hydration is skipped.
        dal_level: Optional DALLevel for architecture checks.
        context: Extra context dict to merge (e.g., analyzer_factory).

    Returns:
        List of RuleResult from the pipeline executor.
    """
    from specweaver.assurance.validation.executor import execute_validation_pipeline

    merged_context: dict[str, Any] = {}

    # Hydrate QA context if we have a code path and project root
    if spec_path and project_root:
        qa_context = hydrate_code_validation_context(
            pipeline,
            spec_path,
            project_root,
            dal_level=dal_level,
        )
        merged_context.update(qa_context)

    # Merge any extra context (e.g., analyzer_factory)
    if context:
        merged_context.update(context)

    return execute_validation_pipeline(
        pipeline,
        spec_text,
        spec_path,
        context=merged_context if merged_context else None,
    )
