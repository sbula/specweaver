# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Where a name occurs in one C or C++ file, and what it is there.

The two grammars share their C core, so one finder reads both. A definition and a
prototype carry the namespace around them as `module`; a method carries its class as
`owner`, also when it is defined out of line as `Class::method`. A name in a macro body is
`string`: the preprocessor may do anything with it.
"""

from __future__ import annotations

import typing

from specweaver.workspace.ast.parsers._ref_tools import inside, mention, ref, text, walk, word
from specweaver.workspace.ast.parsers.interfaces import FileBindings, Reference

_TYPES = ("struct_specifier", "class_specifier", "union_specifier", "enum_specifier")
_NAMES = ("identifier", "type_identifier", "field_identifier", "namespace_identifier")
_STRINGS = {"string_literal": "string_content", "raw_string_literal": "raw_string_content"}
_COMMENTS = ("comment",)


def _namespace(node: typing.Any) -> str:
    names = []
    parent = node.parent
    while parent is not None:
        if parent.type == "namespace_definition" and parent.child_by_field_name("name") is not None:
            names.append(text(parent.child_by_field_name("name")))
        parent = parent.parent
    return "::".join(reversed(names))


def _class_of(node: typing.Any) -> str | None:
    """The class a node is a member of: its class body, or the scope of an out-of-line method."""
    parent = node.parent
    while parent is not None:
        if (
            parent.type in ("class_specifier", "struct_specifier")
            and parent.child_by_field_name("body") is not None
        ):
            name = parent.child_by_field_name("name")
            return text(name) if name is not None else None
        if parent.type == "function_definition":
            scope = _out_of_line_scope(parent)
            if scope:
                return scope
        parent = parent.parent
    return None


def _declarator_name(declarator: typing.Any) -> typing.Any | None:
    """The name node at the bottom of a declarator chain (`*f(int)`, `C::m(...)`)."""
    node = declarator
    while node is not None and node.type not in (
        "identifier",
        "field_identifier",
        "qualified_identifier",
        "destructor_name",
        "operator_name",
    ):
        node = node.child_by_field_name("declarator")
    return node


def _out_of_line_scope(function: typing.Any) -> str | None:
    name = _declarator_name(function.child_by_field_name("declarator"))
    if name is not None and name.type == "qualified_identifier":
        scope = name.child_by_field_name("scope")
        return text(scope).split("::")[-1].split("<")[0] if scope is not None else None
    return None


def _is_static(node: typing.Any) -> bool:
    return any(c.type == "storage_class_specifier" and text(c) == "static" for c in node.children)


def _function_role(ident: typing.Any) -> Reference | None:
    """A function's name in its definition or prototype."""
    holder = ident.parent
    if holder.type == "qualified_identifier":
        holder = holder.parent
    if holder.type != "function_declarator":
        return None
    outer = holder.parent
    while outer is not None and outer.type in (
        "pointer_declarator",
        "reference_declarator",
        "function_declarator",
    ):
        outer = outer.parent
    if outer is None:
        return None
    owner = _class_of(ident)
    kind = "definition" if outer.type == "function_definition" else "declaration"
    if outer.type not in ("function_definition", "declaration", "field_declaration"):
        return None
    binding = "static" if _is_static(outer) else None
    return ref(
        kind,
        ident,
        scope="class" if owner else "module",
        owner=owner,
        module=_namespace(ident),
        binding=binding,
    )


def _declared_name(inner: typing.Any) -> str | None:
    """The variable a parameter or a local declaration introduces."""
    local = (
        inner.type == "declaration"
        and inner.parent is not None
        and inner.parent.type != "translation_unit"
    )
    if inner.type not in ("parameter_declaration", "init_declarator") and not local:
        return None
    declarator = inner.child_by_field_name("declarator")
    name = _declarator_name(declarator) if declarator is not None else None
    return text(name) if name is not None and name.type == "identifier" else None


def _locals(node: typing.Any) -> set[str]:
    names: set[str] = set()
    scope = node.parent
    while scope is not None:
        if scope.type == "function_definition":
            names.update(n for n in map(_declared_name, walk(scope)) if n)
        scope = scope.parent
    return names


