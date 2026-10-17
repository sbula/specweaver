# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every caught error is logged, raised, used, or given its reason (`scripts/check_lost_errors.py`).

Proves: D-FLOW-04 FR-6

`scripts/` is not an importable package, so the module is loaded by path.

| Bucket | Case |
|---|---|
| Happy | a logged, a raised, a used error and a stated reason all pass |
| Boundary | `except*`, a nested handler, a reason in a wrapped `except` header, a reason in the body |
| Degradation | a file that does not parse is reported, never skipped |
| Hostile | `pass`, `return None`, an `as e` never used, a call on a name that only looks like a logger |
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def check() -> ModuleType:
    path = REPO_ROOT / "scripts" / "check_lost_errors.py"
    spec = importlib.util.spec_from_file_location("check_lost_errors", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_lost_errors"] = module
    spec.loader.exec_module(module)
    return module


def _lost(check: ModuleType, body: str) -> list[int]:
    return check.lost_errors(textwrap.dedent(body))


@pytest.mark.parametrize(
    "handler",
    [
        "    logger.debug('no config: %s', path)",
        "    raise ValueError(path) from None",
        "    raise",
        "    return {'error': str(exc)}",
        "    self._log.warning('x')",
    ],
    ids=["logged", "raised-new", "re-raised", "used", "logger-attribute"],
)
def test_a_handled_error_passes(check: ModuleType, handler: str) -> None:
    source = f"try:\n    work()\nexcept OSError as exc:\n{handler}\n"

    assert check.lost_errors(source) == []


def test_a_stated_reason_on_the_except_line_passes(check: ModuleType) -> None:
    source = """
    try:
        json.loads(line)
    except json.JSONDecodeError:  # expected: a non-JSON line is not a diagnostic
        continue
    """
    assert _lost(check, source) == []


@pytest.mark.parametrize(
    "handler",
    ["    pass", "    return None", "    return []", "    continue", "    value = None"],
)
def test_a_silent_handler_is_lost(check: ModuleType, handler: str) -> None:
    source = f"for x in xs:\n  try:\n    work()\n  except OSError:\n  {handler}\n"

    assert check.lost_errors(source) == [4]


def test_an_unused_name_is_not_use(check: ModuleType) -> None:
    source = "try:\n    work()\nexcept OSError as exc:\n    return None\n"

    assert check.lost_errors(source) == [3]


def test_a_reason_in_a_wrapped_except_header_counts(check: ModuleType) -> None:
    source = """
    try:
        work()
    except (
        OSError,
        ValueError,
    ):  # expected: the formatter wrapped this header
        pass
    """
    assert _lost(check, source) == []


def test_a_reason_on_a_one_line_handler_counts(check: ModuleType) -> None:
    source = "try:\n    work()\nexcept OSError: pass  # expected: optional\n"

    assert check.lost_errors(source) == []


def test_a_reason_on_another_line_does_not_count(check: ModuleType) -> None:
    source = """
    try:
        work()
    except OSError:
        pass  # expected: nothing to clean up
    """
    assert _lost(check, source) == [4]


def test_an_empty_reason_does_not_count(check: ModuleType) -> None:
    source = "try:\n    work()\nexcept OSError:  # expected:\n    pass\n"

    assert check.lost_errors(source) == [3]


def test_a_name_that_only_looks_like_a_logger_does_not_count(check: ModuleType) -> None:
    source = "try:\n    work()\nexcept OSError:\n    catalog.info('x')\n"

    assert check.lost_errors(source) == [3]


def test_nested_and_star_handlers_are_each_judged(check: ModuleType) -> None:
    source = """
    try:
        try:
            work()
        except ValueError:
            pass
    except* OSError:
        logger.error("group")
    """
    assert _lost(check, source) == [5]


def test_the_command_names_each_offender_and_counts_reasons(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.py").write_text("try:\n    x()\nexcept OSError:\n    pass\n")
    (tmp_path / "b.py").write_text(
        "try:\n    x()\nexcept OSError:  # expected: optional file\n    pass\n"
    )

    code = check.main([str(tmp_path)])

    out = capsys.readouterr().out
    assert code == 1
    assert f"{tmp_path / 'a.py'}:3" in out
    assert "b.py" not in out.replace("1 reason", "")
    assert "1 reason" in out


def test_a_clean_tree_passes(check: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("try:\n    x()\nexcept OSError:\n    raise\n")

    assert check.main([str(tmp_path)]) == 0


def test_a_file_that_does_not_parse_fails(
    check: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "broken.py").write_text("def (:\n")

    assert check.main([str(tmp_path)]) == 1
    assert "broken.py" in capsys.readouterr().out
