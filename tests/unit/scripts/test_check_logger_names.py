# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every log line reaches the project's handlers (`scripts/check_logger_names.py`).

Proves: D-FLOW-04 FR-9
Proves: D-FLOW-04 NFR-3

A logger named `__name__`, or a name under it, sits below `specweaver`, which `setup_logging`
configures; any other name, and the root logger, bypass the project's console and file.

| Bucket | Case |
|---|---|
| Happy | `getLogger(__name__)` and `getLogger(f"{__name__}.dlx")` pass |
| Boundary | a name under `__name__` with more parts; `logger.error(...)` on a module logger |
| Degradation | a file that does not parse is reported, never skipped |
| Hostile | a literal or variable name, a bare `getLogger()`, `logging.critical(...)` on the root logger |
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def check() -> ModuleType:
    path = REPO_ROOT / "scripts" / "check_logger_names.py"
    spec = importlib.util.spec_from_file_location("check_logger_names", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_logger_names"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "line",
    [
        "logger = logging.getLogger(__name__)",
        'dlx = logging.getLogger(f"{__name__}.dlx.{id(x)}")',
        "logger.error('x %s', 1)",
    ],
)
def test_a_logger_under_the_module_passes(check: ModuleType, line: str) -> None:
    assert check.stray_loggers(f"import logging\n{line}\n") == []


@pytest.mark.parametrize(
    "line",
    [
        'logger = logging.getLogger("dlx_worker")',
        "logger = logging.getLogger(NAME)",
        "logger = logging.getLogger()",
        'logger = logging.getLogger(f"dlx_{id(x)}")',
        "logging.critical('lost %s', 1)",
        "logging.warning('lost')",
    ],
    ids=["literal", "variable", "root", "f-string-elsewhere", "root-critical", "root-warning"],
)
def test_a_logger_outside_the_module_is_named(check: ModuleType, line: str) -> None:
    assert check.stray_loggers(f"import logging\n{line}\n") == [2]


def test_the_command_names_each_offender(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.py").write_text("import logging\nlogging.error('x')\n")
    (tmp_path / "b.py").write_text("import logging\nlogger = logging.getLogger(__name__)\n")

    assert check.main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert f"{tmp_path / 'a.py'}:2" in out
    assert "b.py" not in out


def test_a_file_that_does_not_parse_fails(check: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def (:\n")

    assert check.main([str(tmp_path)]) == 1


def test_the_package_root_logger_is_allowed_in_the_logging_set_up(check: ModuleType) -> None:
    source = 'import logging\nroot = logging.getLogger("specweaver")\n'

    assert check.stray_loggers(source, path="src/specweaver/telemetry_logger.py") == []
    assert check.stray_loggers(source, path="src/specweaver/other.py") == [2]
