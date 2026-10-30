# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A Python program that hangs under the debugger reaches the atom as a timeout that names it.

Proves: TECH-087 FR-15

Real atom, runner and `SubprocessExecutor`; the limit is cut to 1 s so the real executor kills it.

| Bucket | Case |
|---|---|
| Happy | the program prints and exits 0: its output comes back, exit 0 |
| Boundary | the program prints, then hangs: "main.py timed out after 1 s", exit 124 |
| Degradation | the hang is killed by the executor, not waited out |
| Hostile | the printed line looks like a result; it must not read as the verdict |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

pytestmark = pytest.mark.integration


def _atom(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> QARunnerAtom:
    from specweaver.sandbox.language.core.python.runner import PythonQARunner
    from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

    monkeypatch.setattr(PythonQARunner, "_BUILD_TIMEOUT", 1)
    (tmp_path / "main.py").write_text(body, encoding="utf-8")
    return QARunnerAtom(cwd=tmp_path, language="python")


def test_a_program_that_exits_returns_its_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    atom = _atom(tmp_path, monkeypatch, "print('done')\n")

    result = atom.run({"intent": "run_debugger", "target": ".", "entrypoint": "main.py"})

    assert result.exports["exit_code"] == 0
    assert "done" in [e["output"].strip() for e in result.exports["events"]]


def test_a_program_that_hangs_timed_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    atom = _atom(tmp_path, monkeypatch, "import time\nprint('OK', flush=True)\ntime.sleep(30)\n")

    result = atom.run({"intent": "run_debugger", "target": ".", "entrypoint": "main.py"})

    assert result.exports["exit_code"] == 124
    assert [e["output"] for e in result.exports["events"]] == ["main.py timed out after 1 s"]
