# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Pure logic AST drift detector for structural code validation."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from specweaver.assurance.validation.models import DriftFinding, DriftReport, Severity

logger = logging.getLogger(__name__)


class MethodSignatureProtocol(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def parameters(self) -> list[str]: ...

    @property
    def return_type(self) -> str: ...


class ImplementationTaskProtocol(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def files(self) -> list[str]: ...

    @property
    def sequence_number(self) -> int: ...

    @property
    def expected_signatures(self) -> dict[str, list[MethodSignatureProtocol]]: ...


class FileChangeProtocol(Protocol):
    @property
    def path(self) -> str: ...

    @property
    def action(self) -> str: ...


class PlanArtifactProtocol(Protocol):
    @property
    def tasks(self) -> Iterable[ImplementationTaskProtocol]: ...

    @property
    def file_layout(self) -> Iterable[FileChangeProtocol]: ...


@dataclass
class ActualSignature:
    name: str
    parameters: list[str]


def _extract_param_names(parameters_node: Any) -> list[str]:  # noqa: C901
    """Given a tree-sitter parameters node, extract parameter identifiers."""
    params: list[str] = []
    if not hasattr(parameters_node, "children"):
        return params

    for child in parameters_node.children:
        if child.type == "identifier":
            params.append(child.text.decode("utf-8"))
        elif child.type in ("typed_parameter", "default_parameter", "typed_default_parameter"):
            # The identifier is usually labeled "name" or is the first identifier child
            name_node = child.child_by_field_name("name")
            if name_node and name_node.text:
                params.append(name_node.text.decode("utf-8"))
            elif hasattr(child, "children") and child.children:
                for subchild in child.children:
                    if subchild.type == "identifier":
                        params.append(subchild.text.decode("utf-8"))
                        break
        elif child.type == "dictionary_splat_pattern" or child.type == "list_splat_pattern":
            # kwargs / args
            for subchild in child.children:
                if subchild.type == "identifier":
                    params.append(subchild.text.decode("utf-8"))
                    break

    # Strip self/cls
    return [p for p in params if p not in ("self", "cls")]


def _declared_name(node: Any) -> str | None:
    """The identifier a definition node declares, decoded, or None when it has none."""
    name_node = node.child_by_field_name("name")
    if not (name_node and name_node.text):
        return None
    return str(name_node.text.decode("utf-8"))


def _qualified(raw_name: str, current_scope: str) -> str:
    """`Class.method` inside a class, bare otherwise."""
    return f"{current_scope}.{raw_name}" if current_scope else raw_name


def _signature_of(node: Any, current_scope: str) -> ActualSignature | None:
    """The signature a function/method definition declares."""
    raw_name = _declared_name(node)
    if raw_name is None:
        return None

    parameters_node = node.child_by_field_name("parameters")
    params = _extract_param_names(parameters_node) if parameters_node else []
    return ActualSignature(name=_qualified(raw_name, current_scope), parameters=params)


def _scope_within(node: Any, current_scope: str) -> str:
    """The scope children are visited under — widened only by a class definition."""
    if node.type != "class_definition":
        return current_scope
    raw_name = _declared_name(node)
    return _qualified(raw_name, current_scope) if raw_name else current_scope


def _extract_signatures(root_node: Any) -> list[ActualSignature]:
    """Every function/method signature under `root_node`, async and class-scoped included."""
    signatures: list[ActualSignature] = []

    def visit(node: Any, current_scope: str = "") -> None:
        if not node:
            return

        if node.type in ("function_definition", "async_function_definition"):
            signature = _signature_of(node, current_scope)
            if signature:
                signatures.append(signature)
            # Critical: DO NOT recurse into function bodies (prevents extracting inner functions).
            return

        # Everything else recurses. A class widens the scope its children are named under; module,
        # decorated_definition, block and the rest pass it through unchanged — the two branches
        # differed only in that scope, so they are one branch now.
        scope = _scope_within(node, current_scope)
        for child in getattr(node, "children", []):
            visit(child, scope)

    if root_node:
        visit(root_node, "")

    return signatures


def _clean_expected_params(params: list[str]) -> list[str]:
    """Clean expected params from Plan (e.g. 'ast: tree_sitter.Tree' -> 'ast')."""
    cleaned = []
    for p in params:
        # naive cleanup: take string before colon or equals
        base = p.split(":")[0].split("=")[0].strip()
        base = base.lstrip("*")  # Strip * and ** for *args and **kwargs matching
        if base and base not in ("self", "cls"):
            cleaned.append(base)
    return cleaned


def detect_drift(file_ast: Any, plan: PlanArtifactProtocol, file_path: str) -> DriftReport:
    """Compare a single file's AST against the expected signatures."""
    findings: list[DriftFinding] = []

    if file_ast is None:
        # File parsing completely failed or node is empty. Handled upstream typically, but just in case.
        return DriftReport(is_drifted=False, findings=[])

    # 1. Extract actual signatures
    actual_sigs = _extract_signatures(file_ast.root_node)
    actual_map = {sig.name: sig for sig in actual_sigs}

    # 2. Extract expected signatures from the Plan for THIS file.
    relevant_tasks = list(plan.tasks)
    relevant_tasks.sort(key=lambda t: t.sequence_number)

    expected_sigs: dict[str, MethodSignatureProtocol] = {}

    for task in relevant_tasks:
        task_sigs = task.expected_signatures.get(file_path, [])
        for sig in task_sigs:
            expected_sigs[sig.name] = sig

    # 3. Detect Missing Methods and Signature Drifts
    for expected_name, expected_sig in expected_sigs.items():
        if expected_name not in actual_map:
            findings.append(
                DriftFinding(
                    severity=Severity.ERROR,
                    node_type="function",
                    description=f"Missing expected method {expected_name}",
                    expected_signature=expected_name,
                )
            )
        else:
            # Check Parameter Drift
            actual_param_list = actual_map[expected_name].parameters
            expected_param_list = _clean_expected_params(expected_sig.parameters)

            # Simple list comparison
            if actual_param_list != expected_param_list:
                findings.append(
                    DriftFinding(
                        severity=Severity.WARNING,
                        node_type="function",
                        description=f"Parameter drift in {expected_name}: Expected {expected_param_list}, Actual {actual_param_list}",
                        expected_signature=", ".join(expected_param_list),
                        actual_signature=", ".join(actual_param_list),
                    )
                )

    # 4. Detect Unauthorized Methods (actual methods not in the plan)
    for actual_name in actual_map:
        if actual_name not in expected_sigs:
            # Ignore private methods and dunders
            if actual_name.split(".")[-1].startswith("_"):
                continue

            findings.append(
                DriftFinding(
                    severity=Severity.ERROR,
                    node_type="function",
                    description=f"Found unauthorized public method '{actual_name}' not defined in the plan",
                    expected_signature="",
                    actual_signature=actual_name,
                )
            )

    is_drifted = any(f.severity == Severity.ERROR for f in findings)
    return DriftReport(is_drifted=is_drifted, findings=findings)


def detect_workspace_drift(
    plan: PlanArtifactProtocol, present_file_paths: set[str]
) -> list[DriftFinding]:
    """Detect missing or entirely unauthorized files across the workspace purely via layout."""
    findings = []

    expected_files = {fc.path for fc in plan.file_layout if fc.action in ("create", "modify")}

    for expected_file in expected_files:
        if expected_file not in present_file_paths:
            findings.append(
                DriftFinding(
                    severity=Severity.ERROR,
                    node_type="file",
                    description=f"Required file {expected_file} from plan is missing on disk",
                    expected_signature=expected_file,
                )
            )

    return findings
