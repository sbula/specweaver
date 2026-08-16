# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`OpenAPIParser` turns an OpenAPI 3.x document into endpoints and messages. TECH-051 CB-2.

Proves: A-VAL-01 FR-1, A-VAL-01 FR-3

**Nothing protected this module before 2026-08-16.** Mutating `if "paths" not in parsed:` to
`if False:` survived the entire suite — the guard could be deleted and no test anywhere would
notice. This file was created empty in `14d889f2` and is named after the code it now covers.

**Every rejection path is asserted separately**, because they are separate promises to the caller:
a root that is not a mapping, a document with no `openapi` key, unparseable YAML, a missing `paths`
key, and a `paths` value that is not a mapping. `_parse` and `extract_endpoints` each raise
`ProtocolSchemaError`, so a test that only checked the exception type on one input would pass with
four of the five guards deleted.
"""

from __future__ import annotations

import pytest

from specweaver.sandbox.protocol.core.openapi_parser import OpenAPIParser
from specweaver.sandbox.protocol.core.protocol_interfaces import (
    ProtocolSchemaError,
    ProtocolSchemaInterface,
)

_PETSTORE = """openapi: 3.0.3
info:
  title: Petstore
  version: 1.0.0
paths:
  /pets:
    get:
      operationId: listPets
      summary: List all pets
    post:
      operationId: createPet
  /pets/{petId}:
    get:
      operationId: showPetById
components:
  schemas:
    Pet:
      type: object
      properties:
        id:
          type: integer
    Error:
      type: object
"""

#: Valid and endpoint-free: a document may describe schemas and expose no paths.
_NO_COMPONENTS = """openapi: 3.0.3
paths:
  /health:
    get:
      operationId: health
"""


class TestOpenAPIParserExtractEndpoints:
    """FR-1 — endpoints come out of `paths`, one per method."""

    def test_every_method_under_every_path_becomes_an_endpoint(self) -> None:
        """[Happy] two methods on `/pets` and one on `/pets/{petId}` → three endpoints."""
        endpoints = OpenAPIParser().extract_endpoints(_PETSTORE)

        assert [(e.method, e.path) for e in endpoints] == [
            ("GET", "/pets"),
            ("POST", "/pets"),
            ("GET", "/pets/{petId}"),
        ]

    def test_the_method_is_upper_cased_and_the_path_is_not(self) -> None:
        """[Boundary] OpenAPI writes methods in lower case and HTTP speaks upper.

        The path must survive untouched — upper-casing it would break `/pets/{petId}`, and a test
        asserting only on the method would not notice.
        """
        by_path = {e.path for e in OpenAPIParser().extract_endpoints(_PETSTORE)}

        assert by_path == {"/pets", "/pets/{petId}"}
        assert all(e.method.isupper() for e in OpenAPIParser().extract_endpoints(_PETSTORE))

    def test_the_operation_body_is_carried_as_properties(self) -> None:
        """[Happy] `operationId` is what a contract-drift check compares against code."""
        first = OpenAPIParser().extract_endpoints(_PETSTORE)[0]

        assert first.properties["operationId"] == "listPets"
        assert first.properties["summary"] == "List all pets"

    def test_a_path_whose_value_is_not_a_mapping_is_skipped_not_fatal(self) -> None:
        """[Graceful degradation] one malformed path entry must not lose the whole document."""
        schema = "openapi: 3.0.3\npaths:\n  /broken: not-a-mapping\n  /ok:\n    get:\n      operationId: ok\n"

        endpoints = OpenAPIParser().extract_endpoints(schema)

        assert [(e.method, e.path) for e in endpoints] == [("GET", "/ok")]


class TestOpenAPIParserExtractMessages:
    """FR-1 — messages come out of `components.schemas`."""

    def test_each_component_schema_becomes_a_message(self) -> None:
        """[Happy] the schema body is carried whole, since drift compares its fields."""
        messages = OpenAPIParser().extract_messages(_PETSTORE)

        assert [m.name for m in messages] == ["Pet", "Error"]
        assert messages[0].properties["properties"]["id"]["type"] == "integer"

    def test_a_document_without_components_yields_no_messages(self) -> None:
        """[Boundary] absent components is valid, and must not raise."""
        assert OpenAPIParser().extract_messages(_NO_COMPONENTS) == []

    def test_components_that_are_not_a_mapping_yield_no_messages(self) -> None:
        """[Hostile] a scalar where a mapping belongs degrades to empty rather than crashing."""
        assert OpenAPIParser().extract_messages("openapi: 3.0.3\ncomponents: 7\n") == []

    def test_schemas_that_are_not_a_mapping_yield_no_messages(self) -> None:
        """[Hostile] the same one level deeper — a separate guard, so a separate test."""
        assert OpenAPIParser().extract_messages("openapi: 3.0.3\ncomponents:\n  schemas: 7\n") == []


class TestOpenAPIParserRejectsBadInput:
    """FR-3 — five distinct rejections, asserted on their messages so they cannot be conflated."""

    def test_a_root_that_is_not_a_mapping_is_rejected(self) -> None:
        """[Hostile] a YAML list parses fine and is not a schema."""
        with pytest.raises(ProtocolSchemaError, match="dictionary"):
            OpenAPIParser().extract_endpoints("- one\n- two\n")

    def test_a_document_without_the_openapi_key_is_rejected(self) -> None:
        """[Hostile] the version key is how this parser knows the document is its business."""
        with pytest.raises(ProtocolSchemaError, match="openapi"):
            OpenAPIParser().extract_endpoints("paths:\n  /x:\n    get: {}\n")

    def test_malformed_yaml_is_rejected(self) -> None:
        """[Hostile] a YAML error becomes the interface's error, not a `ruamel` one leaking out."""
        with pytest.raises(ProtocolSchemaError, match="Malformed YAML"):
            OpenAPIParser().extract_endpoints("openapi: 3.0.3\npaths: [unclosed\n")

    def test_a_document_without_paths_is_rejected(self) -> None:
        """[Hostile] the guard that survived a whole-suite mutant until this test existed."""
        with pytest.raises(ProtocolSchemaError, match="paths"):
            OpenAPIParser().extract_endpoints("openapi: 3.0.3\ninfo:\n  title: x\n")

    def test_paths_that_are_not_a_mapping_are_rejected(self) -> None:
        """[Hostile] present but wrong-typed is a different failure from absent."""
        with pytest.raises(ProtocolSchemaError, match="must be a dictionary"):
            OpenAPIParser().extract_endpoints("openapi: 3.0.3\npaths: 7\n")

    def test_messages_do_not_require_paths(self) -> None:
        """[Boundary] `extract_messages` shares `_parse` but not the `paths` guard.

        Asserted because the two entry points have different contracts: a schema-only document is
        useless for endpoints and perfectly good for messages, and folding the guard into `_parse`
        would break that quietly.
        """
        assert OpenAPIParser().extract_messages(
            "openapi: 3.0.3\ncomponents:\n  schemas:\n    A: {}\n"
        )


class TestOpenAPIParserImplementsTheInterface:
    """FR-3 — the declaration `ProtocolParserFactory`'s return type rests on."""

    def test_the_parser_is_a_protocol_schema_interface(self) -> None:
        assert isinstance(OpenAPIParser(), ProtocolSchemaInterface)
