import sqlite3
from abc import ABC, abstractmethod
from typing import Any


class AbstractGraphRepository(ABC):
    """Abstract interface for persistent Graph Storage to support future Postgres adapter."""

    @abstractmethod
    def flush_to_db(self, nx_graph: Any) -> None:
        pass

    @abstractmethod
    def load_from_db(self) -> tuple[Any, dict[str, int]]:
        pass

    @abstractmethod
    def purge_file(self, file_id: str) -> None:
        pass

    @abstractmethod
    def get_all_file_hashes(self) -> dict[str, str]:
        pass

class SqliteGraphRepository(AbstractGraphRepository):
    """SQLite implementation of the Graph Repository."""

    def __init__(self, db_path: str, validated_service_name: str):
        self.db_path = db_path
        self.validated_service_name = validated_service_name
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        # WAL mode to prevent Lock Contention (RT-4)
        conn.execute("PRAGMA journal_mode=WAL;")
        # Enable Foreign Keys
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            # Nodes schema
            conn.execute('''
                CREATE TABLE IF NOT EXISTS nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    semantic_hash TEXT UNIQUE,
                    clone_hash TEXT,
                    file_id TEXT,
                    service_name TEXT,
                    package_name TEXT,
                    is_active INTEGER DEFAULT 1,
                    metadata JSON
                )
            ''')

            # Edges schema (no FK on target_id due to Lazy Edges)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS edges (
                    source_id INTEGER,
                    target_id INTEGER,
                    type TEXT,
                    metadata JSON,
                    PRIMARY KEY (source_id, target_id, type),
                    FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE
                )
            ''')

    def _extract_nodes(self, nx_graph: Any) -> tuple[list[Any], list[Any]]:
        import json
        node_batch = []
        ghost_hashes = set()

        for semantic_hash, data in nx_graph.nodes(data=True):
            if not data:  # It's a ghost node created by add_edge
                ghost_hashes.add(semantic_hash)
            else:
                meta_str = json.dumps(data.get("metadata", {}), default=str)
                node_batch.append((
                    semantic_hash, data.get("clone_hash", ""), data.get("file_id", ""),
                    self.validated_service_name, data.get("package_name", ""), 1, meta_str
                ))

        for _source_hash, target_hash, _data in nx_graph.edges(data=True):
            if target_hash not in nx_graph.nodes or not nx_graph.nodes[target_hash]:
                ghost_hashes.add(target_hash)

        ghost_batch = [(th, "", "", self.validated_service_name, "", 0, "{}") for th in ghost_hashes]
        return node_batch, ghost_batch

    def _get_hash_to_id_map(self, cursor: sqlite3.Cursor, hashes: list[Any]) -> dict[str, int]:
        hash_to_id = {}
        for i in range(0, len(hashes), 999):
            chunk = hashes[i:i+999]
            placeholders = ",".join(["?"] * len(chunk))
            cursor.execute(f"SELECT semantic_hash, id FROM nodes WHERE semantic_hash IN ({placeholders})", chunk)
            for h, int_id in cursor.fetchall():
                hash_to_id[h] = int_id
        return hash_to_id

    def flush_to_db(self, nx_graph: Any) -> None:
        import json
        node_batch, ghost_batch = self._extract_nodes(nx_graph)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            upsert_sql = '''
                INSERT INTO nodes (semantic_hash, clone_hash, file_id, service_name, package_name, is_active, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(semantic_hash) DO UPDATE SET
                    is_active=1, clone_hash=excluded.clone_hash, file_id=excluded.file_id,
                    package_name=excluded.package_name, metadata=excluded.metadata
            '''
            for i in range(0, len(node_batch), 5000):
                cursor.executemany(upsert_sql, node_batch[i:i+5000])

            ghost_sql = '''
                INSERT OR IGNORE INTO nodes (semantic_hash, clone_hash, file_id, service_name, package_name, is_active, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            '''
            for i in range(0, len(ghost_batch), 5000):
                cursor.executemany(ghost_sql, ghost_batch[i:i+5000])

            all_hashes = [row[0] for row in node_batch] + [row[0] for row in ghost_batch]
            hash_to_id = self._get_hash_to_id_map(cursor, all_hashes)

            edge_batch = []
            for source_hash, target_hash, data in nx_graph.edges(data=True):
                source_id = hash_to_id.get(source_hash)
                target_id = hash_to_id.get(target_hash)
                if source_id is not None and target_id is not None:
                    meta_str = json.dumps(data.get("metadata", {}), default=str)
                    edge_batch.append((source_id, target_id, data.get("type", "CALLS"), meta_str))

            edge_sql = '''
                INSERT OR REPLACE INTO edges (source_id, target_id, type, metadata)
                VALUES (?, ?, ?, ?)
            '''
            for i in range(0, len(edge_batch), 5000):
                cursor.executemany(edge_sql, edge_batch[i:i+5000])

            conn.commit()

    def load_from_db(self) -> tuple[Any, dict[str, int]]:
        import json

        import networkx as nx  # type: ignore

        nx_graph = nx.DiGraph()
        hash_to_id = {}

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, semantic_hash, clone_hash, file_id, service_name, package_name, metadata
                FROM nodes
                WHERE is_active = 1 AND service_name = ?
            ''', (self.validated_service_name,))

            for row in cursor.fetchall():
                node_id, semantic_hash, clone_hash, file_id, service_name, package_name, meta_str = row

                hash_to_id[semantic_hash] = node_id

                try:
                    metadata = json.loads(meta_str) if meta_str else {}
                except json.JSONDecodeError:
                    metadata = {}

                nx_graph.add_node(
                    node_id,
                    semantic_hash=semantic_hash,
                    clone_hash=clone_hash,
                    file_id=file_id,
                    service_name=service_name,
                    package_name=package_name,
                    metadata=metadata
                )

            cursor.execute('''
                SELECT e.source_id, e.target_id, e.type, e.metadata
                FROM edges e
                JOIN nodes n1 ON e.source_id = n1.id
                JOIN nodes n2 ON e.target_id = n2.id
                WHERE n1.is_active = 1 AND n2.is_active = 1
                  AND n1.service_name = ? AND n2.service_name = ?
            ''', (self.validated_service_name, self.validated_service_name))

            for source_id, target_id, edge_type, meta_str in cursor.fetchall():
                try:
                    metadata = json.loads(meta_str) if meta_str else {}
                except json.JSONDecodeError:
                    metadata = {}

                nx_graph.add_edge(source_id, target_id, type=edge_type, metadata=metadata)

        return nx_graph, hash_to_id

    def purge_file(self, file_id: str) -> None:
        with self._get_connection() as conn:
            conn.execute('''
                UPDATE nodes
                SET is_active = 0
                WHERE file_id = ? AND service_name = ?
            ''', (file_id, self.validated_service_name))
            conn.commit()

    def get_all_file_hashes(self) -> dict[str, str]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT file_id, clone_hash
                FROM nodes
                WHERE service_name = ? AND file_id != ""
                GROUP BY file_id
            ''', (self.validated_service_name,))
            return {row[0]: row[1] for row in cursor.fetchall()}
