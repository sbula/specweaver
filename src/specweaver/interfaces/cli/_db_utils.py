import asyncio

import anyio
import nest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from specweaver.core.config.database import session_scope
from specweaver.core.flow.store import Base as FlowBase
from specweaver.infrastructure.llm.store import Base as LlmBase
from specweaver.infrastructure.llm.store import LlmProfile
from specweaver.workspace.store import Base as WorkspaceBase


def bootstrap_database(db_path: str) -> None:
    """Create tables and apply defaults natively. Idempotent."""
    import pathlib

    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async def _create_all() -> None:
        db_posix = pathlib.Path(db_path).absolute().as_posix()
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_posix}")
        async with engine.begin() as conn:
            print("LlmBase tables:", LlmBase.metadata.tables.keys())
            print("WorkspaceBase tables:", WorkspaceBase.metadata.tables.keys())
            print("FlowBase tables:", FlowBase.metadata.tables.keys())
            await conn.run_sync(LlmBase.metadata.create_all)
            await conn.run_sync(WorkspaceBase.metadata.create_all)
            await conn.run_sync(FlowBase.metadata.create_all)

        # Seed default LLM profiles if empty
        async with session_scope(engine) as session:
            result = await session.execute(select(LlmProfile).limit(1))
            if result.first() is None:
                defaults = [
                    LlmProfile(
                        name="system-default",
                        is_global=1,
                        provider="gemini",
                        model="gemini-2.5-pro",
                        temperature=0.7,
                        max_output_tokens=8192,
                        response_format="text",
                    ),
                    LlmProfile(
                        name="implement",
                        is_global=1,
                        provider="gemini",
                        model="gemini-2.5-flash",
                        temperature=0.2,
                        max_output_tokens=8192,
                        response_format="text",
                    ),
                    LlmProfile(
                        name="review",
                        is_global=1,
                        provider="gemini",
                        model="gemini-2.5-flash",
                        temperature=0.0,
                        max_output_tokens=8192,
                        response_format="text",
                    ),
                ]
                session.add_all(defaults)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        nest_asyncio.apply(loop)
        loop.run_until_complete(_create_all())
    else:
        anyio.run(_create_all)
