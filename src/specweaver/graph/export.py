import networkx as nx

from specweaver.graph.engine import InMemoryGraphEngine


def generate_graphml_payload(engine: InMemoryGraphEngine) -> str:
    """
    Serializes the InMemoryGraphEngine's NetworkX graph to GraphML format.
    Returns the raw XML string payload, leaving physical I/O to the CLI layer.
    """
    with engine._lock:
        return "".join(nx.generate_graphml(engine._graph))

def export_to_graphml(engine: InMemoryGraphEngine, target_path: str, workspace_root: str) -> None:
    """
    Serializes the graph and writes it to disk.
    Employs RT-16: Strict Path Traversal validation.
    """
    import os

    # RT-16: Resolve absolute paths to prevent ../../../ attacks
    abs_target = os.path.abspath(target_path)
    abs_root = os.path.abspath(workspace_root)

    if not abs_target.startswith(abs_root):
        raise ValueError(f"Path traversal detected. Target {abs_target} is outside workspace {abs_root}")

    payload = generate_graphml_payload(engine)

    with open(abs_target, "w", encoding="utf-8") as f:
        f.write(payload)
