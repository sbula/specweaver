# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from typing import Any

from specweaver.graph.core.engine.hashing import SemanticHasher
from specweaver.graph.core.engine.models import GraphEdge, GraphNode
from specweaver.graph.core.engine.ontology import EdgeKind, NodeKind

_MODULE_SEPARATORS = (".", "::", "/")

# A module we did not collect still gets a node, so a traversal can tell "nothing imports this"
# from "its importer is outside what we parsed". The prefix cannot collide with a real path.
_GHOST_PREFIX = "<unresolved-module>/"


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

        file_node = GraphNode(
            semantic_hash=file_hash, kind=NodeKind.FILE, name=basename, file_id=filepath
        )
        nodes.append(file_node)

        if not ast_data or not isinstance(ast_data, dict):
            return nodes, edges

        self._map_imports(ast_data.get("imports", []), file_hash, known_files, edges)

        # 2. Extract children based on type
        children = ast_data.get("children", [])
        if not isinstance(children, list):
            return nodes, edges

        for child in children:
            if not isinstance(child, dict):
                continue

            self._map_child(filepath, child, file_hash, nodes, edges, depth=1)

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
            target = (
                self.hasher.hash_file(resolved)
                if resolved is not None
                else self.hasher.hash_file(f"{_GHOST_PREFIX}{module}")
            )
            edges.append(
                GraphEdge(source_hash=file_hash, target_hash=target, kind=EdgeKind.IMPORTS)
            )

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