def _member(ident: typing.Any) -> Reference | None:
    parent = ident.parent
    if parent.type == "field_expression" and ident == parent.child_by_field_name("field"):
        call = parent.parent
        if call is None or call.type != "call_expression":
            return ref("field", ident)
        receiver = parent.child_by_field_name("argument")
        binding = (
            "this"
            if receiver.type == "this"
            else ("local" if text(receiver) in _locals(ident) else None)
        )
        return ref(
            "attribute",
            ident,
            owner=_class_of(ident),
            receiver=text(receiver),
            receiver_binding=binding,
        )
    if parent.type == "qualified_identifier" and ident == parent.child_by_field_name("name"):
        scope = parent.child_by_field_name("scope")
        return ref(
            "path",
            ident,
            qualifier=text(scope) if scope is not None else "",
            owner=_class_of(ident),
            module=_namespace(ident),
        )
    return None


def _type_role(ident: typing.Any) -> Reference:
    parent = ident.parent
    if parent.type in _TYPES and parent.child_by_field_name("body") is not None:
        return ref(
            "definition",
            ident,
            scope="class" if _class_of(parent) else "module",
            module=_namespace(ident),
            binding="type",
        )
    if parent.type == "type_definition":
        return ref("definition", ident, scope="module", module=_namespace(ident), binding="type")
    return ref("type", ident, module=_namespace(ident))


def _identifier(ident: typing.Any) -> Reference:
    if ident.type == "type_identifier" and ident.parent.type != "qualified_identifier":
        return _type_role(ident)
    found = _function_role(ident) or _member(ident)
    if found is not None:
        return found
    if ident.type == "field_identifier":
        return ref("field", ident)
    if ident.type == "namespace_identifier":
        return ref("bare", ident, binding="scope", module=_namespace(ident))
    if ident.parent.type in ("preproc_def", "preproc_function_def", "preproc_params"):
        return ref("string", ident)
    binding = "local" if text(ident) in _locals(ident) else "free"
    return ref("bare", ident, owner=_class_of(ident), module=_namespace(ident), binding=binding)


def _using(node: typing.Any, name: str) -> list[Reference]:
    path = next((c for c in node.named_children if c.type == "qualified_identifier"), None)
    if path is None:
        return []
    last = path.child_by_field_name("name")
    while last is not None and last.type == "qualified_identifier":
        last = last.child_by_field_name("name")
    if last is None or text(last) != name:
        return []
    qualifier = text(path)[: -len(name)].rstrip(":")
    return [ref("import", last, qualifier=qualifier, scope="last")]


def find_references(root: typing.Any, name: str) -> list[Reference]:
    """Every place `name` occurs under `root`, in byte order."""
    if not name:
        return []
    pattern = word(name)
    found: list[Reference] = []
    for node in walk(root):
        if node.type == "using_declaration":
            found.extend(_using(node, name))
        elif (
            node.type in _NAMES and text(node) == name and not inside(node, ("using_declaration",))
        ):
            found.append(_identifier(node))
        elif node.type == "preproc_arg":
            if pattern.search(text(node)):
                found.append(ref("string", node))
        elif node.parent is not None and node.parent.type != "preproc_include":
            found.extend(filter(None, [mention(node, name, pattern, _STRINGS, _COMMENTS)]))
    return sorted(found, key=lambda r: r.start_byte)


def _add_class(facts: FileBindings, node: typing.Any) -> None:
    name = node.child_by_field_name("name")
    if name is None:
        return
    facts.defs.add(text(name))
    clause = next((c for c in node.children if c.type == "base_class_clause"), None)
    if clause is not None:
        kinds = ("type_identifier", "qualified_identifier", "template_type")
        facts.bases[text(name)] = [text(c) for c in clause.named_children if c.type in kinds]


def file_bindings(root: typing.Any) -> FileBindings:
    """Quoted includes (as `imports`), `using namespace` (as `wildcards`) and class bases."""
    facts = FileBindings()
    for node in walk(root):
        if node.type == "preproc_include":
            path = node.child_by_field_name("path")
            if path is not None and path.type == "string_literal":
                facts.imports[text(path).strip('"')] = ("include", None)
        elif node.type == "using_declaration" and any(c.type == "namespace" for c in node.children):
            facts.wildcards.append(text(node.named_children[-1]))
        elif node.type in ("class_specifier", "struct_specifier") and node.child_by_field_name(
            "body"
        ):
            _add_class(facts, node)
    return facts
