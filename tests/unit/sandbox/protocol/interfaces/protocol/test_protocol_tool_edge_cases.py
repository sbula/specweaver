# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`ProtocolTool`'s boundary catch. TECH-051 CB-2.

Proves: A-VAL-01 FR-4

The tool wraps each atom call in `try/except Exception` and returns
`{"status": "error", "error": "Tool boundary exception: …"}`. That branch is unreachable through
normal use — `ProtocolAtom.run` already converts every failure into a FAILED result rather than
raising — which is precisely why it needs its own tests: **an unreachable branch is untested by
default, and this one is the last thing between an agent and a traceback.**

Both intents are tested separately. The two methods carry the same code twice, so a fix applied to
one and not the other is exactly the drift a shared assertion would hide.
"""

from __future__ import annotations

from unittest.mock import patch

from specweaver.sandbox.protocol.interfaces.tool import ProtocolTool


class TestProtocolToolBoundaryCatch:
    """FR-4 — an exception from below becomes a payload, never a raise."""

    def test_endpoints_convert_an_atom_exception_into_an_error_payload(self) -> None:
        """[Graceful degradation] the agent receives a dict it can act on."""
        with patch(
            "specweaver.sandbox.protocol.core.atom.ProtocolAtom.run",
            side_effect=RuntimeError("atom exploded"),
        ):
            out = ProtocolTool().extract_schema_endpoints("/tmp/whatever.yaml")

        assert out["status"] == "error"
        assert "Tool boundary exception" in out["error"]
        assert "atom exploded" in out["error"]

    def test_messages_convert_an_atom_exception_into_an_error_payload(self) -> None:
        """[Graceful degradation] the second method, asserted separately because it is a copy."""
        with patch(
            "specweaver.sandbox.protocol.core.atom.ProtocolAtom.run",
            side_effect=RuntimeError("atom exploded"),
        ):
            out = ProtocolTool().extract_schema_messages("/tmp/whatever.yaml")

        assert out["status"] == "error"
        assert "Tool boundary exception" in out["error"]

    def test_the_original_reason_survives_into_the_payload(self) -> None:
        """[Boundary] a boundary catch that swallowed the cause would be worse than the traceback.

        The agent has nothing else to go on: it cannot read the log, so the message is the whole
        diagnosis.
        """
        with patch(
            "specweaver.sandbox.protocol.core.atom.ProtocolAtom.run",
            side_effect=KeyError("expected_key"),
        ):
            out = ProtocolTool().extract_schema_endpoints("/tmp/whatever.yaml")

        assert "expected_key" in out["error"]

    def test_a_keyboard_interrupt_is_not_swallowed(self) -> None:
        """[Hostile] `except Exception` must not catch `BaseException`, or Ctrl-C stops working.

        Asserted rather than assumed: widening the catch to `BaseException` is a plausible-looking
        edit that would make the tool eat an interrupt and return an error payload instead.
        """
        import pytest

        with (
            patch(
                "specweaver.sandbox.protocol.core.atom.ProtocolAtom.run",
                side_effect=KeyboardInterrupt(),
            ),
            pytest.raises(KeyboardInterrupt),
        ):
            ProtocolTool().extract_schema_endpoints("/tmp/whatever.yaml")
