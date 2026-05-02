from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from specweaver.core.config.database import create_async_engine, session_scope
from specweaver.infrastructure.llm.store import LlmProfile
from specweaver.interfaces.cli._db_utils import bootstrap_database

if TYPE_CHECKING:
    from pathlib import Path


def test_bootstrap_database_happy_path(tmp_path: Path) -> None:
    """bootstrap_database should be idempotent and create seed data."""
    db_path = tmp_path / "test.db"
    
    # Run twice to test idempotence
    bootstrap_database(str(db_path))
    bootstrap_database(str(db_path))
    
    # Verify tables created using standard sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert "llm_profiles" in tables
    assert "projects" in tables
    assert "active_state" in tables
    conn.close()

def test_bootstrap_database_seeds_data(tmp_path: Path) -> None:
    """Verifies that the 3 default profiles are seeded."""
    db_path = tmp_path / "test.db"
    bootstrap_database(str(db_path))
    
    import anyio
    
    async def _verify():
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        try:
            async with session_scope(engine) as session:
                result = await session.execute(select(LlmProfile))
                profiles = result.scalars().all()
                assert len(profiles) == 3
                names = {p.name for p in profiles}
                assert names == {"system-default", "implement", "review"}
        finally:
            await engine.dispose()
            
    anyio.run(_verify)
