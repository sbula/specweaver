# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Abstract interface isolating format-specific parser logic."""

from abc import ABC, abstractmethod

from specweaver.sandbox.protocol.core.models import ProtocolEndpoint, ProtocolMessage


class ProtocolSchemaError(Exception):
    """Native exception thrown when a schema is violently malformed and untraversable."""

    pass


class ProtocolSchemaInterface(ABC):
    """Boundary unifying how schema properties are explicitly queried by the sandbox."""

    @abstractmethod
    def extract_endpoints(self, raw_schema: str) -> list[ProtocolEndpoint]:
        """Parse schema and return all endpoints via unified typing."""
        ...

    @abstractmethod
    def extract_messages(self, raw_schema: str) -> list[ProtocolMessage]:
        """Parse schema and return all discrete payload types via unified typing."""
        ...
