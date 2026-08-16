# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`ProtocolParserFactory` picks a parser by sniffing the payload. TECH-051 CB-2.

Proves: A-VAL-01 FR-3

**The dispatch is the whole capability's front door**, and it was untested. Choosing wrong is worse
than failing: an OpenAPI document handed to the AsyncAPI parser raises *"Missing 'channels'"*, which
sends the reader looking for a channels block in a file that should never have one.

**Every branch is asserted by the type it returns, not by "it did not raise".** The three formats
share a base class, so `isinstance(result, ProtocolSchemaInterface)` passes for all three and proves
nothing about the choice.
"""

from __future__ import annotations

import pytest

from specweaver.sandbox.protocol.core.asyncapi_parser import AsyncAPIParser
from specweaver.sandbox.protocol.core.factory import ProtocolParserFactory
from specweaver.sandbox.protocol.core.grpc_parser import GRPCParser
from specweaver.sandbox.protocol.core.openapi_parser import OpenAPIParser
from specweaver.sandbox.protocol.core.protocol_interfaces import ProtocolSchemaError


class TestProtocolParserFactoryPicksByFormat:
    """FR-3 — one parser per format, chosen from the payload alone."""

    def test_proto3_syntax_selects_the_grpc_parser(self) -> None:
        """[Happy] the `syntax = "proto3"` token is the gRPC marker."""
        parser = ProtocolParserFactory.create_parser('syntax = "proto3";\nservice S {}\n')

        assert isinstance(parser, GRPCParser)

    def test_proto2_and_single_quotes_are_recognised_too(self) -> None:
        """[Boundary] the regex allows either version and either quote style.

        Both are legal proto, and a factory that only knew `"proto3"` with double quotes would send
        a proto2 file to the YAML branch, where it fails as an unrecognisable schema.
        """
        assert isinstance(ProtocolParserFactory.create_parser("syntax = 'proto2';\n"), GRPCParser)

    def test_an_openapi_key_selects_the_openapi_parser(self) -> None:
        """[Happy] the version key is the OpenAPI 3.x marker."""
        parser = ProtocolParserFactory.create_parser("openapi: 3.0.3\npaths: {}\n")

        assert isinstance(parser, OpenAPIParser)

    def test_a_swagger_key_also_selects_the_openapi_parser(self) -> None:
        """[Boundary] Swagger 2.0 documents use `swagger:` and the same parser reads them."""
        parser = ProtocolParserFactory.create_parser("swagger: '2.0'\npaths: {}\n")

        assert isinstance(parser, OpenAPIParser)

    def test_an_asyncapi_key_selects_the_asyncapi_parser(self) -> None:
        """[Happy] and NOT the OpenAPI parser, which is the failure that reads as a schema bug."""
        parser = ProtocolParserFactory.create_parser("asyncapi: 2.6.0\nchannels: {}\n")

        assert isinstance(parser, AsyncAPIParser)
        assert not isinstance(parser, OpenAPIParser)

    def test_proto_wins_over_a_yaml_lookalike(self) -> None:
        """[Boundary] the proto check runs first, and a `.proto` may contain the word openapi.

        Order is behaviour here: a comment mentioning `openapi:` inside a proto file must not
        divert it to the YAML branch, where it would not parse at all.
        """
        payload = 'syntax = "proto3";\n// see openapi: 3.0.3 for the REST twin\nservice S {}\n'

        assert isinstance(ProtocolParserFactory.create_parser(payload), GRPCParser)


class TestProtocolParserFactoryRejectsWhatItCannotPlace:
    """FR-3 — an unrecognised payload fails here rather than deeper, where the error misleads."""

    def test_an_empty_payload_is_rejected(self) -> None:
        """[Hostile] and with its own message: empty is a different mistake from unrecognisable."""
        with pytest.raises(ProtocolSchemaError, match="empty payload"):
            ProtocolParserFactory.create_parser("")

    def test_a_whitespace_only_payload_is_rejected_as_empty(self) -> None:
        """[Hostile] `strip()` is what makes this the empty case rather than the unknown one."""
        with pytest.raises(ProtocolSchemaError, match="empty payload"):
            ProtocolParserFactory.create_parser("   \n\t\n  ")

    def test_valid_yaml_with_no_format_marker_is_rejected(self) -> None:
        """[Hostile] parseable and unplaceable — the message names all three markers it looked for."""
        with pytest.raises(ProtocolSchemaError, match=r"openapi.*asyncapi.*proto"):
            ProtocolParserFactory.create_parser("title: something\nversion: 1\n")

    def test_unparseable_yaml_is_rejected_as_a_protocol_error(self) -> None:
        """[Hostile] a `ruamel` scanner error is wrapped, so callers branch on one exception type."""
        with pytest.raises(ProtocolSchemaError, match="Unable to parse schema payload"):
            ProtocolParserFactory.create_parser("key: [unclosed\n  other: {\n")

    def test_a_yaml_scalar_is_rejected_rather_than_treated_as_a_document(self) -> None:
        """[Hostile] a bare string parses to a `str`, which has no format key to find."""
        with pytest.raises(ProtocolSchemaError, match="Unable to determine"):
            ProtocolParserFactory.create_parser("just a sentence")
