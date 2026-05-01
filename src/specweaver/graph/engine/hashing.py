import hashlib


class SemanticHasher:
    """
    Generates deterministic, stable semantic hashes for the Knowledge Graph.
    RT-21: File paths are case-insensitively normalized to prevent OS thrashing.
    """

    @staticmethod
    def _normalize_path(filepath: str) -> str:
        if not filepath:
            raise ValueError("Cannot hash empty filepath.")
        return filepath.replace("\\", "/").lower()

    def hash_file(self, filepath: str) -> str:
        """Hash a file based on its normalized path."""
        norm_path = self._normalize_path(filepath)
        return hashlib.sha256(f"FILE:{norm_path}".encode()).hexdigest()

    def hash_node(self, filepath: str, fully_qualified_name: str) -> str:
        """Hash a specific class or function within a file."""
        if not fully_qualified_name:
            raise ValueError("Cannot hash empty node name.")

        norm_path = self._normalize_path(filepath)
        # We explicitly DO NOT hash the node content (body) here!
        # Hashing the content would cause the node ID to change on every keystroke,
        # which would orphan LLM feedback metadata attached to the node ID.
        key = f"NODE:{norm_path}:{fully_qualified_name}"
        return hashlib.sha256(key.encode('utf-8')).hexdigest()
