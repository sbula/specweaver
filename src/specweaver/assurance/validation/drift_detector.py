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


#: Parameter node types whose identifier is labelled `name`, or is the first identifier child.
_ANNOTATED_PARAMS = ("typed_parameter", "default_parameter", "typed_default_parameter")
#: `*args` / `**kwargs`, whose identifier is simply the first one inside.
_SPLAT_PARAMS = ("dictionary_splat_pattern", "list_splat_pattern")


def _first_identifier(node: Any) -> str | None:
    """The first `identifier` child's text, or None."""
    for child in getattr(node, "children", None) or ():
        if child.type == "identifier" and child.text:
            return str(child.text.decode("utf-8"))
    return None


def _param_name(child: Any) -> str | None:
    """One parameter node's identifier, whichever of the four shapes it is."""
    if child.type == "identifier":
        return str(child.text.decode("utf-8"))
    if child.type in _ANNOTATED_PARAMS:
        name_node = child.child_by_field_name("name")
        if name_node and name_node.text:
            return str(name_node.text.decode("utf-8"))
        return _first_identifier(child)
    if child.type in _SPLAT_PARAMS:
        return _first_identifier(child)
    return None


def _extract_param_names(parameters_node: Any) -> list[str]:
    """Given a tree-sitter parameters node, extract parameter identifiers.

    Per-shape naming is its own function, so this reads as "name every parameter, minus the
    implicit receiver" rather than as three nested loops inside a three-way type branch.
    """
    names = (_param_name(child) for child in getattr(parameters_node, "children", None) or ())
    return [n for n in names if n and n not in ("self", "cls")]


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


def _planned_vs_actual(
    expected_sigs: dict[str, MethodSignatureProtocol], actual_map: dict[str, Any]
) -> list[DriftFinding]:
    """Every planned method that is missing (ERROR) or whose parameters moved (WARNING)."""
    findings: list[DriftFinding] = []
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
            continue

        actual_param_list = actual_map[expected_name].parameters
        expected_param_list = _clean_expected_params(expected_sig.parameters)
        if actual_param_list != expected_param_list:
            findings.append(
                DriftFinding(
                    severity=Severity.WARNING,
                    node_type="function",
                    description=(
                        f"Parameter drift in {expected_name}: "
                        f"Expected {expected_param_list}, Actual {actual_param_list}"
                    ),
                    expected_signature=", ".join(expected_param_list),
                    actual_signature=", ".join(actual_param_list),
                )
            )
    return findings


def _unauthorised_methods(
    expected_sigs: dict[str, MethodSignatureProtocol], actual_map: dict[str, Any]
) -> list[DriftFinding]:
    """Public methods present in the code but absent from the plan. Private names are ignored."""
    return [
        DriftFinding(
            severity=Severity.ERROR,
            node_type="function",
            description=f"Found unauthorized public method '{name}' not defined in the plan",
            expected_signature="",
            actual_signature=name,
        )
        for name in actual_map
        if name not in expected_sigs and not name.split(".")[-1].startswith("_")
    ]


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
    findings.extend(_planned_vs_actual(expected_sigs, actual_map))

    # 4. Detect Unauthorized Methods (actual methods not in the plan)
    findings.extend(_unauthorised_methods(expected_sigs, actual_map))

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
