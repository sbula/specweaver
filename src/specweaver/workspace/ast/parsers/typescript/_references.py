# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Where a name occurs in one TypeScript file, and what it is there.

A file is a module: a name comes from its own declarations or an `import`. A member is always
reached through something (`this.m()`, `obj.m()`); an object-literal key of the name is
reported as `string`, since a shape may stand in for a class.
"""

from __future__ import annotations

import typing

from specweaver.workspace.ast.parsers._ref_tools import mention, ref, text, walk, word
from specweaver.workspace.ast.parsers.interfaces import FileBindings, Reference

_FUNCTIONS = (
    "function_declaration",
    "function_expression",
    "arrow_function",
    "method_definition",
    "generator_function_declaration",
)
_CLASSES = ("class_declaration", "abstract_class_declaration", "interface_declaration")
_TYPE_DECLS = (*_CLASSES, "enum_declaration")
_PARAMETERS = ("required_parameter", "optional_parameter", "rest_pattern")
_PATTERN_NAMES = ("identifier", "shorthand_property_identifier_pattern")


def _owner(node: typing.Any) -> str | None:
    parent = node.parent
    while parent is not None:
        if parent.type in _CLASSES:
            return text(parent.child_by_field_name("name"))
        parent = parent.parent
    return None


def _scope(node: typing.Any) -> typing.Any | None:
    """The function around `node`, or None at module level."""
    parent = node.parent
    while parent is not None:
        if parent.type in _FUNCTIONS:
            return parent
        parent = parent.parent
    return None


def _pattern_names(node: typing.Any) -> list[str]:
    return [text(n) for n in walk(node) if n.type in _PATTERN_NAMES]


def _declared_in(scope: typing.Any) -> set[str]:
    """The names a function declares: parameters, variables, inner functions and classes."""
    names: set[str] = set()
    for node in walk(scope):
        if node is not scope and node.type in _FUNCTIONS and node.parent is not None:
            name = node.child_by_field_name("name")
            if name is not None:
                names.add(text(name))
        elif node.type == "variable_declarator":
            names.update(_pattern_names(node.child_by_field_name("name")))
        elif node.type in _PARAMETERS or node.type == "catch_clause":
            pattern = node.child_by_field_name("pattern") or node.child_by_field_name("parameter")
            names.update(_pattern_names(pattern if pattern is not None else node))
    return names


def _binding(node: typing.Any, module: dict[str, set[str]]) -> str:
    scope = _scope(node)
    while scope is not None:
        if text(node) in _declared_in(scope):
            return "local"
        scope = _scope(scope)
    kinds = module.get(text(node), set())
    if not kinds:
        return "free"
    if len(kinds) > 1:
        return "mixed"
    return {"def": "module_def", "import": "import", "other": "module_other"}[next(iter(kinds))]


def _this_binding(receiver: typing.Any) -> str:
    """`this`, or `rebound` when a `function` between it and its class gives it another `this`."""
    parent = receiver.parent
    while parent is not None and parent.type not in _CLASSES:
        if parent.type in (
            "function_expression",
            "function_declaration",
            "generator_function_declaration",
        ):
            return "rebound"
        parent = parent.parent
    return str(receiver.type)


def _receiver_binding(receiver: typing.Any, module: dict[str, set[str]]) -> str | None:
    if receiver.type in ("this", "super"):
        return _this_binding(receiver)
    root = receiver
    while root.type == "member_expression":
        root = root.child_by_field_name("object")
    return _binding(root, module) if root.type == "identifier" else None


def _source(statement: typing.Any) -> str | None:
    source = statement.child_by_field_name("source") if statement is not None else None
    return text(source).strip("'\"`") if source is not None else None


def _property(node: typing.Any, module: dict[str, set[str]]) -> Reference:
    parent = node.parent
    owner = _owner(node)
    if parent.type == "method_definition":
        in_class = parent.parent is not None and parent.parent.type == "class_body"
        return (
            ref("definition", node, scope="class", owner=owner) if in_class else ref("string", node)
        )
    if parent.type in ("method_signature", "abstract_method_signature"):
        return ref("definition", node, scope="class", owner=owner)
    if parent.type == "member_expression":
        receiver = parent.child_by_field_name("object")
        return ref(
            "attribute",
            node,
            owner=owner,
            receiver=text(receiver),
            receiver_binding=_receiver_binding(receiver, module),
        )
    if parent.type == "pair":
        return ref("string", node)
    return ref("field", node, owner=owner)


def _declaration(node: typing.Any) -> Reference | None:
    parent = node.parent
    named = node == parent.child_by_field_name("name")
    if parent.type in _TYPE_DECLS and named:
        scope = "module" if _owner(parent) is None and _scope(parent) is None else "class"
        return ref("definition", node, scope=scope, owner=_owner(parent), binding="type")
    if parent.type in ("function_declaration", "generator_function_declaration") and named:
        return ref("definition", node, scope="function" if _scope(parent) else "module")
    if parent.type == "variable_declarator" and named:
        value = parent.child_by_field_name("value")
        if (
            value is not None
            and value.type in ("arrow_function", "function_expression")
            and not _scope(parent)
        ):
            return ref("definition", node, scope="module")
        return ref("field", node)
    return None


def _import_like(node: typing.Any) -> Reference | None:
    parent = node.parent
    if parent.type not in ("import_specifier", "export_specifier"):
        return None
    if node != parent.child_by_field_name("name"):
        return ref("field", node)
    alias = parent.child_by_field_name("alias")
    statement = parent.parent
    while statement is not None and statement.type not in ("import_statement", "export_statement"):
        statement = statement.parent
    source = _source(statement)
    if parent.type == "export_specifier" and source is None:
        return None
    return ref("import", node, module=source, alias=text(alias) if alias is not None else None)


def _identifier(node: typing.Any, module: dict[str, set[str]]) -> Reference:
    if node.type == "property_identifier":
        return _property(node, module)
    if node.type == "shorthand_property_identifier":
        return ref("string", node)
    if node.type == "type_identifier":
        declared = _declaration(node)
        if declared is not None:
            return declared
        parent = node.parent
        qualifier = None
        if parent.type == "nested_type_identifier":
            qualifier = text(parent.child_by_field_name("module"))
        return ref(
            "type", node, qualifier=qualifier, owner=_owner(node), binding=_binding(node, module)
        )
    found = _declaration(node) or _import_like(node)
    if found is not None:
        return found
    if node.parent.type in (*_PARAMETERS, "catch_clause") or node.parent.type.endswith("_pattern"):
        return ref("field", node)
    if node.parent.type in ("namespace_import", "import_clause"):
        return ref("field", node)
    return ref("bare", node, owner=_owner(node), binding=_binding(node, module))


def _module_kinds(root: typing.Any) -> dict[str, set[str]]:
    facts = file_bindings(root)
    kinds: dict[str, set[str]] = {}
    for name in facts.defs:
        kinds.setdefault(name, set()).add("def")
    for name in facts.imports:
        kinds.setdefault(name, set()).add("import")
    for name in facts.others:
        kinds.setdefault(name, set()).add("other")
    return kinds


_NAMES = ("identifier", "type_identifier", "property_identifier", "shorthand_property_identifier")


def find_references(root: typing.Any, name: str) -> list[Reference]:
    """Every place `name` occurs under `root`, in byte order."""
    if not name:
        return []
    module = _module_kinds(root)
    pattern = word(name)
    found: list[Reference] = []
    for node in walk(root):
        if node.type in _NAMES and text(node) == name:
            found.append(_identifier(node, module))
        else:
            strings = {"string": "string_fragment", "template_string": "string_fragment"}
            skip = ("import_statement", "export_statement")
            found.extend(filter(None, [mention(node, name, pattern, strings, ("comment",), skip)]))
    return sorted(found, key=lambda r: r.start_byte)


def _heritage(declaration: typing.Any) -> list[str]:
    bases = []
    for clause in walk(declaration):
        if clause.type == "extends_clause":
            value = clause.child_by_field_name("value")
            if value is not None:
                bases.append(text(value))
        elif clause.type in ("implements_clause", "extends_type_clause"):
            bases.extend(
                text(t)
                for t in clause.named_children
                if t.type in ("type_identifier", "nested_type_identifier", "generic_type")
            )
        if clause.type == "class_body" or clause.type == "interface_body":
            break
    return [b.split("<")[0] for b in bases]


def _add_import(facts: FileBindings, statement: typing.Any) -> None:
    source = _source(statement) or ""
    for node in walk(statement):
        if node.type == "import_specifier":
            name = text(node.child_by_field_name("name"))
            alias = node.child_by_field_name("alias")
            facts.imports[text(alias) if alias is not None else name] = (source, name)
        elif node.type == "namespace_import":
            facts.imports[text(node.named_children[-1])] = (source, None)
        elif node.type == "identifier" and node.parent.type == "import_clause":
            facts.imports[text(node)] = (source, "default")


def _add_export(facts: FileBindings, statement: typing.Any) -> None:
    source = _source(statement)
    if source is not None and any(c.type == "*" for c in statement.children):
        facts.wildcards.append(source)
    for node in walk(statement):
        if node.type == "export_specifier":
            name = text(node.child_by_field_name("name"))
            alias = node.child_by_field_name("alias")
            facts.statics[text(alias) if alias is not None else name] = (source or "", name)
    declaration = statement.child_by_field_name("declaration")
    if declaration is not None:
        _add_declaration(facts, declaration)


def _add_declaration(facts: FileBindings, node: typing.Any) -> None:
    if node.type in (*_TYPE_DECLS, "function_declaration", "generator_function_declaration"):
        name = text(node.child_by_field_name("name"))
        facts.defs.add(name)
        if node.type in _CLASSES and _heritage(node):
            facts.bases[name] = _heritage(node)
    elif node.type in ("lexical_declaration", "variable_declaration"):
        for declarator in node.named_children:
            if declarator.type != "variable_declarator":
                continue
            value = declarator.child_by_field_name("value")
            target = (
                facts.defs
                if value is not None and value.type in ("arrow_function", "function_expression")
                else facts.others
            )
            target.update(_pattern_names(declarator.child_by_field_name("name")))


def file_bindings(root: typing.Any) -> FileBindings:
    """What the module level of one TypeScript file imports, declares, exports and extends."""
    facts = FileBindings()
    for node in root.named_children:
        if node.type == "import_statement":
            _add_import(facts, node)
        elif node.type == "export_statement":
            _add_export(facts, node)
        else:
            _add_declaration(facts, node)
    return facts
