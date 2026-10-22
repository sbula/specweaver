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

import pytest

from specweaver.sandbox.base import AtomResult, AtomStatus
from specweaver.sandbox.protocol.core.atom import ProtocolAtom
from specweaver.sandbox.security import WorkspaceBoundary

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
        result = ProtocolAtom(WorkspaceBoundary([tmp_path])).run(
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
        result = ProtocolAtom(WorkspaceBoundary([tmp_path])).run(
            {"action": "extract_schema_messages", "file_path": _schema(tmp_path, name="api.txt")}
        )

        assert result.status == AtomStatus.SUCCESS
        assert result.exports["data"] == [{"name": "Pet", "properties": {"type": "object"}}]


class TestProtocolAtomFailsWithoutRaising:
    """FR-4 — four failure modes, four messages, and never an exception out of `run`."""

    def test_a_missing_action_fails(self, tmp_path: Path) -> None:
        """[Hostile] an incomplete context is the engine's mistake, reported not thrown."""
        result = ProtocolAtom(WorkspaceBoundary([tmp_path])).run({"file_path": _schema(tmp_path)})

        assert result.status == AtomStatus.FAILED
        assert "action" in result.message

    def test_a_missing_file_path_fails(self, tmp_path: Path) -> None:
        """[Hostile] the same guard's other half — asserted separately because it is one `or`."""
        result = ProtocolAtom(WorkspaceBoundary([tmp_path])).run(
            {"action": "extract_schema_endpoints"}
        )

        assert result.status == AtomStatus.FAILED
        assert "file_path" in result.message

    def test_an_unknown_action_fails_and_names_it(self, tmp_path: Path) -> None:
        """[Hostile] a typo'd intent must say which intent, or the pipeline author cannot fix it."""
        result = ProtocolAtom(WorkspaceBoundary([tmp_path])).run(
            {"action": "extract_schema_bananas", "file_path": _schema(tmp_path)}
        )

        assert result.status == AtomStatus.FAILED
        assert "extract_schema_bananas" in result.message
        assert result.exports["status"] == "error"

    def test_a_missing_file_fails_without_raising(self, tmp_path: Path) -> None:
        """[Graceful degradation] `FileNotFoundError` is caught and turned into a result."""
        result = ProtocolAtom(WorkspaceBoundary([tmp_path])).run(
            {"action": "extract_schema_endpoints", "file_path": str(tmp_path / "absent.yaml")}
        )

        assert result.status == AtomStatus.FAILED
        assert "absent.yaml" in result.message

    def test_a_missing_relative_file_is_named_as_given(self, tmp_path: Path) -> None:
        """[Graceful degradation] Proves: TECH-075 FR-4. The answer echoes the input only."""
        result = ProtocolAtom(WorkspaceBoundary([tmp_path])).run(
            {"action": "extract_schema_endpoints", "file_path": "absent.yaml"}
        )

        assert result.message == "File not found: absent.yaml"

    def test_a_directory_is_rejected_as_a_missing_file_not_as_a_crash(self, tmp_path: Path) -> None:
        """[Hostile] `is_file()` and not `exists()` — a directory path must not be read.

        **The message is the assertion, and the first draft of this test got it wrong.** Asserting
        only `status == FAILED` passed with the guard weakened to `exists()`: the directory then
        reached `read_text`, raised `IsADirectoryError`, and fell into the catch-all — still a
        FAILED result, so the mutant survived. What actually distinguishes the two is what the user
        is told, so that is what is pinned.
        """
        result = ProtocolAtom(WorkspaceBoundary([tmp_path])).run(
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
        result = ProtocolAtom(WorkspaceBoundary([tmp_path])).run(
            {
                "action": "extract_schema_endpoints",
                "file_path": _schema(tmp_path, body="title: not a schema\n"),
            }
        )

        assert result.status == AtomStatus.FAILED
        assert "determine protocol schema type" in result.message
        assert result.exports["error"] == result.message


class TestProtocolAtomReadsOnlyInsideItsBoundary:
    """Proves: TECH-075 FR-4, NFR-1, NFR-3, NFR-4.

    A path the atom is given is checked by its boundary before the file is opened. A refused path
    is a FAILED result, the file is never read, and the message names only what was given.
    """

    @staticmethod
    def _run(atom: ProtocolAtom, file_path: str) -> AtomResult:
        return atom.run({"action": "extract_schema_endpoints", "file_path": file_path})

    @staticmethod
    def _project(tmp_path: Path) -> Path:
        project = tmp_path / "project"
        project.mkdir()
        return project

    def test_an_atom_needs_a_boundary(self) -> None:
        """[Hostile] no boundary, no atom: there is nothing to check a path against (NFR-1)."""
        with pytest.raises(TypeError):
            ProtocolAtom()  # type: ignore[call-arg]

    def test_a_relative_path_is_read_from_the_project_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """[Boundary] the process folder plays no part."""
        project = self._project(tmp_path)
        _schema(project)
        monkeypatch.chdir(tmp_path)
        result = self._run(ProtocolAtom(WorkspaceBoundary([project])), "api.yaml")
        assert result.status == AtomStatus.SUCCESS

    def test_a_contract_under_an_api_path_is_read(self, tmp_path: Path) -> None:
        """[Happy] a neighbour's read-only API path is inside (NFR-4)."""
        project = self._project(tmp_path)
        neighbour = tmp_path / "neighbour"
        neighbour.mkdir()
        atom = ProtocolAtom(WorkspaceBoundary([project], api_paths=[neighbour]))
        assert self._run(atom, _schema(neighbour)).status == AtomStatus.SUCCESS

    @pytest.mark.parametrize("given", ["../secret.yaml", "ABSOLUTE", "escape.yaml", "a\x00.yaml"])
    def test_a_path_outside_is_refused_and_never_opened(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, given: str
    ) -> None:
        """[Hostile] climbing out, an absolute path, an escaping link (NFR-3), a null byte."""
        project = self._project(tmp_path)
        secret = _schema(tmp_path, name="secret.yaml")
        (project / "escape.yaml").symlink_to(secret)
        given = secret if given == "ABSOLUTE" else given
        opened: list[str] = []
        monkeypatch.setattr(
            ProtocolAtom, "_read_file", lambda _self, p, _given: opened.append(str(p)) or ""
        )

        result = self._run(ProtocolAtom(WorkspaceBoundary([project])), given)

        assert result.status == AtomStatus.FAILED
        assert result.exports["status"] == "error"
        assert opened == []

    def test_the_refusal_names_the_given_path_not_where_it_lands(self, tmp_path: Path) -> None:
        """[Hostile] the resolved location stays out of the answer (NFR-2 spirit)."""
        project = self._project(tmp_path)
        _schema(tmp_path, name="secret.yaml")
        result = self._run(ProtocolAtom(WorkspaceBoundary([project])), "../secret.yaml")
        assert "../secret.yaml" in result.message
        assert str(tmp_path) not in result.message
        assert result.exports["error"] == result.message
