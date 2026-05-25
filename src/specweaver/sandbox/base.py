# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Atom base classes — fundamental building blocks of Flows.

Atoms are the smallest, indivisible elements of a Flow DAG.
They are orchestrated by the Engine, not by agents.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.models import ToolDefinition

logger = logging.getLogger(__name__)


class AtomStatus(StrEnum):
    """Result status for an Atom execution."""

    SUCCESS = "SUCCESS"  # Action completed as intended
    FAILED = "FAILED"  # Action failed permanently
    RETRY = "RETRY"  # Transient failure, Engine should retry


@dataclass(frozen=True)
class AtomResult:
    """Standardized result from an Atom execution.

    Attributes:
        status: The execution outcome.
        message: Human-readable summary for logs.
        exports: Data to write back to the Flow context.
    """

    status: AtomStatus
    message: str
    exports: dict[str, Any] = field(default_factory=dict)


class Atom(ABC):
    """Abstract base class for all Atoms.

    Atoms are stateless, deterministic building blocks.
    The Engine calls run() and persists state before/after.
    """

    @abstractmethod
    def run(self, context: dict[str, Any]) -> AtomResult:
        """Execute the discrete unit of work.

        Args:
            context: Runtime state from the Flow Engine
                     (populated by previous atoms).

        Returns:
            AtomResult describing the outcome.
        """

    def cleanup(self) -> None:  # noqa: B027
        """Graceful teardown hook (SIGINT/SIGTERM/Pause).

        Used strictly for releasing OS-level resources.
        Must NOT perform logical rollback.
        """


class BaseTool(ABC):
    """Abstract base class representing an LLM-accessible sandbox tool.

    All sandbox tool facades must inherit this class. Role-based access
    control (RBAC) is enforced structurally by the facade layer (methods
    physically absent), so no `allowed_intents` property is required here.
    """

    NO_ROLE: str = "no_role"

    @property
    @abstractmethod
    def role(self) -> str:
        """The role this facade is configured for.

        Return BaseTool.NO_ROLE for tools without role-based access control.
        """

    @abstractmethod
    def definitions(self) -> list[ToolDefinition]:
        """Return the list of tool definitions for LLM registration."""
