# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`AsyncAPIParser` turns an AsyncAPI document into channels and messages. TECH-051 CB-2.

Proves: A-VAL-01 FR-1, A-VAL-01 FR-3

**Nothing protected this module before 2026-08-16.** It was one of the nine files created empty in
`14d889f2` and never filled, so `A-VAL-01` shipped `✅` at DAL-A with a third of its promised
formats untested.

**AsyncAPI is not OpenAPI with different words, and the tests say so where it matters**: a channel
is not a path with a verb, so this parser emits one endpoint per channel with the sentinel method
`CHANNEL`, and its rejection set differs — `channels` is required, `components` is not.
"""

from __future__ import annotations

import pytest

from specweaver.sandbox.protocol.core.asyncapi_parser import AsyncAPIParser
from specweaver.sandbox.protocol.core.protocol_interfaces import (
    ProtocolSchemaError,
    ProtocolSchemaInterface,
)

_ORDERS = """asyncapi: 2.6.0
info:
  title: Orders
  version: 1.0.0
channels:
  order/created:
    subscribe:
      operationId: onOrderCreated
  order/cancelled:
    publish:
      operationId: cancelOrder
components:
  messages:
    OrderCreated:
      payload:
        type: object
    OrderCancelled:
      payload:
        type: object
"""


class TestAsyncAPIParserExtractEndpoints:
    """FR-1 — one endpoint per channel."""

    def test_each_channel_becomes_one_endpoint_keyed_by_its_name(self) -> None:
        """[Happy] a channel name is the path, verbatim — slashes are part of the topic."""
        endpoints = AsyncAPIParser().extract_endpoints(_ORDERS)

        assert [e.path for e in endpoints] == ["order/created", "order/cancelled"]

    def test_the_method_is_the_channel_sentinel_not_an_http_verb(self) -> None:
        """[Boundary] AsyncAPI has no verbs; `CHANNEL` is what distinguishes these from REST.

        Worth its own assertion because a contract-drift check branches on `method`, and silently
        emitting `GET` here would make every channel look like an HTTP route.
        """
        assert {e.method for e in AsyncAPIParser().extract_endpoints(_ORDERS)} == {"CHANNEL"}

    def test_the_channel_body_is_carried_as_properties(self) -> None:
        """[Happy] `subscribe` / `publish` are the direction, and drift compares them."""
        created, cancelled = AsyncAPIParser().extract_endpoints(_ORDERS)

        assert created.properties["subscribe"]["operationId"] == "onOrderCreated"
        assert cancelled.properties["publish"]["operationId"] == "cancelOrder"

    def test_a_channel_whose_value_is_not_a_mapping_is_skipped_not_fatal(self) -> None:
        """[Graceful degradation] one bad channel must not lose the rest of the document."""
        payload = "asyncapi: 2.6.0\nchannels:\n  broken: 7\n  fine:\n    publish: {}\n"

        assert [e.path for e in AsyncAPIParser().extract_endpoints(payload)] == ["fine"]


class TestAsyncAPIParserExtractMessages:
    """FR-1 — messages come out of `components.messages`."""

    def test_each_component_message_becomes_a_message(self) -> None:
        """[Happy] name and payload both survive, since drift compares the payload shape."""
        messages = AsyncAPIParser().extract_messages(_ORDERS)

        assert [m.name for m in messages] == ["OrderCreated", "OrderCancelled"]
        assert messages[0].properties["payload"]["type"] == "object"

    def test_a_document_without_components_yields_no_messages(self) -> None:
        """[Boundary] unlike `channels`, components are optional — absence is not an error."""
        assert (
            AsyncAPIParser().extract_messages("asyncapi: 2.6.0\nchannels:\n  a:\n    publish: {}\n")
            == []
        )

    def test_components_that_are_not_a_mapping_yield_no_messages(self) -> None:
        """[Hostile] a scalar where a mapping belongs degrades to empty."""
        assert AsyncAPIParser().extract_messages("asyncapi: 2.6.0\ncomponents: 7\n") == []

    def test_messages_that_are_not_a_mapping_yield_no_messages(self) -> None:
        """[Hostile] the same guard one level deeper, and a separate branch in the source."""
        assert (
            AsyncAPIParser().extract_messages("asyncapi: 2.6.0\ncomponents:\n  messages: 7\n") == []
        )

    def test_a_message_whose_value_is_not_a_mapping_is_skipped(self) -> None:
        """[Graceful degradation] one malformed entry must not lose its siblings."""
        payload = (
            "asyncapi: 2.6.0\ncomponents:\n  messages:\n    Bad: 7\n    Good:\n      payload: {}\n"
        )

        assert [m.name for m in AsyncAPIParser().extract_messages(payload)] == ["Good"]


class TestAsyncAPIParserRejectsBadInput:
    """FR-3 — asserted on messages, so four distinct guards cannot collapse into one test."""

    def test_a_root_that_is_not_a_mapping_is_rejected(self) -> None:
        """[Hostile] a YAML list parses and is not a document."""
        with pytest.raises(ProtocolSchemaError, match="root must be a dictionary"):
            AsyncAPIParser().extract_endpoints("- a\n- b\n")

    def test_malformed_yaml_is_rejected_as_a_protocol_error(self) -> None:
        """[Hostile] the `ruamel` error is wrapped, not leaked — callers branch on our type."""
        with pytest.raises(ProtocolSchemaError, match="Failed to parse AsyncAPI YAML"):
            AsyncAPIParser().extract_endpoints("asyncapi: 2.6.0\nchannels: [unclosed\n")

    def test_a_document_without_channels_is_rejected(self) -> None:
        """[Hostile] channels are the point of an AsyncAPI document."""
        with pytest.raises(ProtocolSchemaError, match="Missing 'channels'"):
            AsyncAPIParser().extract_endpoints("asyncapi: 2.6.0\ninfo:\n  title: x\n")

    def test_channels_that_are_not_a_mapping_are_rejected(self) -> None:
        """[Hostile] present-but-wrong-typed is a different failure from absent."""
        with pytest.raises(ProtocolSchemaError, match="'channels' must be a dictionary"):
            AsyncAPIParser().extract_endpoints("asyncapi: 2.6.0\nchannels: 7\n")

    def test_messages_do_not_require_channels(self) -> None:
        """[Boundary] the `channels` guard belongs to endpoints only.

        A document carrying only components is useless for endpoints and valid for messages;
        hoisting the guard into `_parse_yaml` would break that without any other test noticing.
        """
        payload = "asyncapi: 2.6.0\ncomponents:\n  messages:\n    A:\n      payload: {}\n"

        assert [m.name for m in AsyncAPIParser().extract_messages(payload)] == ["A"]


class TestAsyncAPIParserImplementsTheInterface:
    """FR-3 — the declaration the factory's return type rests on."""

    def test_the_parser_is_a_protocol_schema_interface(self) -> None:
        assert isinstance(AsyncAPIParser(), ProtocolSchemaInterface)
