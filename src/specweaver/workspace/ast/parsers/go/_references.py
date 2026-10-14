# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Where a name occurs in one Go file, and what it is there.

A method's definition carries its receiver type as `owner` and its receiver variable as
`alias`. A call `g.M()` carries `g` as `receiver`; its `receiver_binding` is `receiver` when
`g` is the enclosing method's own receiver, `import` for a package name, `local` or `free`.
"""

from __future__ import annotations

import typing

from specweaver.workspace.ast.parsers._ref_tools import mention, ref, text, walk, word
from specweaver.workspace.ast.parsers.interfaces import FileBindings, Reference

_SCOPES = ("function_declaration", "method_declaration", "func_literal")
_STRINGS = {
    "interpreted_string_literal": "interpreted_string_literal_content",
    "raw_string_literal": "raw_string_literal_content",
}


def _receiver(method: typing.Any) -> tuple[str | None, str | None]:
    """`(type name, variable name)` of a method's receiver."""
    params = method.child_by_field_name("receiver")
    declaration = (
        next((c for c in params.named_children if c.type == "parameter_declaration"), None)
        if params
        else None
    )
    if declaration is None:
        return None, None
    names = [
        n for n in walk(declaration.child_by_field_name("type")) if n.type == "type_identifier"
    ]
    variable = declaration.child_by_field_name("name")
    return (text(names[0]) if names else None), (text(variable) if variable is not None else None)


def _method(node: typing.Any) -> typing.Any | None:
    parent = node.parent
    while parent is not None and parent.type not in ("method_declaration", "function_declaration"):
        parent = parent.parent
    return parent if parent is not None and parent.type == "method_declaration" else None


def _declares(node: typing.Any) -> bool:
    parent = node.parent
    if parent.type in (
        "parameter_declaration",
        "var_spec",
        "const_spec",
        "variadic_parameter_declaration",
    ):
        return any(c == node for c in parent.children_by_field_name("name"))
    if parent.type == "expression_list" and parent.parent is not None:
        statement = parent.parent
        if (
            statement.type in ("short_var_declaration", "range_clause")
            and statement.child_by_field_name("left") == parent
        ):
            return True
    return False


def _locals(node: typing.Any) -> set[str]:
    names: set[str] = set()
    scope = node.parent
    while scope is not None:
        if scope.type in _SCOPES:
            names |= {text(n) for n in walk(scope) if n.type == "identifier" and _declares(n)}
        scope = scope.parent
    return names


def _receiver_binding(operand: typing.Any, imports: set[str]) -> str | None:
    if operand.type != "identifier":
        return None
    method = _method(operand)
    if method is not None and _receiver(method)[1] == text(operand):
        return "receiver"
    if text(operand) in _locals(operand):
        return "local"
    return "import" if text(operand) in imports else "free"


def _definition(node: typing.Any) -> Reference | None:
    parent = node.parent
    if node != parent.child_by_field_name("name"):
        return None
    if parent.type == "function_declaration":
        return ref("definition", node, scope="module")
    if parent.type == "method_declaration":
        owner, variable = _receiver(parent)
        return ref("definition", node, scope="class", owner=owner, alias=variable)
    if parent.type == "type_spec":
        nested = (
            parent.parent is not None
            and parent.parent.parent is not None
            and parent.parent.parent.type != "source_file"
        )
        return ref("definition", node, scope="function" if nested else "module", binding="type")
    if parent.type == "method_elem":
        interface = parent.parent.parent if parent.parent is not None else None
        owner = (
            text(interface.child_by_field_name("name"))
            if interface is not None and interface.type == "type_spec"
            else None
        )
        return ref("definition", node, scope="class", owner=owner, binding="interface")
    return None


def _owner(node: typing.Any) -> str | None:
    method = _method(node)
    return _receiver(method)[0] if method is not None else None


def _identifier(node: typing.Any, imports: set[str]) -> Reference:
    found = _definition(node)
    if found is not None:
        return found
    parent = node.parent
    if parent.type == "selector_expression" and node == parent.child_by_field_name("field"):
        operand = parent.child_by_field_name("operand")
        return ref(
            "attribute",
            node,
            owner=_owner(node),
            receiver=text(operand),
            receiver_binding=_receiver_binding(operand, imports),
        )
    if parent.type == "qualified_type" and node == parent.child_by_field_name("name"):
        return ref("type", node, qualifier=text(parent.child_by_field_name("package")))
    if node.type == "field_identifier":
        return ref("field", node)
    if node.type == "type_identifier":
        return ref("type", node, owner=_owner(node))
    if _declares(node):
        return ref("field", node)
    binding = "local" if text(node) in _locals(node) else "free"
    return ref("bare", node, owner=_owner(node), binding=binding)


def find_references(root: typing.Any, name: str) -> list[Reference]:
    """Every place `name` occurs under `root`, in byte order."""
    if not name:
        return []
    imports = set(file_bindings(root).imports)
    pattern = word(name)
    found: list[Reference] = []
    for node in walk(root):
        if (
            node.type in ("identifier", "type_identifier", "field_identifier")
            and text(node) == name
        ):
            found.append(_identifier(node, imports))
        else:
            found.extend(
                filter(
                    None, [mention(node, name, pattern, _STRINGS, ("comment",), ("import_spec",))]
                )
            )
    return sorted(found, key=lambda r: r.start_byte)


def _add_import(facts: FileBindings, spec: typing.Any) -> None:
    path = text(spec.child_by_field_name("path")).strip('"`')
    alias = spec.child_by_field_name("name")
    if alias is None:
        facts.imports[path.rsplit("/", 1)[-1]] = (path, None)
    elif alias.type == "dot":
        facts.wildcards.append(path)
    elif text(alias) != "_":
        facts.imports[text(alias)] = (path, "alias")


_DECLARATIONS = ("function_declaration", "type_declaration", "var_declaration", "const_declaration")
_NAMED = ("function_declaration", "type_spec", "var_spec", "const_spec")


def file_bindings(root: typing.Any) -> FileBindings:
    """The package, imports (`local → (path, "alias" or None)`), dot imports and top-level names."""
    facts = FileBindings()
    for node in walk(root):
        if node.type == "package_clause":
            facts.package = text(node.named_children[0])
        elif node.type == "import_spec":
            _add_import(facts, node)
    for node in root.named_children:
        if node.type in _DECLARATIONS:
            facts.defs.update(
                text(spec.child_by_field_name("name"))
                for spec in walk(node)
                if spec.type in _NAMED and spec.child_by_field_name("name") is not None
            )
    return facts
