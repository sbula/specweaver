import asyncio
from specweaver.core.config.cli_db_utils import bootstrap_database
from specweaver.core.config.database import create_async_engine
from sqlalchemy import text

async def check():
    bootstrap_database('test_check.db')
    engine = create_async_engine('sqlite+aiosqlite:///test_check.db')
    async with engine.begin() as conn:
        res = await conn.execute(text("PRAGMA table_info(projects)"))
        cols = [row[1] for row in res.fetchall()]
        print('Columns in projects:', cols)

asyncio.run(check())
