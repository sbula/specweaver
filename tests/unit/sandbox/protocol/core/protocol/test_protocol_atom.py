# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`ProtocolAtom` is the engine's way into the parsers. TECH-051 CB-2.

Proves: A-VAL-01 FR-4

The atom is the seam between the flow engine and the protocol package: it reads a file, asks the
factory for a parser, and returns an `AtomResult` the engine branches on. Nothing tested it.

**Every failure returns a FAILED result rather than raising**, which is the atom contract — an atom
that throws takes the pipeline down instead of failing one step. Each failure mode gets its own
test because they are separate branches carrying separate messages, and a single "it failed" check
would pass with three of them deleted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.protocol.core.atom import ProtocolAtom

if TYPE_CHECKING:
    from pathlib import Path

_PETSTORE = """openapi: 3.0.3
paths:
  /pets:
    get:
      operationId: listPets
components:
  schemas:
    Pet:
      type: object
"""


def _schema(tmp_path: Path, body: str = _PETSTORE, name: str = "api.yaml") -> str:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return str(path)


class TestProtocolAtomExtractsEndpoints:
    """FR-4 — the endpoint intent, end to end from a file on disk."""

    def test_endpoints_are_exported_as_plain_dicts(self, tmp_path: Path) -> None:
        """[Happy] the engine serialises exports, so models must already be dumped."""
        result = ProtocolAtom().run(
            {"action": "extract_schema_endpoints", "file_path": _schema(tmp_path)}
        )

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["status"] == "success"
        assert result.exports["data"] == [
            {"method": "GET", "path": "/pets", "properties": {"operationId": "listPets"}}
        ]


class TestProtocolAtomExtractsMessages:
    """FR-4 — the message intent, which reads the same file through a different call."""

    def test_messages_are_exported_as_plain_dicts(self, tmp_path: Path) -> None:
        """[Happy] and the format is sniffed from the payload, not from the file extension."""
        result = ProtocolAtom().run(
            {"action": "extract_schema_messages", "file_path": _schema(tmp_path, name="api.txt")}
        )

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["data"] == [{"name": "Pet", "properties": {"type": "object"}}]


class TestProtocolAtomFailsWithoutRaising:
    """FR-4 — four failure modes, four messages, and never an exception out of `run`."""

    def test_a_missing_action_fails(self, tmp_path: Path) -> None:
        """[Hostile] an incomplete context is the engine's mistake, reported not thrown."""
        result = ProtocolAtom().run({"file_path": _schema(tmp_path)})

        assert result.status == AtomStatus.FAILED
        assert "action" in result.message

    def test_a_missing_file_path_fails(self) -> None:
        """[Hostile] the same guard's other half — asserted separately because it is one `or`."""
        result = ProtocolAtom().run({"action": "extract_schema_endpoints"})

        assert result.status == AtomStatus.FAILED
        assert "file_path" in result.message

    def test_an_unknown_action_fails_and_names_it(self, tmp_path: Path) -> None:
        """[Hostile] a typo'd intent must say which intent, or the pipeline author cannot fix it."""
        result = ProtocolAtom().run(
            {"action": "extract_schema_bananas", "file_path": _schema(tmp_path)}
        )

        assert result.status == AtomStatus.FAILED
        assert "extract_schema_bananas" in result.message
        assert result.exports["status"] == "error"

    def test_a_missing_file_fails_without_raising(self, tmp_path: Path) -> None:
        """[Graceful degradation] `FileNotFoundError` is caught and turned into a result."""
        result = ProtocolAtom().run(
            {"action": "extract_schema_endpoints", "file_path": str(tmp_path / "absent.yaml")}
        )

        assert result.status == AtomStatus.FAILED
        assert "absent.yaml" in result.message

    def test_a_directory_is_rejected_as_a_missing_file_not_as_a_crash(self, tmp_path: Path) -> None:
        """[Hostile] `is_file()` and not `exists()` — a directory path must not be read.

        **The message is the assertion, and the first draft of this test got it wrong.** Asserting
        only `status == FAILED` passed with the guard weakened to `exists()`: the directory then
        reached `read_text`, raised `IsADirectoryError`, and fell into the catch-all — still a
        FAILED result, so the mutant survived. What actually distinguishes the two is what the user
        is told, so that is what is pinned.
        """
        result = ProtocolAtom().run(
            {"action": "extract_schema_endpoints", "file_path": str(tmp_path)}
        )

        assert result.status == AtomStatus.FAILED
        assert "File not found" in result.message
        assert "Unexpected error" not in result.message

    def test_an_unrecognisable_schema_fails_with_the_parser_error(self, tmp_path: Path) -> None:
        """[Graceful degradation] `ProtocolSchemaError` from the factory reaches the caller intact.

        The message matters: the atom is where a pipeline author sees why their schema was refused,
        and replacing it with a generic failure would make every format problem look the same.
        """
        result = ProtocolAtom().run(
            {
                "action": "extract_schema_endpoints",
                "file_path": _schema(tmp_path, body="title: not a schema\n"),
            }
        )

        assert result.status == AtomStatus.FAILED
        assert "determine protocol schema type" in result.message
        assert result.exports["error"] == result.message
