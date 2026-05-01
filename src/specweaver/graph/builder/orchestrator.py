from pathlib import Path
from typing import Any

from specweaver.graph.builder.mapper import OntologyMapper
from specweaver.graph.engine.core import InMemoryGraphEngine
from specweaver.graph.engine.hashing import SemanticHasher


class GraphBuilder:
    """
    Application layer orchestrator for the Knowledge Graph.
    Coordinates the pure-logic engine with file system events and boundaries.
    """
    def __init__(self, engine: InMemoryGraphEngine, parser: Any = None):
        self.engine = engine
        self.mapper = OntologyMapper()
        self.hasher = SemanticHasher()
        self.parser = parser

    def ingest_ast(self, filepath: str, ast_data: dict[str, Any]) -> None:
        """
        Takes raw AST data, maps it to the ontology, and calculates deltas
        to safely upsert/remove nodes from the engine.
        """
        new_nodes, new_edges = self.mapper.map_ast_to_nodes(filepath, ast_data)
        new_hashes = {node.semantic_hash for node in new_nodes}
        new_edge_keys = {(e.source_hash, e.target_hash) for e in new_edges}

        file_hash = self.hasher.hash_file(filepath)
        norm_path = self.hasher._normalize_path(filepath)

        existing_hashes: set[str] = set()
        existing_edge_keys: set[tuple[str, str]] = set()

        with self.engine._lock:
            # Gather nodes associated with this file
            for int_id, data in self.engine._graph.nodes(data=True):
                if data.get("file_id") == filepath or data.get("file_id") == norm_path:
                    semantic_hash = self.engine._int_to_hash.get(int_id)
                    if semantic_hash:
                        existing_hashes.add(semantic_hash)

            # Gather edges originating from this file
            for u, v, _data in self.engine._graph.edges(data=True):
                source_hash = self.engine._int_to_hash.get(u)
                if source_hash in existing_hashes or source_hash == file_hash:
                    target_hash = self.engine._int_to_hash.get(v)
                    if target_hash:
                        existing_edge_keys.add((source_hash, target_hash))

        nodes_to_remove = existing_hashes - new_hashes
        edges_to_remove = existing_edge_keys - new_edge_keys

        # 1. Remove stale edges
        for u_hash, v_hash in edges_to_remove:
            self.engine.remove_edge(u_hash, v_hash)

        # 2. Remove stale nodes
        for hash_to_remove in nodes_to_remove:
            self.engine.remove_node(hash_to_remove)

        # 3. Upsert new/updated nodes
        for node in new_nodes:
            self.engine.upsert_node(node)

        # 4. Upsert new/updated edges
        for edge in new_edges:
            self.engine.upsert_edge(edge)

    def ingest_file(self, filepath: str) -> None:
        """
        Reads a file from disk, parses it via the injected parser, and ingests it.
        """
        path = Path(filepath)
        if not path.exists():
            self.ingest_ast(filepath, {"type": "module", "children": []})
            return

        if self.parser:
            ast_data = self.parser(str(path))
            self.ingest_ast(filepath, ast_data)

    def export_graph_to_disk(self, workspace_root: str, output_name: str) -> str:
        """
        Exports the in-memory graph to disk safely.
        RT-16: Path traversal prevention.
        RT-5: Appends *.graphml to .gitignore.
        """
        root_path = Path(workspace_root).resolve()

        # RT-16: Prevent path traversal in the filename
        if ".." in output_name or "/" in output_name or "\\" in output_name:
            raise ValueError(f"Invalid output name: {output_name}. Must be a simple filename.")

        if not output_name.endswith(".graphml"):
            output_name += ".graphml"

        output_path = (root_path / output_name).resolve()

        # Double check it is strictly inside the workspace root
        if not str(output_path).startswith(str(root_path)):
            raise ValueError("Path traversal attempt detected.")

        graphml_content = self.engine.to_graphml_string()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(graphml_content)

        self._ensure_gitignore(root_path)

        return str(output_path)

    def _ensure_gitignore(self, root_path: Path) -> None:
        """RT-5: Automatically append *.graphml to .gitignore to prevent proprietary architecture leaks."""
        gitignore_path = root_path / ".gitignore"

        if gitignore_path.exists():
            with open(gitignore_path, encoding="utf-8") as f:
                content = f.read()
            if "*.graphml" in content:
                return

        # Append or create
        with open(gitignore_path, "a", encoding="utf-8") as f:
            f.write("\n# SpecWeaver auto-generated graph exports\n*.graphml\n")
