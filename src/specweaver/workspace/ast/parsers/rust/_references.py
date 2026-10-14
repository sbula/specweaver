# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Where a name occurs in one Rust file, and what it is there.

A path like `crate::util::total` is a `path` reference whose `qualifier` is the part before the
last `::`. A method's definition carries its impl's type as `owner` and, in `impl Trait for
Type`, the trait as `qualifier`. A name inside a macro call is `string`: a macro may do
anything with it.
"""

from __future__ import annotations

import typing

from specweaver.workspace.ast.parsers._ref_tools import mention, ref, text, walk, word
from specweaver.workspace.ast.parsers.interfaces import FileBindings, Reference

_ITEMS = ("struct_item", "enum_item", "trait_item", "type_item", "union_item")
_FUNCTIONS = ("function_item", "function_signature_item")
_SCOPES = ("function_item", "closure_expression")
_PATTERN_PARENTS = (
    "closure_parameters",
    "tuple_pattern",
    "slice_pattern",
    "ref_pattern",
    "mut_pattern",
    "captured_pattern",
    "or_pattern",
    "match_pattern",
    "field_pattern",
    "tuple_struct_pattern",
)
_KEYWORD_SEGMENTS = ("crate", "self", "super")


def _type_name(node: typing.Any) -> str | None:
    """The plain name of a type node: `Loud` for `Loud`, `Wrap<T>` or `a::Loud`."""
    if node is None:
        return None
    if node.type == "generic_type":
        node = node.child_by_field_name("type")
    if node is not None and node.type == "scoped_type_identifier":
        node = node.child_by_field_name("name")
    return text(node) if node is not None else None


def _container(declaration: typing.Any) -> typing.Any | None:
    """The impl, trait or inline mod a declaration sits in, or None at the file's top."""
    parent = declaration.parent
    if parent is None or parent.type != "declaration_list":
        return None
    return parent.parent


def _definition(ident: typing.Any, declaration: typing.Any, is_type: bool) -> Reference:
    container = _container(declaration)
    if container is None:
        nested = declaration.parent is not None and declaration.parent.type != "source_file"
        scope = "function" if nested else "module"
        return ref("definition", ident, scope=scope, binding="type" if is_type else None)
    if container.type == "mod_item":
        return ref("definition", ident, scope="nested", binding="type" if is_type else None)
    if container.type == "trait_item":
        trait_name = text(container.child_by_field_name("name"))
        return ref("definition", ident, scope="class", owner=trait_name, binding="trait")
    trait = container.child_by_field_name("trait")
    owner = _type_name(container.child_by_field_name("type"))
    return ref(
        "definition", ident, scope="class", owner=owner, qualifier=text(trait) if trait else None
    )


def _impl_owner(node: typing.Any) -> str | None:
    """The type of the impl, or the trait, around `node`."""
    parent = node.parent
    while parent is not None:
        if parent.type == "impl_item":
            return _type_name(parent.child_by_field_name("type"))
        if parent.type == "trait_item":
            return text(parent.child_by_field_name("name"))
        parent = parent.parent
    return None


def _is_pattern_name(ident: typing.Any) -> bool:
    parent = ident.parent
    if parent.type in _PATTERN_PARENTS:
        return True
    if parent.type in ("parameter", "let_declaration", "for_expression"):
        return bool(ident == parent.child_by_field_name("pattern"))
    return False


def _binding(node: typing.Any) -> str:
    scope = node.parent
    while scope is not None:
        if scope.type in _SCOPES:
            declared = {
                text(n) for n in walk(scope) if n.type == "identifier" and _is_pattern_name(n)
            }
            if text(node) in declared:
                return "local"
        scope = scope.parent
    return "free"


def _in_macro(node: typing.Any) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type == "token_tree":
            return True
        parent = parent.parent
    return False


def _inside(node: typing.Any, kind: str) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type == kind:
            return True
        parent = parent.parent
    return False


def _declared(node: typing.Any) -> Reference | None:
    parent = node.parent
    if node != parent.child_by_field_name("name"):
        return None
    if parent.type in _ITEMS:
        return _definition(node, parent, is_type=True)
    if parent.type in _FUNCTIONS:
        return _definition(node, parent, is_type=False)
    if parent.type in (
        "mod_item",
        "enum_variant",
        "field_declaration",
        "const_item",
        "static_item",
    ):
        return ref("field", node)
    return None


def _used(node: typing.Any) -> Reference:
    parent = node.parent
    if parent.type in (
        "scoped_identifier",
        "scoped_type_identifier",
    ) and node == parent.child_by_field_name("name"):
        path = parent.child_by_field_name("path")
        return ref(
            "path", node, qualifier=text(path) if path is not None else "", owner=_impl_owner(node)
        )
    if parent.type == "field_expression" and node == parent.child_by_field_name("field"):
        return _field_use(node, parent)
    if node.type == "field_identifier":
        return ref("field", node)
    if node.type == "type_identifier":
        return ref("type", node, owner=_impl_owner(node))
    if _is_pattern_name(node):
        return ref("field", node)
    if parent.type == "macro_invocation":
        return ref("field", node)
    return ref("bare", node, owner=_impl_owner(node), binding=_binding(node))


