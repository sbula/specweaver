# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Pydantic datamodels structurally bounding generic Schemas."""

from typing import Any

from pydantic import BaseModel, Field


class ProtocolEndpoint(BaseModel):
    """Represents an API Route from a Schema."""
    method: str
    path: str
    properties: dict[str, Any] = Field(default_factory=dict)

class ProtocolMessage(BaseModel):
    """Represents a discrete Schema Payload Type."""
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)

class ProtocolSchemaSet(BaseModel):
    """The normalized top-level output of a successfully parsed schema."""
    endpoints: list[ProtocolEndpoint] = Field(default_factory=list)
    messages: list[ProtocolMessage] = Field(default_factory=list)
