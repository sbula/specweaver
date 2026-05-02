import anyio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from specweaver.core.config.database import session_scope
from specweaver.core.flow.store import Base as FlowBase
from specweaver.infrastructure.llm.store import Base as LlmBase, LlmProfile
from specweaver.workspace.store import Base as WorkspaceBase


def bootstrap_database(db_path: str) -> None:
    """Create tables and apply defaults natively. Idempotent."""

    async def _create_all() -> None:
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        async with engine.begin() as conn:
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

    anyio.run(_create_all)
