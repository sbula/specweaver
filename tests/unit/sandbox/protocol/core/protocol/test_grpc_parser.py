# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`GRPCParser` turns a `.proto` document into endpoints and messages. TECH-051 CB-1.

Proves: A-VAL-01 FR-2, A-VAL-01 FR-3

**This file was empty until 2026-08-16.** It was created with a licence header and nothing else in
`14d889f2`, a tooling refactor, and never filled — so it read as coverage in a directory listing
while `A-VAL-01` (Protocol/Schema Analyzers, ✅, DAL-A) shipped with `check_fr_coverage` reporting
0 of 5 FRs proven.

**One test here was rescued rather than written.**
`test_malformed_syntax_raises_and_logs` lived in
`tests/integration/infrastructure/test_llm_logging_integration.py` — a file about **LLM logging** —
where it was the single protector of this parser's error path. Mutating
`raise ProtocolSchemaError(...) from e` to `return []` killed exactly one test, from there. It is
now in the file named after the code it covers.

**Expectations are derived from the `.proto` input, not from running the parser.** `Greeter/SayHello`
is what the gRPC path convention says a service and an rpc make; `stream` in the proto is what makes
a call streaming. Reading the values off the implementation and pasting them back is vacuous-proof
pattern 7, and it is the easy mistake in a parser test.
"""

from __future__ import annotations

import logging

import pytest

from specweaver.sandbox.protocol.core.grpc_parser import GRPCParser
from specweaver.sandbox.protocol.core.protocol_interfaces import (
    ProtocolSchemaError,
    ProtocolSchemaInterface,
)

_GREETER = """syntax = "proto3";
message HelloRequest { string name = 1; }
message HelloReply { string message = 1; }
service Greeter {
  rpc SayHello (HelloRequest) returns (HelloReply);
  rpc Chat (stream HelloRequest) returns (stream HelloReply);
}
"""

#: Messages, no service. A schema can legitimately define payloads and expose no RPCs.
_MESSAGES_ONLY = """syntax = "proto3";
message Lonely { int32 id = 1; }
"""


class TestGRPCParserExtractEndpoints:
    """FR-2 — service and RPC skeletons come out of the document."""

    def test_each_rpc_becomes_one_endpoint_pathed_by_service_and_method(self) -> None:
        """[Happy] `service Greeter { rpc SayHello }` → the path `Greeter/SayHello`."""
        endpoints = GRPCParser().extract_endpoints(_GREETER)

        assert [e.path for e in endpoints] == ["Greeter/SayHello", "Greeter/Chat"]
        assert {e.method for e in endpoints} == {"RPC"}

    def test_request_and_response_types_survive_extraction(self) -> None:
        """[Happy] the two message names named in the rpc are the two carried on the endpoint."""
        say_hello = GRPCParser().extract_endpoints(_GREETER)[0]

        assert say_hello.properties["request_type"] == "HelloRequest"
        assert say_hello.properties["response_type"] == "HelloReply"

    def test_streaming_is_read_from_the_stream_keyword_on_each_side(self) -> None:
        """[Boundary] `stream` on one side must not set the flag on the other.

        Asserted per side rather than as a pair: a parser that reported both sides from one keyword
        would satisfy a `{'client': True, 'server': True}` assertion on this proto and be wrong on
        every half-streaming call, which is the common shape.
        """
        unary, bidi = GRPCParser().extract_endpoints(_GREETER)

        assert unary.properties["client_streaming"] is False
        assert unary.properties["server_streaming"] is False
        assert bidi.properties["client_streaming"] is True
        assert bidi.properties["server_streaming"] is True

    def test_a_schema_with_no_service_yields_no_endpoints(self) -> None:
        """[Boundary] messages without RPCs is valid, and must not be an error."""
        assert GRPCParser().extract_endpoints(_MESSAGES_ONLY) == []


class TestGRPCParserExtractMessages:
    """FR-2 — message payloads come out of the document."""

    def test_fields_carry_name_type_and_number(self) -> None:
        """[Happy] `string name = 1` → all three parts, because a field number is not decoration."""
        messages = GRPCParser().extract_messages(_GREETER)

        assert [m.name for m in messages] == ["HelloRequest", "HelloReply"]
        assert messages[0].properties["fields"] == [{"name": "name", "type": "string", "number": 1}]

    def test_a_schema_with_no_message_yields_no_messages(self) -> None:
        """[Boundary] a service-only document is valid and empty on this side."""
        service_only = 'syntax = "proto3";\nservice S { rpc M (A) returns (B); }\n'
        assert GRPCParser().extract_messages(service_only) == []


class TestGRPCParserRejectsBadInput:
    """FR-3 — the interface's error contract, which callers branch on."""

    def test_malformed_syntax_raises_and_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """[Hostile] invalid proto → `ProtocolSchemaError`, with the reason logged first.

        Moved verbatim in behaviour from `test_llm_logging_integration.py`, where it was the only
        thing protecting this path. Both halves matter: callers branch on the exception type, and
        the log is what a user sees when a schema will not parse.
        """
        parser = GRPCParser()

        with caplog.at_level(logging.DEBUG), pytest.raises(ProtocolSchemaError):
            parser.extract_endpoints(
                "syntax = proto3; \n message invalid { int missing_semicolon }"
            )

        logs = [
            r for r in caplog.records if r.name == "specweaver.sandbox.protocol.core.grpc_parser"
        ]
        assert logs, "the parser raised without saying why"
        assert "parse" in logs[-1].message.lower()

    def test_a_non_empty_document_that_parses_to_nothing_is_an_error(self) -> None:
        """[Hostile] prose is not a schema — and `proto_schema_parser` returns an empty AST for it
        rather than raising, so the parser's own guard is the only thing that catches it."""
        with pytest.raises(ProtocolSchemaError):
            GRPCParser().extract_endpoints("this is not a protocol buffer definition at all")

    def test_an_empty_document_is_not_an_error(self) -> None:
        """[Boundary] the guard above must not fire on genuinely empty input.

        The distinction is deliberate in the source (`payload.strip()`): nothing to parse is not the
        same as something unparseable, and conflating them would make an empty file a hard failure.
        """
        assert GRPCParser().extract_endpoints("") == []
        assert GRPCParser().extract_messages("   \n  ") == []


class TestGRPCParserImplementsTheInterface:
    """FR-3 — the unifying interface, which is what lets `ProtocolParserFactory` return any parser."""

    def test_the_parser_is_a_protocol_schema_interface(self) -> None:
        """[Happy] declared, not merely duck-typed — the factory's return type depends on it."""
        assert isinstance(GRPCParser(), ProtocolSchemaInterface)
