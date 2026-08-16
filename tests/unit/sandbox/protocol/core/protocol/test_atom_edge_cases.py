# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`ProtocolAtom`'s last-resort failure handling. TECH-051 CB-2.

Proves: A-VAL-01 FR-4

`test_protocol_atom.py` covers the named failures — missing context keys, an unknown intent, an
absent file, a schema the factory cannot place. This file covers the branch underneath them: the
bare `except Exception` that exists because an atom which **raises** takes the whole pipeline down,
while an atom which **returns FAILED** costs one step.

That branch is the hardest to reach on purpose — every foreseeable error is already typed and
caught above it — so each test here provokes a genuinely unforeseen failure rather than asserting
the catch-all exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.protocol.core.atom import ProtocolAtom

if TYPE_CHECKING:
    from pathlib import Path


class TestProtocolAtomSurvivesUnforeseenFailures:
    """FR-4 — nothing escapes `run`, whatever the parser or the filesystem does."""

    def test_a_file_that_is_not_utf8_fails_rather_than_raising(self, tmp_path: Path) -> None:
        """[Hostile] a binary file is neither a schema nor a `FileNotFoundError`.

        `read_text(encoding="utf-8")` raises `UnicodeDecodeError`, which is not one of the two
        typed catches — so this is the catch-all doing its job on a real input rather than a
        contrived one.
        """
        binary = tmp_path / "schema.bin"
        binary.write_bytes(b"\xff\xfe\x00\x01openapi: 3.0.3\xff")

        result = ProtocolAtom().run(
            {"action": "extract_schema_endpoints", "file_path": str(binary)}
        )

        assert result.status == AtomStatus.FAILED
        assert "Unexpected error" in result.message
        assert result.exports["status"] == "error"

    def test_an_unexpected_parser_exception_is_contained(self, tmp_path: Path) -> None:
        """[Graceful degradation] a parser bug must fail one step, never the pipeline.

        `MemoryError` is used because it is unambiguously not a schema problem: nothing in the
        typed catches would ever claim it, so a passing test here cannot be an accident of which
        exception was chosen.
        """
        schema = tmp_path / "api.yaml"
        schema.write_text("openapi: 3.0.3\npaths: {}\n", encoding="utf-8")

        with patch(
            "specweaver.sandbox.protocol.core.factory.ProtocolParserFactory.create_parser",
            side_effect=MemoryError("out of memory mid-parse"),
        ):
            result = ProtocolAtom().run(
                {"action": "extract_schema_endpoints", "file_path": str(schema)}
            )

        assert result.status == AtomStatus.FAILED
        assert "out of memory mid-parse" in result.message

    def test_the_error_message_and_the_export_agree(self, tmp_path: Path) -> None:
        """[Boundary] the engine reads `message`, an agent reads `exports["error"]`.

        They are written separately in the source, so they can drift — and a reader comparing a log
        line against a tool result would then be chasing two different stories about one failure.
        """
        result = ProtocolAtom().run(
            {"action": "extract_schema_endpoints", "file_path": str(tmp_path / "gone.yaml")}
        )

        assert result.exports["error"] == result.message

    def test_an_empty_context_fails_without_touching_the_filesystem(self) -> None:
        """[Hostile] the guard runs before any I/O, so a caller with nothing cannot cause a read."""
        with patch.object(ProtocolAtom, "_read_file", side_effect=AssertionError("must not read")):
            result = ProtocolAtom().run({})

        assert result.status == AtomStatus.FAILED
        assert "Missing" in result.message