def _field_use(node: typing.Any, parent: typing.Any) -> Reference:
    """`value.name(...)` is a method call on `value`; `value.name` alone is a field."""
    call = parent.parent
    if (
        call is None
        or call.type != "call_expression"
        or call.child_by_field_name("function") != parent
    ):
        return ref("field", node)
    value = parent.child_by_field_name("value")
    receiver = (
        "self"
        if value.type == "self"
        else (_binding(value) if value.type == "identifier" else None)
    )
    return ref(
        "attribute", node, owner=_impl_owner(node), receiver=text(value), receiver_binding=receiver
    )


def _identifier(node: typing.Any) -> Reference:
    if _in_macro(node):
        return ref("string", node)
    return _declared(node) or _used(node)


def use_entries(
    node: typing.Any, prefix: tuple[typing.Any, ...] = ()
) -> list[tuple[list[typing.Any], typing.Any | None, bool]]:
    """`(segments, alias, glob)` for each name one `use` tree brings in."""
    if node.type in ("identifier", "self", "crate", "super"):
        return [([*prefix, node], None, False)]
    if node.type == "scoped_identifier":
        return [([*prefix, *_segments(node)], None, False)]
    if node.type == "use_as_clause":
        path = node.child_by_field_name("path")
        return [([*prefix, *_segments(path)], node.child_by_field_name("alias"), False)]
    if node.type == "use_wildcard":
        path = next((c for c in node.named_children), None)
        return [([*prefix, *(_segments(path) if path is not None else [])], None, True)]
    if node.type == "scoped_use_list":
        path = node.child_by_field_name("path")
        inner = (*prefix, *(_segments(path) if path is not None else []))
        return use_entries(node.child_by_field_name("list"), inner)
    if node.type == "use_list":
        return [entry for child in node.named_children for entry in use_entries(child, prefix)]
    return []


def _segments(node: typing.Any) -> list[typing.Any]:
    return [n for n in walk(node) if n.type in ("identifier", *_KEYWORD_SEGMENTS)]


def _use_refs(declaration: typing.Any, name: str) -> list[Reference]:
    found = []
    for segments, alias, glob in use_entries(declaration.child_by_field_name("argument")):
        for i, segment in enumerate(segments):
            if text(segment) == name and segment.type == "identifier":
                last = i == len(segments) - 1 and not glob
                qualifier = "::".join(text(s) for s in segments[:i])
                found.append(
                    ref(
                        "import",
                        segment,
                        qualifier=qualifier,
                        scope="last" if last else "inner",
                        alias=text(alias) if alias is not None else None,
                    )
                )
    return found


def find_references(root: typing.Any, name: str) -> list[Reference]:
    """Every place `name` occurs under `root`, in byte order."""
    if not name:
        return []
    pattern = word(name)
    found: list[Reference] = []
    for node in walk(root):
        if node.type == "use_declaration":
            found.extend(_use_refs(node, name))
        elif (
            node.type in ("identifier", "type_identifier", "field_identifier")
            and text(node) == name
        ):
            if not _inside(node, "use_declaration"):
                found.append(_identifier(node))
        else:
            strings = {"string_literal": "string_content", "raw_string_literal": "string_content"}
            found.extend(
                filter(
                    None, [mention(node, name, pattern, strings, ("line_comment", "block_comment"))]
                )
            )
    return sorted(found, key=lambda r: r.start_byte)


def _add_use(facts: FileBindings, declaration: typing.Any) -> None:
    public = any(c.type == "visibility_modifier" for c in declaration.children)
    for segments, alias, glob in use_entries(declaration.child_by_field_name("argument")):
        names = [text(s) for s in segments]
        path = "::".join(names)
        if glob:
            facts.wildcards.append(path)
            continue
        local = (
            text(alias)
            if alias is not None
            else (names[-2] if names[-1] == "self" and len(names) > 1 else names[-1])
        )
        facts.imports[local] = (path, None)
        if public:
            facts.statics[local] = (path, "")


def file_bindings(root: typing.Any) -> FileBindings:
    """What the top of one Rust file uses, declares, re-exports, and which traits each type has."""
    facts = FileBindings()
    for node in root.named_children:
        if node.type == "use_declaration":
            _add_use(facts, node)
        elif node.type == "mod_item":
            facts.others.add(text(node.child_by_field_name("name")))
        elif node.type in (*_ITEMS, "function_item", "const_item", "static_item"):
            facts.defs.add(text(node.child_by_field_name("name")))
        elif node.type == "impl_item" and node.child_by_field_name("trait") is not None:
            owner = _type_name(node.child_by_field_name("type"))
            if owner:
                facts.bases.setdefault(owner, []).append(text(node.child_by_field_name("trait")))
    return facts
