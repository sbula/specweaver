# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from typing import Any, ClassVar

from specweaver.graph.core.engine.hashing import SemanticHasher
from specweaver.graph.core.engine.models import GraphEdge, GraphNode, fit_metadata_value
from specweaver.graph.core.engine.ontology import EdgeKind, NodeKind

_MODULE_SEPARATORS = (".", "::", "/")

# Something we did not collect still gets a node, so a traversal can tell "nothing depends on this"
# from "what depends on it is outside what we parsed". The prefixes cannot collide with a real path,
# and they are SEPARATE per kind: a module named `Foo` and a type named `Foo` are different unknowns,
# and one ghost for both would report a file's missing dependency as a type's missing parent.
_GHOST_MODULE_PREFIX = "<unresolved-module>/"
_GHOST_TYPE_PREFIX = "<unresolved-type>/"
_GHOST_PROCEDURE_PREFIX = "<unresolved-procedure>/"


def _module_segments(module: str) -> list[str]:
    """The path-ish parts of an import, whatever the language spelled them with.

    Python writes `a.b`, Rust `crate::alpha::beta`, Go and TypeScript `a/b`. Empty parts fall out,
    which is what turns a relative `.sibling` into `['sibling']` without a special case.
    """
    normalised = module
    for separator in _MODULE_SEPARATORS:
        normalised = normalised.replace(separator, "\x00")
    return [part for part in normalised.split("\x00") if part]


def resolve_module(module: str, known_files: frozenset[str]) -> str | None:
    """The one collected file an import names, or None when it names no single one.

    Suffix-matching, longest first: `crate::alpha::beta` finds `src/alpha/beta.rs` because `crate`
    is not a directory. A package is tried as both `a/b.<ext>` and `a/b/__init__.<ext>`. Matching is
    case-insensitive because `normalize_path` lowercases before hashing (RT-21), so a case-sensitive
    match here would disagree with the hash it is about to compute.

    None covers unresolved AND ambiguous alike. `ADR-006` makes the graph the truth store, so a
    reader seeing a visible unknown is better served than one following an invented dependency.
    """
    segments = _module_segments(module)
    if not segments:
        return None

    lowered = {path.replace("\\", "/").lower(): path for path in known_files}
    for start in range(len(segments)):
        stem = "/".join(segments[start:])
        matches = {original for lower, original in lowered.items() if _matches_stem(lower, stem)}
        if len(matches) == 1:
            return matches.pop()
        if matches:
            return None
    return None


def _ghost(hasher: SemanticHasher, prefix: str, name: str) -> tuple[str, dict[str, Any]]:
    """The ghost node an unresolved `name` points at, and the metadata saying what it was.

    `FR-12`. One helper for all three namespaces because they are three call sites making one
    promise: written separately, each could drift on its own while its own tests kept passing.
    """
    return hasher.hash_file(f"{prefix}{name}"), {"raw": fit_metadata_value(name)}


def _matches_stem(candidate: str, stem: str) -> bool:
    """Whether a collected path is the module `stem`, as a file or as a package."""
    for tail in (stem, f"{stem}/__init__"):
        without_suffix = candidate.rsplit(".", 1)[0]
        if without_suffix == tail or without_suffix.endswith(f"/{tail}"):
            return True
    return False


