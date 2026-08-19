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

#: The two context keys `C13` reads. Both were absent, and it skipped for want of either.
_KEY_PROTOCOL = "protocol_schema"
_KEY_AST = "ast_payload"

#: Contract files, by extension. YAML is sniffed rather than parsed on sight: a project holds far
#: more YAML than it holds schemas, and handing every one to the factory means catching an exception
#: per file to learn what a first line already says.
_PROTO_SUFFIX = ".proto"
_YAML_SUFFIXES = (".yaml", ".yml")
_YAML_MARKERS = ("openapi:", "swagger:", "asyncapi:")

#: Directories never searched for contracts. A vendored dependency's schema is not this project's.
_SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "target",
        "build",
        "dist",
        "__pycache__",
        ".specweaver",
    }
)

#: How far under the project root to look. A contract lives near the top of a repository; walking a
#: whole monorepo to find one costs more than it can return.
_MAX_DEPTH = 3


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

    context: dict[str, Any] = {}

    # C13 needs no QA atom, only the project's own contract files — so it is hydrated before the
    # early return below, which exists for the atoms. Leaving it after meant a pipeline running C13
    # and nothing else hydrated nothing, and C13 reported SKIP for want of a key.
    if "C13" in active_rules:
        endpoints = discover_protocol_endpoints(project_root)
        if endpoints:
            context[_KEY_PROTOCOL] = endpoints
            # C13 reads `ast_payload` as a KEY of its context. The executor makes the step's payload
            # BE the context and merges this dict over it, so that key exists only if something puts
            # it there — which nothing did, on either path.
            context[_KEY_AST] = _read_code_structure(code_path, project_root)

    if not qa_rules_active:
        logger.debug("hydrate_code_validation_context: no QA rules active, skipping hydration")
        return context

    logger.debug(
        "hydrate_code_validation_context: hydrating for rules %s (code=%s)",
        qa_rules_active,
        code_path.name,
    )

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


def _read_code_structure(code_path: Path, project_root: Path) -> dict[str, Any]:
    """The code's own structure, as `C13` compares a contract against it.

    Built here rather than taken from the caller so both entry points behave the same. The pipeline
    handler already assembles one for its own use; this is the copy `C13` can actually read, and an
    empty dict on failure keeps a code check running — a structure that cannot be read is a reason to
    skip the comparison, not to fail the file.
    """
    from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom

    try:
        # Project-relative, because the atom rejects an absolute path as a traversal attempt — and
        # a rejected read exports `{}`, which is indistinguishable from a file with no structure.
        target = code_path.resolve()
        root = project_root.resolve()
        relative = target.relative_to(root) if target.is_relative_to(root) else code_path
        atom = CodeStructureAtom(cwd=root)
        result = atom.run({"intent": "read_file_structure", "path": relative.as_posix()})
    except Exception as exc:
        logger.warning("Could not read the structure of %s for contract drift: %s", code_path, exc)
        return {}
    exports = getattr(result, "exports", None)
    return exports if isinstance(exports, dict) else {}


def _is_contract(path: Path) -> bool:
    """Whether this file declares a protocol schema, decided as cheaply as possible."""
    if path.suffix == _PROTO_SUFFIX:
        return True
    if path.suffix not in _YAML_SUFFIXES:
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4096]
    except OSError:
        return False
    return any(marker in head for marker in _YAML_MARKERS)


def discover_protocol_endpoints(project_root: Path) -> list[Any]:
    """Every endpoint the project's own contract files declare.

    Returns `[]` when a project declares no contract, which leaves `C13` skipping — the honest answer
    where there is nothing to compare against. The defect this closes was C13 skipping when a
    contract WAS present, because nothing looked for one.

    A file that cannot be parsed is skipped with a warning rather than failing the run: an unrelated
    `.yaml` that happens to carry an `openapi:` line should not stop a code check.

    Read through `ProtocolAtom` rather than the parser factory, which is not part of `sandbox`'s
    public interface — and the atom hands back plain dicts, which is the shape `C13`'s own unit test
    has always fed it.
    """
    from specweaver.sandbox.base import AtomStatus
    from specweaver.sandbox.protocol.core.atom import ProtocolAtom

    atom = ProtocolAtom()
    endpoints: list[Any] = []
    for path in sorted(project_root.rglob("*")):
        if not path.is_file() or not _is_contract(path):
            continue
        relative = path.relative_to(project_root)
        if set(relative.parts) & _SKIP_DIRS or len(relative.parts) > _MAX_DEPTH:
            continue
        result = atom.run({"action": "extract_schema_endpoints", "file_path": str(path)})
        if result.status is not AtomStatus.SUCCESS:
            logger.warning(
                "Contract file %s is not a schema this can read: %s", relative, result.message
            )
            continue
        endpoints.extend(result.exports.get("data", []))
    logger.debug(
        "discover_protocol_endpoints: %d endpoint(s) under %s", len(endpoints), project_root
    )
    return endpoints


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
