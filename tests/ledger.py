# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A real cost ledger for tests: a fresh SQLite database, read back row by row.

The collector writes every call to the ledger itself (`C-FLOW-01` FR-4), so a test that wants to
know what a call recorded reads the ledger, not the collector. Import it explicitly:
`from tests.ledger import Ledger`.
"""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace
from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database

if TYPE_CHECKING:
    from pathlib import Path


class Ledger:
    """A fresh ledger at `folder/specweaver.db`; `db` goes to the collector, `rows` reads it back."""

    def __init__(self, folder: Path) -> None:
        self.path = folder / "specweaver.db"
        bootstrap_database(str(self.path))
        self.db = Database(self.path)

    @property
    def rows(self) -> list[SimpleNamespace]:
        """Every row, oldest first; `estimated_cost_usd` names the cost as a record did."""
        with sqlite3.connect(self.path) as conn:
            conn.row_factory = sqlite3.Row
            found = conn.execute("SELECT * FROM llm_usage_log ORDER BY id").fetchall()
        return [
            SimpleNamespace(**dict(row), estimated_cost_usd=row["estimated_cost"]) for row in found
        ]