class OntologyMapper:
    """
    Translates raw Tree-Sitter/Polyglot AST outputs into the Universal Graph Ontology.
    """

    MAX_AST_DEPTH = 500

    def __init__(self, id_prefix: str = "") -> None:
        self.hasher = SemanticHasher(id_prefix)

    def map_ast_to_nodes(
        self,
        filepath: str,
        ast_data: dict[str, Any] | None,
        known_files: frozenset[str] = frozenset(),
        symbol_index: dict[str, set[str]] | None = None,
        procedure_index: dict[str, set[tuple[str, str]]] | None = None,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """
        Parses an AST dictionary and returns a list of mapped GraphNodes and GraphEdges.
        Always returns at least a FILE node.
        """
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        # 1. Create the FILE node
        file_hash = self.hasher.hash_file(filepath)

        # simple basename extraction
        basename = filepath
        if "/" in filepath:
            basename = filepath.split("/")[-1]
        elif "\\" in filepath:
            basename = filepath.split("\\")[-1]

        # A file the build could not read carries that on its node, so a traversal returning no
        # edges can be told apart from one whose file was never opened.
        unparsed = (ast_data or {}).get("unparsed") if isinstance(ast_data, dict) else None
        file_node = GraphNode(
            semantic_hash=file_hash,
            kind=NodeKind.FILE,
            name=basename,
            file_id=filepath,
            metadata={"unparsed": unparsed} if unparsed else {},
        )
        nodes.append(file_node)

        if not ast_data or not isinstance(ast_data, dict):
            return nodes, edges

        self._map_imports(ast_data.get("imports", []), file_hash, known_files, edges)
        # A call outside any declaration belongs to the file: module-level code is a real
        # dependency, and there is no symbol to attribute it to.
        self._map_calls(file_hash, ast_data.get("calls", []), procedure_index or {}, edges)

        # 2. Extract children based on type
        children = ast_data.get("children", [])
        if not isinstance(children, list):
            return nodes, edges

        for child in children:
            if not isinstance(child, dict):
                continue

            self._map_child(filepath, child, file_hash, nodes, edges, depth=1)
            self._map_supertypes(filepath, child, symbol_index or {}, edges)
            if child.get("name"):
                self._map_calls(
                    self.hasher.hash_node(filepath, str(child["name"])),
                    child.get("calls", []),
                    procedure_index or {},
                    edges,
                )

        return nodes, edges

    def _map_imports(
        self,
        imports: Any,
        file_hash: str,
        known_files: frozenset[str],
        edges: list[GraphEdge],
    ) -> None:
        """One `IMPORTS` edge per import: to the file it names, or to a ghost when it names none."""
        if not isinstance(imports, list):
            return
        for module in imports:
            if not isinstance(module, str) or not _module_segments(module):
                continue
            resolved = resolve_module(module, known_files)
            meta: dict[str, Any] = {}
            if resolved is not None:
                target = self.hasher.hash_file(resolved)
            else:
                target, meta = _ghost(self.hasher, _GHOST_MODULE_PREFIX, module)

            edges.append(
                GraphEdge(
                    source_hash=file_hash,
                    target_hash=target,
                    kind=EdgeKind.IMPORTS,
                    metadata=meta,
                )
            )

    _SUPERTYPE_EDGE_KINDS: ClassVar[dict[str, EdgeKind]] = {
        "extends": EdgeKind.EXTENDS,
        "implements": EdgeKind.IMPLEMENTS,
    }

    def _map_supertypes(
        self,
        filepath: str,
        child: dict[str, Any],
        symbol_index: dict[str, set[str]],
        edges: list[GraphEdge],
    ) -> None:
        """One edge per declared supertype, from the type to the type it names.

        Type to type, not file to file: `IMPORTS` already answers which files a file depends on, and
        this answers which type another is built from. Unresolved and ambiguous both become a ghost —
        two classes of one name are not one class, and a reader following an invented parent is worse
        served than one seeing a visible unknown.
        """
        name = child.get("name")
        if not name:
            return
        source = self.hasher.hash_node(filepath, str(name))
        for record in child.get("supertypes", []) or []:
            if not isinstance(record, dict):
                continue
            kind = self._SUPERTYPE_EDGE_KINDS.get(str(record.get("kind", "")))
            supertype = record.get("name")
            if kind is None or not supertype:
                continue
            target, meta = self._supertype_target(str(supertype), symbol_index)
            edges.append(
                GraphEdge(source_hash=source, target_hash=target, kind=kind, metadata=meta)
            )

    def _supertype_target(
        self, name: str, symbol_index: dict[str, set[str]]
    ) -> tuple[str, dict[str, Any]]:
        """The node the supertype names, or a ghost carrying the name it could not resolve."""
        declared_in = symbol_index.get(name, set())
        if len(declared_in) == 1:
            return self.hasher.hash_node(next(iter(declared_in)), name), {}
        return _ghost(self.hasher, _GHOST_TYPE_PREFIX, name)

    def _map_calls(
        self,
        source: str,
        callees: Any,
        procedure_index: dict[str, set[tuple[str, str]]],
        edges: list[GraphEdge],
    ) -> None:
        """One `CALLS` edge per call site, to the procedure it names or to a ghost.

        A recursive call becomes a self-edge rather than being filtered: a function calling itself
        is a real dependency, and a traversal that silently drops it is wrong about the graph.
        """
        if not isinstance(callees, list):
            return
        for callee in callees:
            if not isinstance(callee, str) or not callee:
                continue
            target, meta = self._callee_target(callee, procedure_index)
            edges.append(
                GraphEdge(
                    source_hash=source, target_hash=target, kind=EdgeKind.CALLS, metadata=meta
                )
            )

    def _callee_target(
        self, name: str, procedure_index: dict[str, set[tuple[str, str]]]
    ) -> tuple[str, dict[str, Any]]:
        """The procedure the call names, or a ghost carrying the name it could not resolve."""
        declared_in = procedure_index.get(name, set())
        if len(declared_in) == 1:
            filepath, qualified = next(iter(declared_in))
            return self.hasher.hash_node(filepath, qualified), {}
        return _ghost(self.hasher, _GHOST_PROCEDURE_PREFIX, name)

    def _check_depth(
        self, filepath: str, file_hash: str, nodes: list[GraphNode], depth: int
    ) -> bool:
        if depth > self.MAX_AST_DEPTH:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"AST Bomb Protection: exceeded MAX_AST_DEPTH ({self.MAX_AST_DEPTH}) in {filepath}"
            )
            # Mark the root file node as partial
            for node in nodes:
                if node.kind == NodeKind.FILE and node.semantic_hash == file_hash:
                    if not getattr(node, "metadata", None):
                        node.metadata = {}
                    node.metadata["is_partial"] = True
            return True
        return False

    def _map_child(
        self,
        filepath: str,
        child: dict[str, Any],
        file_hash: str,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        depth: int,
    ) -> None:
        if self._check_depth(filepath, file_hash, nodes, depth):
            return

        node_type = child.get("type", "")
        name = child.get("name", "")

        if not name:
            return

        kind = None
        if node_type in ("function_definition", "method_declaration"):
            kind = NodeKind.PROCEDURE
        elif node_type in ("class_definition", "class_declaration", "interface_declaration"):
            kind = NodeKind.DATA_STRUCTURE
        elif node_type == "module":
            kind = NodeKind.MODULE

        if kind:
            node_hash = self.hasher.hash_node(filepath, name)
            nodes.append(GraphNode(semantic_hash=node_hash, kind=kind, name=name, file_id=filepath))
            # Build CONTAINS edge from FILE to this structural node
            edges.append(
                GraphEdge(source_hash=file_hash, target_hash=node_hash, kind=EdgeKind.CONTAINS)
            )

        # Recurse for nested children
        nested_children = child.get("children", [])
        if isinstance(nested_children, list):
            for nested in nested_children:
                if isinstance(nested, dict):
                    self._map_child(filepath, nested, file_hash, nodes, edges, depth + 1)
