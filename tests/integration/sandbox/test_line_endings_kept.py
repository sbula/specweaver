# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A change keeps every file's line endings: only the changed text changes.

Proves: D-SENS-06 FR-3

The Atom and a real `FileExecutor` on disk. Before this, a read in text mode turned `\\r\\n` into
`\\n`, so one rename rewrote every line of a Windows file.

| Bucket | Case |
|---|---|
| Happy | a rename in a CRLF file keeps CRLF; an LF file keeps LF |
| Boundary | a file with both endings keeps both |
| Degradation | a doc written into a CRLF file gets CRLF lines |
| Hostile | the read tool returns the bytes as they are, `\\r` included |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom
from specweaver.sandbox.filesystem.core.executor import FileExecutor

if TYPE_CHECKING:
    from pathlib import Path


def _project(root: Path, files: dict[str, bytes]) -> Path:
    for rel, data in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    return root


@pytest.mark.parametrize("eol", [b"\r\n", b"\n"], ids=["crlf", "lf"])
def test_a_rename_keeps_the_line_endings(tmp_path: Path, eol: bytes) -> None:
    text = b"def f():%b    return 1%b%b%bdef g():%b    return f()%b" % ((eol,) * 6)
    root = _project(tmp_path / "p", {"app/__init__.py": b"", "app/a.py": text})

    result = CodeStructureAtom(cwd=root).run(
        {"intent": "rename_symbol", "path": "app/a.py", "symbol_name": "f", "new_name": "h"}
    )

    assert result.status == AtomStatus.SUCCESS, result.message
    assert (root / "app/a.py").read_bytes() == text.replace(b"f()", b"h()").replace(
        b"def f", b"def h"
    )


def test_mixed_endings_stay_mixed(tmp_path: Path) -> None:
    text = b"def f():\r\n    return 1\n\n\ndef g():\r\n    return f()\n"
    root = _project(tmp_path / "p", {"app/__init__.py": b"", "app/a.py": text})

    CodeStructureAtom(cwd=root).run(
        {"intent": "rename_symbol", "path": "app/a.py", "symbol_name": "f", "new_name": "h"}
    )

    assert (root / "app/a.py").read_bytes() == text.replace(b"f()", b"h()").replace(
        b"def f", b"def h"
    )


def test_a_doc_in_a_crlf_file_gets_crlf_lines(tmp_path: Path) -> None:
    root = _project(tmp_path / "p", {"m.go": b"package m\r\n\r\nfunc F() {}\r\n"})

    result = CodeStructureAtom(cwd=root).run(
        {"intent": "replace_symbol_doc", "path": "m.go", "symbol_name": "F", "doc": "A.\nB."}
    )

    assert result.status == AtomStatus.SUCCESS, result.message
    assert (root / "m.go").read_bytes() == b"package m\r\n\r\n// A.\r\n// B.\r\nfunc F() {}\r\n"


def test_the_executor_reads_and_writes_the_bytes_as_they_are(tmp_path: Path) -> None:
    root = _project(tmp_path / "p", {"a.txt": b"one\r\ntwo\nthree\r\n"})
    executor = FileExecutor(root)

    assert executor.read("a.txt").data == "one\r\ntwo\nthree\r\n"
    assert executor.read_lines("a.txt", 1, 1).data == ("one\r\n", 3)
    executor.write("b.txt", "x\ny\r\n")
    assert (root / "b.txt").read_bytes() == b"x\ny\r\n"
