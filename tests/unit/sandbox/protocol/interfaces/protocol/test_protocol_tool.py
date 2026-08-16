# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`ProtocolTool` is the agent-facing surface over the protocol atom. TECH-051 CB-2.

Proves: A-VAL-01 FR-4

Two tests elsewhere instantiate this class — `test_sandbox_registry.py` and
`test_dispatcher_domain_conformance.py` — and neither calls a method on it. Both are wiring checks.
Nothing exercised what the tool actually does.

**The declarations are asserted as carefully as the behaviour.** An LLM chooses this tool from its
`ToolDefinition`, so a missing `required` flag or a renamed parameter is a silent capability loss:
the model calls the tool without a `file_path` and gets an error it cannot diagnose.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.sandbox.base import BaseTool
from specweaver.sandbox.protocol.interfaces.tool import ProtocolTool

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


def _schema(tmp_path: Path, body: str = _PETSTORE) -> str:
    path = tmp_path / "api.yaml"
    path.write_text(body, encoding="utf-8")
    return str(path)


class TestProtocolToolDefinitions:
    """FR-4 — what an LLM is told this tool can do."""

    def test_both_intents_are_offered(self) -> None:
        """[Happy] the two atom actions are the two tool names, or one is unreachable."""
        names = [d.name for d in ProtocolTool().definitions()]

        assert names == ["extract_schema_endpoints", "extract_schema_messages"]

    def test_each_intent_is_also_a_callable_method(self) -> None:
        """[Boundary] a definition the dispatcher cannot resolve to a method is a dead advert.

        Asserted by lookup rather than by eye: the two lists are maintained separately in the
        source, so they can drift the moment a third intent is added.
        """
        tool = ProtocolTool()

        for definition in tool.definitions():
            assert callable(getattr(tool, definition.name, None)), definition.name

    def test_file_path_is_required_on_every_intent(self) -> None:
        """[Boundary] the model omits optional arguments — a non-required path means no path."""
        for definition in ProtocolTool().definitions():
            params = {p.name: p for p in definition.parameters}
            assert "file_path" in params, definition.name
            assert params["file_path"].required is True, definition.name
            assert params["file_path"].type == "string", definition.name


class TestProtocolToolRole:
    """FR-4 — the tool is deliberately outside role gating."""

    def test_the_tool_declares_no_role(self) -> None:
        """[Boundary] reading a schema file grants no capability, so it needs no role.

        Pinned because `NO_ROLE` is a sentinel: if it were swapped for a real role string, every
        agent without that role would silently lose the tool rather than be refused it.
        """
        assert ProtocolTool().role == BaseTool.NO_ROLE


class TestProtocolToolExtractsThroughTheAtom:
    """FR-4 — the tool returns the atom's exports, unwrapped."""

    def test_endpoints_come_back_as_the_atom_exports(self, tmp_path: Path) -> None:
        """[Happy] the tool hands back `exports`, not an `AtomResult` the LLM cannot read."""
        out = ProtocolTool().extract_schema_endpoints(_schema(tmp_path))

        assert out["status"] == "success"
        assert out["data"] == [
            {"method": "GET", "path": "/pets", "properties": {"operationId": "listPets"}}
        ]

    def test_messages_come_back_as_the_atom_exports(self, tmp_path: Path) -> None:
        """[Happy] the second intent, which reads the same file through a different call."""
        out = ProtocolTool().extract_schema_messages(_schema(tmp_path))

        assert out["status"] == "success"
        assert out["data"] == [{"name": "Pet", "properties": {"type": "object"}}]

    def test_a_missing_file_returns_an_error_payload(self, tmp_path: Path) -> None:
        """[Graceful degradation] the agent gets a readable dict, never a traceback."""
        out = ProtocolTool().extract_schema_endpoints(str(tmp_path / "absent.yaml"))

        assert out["status"] == "error"
        assert "absent.yaml" in out["error"]

    def test_an_unrecognisable_schema_returns_the_parser_error(self, tmp_path: Path) -> None:
        """[Hostile] the reason survives the whole way out to the agent that must act on it."""
        out = ProtocolTool().extract_schema_messages(_schema(tmp_path, body="title: nope\n"))

        assert out["status"] == "error"
        assert "determine protocol schema type" in out["error"]
