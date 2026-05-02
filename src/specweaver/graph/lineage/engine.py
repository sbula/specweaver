from typing import Any

from specweaver.graph.lineage.repository import LineageRepositoryProtocol


class LineageEngine:
    """Pure mathematical engine for graph traversal and cycle detection of artifacts."""

    def __init__(self, repo: LineageRepositoryProtocol):
        self.repo = repo

    def find_root(self, current_uuid: str) -> str:
        """Safe walk up the lineage graph to find the root node, avoiding cycles."""
        visited = set()
        current = current_uuid
        while True:
            if current in visited:
                break
            visited.add(current)
            try:
                history = self.repo.get_artifact_history(current)
            except Exception:
                # If repository is disconnected or corrupted, fail gracefully
                history = []
            if not history:
                break
            parent_id = history[0].get("parent_id")
            if not parent_id:
                break
            current = parent_id
        return current

    def build_tree(self, root_uuid: str) -> dict[str, Any]:
        """Recursively build a tree representation of the lineage graph, detecting cycles."""

        def _build(node_uid: str, visited: set[str]) -> dict[str, Any]:
            if node_uid in visited:
                return {
                    "id": node_uid,
                    "history": [],
                    "children": [],
                    "circular": True,
                }

            visited.add(node_uid)
            try:
                hist = self.repo.get_artifact_history(node_uid)
                children_rows = self.repo.get_children(node_uid)
            except Exception:
                hist = []
                children_rows = []

            child_uids = list(
                dict.fromkeys(
                    c["artifact_id"]
                    for c in children_rows
                    if c["artifact_id"] != node_uid
                )
            )

            node_data: dict[str, Any] = {
                "id": node_uid,
                "history": hist,
                "circular": False,
                "children": [],
            }

            for c_uid in child_uids:
                node_data["children"].append(_build(c_uid, visited.copy()))

            return node_data

        return _build(root_uuid, set())
