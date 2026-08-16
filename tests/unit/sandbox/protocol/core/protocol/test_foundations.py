# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The models and the interface every protocol parser is built on. TECH-051 CB-2.

Proves: A-VAL-01 FR-3

`ProtocolEndpoint`, `ProtocolMessage` and `ProtocolSchemaSet` are the unified output the three
parsers agree to produce, and `ProtocolSchemaInterface` is the contract that makes them
interchangeable to `ProtocolParserFactory`. They are small, which is why they were never tested and
why the tests are short — not why they do not matter: **the whole point of the interface is that a
caller can swap parsers, and nothing checked that the abstract methods were actually abstract.**
"""

from __future__ import annotations

import pytest

from specweaver.sandbox.protocol.core.models import (
    ProtocolEndpoint,
    ProtocolMessage,
    ProtocolSchemaSet,
)
from specweaver.sandbox.protocol.core.protocol_interfaces import (
    ProtocolSchemaError,
    ProtocolSchemaInterface,
)


class TestProtocolEndpoint:
    """The endpoint model the three parsers converge on."""

    def test_method_and_path_are_required(self) -> None:
        """[Hostile] an endpoint without a path is not addressable, so it must not construct."""
        with pytest.raises(Exception, match="path"):
            ProtocolEndpoint(method="GET")

    def test_properties_default_to_an_empty_dict_not_none(self) -> None:
        """[Boundary] callers index into `properties`; `None` would make every read a crash.

        A shared default would be worse still — asserted by mutating one instance and reading
        another, which is the classic mutable-default bug and invisible to a single-object test.
        """
        first = ProtocolEndpoint(method="GET", path="/a")
        second = ProtocolEndpoint(method="GET", path="/b")

        assert first.properties == {}
        first.properties["x"] = 1
        assert second.properties == {}


class TestProtocolMessage:
    """The payload model."""

    def test_name_is_required(self) -> None:
        """[Hostile] a message with no name cannot be matched against code."""
        with pytest.raises(Exception, match="name"):
            ProtocolMessage()

    def test_properties_are_not_shared_between_instances(self) -> None:
        """[Boundary] same mutable-default trap as the endpoint, same reason it matters."""
        first = ProtocolMessage(name="A")
        second = ProtocolMessage(name="B")

        first.properties["x"] = 1
        assert second.properties == {}


class TestProtocolSchemaSet:
    """The normalised whole-document result."""

    def test_both_halves_default_to_empty(self) -> None:
        """[Boundary] a document with neither endpoints nor messages is empty, not invalid."""
        empty = ProtocolSchemaSet()

        assert empty.endpoints == []
        assert empty.messages == []

    def test_it_carries_both_halves_together(self) -> None:
        """[Happy] the pairing is the point — drift compares endpoints against messages."""
        schema_set = ProtocolSchemaSet(
            endpoints=[ProtocolEndpoint(method="GET", path="/a")],
            messages=[ProtocolMessage(name="A")],
        )

        assert [e.path for e in schema_set.endpoints] == ["/a"]
        assert [m.name for m in schema_set.messages] == ["A"]


class TestProtocolSchemaInterface:
    """The contract that lets the factory return any parser behind one type."""

    def test_the_interface_cannot_be_instantiated(self) -> None:
        """[Hostile] an ABC with unimplemented methods must refuse, or a subclass can forget one."""
        with pytest.raises(TypeError):
            ProtocolSchemaInterface()  # type: ignore[abstract]

    def test_a_subclass_missing_a_method_cannot_be_instantiated(self) -> None:
        """[Hostile] the guarantee callers rely on: both methods exist on whatever they are given.

        This is what makes `isinstance(parser, ProtocolSchemaInterface)` worth asserting elsewhere.
        Without it the check would prove inheritance and not capability.
        """

        class HalfParser(ProtocolSchemaInterface):
            def extract_endpoints(self, raw_schema: str):  # type: ignore[override]
                return []

        with pytest.raises(TypeError, match="extract_messages"):
            HalfParser()  # type: ignore[abstract]


class TestProtocolSchemaError:
    """The one exception type every caller branches on."""

    def test_it_is_an_exception_and_carries_its_message(self) -> None:
        """[Happy] callers log `str(e)`; an error that loses its reason is a silent failure."""
        error = ProtocolSchemaError("Missing 'paths' key")

        assert isinstance(error, Exception)
        assert str(error) == "Missing 'paths' key"
