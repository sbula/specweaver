"""Agent Memory Bank — Repository Facade.

Combines the core CRUD operations, DAG operations, and resilience behaviors into
a single, cohesive `MemoryRepository` class.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from specweaver.workspace.memory.repository.core import MemoryRepositoryCoreMixin
from specweaver.workspace.memory.repository.dag import MemoryRepositoryDAGMixin
from specweaver.workspace.memory.repository.resilience import MemoryRepositoryResilienceMixin


class MemoryRepository(
    MemoryRepositoryCoreMixin,
    MemoryRepositoryDAGMixin,
    MemoryRepositoryResilienceMixin,
):
    """Repository for the Agent Memory Bank (US-28).

    Provides core CRUD operations, formal State Transition Matrix enforcement,
    defect invariants, context cleanup, DAG cycle detection, and zombie resilience
    for task lifecycle management.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
