# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Where a name occurs in one Python file, and what binds it there.

Python's own scope rule: a name bound anywhere in a function is local to all of that function,
and a class body's names are not seen by its methods.
"""

from __future__ import annotations

import re
import typing

from specweaver.workspace.ast.parsers.interfaces import FileBindings, Reference

_FUNCTION_SCOPES = ("function_definition", "lambda")
_IMPORTS = ("import_from_statement", "import_statement")
_PATTERNS = (
    "pattern_list",
    "tuple_pattern",
    "list_pattern",
    "tuple",
    "list",
    "parenthesized_expression",
    "list_splat_pattern",
)
_TARGETS = ("assignment", "augmented_assignment", "for_statement", "for_in_clause")
_PARAMETER_LISTS = ("parameters", "lambda_parameters")


def _text(node: typing.Any) -> str:
    return str(node.text.decode("utf-8", errors="replace"))


def _walk(root: typing.Any) -> typing.Iterator[typing.Any]:
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def _scope_of(node: typing.Any) -> typing.Any:
    """The function, lambda or class whose scope `node` is in; the module root otherwise."""
    child, parent = node, node.parent
    while parent is not None:
        if parent.type in _FUNCTION_SCOPES and child in (
            parent.child_by_field_name("parameters"),
            parent.child_by_field_name("body"),
        ):
            return parent
        if parent.type == "class_definition" and child == parent.child_by_field_name("body"):
            return parent
        child, parent = parent, parent.parent
    return child


def _in_import(node: typing.Any) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type in _IMPORTS:
            return True
        parent = parent.parent
    return False


def _is_target(ident: typing.Any) -> bool:
    """Whether `ident` is assigned to: an assignment, `for`, `with … as`, `except … as`, `:=`."""
    child, parent = ident, ident.parent
    while parent is not None and parent.type in _PATTERNS:
        child, parent = parent, parent.parent
    if parent is None:
        return False
    if parent.type in _TARGETS:
        return bool(child == parent.child_by_field_name("left"))
    if parent.type == "named_expression":
        return bool(child == parent.child_by_field_name("name"))
    return bool(parent.type == "as_pattern_target")


def _is_parameter(ident: typing.Any) -> bool:
    parent = ident.parent
    if parent.type in _PARAMETER_LISTS:
        return True
    if parent.type in ("default_parameter", "typed_default_parameter"):
        return bool(ident == parent.child_by_field_name("name"))
    if parent.type == "typed_parameter":
        return bool(parent.children and ident == parent.children[0])
    if parent.type in ("list_splat_pattern", "dictionary_splat_pattern"):
        return parent.parent is not None and parent.parent.type in _PARAMETER_LISTS
    return False


def _binding_kind(ident: typing.Any) -> str | None:
    """`def`, `other`, `escape`, or None when `ident` binds nothing."""
    parent = ident.parent
    if parent.type in ("function_definition", "class_definition"):
        return "def" if ident == parent.child_by_field_name("name") else None
    if parent.type in ("global_statement", "nonlocal_statement"):
        return "escape"
    if _is_parameter(ident) or _is_target(ident):
        return "other"
    return None


def _import_names(node: typing.Any) -> typing.Iterator[tuple[str, str, str | None, typing.Any]]:
    """`(local name, module, imported name or None, name node)` for each name an import binds."""
    if node.type == "import_statement":
        for name in node.children_by_field_name("name"):
            if name.type == "aliased_import":
                dotted = name.child_by_field_name("name")
                yield _text(name.child_by_field_name("alias")), _text(dotted), None, dotted
            else:
                yield _text(name).split(".")[0], _text(name).split(".")[0], None, name
        return
    module = _text(node.child_by_field_name("module_name"))
    for name in node.children_by_field_name("name"):
        if name.type == "aliased_import":
            dotted = name.child_by_field_name("name")
            yield _text(name.child_by_field_name("alias")), module, _text(dotted), dotted
        else:
            yield _text(name), module, _text(name), name


class _Scopes:
    """The names each scope binds, and how."""

    def __init__(self, root: typing.Any) -> None:
        self.root = root
        self.binds: dict[int, dict[str, set[str]]] = {}
        for node in _walk(root):
            if node.type == "identifier" and not _in_import(node):
                kind = _binding_kind(node)
                if kind is not None:
                    owner = node.parent if kind == "def" else node
                    self._bind(_scope_of(owner), _text(node), kind)
            elif node.type in _IMPORTS:
                for local, _, _, _ in _import_names(node):
                    self._bind(_scope_of(node), local, "import")

    def _bind(self, scope: typing.Any, name: str, kind: str) -> None:
        self.binds.setdefault(scope.id, {}).setdefault(name, set()).add(kind)

    def kinds(self, scope: typing.Any, name: str) -> set[str]:
        return self.binds.get(scope.id, {}).get(name, set())

    def lookup(self, node: typing.Any, name: str) -> str:
        """What binds `name` where `node` reads it."""
        scope, innermost = _scope_of(node), True
        while scope != self.root:
            kinds = self.kinds(scope, name)
            if scope.type == "class_definition":
                if innermost and kinds:
                    return "class"
            elif "escape" in kinds:
                return "escape"
            elif kinds:
                return "local"
            scope, innermost = _scope_of(scope), False
        return _module_binding(self.kinds(self.root, name))


def _module_binding(kinds: set[str]) -> str:
    if not kinds:
        return "free"
    if len(kinds) > 1:
        return "mixed"
    return {"def": "module_def", "import": "import", "other": "module_other"}.get(
        next(iter(kinds)), "mixed"
    )


def _owner(node: typing.Any) -> str | None:
    parent = node.parent
    while parent is not None:
        if parent.type == "class_definition":
            return _text(parent.child_by_field_name("name"))
        parent = parent.parent
    return None


def _root_identifier(node: typing.Any) -> typing.Any | None:
    while node is not None and node.type == "attribute":
        node = node.child_by_field_name("object")
    return node if node is not None and node.type == "identifier" else None


def _scope_word(node: typing.Any) -> str:
    scope = _scope_of(node)
    if scope.type == "class_definition":
        return "class"
    return "function" if scope.type in _FUNCTION_SCOPES else "module"


def _ref(kind: str, node: typing.Any, **extra: typing.Any) -> Reference:
    return Reference(kind, node.start_point[0] + 1, node.start_byte, node.end_byte, **extra)


def _identifier_ref(scopes: _Scopes, ident: typing.Any, name: str) -> Reference:
    parent = ident.parent
    if parent.type in ("function_definition", "class_definition") and (
        ident == parent.child_by_field_name("name")
    ):
        return _ref("definition", ident, scope=_scope_word(parent), owner=_owner(parent))
    if parent.type == "attribute" and ident == parent.child_by_field_name("attribute"):
        receiver = parent.child_by_field_name("object")
        root = _root_identifier(receiver)
        return _ref(
            "attribute",
            ident,
            owner=_owner(ident),
            receiver=_text(receiver),
            receiver_binding=scopes.lookup(root, _text(root)) if root is not None else None,
        )
    if parent.type == "keyword_argument" and ident == parent.child_by_field_name("name"):
        return _ref("keyword", ident)
    if parent.type in ("global_statement", "nonlocal_statement"):
        return _ref("scope_escape", ident)
    return _ref("bare", ident, owner=_owner(ident), binding=scopes.lookup(ident, name))


def _text_ref(node: typing.Any, name: str, word: re.Pattern[str]) -> Reference | None:
    if node.type == "comment":
        return _ref("text", node) if word.search(_text(node)) else None
    parts = [c for c in node.children if c.type == "string_content"]
    content = "".join(_text(c) for c in parts)
    if content == name and all(c.type != "interpolation" for c in node.children):
        return _ref("string", node)
    return _ref("text", node) if word.search(content) else None


def find_references(root: typing.Any, name: str) -> list[Reference]:
    """Every place `name` occurs under `root`, in byte order."""
    if not name:
        return []
    scopes = _Scopes(root)
    word = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
    refs: list[Reference] = []
    for node in _walk(root):
        if node.type == "identifier" and _text(node) == name and not _in_import(node):
            refs.append(_identifier_ref(scopes, node, name))
        elif node.type in ("comment", "string"):
            found = _text_ref(node, name, word)
            if found is not None:
                refs.append(found)
        elif node.type == "import_from_statement":
            refs.extend(
                _ref("import", dotted, module=module, alias=None if local == name else local)
                for local, module, imported, dotted in _import_names(node)
                if imported == name
            )
    return sorted(refs, key=lambda r: r.start_byte)


def _base_names(class_node: typing.Any) -> list[str]:
    bases = class_node.child_by_field_name("superclasses")
    names: list[str] = []
    for child in bases.named_children if bases is not None else []:
        if child.type == "subscript":
            child = child.child_by_field_name("value")
        if child is not None and child.type in ("identifier", "attribute"):
            names.append(_text(child))
    return names


def file_bindings(root: typing.Any) -> FileBindings:
    """What the module level of the file under `root` binds."""
    scopes = _Scopes(root)
    facts = FileBindings()
    for name, kinds in scopes.binds.get(root.id, {}).items():
        if "def" in kinds:
            facts.defs.add(name)
        if "other" in kinds:
            facts.others.add(name)
    for node in _walk(root):
        if _scope_of(node) != root:
            continue
        if node.type in _IMPORTS:
            _add_import(facts, node)
        elif node.type == "class_definition" and _base_names(node):
            facts.bases[_text(node.child_by_field_name("name"))] = _base_names(node)
    return facts


def _add_import(facts: FileBindings, node: typing.Any) -> None:
    if any(c.type == "wildcard_import" for c in node.children):
        facts.wildcards.append(_text(node.child_by_field_name("module_name")))
    for local, module, imported, _ in _import_names(node):
        facts.imports[local] = (module, imported)


def _import_statement_refs(node: typing.Any) -> list[Reference]:
    return [
        _ref(
            "import",
            dotted,
            module=_text(dotted),
            alias=None if local == module.split(".")[0] else local,
        )
        for local, module, _, dotted in _import_names(node)
    ]


def _from_statement_refs(node: typing.Any) -> list[Reference]:
    module_node = node.child_by_field_name("module_name")
    names = list(_import_names(node))
    listed = ",".join(imported or "" for _, _, imported, _ in names)
    found = [_ref("from", module_node, module=_text(module_node), receiver=listed)]
    for local, module, imported, dotted in names:
        alias = None if local == imported else local
        found.append(_ref("from_name", dotted, module=module, receiver=listed, alias=alias))
    return found


def module_references(root: typing.Any) -> list[Reference]:
    """Each module path in an import, each imported name of a `from` import, each string.

    `import a.b [as c]` is kind `import`; `from M import ...` gives one `from` (the span of `M`)
    and one `from_name` per name, carrying `module=M`, the names of the statement in `receiver`
    and any alias. A string's content is in `module`, for a move to check against.
    """
    found: list[Reference] = []
    for node in _walk(root):
        if node.type == "import_statement":
            found.extend(_import_statement_refs(node))
        elif node.type == "import_from_statement":
            found.extend(_from_statement_refs(node))
        elif node.type == "string":
            content = "".join(_text(c) for c in node.children if c.type == "string_content")
            found.append(_ref("string", node, module=content))
    return sorted(found, key=lambda r: r.start_byte)


def dotted_spans(root: typing.Any, dotted: str) -> list[Reference]:
    """Each expression outside imports whose text is exactly `dotted`, like `app.greeter`."""
    return [
        _ref("chain", node)
        for node in _walk(root)
        if node.type in ("attribute", "identifier")
        and _text(node) == dotted
        and not _in_import(node)
        and not (
            node.parent is not None
            and node.parent.type == "attribute"
            and node == node.parent.child_by_field_name("attribute")
        )
    ]
