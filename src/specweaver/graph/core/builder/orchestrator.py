from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.graph.core.builder.mapper import OntologyMapper
from specweaver.graph.core.engine.hashing import SemanticHasher

if TYPE_CHECKING:
    from specweaver.graph.core.engine.protocol import GraphEngineProtocol


class GraphBuilder:
    """
    Application layer orchestrator for the Knowledge Graph.
    Coordinates the pure-logic engine with file system events and boundaries.
    """

    def __init__(
        self, engine: "GraphEngineProtocol", parser: Any = None, id_prefix: str = ""
    ) -> None:
        """
        Initializes the GraphBuilder.

        Args:
            engine: The GraphEngine implementation (e.g. InMemoryGraphEngine).
            parser: Optional callable that returns an AST dict for a filepath.
            id_prefix: The microservice prefix for globally unique IDs.
        """
        self.engine = engine
        self.parser = parser
        self.mapper = OntologyMapper(id_prefix=id_prefix)
        self.id_prefix = id_prefix
        self.hasher = SemanticHasher(id_prefix=id_prefix)

    def ingest_ast(self, filepath: str, ast_data: dict[str, Any]) -> None:
        """
        Takes raw AST data, maps it to the ontology, and calculates deltas
        to safely upsert/remove nodes from the engine.
        """
        new_nodes, new_edges = self.mapper.map_ast_to_nodes(filepath, ast_data)
        new_hashes = {node.semantic_hash for node in new_nodes}
        new_edge_keys = {(e.source_hash, e.target_hash) for e in new_edges}

        file_hash = self.hasher.hash_file(filepath)
        norm_path = self.hasher.normalize_path(filepath)

        existing_hashes, existing_edge_keys = self._get_existing_elements(
            filepath, norm_path, file_hash
        )

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

    def collect_files(self, target_path: Path) -> set[str]:
        """Collects all python files from a target path."""
        target = Path(target_path)
        if target.is_file():
            if target.suffix == ".py":
                return {str(target)}
            return set()

        found = set()
        for p in target.rglob("*.py"):
            if p.is_file():
                found.add(str(p))
        return found

    def ingest_target(self, target_path: Path) -> int:
        """Collects files and ingests them, returning the number of ingested files."""
        # Special case: if it's a non-existent path, fall back to ingest_file for degradation
        if not Path(target_path).exists():
            self.ingest_file(str(target_path))
            return 1

        files = self.collect_files(target_path)
        count = 0
        for f in files:
            self.ingest_file(f)
            count += 1
        return count

    def _get_existing_elements(
        self, filepath: str, norm_path: str, file_hash: str
    ) -> tuple[set[str], set[tuple[str, str]]]:
        # Use public API for nodes (uses the _file_index internally for O(1) performance)
        existing_hashes = self.engine.get_nodes_for_file(filepath)

        # Include the file's own hash in case it has incoming/outgoing edges not strictly bound to its internal AST
        query_hashes = existing_hashes | {file_hash}

        # Use public API for edges (uses NetworkX nbunch optimized lookup)
        existing_edge_keys = self.engine.get_edges_involving(query_hashes)

        return existing_hashes, existing_edge_keys

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


class GraphOrchestrator:
    """High-level service coordinating graph ingestion and persistence."""

    @staticmethod
    def build_target(target_path: Path, project_path: Path) -> int:
        from specweaver.assurance.graph.loader import load_topology
        from specweaver.graph.core.engine.core import InMemoryGraphEngine
        from specweaver.graph.core.store.repository import SqliteGraphRepository
        from specweaver.workspace.ast.adapters.graph_adapter import extract_ast_dict

        service_name = "default"
        topology = load_topology(project_path)
        if topology and topology.nodes:
            for node in topology.nodes.values():
                if node.yaml_path and str(node.yaml_path.parent) == str(project_path.resolve()):
                    service_name = node.name
                    break

        db_path = str(project_path / ".specweaver" / "graph.db")
        repo = SqliteGraphRepository(db_path, service_name)
        engine = InMemoryGraphEngine()
        builder = GraphBuilder(engine=engine, parser=extract_ast_dict, id_prefix=service_name)

        # Stale Graph Boot Trap
        files = builder.collect_files(target_path)
        repo.purge_stale_entries(files)

        # Load existing graph state
        semantic_digraph = repo.load_from_db()
        engine.load_semantic_digraph(semantic_digraph)

        # Ingest
        count = builder.ingest_target(target_path)

        # Persist
        repo.persist_semantic_digraph(engine.export_semantic_digraph())

        return count
