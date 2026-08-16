# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the collection guard (`scripts/check_test_collection.py`).

Proves: TECH-051 FR-2, TECH-051 FR-3

`TECH-051` CB-3. A test file that pytest collects nothing from reads as coverage in a directory
listing, in review, and to anyone deciding not to write a test because one appears to exist. Twelve
files were in that state on 2026-08-16 and three of them hid 24 tests behind a class named
`QARunnerTelemetryFlush` — no `Test` prefix, so never collected.

**Every rule is driven against synthetic files, never against the repo's own state.** A test
asserting "the tree is clean" passes for exactly as long as nobody breaks it and says nothing about
whether the rule works. The one live-repo assertion is at the bottom and is deliberately the last
line of defence, not the evidence.

`scripts/` is not an importable package, so the module is loaded by path.
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

HEADER = (
    "# Copyright (c) 2026 sbula. All rights reserved.\n"
    "# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.\n"
)


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ctc() -> ModuleType:
    return _load("check_test_collection")


def _tree(root: Path, files: dict[str, str]) -> Path:
    tests = root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        path = tests / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(HEADER + body, encoding="utf-8")
    return tests


#: The shape that started this ticket: methods named `test_*`, class not named `Test*`.
_UNPREFIXED_CLASS = """
class QARunnerTelemetryFlush:
    def test_flush_called_on_successful_run(self):
        assert True

    def test_flush_called_on_failed_run(self):
        assert True
"""

_CONFORMING_CLASS = """
class TestFlush:
    def test_flush_called_on_successful_run(self):
        assert True
"""

_MODULE_LEVEL_FUNCTION = """
def test_it_works():
    assert True
"""


class TestContributedTests:
    """`contributed_tests` applies pytest's collection rules statically."""

    def test_a_module_level_function_counts(self, ctc: ModuleType, tmp_path: Path) -> None:
        tests = _tree(tmp_path, {"test_a.py": _MODULE_LEVEL_FUNCTION})
        assert ctc.contributed_tests(tests / "test_a.py") == 1

    def test_methods_in_a_test_prefixed_class_count(self, ctc: ModuleType, tmp_path: Path) -> None:
        tests = _tree(tmp_path, {"test_b.py": _CONFORMING_CLASS})
        assert ctc.contributed_tests(tests / "test_b.py") == 1

    def test_methods_in_an_unprefixed_class_do_not_count(
        self, ctc: ModuleType, tmp_path: Path
    ) -> None:
        """The defect itself: two `test_*` methods, and pytest sees none of them."""
        tests = _tree(tmp_path, {"test_c.py": _UNPREFIXED_CLASS})
        assert ctc.contributed_tests(tests / "test_c.py") == 0

    def test_a_file_with_no_definitions_at_all_counts_zero(
        self, ctc: ModuleType, tmp_path: Path
    ) -> None:
        """The nine `sandbox/protocol` stubs were exactly this — a licence header and nothing."""
        tests = _tree(tmp_path, {"test_d.py": "\n"})
        assert ctc.contributed_tests(tests / "test_d.py") == 0

    def test_a_helper_function_is_not_a_test(self, ctc: ModuleType, tmp_path: Path) -> None:
        """`_scaffold` and friends are not tests, however many of them a file has."""
        tests = _tree(tmp_path, {"test_e.py": "\ndef _scaffold():\n    return 1\n"})
        assert ctc.contributed_tests(tests / "test_e.py") == 0

    def test_an_async_test_counts(self, ctc: ModuleType, tmp_path: Path) -> None:
        """`asyncio_mode = auto` means an async def is a test like any other here."""
        tests = _tree(tmp_path, {"test_f.py": "\nasync def test_async():\n    assert True\n"})
        assert ctc.contributed_tests(tests / "test_f.py") == 1

    def test_a_nested_class_inside_a_test_class_counts(
        self, ctc: ModuleType, tmp_path: Path
    ) -> None:
        """pytest recurses into `Test*` classes, so a rule that only looked one level would
        under-count and report a real file as empty — a false accusation is as bad as a miss."""
        body = "\nclass TestOuter:\n    class TestInner:\n        def test_deep(self):\n            assert True\n"
        tests = _tree(tmp_path, {"test_g.py": body})
        assert ctc.contributed_tests(tests / "test_g.py") == 1

    def test_a_file_that_cannot_be_parsed_is_not_silently_zero(
        self, ctc: ModuleType, tmp_path: Path
    ) -> None:
        """A syntax error is a different problem, and reporting it as "contributes nothing" would
        send the reader looking for a missing class instead of a missing colon."""
        tests = _tree(tmp_path, {"test_h.py": "\ndef test_broken(:\n"})
        with pytest.raises(SyntaxError):
            ctc.contributed_tests(tests / "test_h.py")


class TestContributedTestsWithMarkers:
    """FR-3 — `contributed_tests` counts a marked file; 13 are excluded by `live` on purpose."""

    def test_a_module_level_marker_file_still_contributes(
        self, ctc: ModuleType, tmp_path: Path
    ) -> None:
        """`pytestmark = pytest.mark.live` removes a file from the DEFAULT run, not from
        collection. Counting markers would report all 13 as holes and train the reader to ignore
        this check — which is how the 24 hidden tests survived a year of review."""
        body = "\nimport pytest\n\npytestmark = pytest.mark.live\n\n\ndef test_needs_a_key():\n    assert True\n"
        tests = _tree(tmp_path, {"test_i.py": body})
        assert ctc.contributed_tests(tests / "test_i.py") == 1


class TestOffenders:
    """`offenders` walks a tree and names what contributes nothing."""

    def test_only_the_empty_files_are_reported(self, ctc: ModuleType, tmp_path: Path) -> None:
        tests = _tree(
            tmp_path,
            {
                "test_ok.py": _MODULE_LEVEL_FUNCTION,
                "unit/test_hidden.py": _UNPREFIXED_CLASS,
                "unit/test_stub.py": "\n",
            },
        )
        found = {path for path, _ in ctc.offenders(tests)}
        assert found == {"unit/test_hidden.py", "unit/test_stub.py"}

    def test_the_reason_distinguishes_the_two_causes(self, ctc: ModuleType, tmp_path: Path) -> None:
        """A rename and a missing file are different fixes, so they must read differently."""
        tests = _tree(tmp_path, {"test_hidden.py": _UNPREFIXED_CLASS, "test_stub.py": "\n"})
        reasons = dict(ctc.offenders(tests))

        assert "QARunnerTelemetryFlush" in reasons["test_hidden.py"]
        assert "nothing" in reasons["test_stub.py"].lower()

    def test_files_that_are_not_test_modules_are_never_candidates(
        self, ctc: ModuleType, tmp_path: Path
    ) -> None:
        """`conftest.py`, `rendering.py` and `__init__.py` hold no tests and are not accused.

        **This replaces a test that proved nothing.** The first version asserted the same thing
        against an explicit exemption list in the source — and a mutant emptying that list survived,
        because the walk globs `test_*.py` and these names never matched it. The list was dead code
        wearing a passing test; both were deleted, and this asserts the property that is actually
        load-bearing.
        """
        tests = _tree(tmp_path, {"conftest.py": "\n", "rendering.py": "\n", "__init__.py": "\n"})

        assert ctc.offenders(tests) == []
        assert ctc.offenders(tests) == [], "a second call must not accumulate state"


class TestCollectionPrefixes:
    """NFR-2 — the rule reads pytest's configuration rather than assuming its defaults."""

    def test_the_defaults_are_used_when_nothing_is_configured(
        self, ctc: ModuleType, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")

        assert ctc.collection_prefixes(tmp_path) == ("Test", "test")

    def test_a_configured_prefix_is_honoured(self, ctc: ModuleType, tmp_path: Path) -> None:
        """A project renaming its convention must not turn every file into a false accusation."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\npython_classes = "Spec*"\n', encoding="utf-8"
        )

        assert ctc.collection_prefixes(tmp_path) == ("Spec", "test")

    def test_a_pattern_this_rule_cannot_honour_fails_loudly(
        self, ctc: ModuleType, tmp_path: Path
    ) -> None:
        """[Hostile] two patterns, or a mid-string wildcard, are beyond a prefix comparison.

        Guessing would be worse than refusing: the check would report every conforming file as a
        hole and be believed, because it has been right until then. Found by a mutant — replacing
        the raise with `pass` survived, since this repo configures neither key and nothing reached
        the branch.
        """
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\npython_classes = "Test* Spec*"\n', encoding="utf-8"
        )

        with pytest.raises(NotImplementedError, match="python_classes"):
            ctc.collection_prefixes(tmp_path)

    def test_a_missing_pyproject_falls_back_to_the_defaults(
        self, ctc: ModuleType, tmp_path: Path
    ) -> None:
        """[Boundary] no config is not a broken config."""
        assert ctc.collection_prefixes(tmp_path) == ("Test", "test")


class TestCompareWithPytest:
    """FR-2 — the static rule is worth exactly its agreement with the real collector."""

    def test_the_static_count_matches_a_real_collection_pass(self, ctc: ModuleType) -> None:
        """Run pytest for real over this repo and compare the two sets file by file.

        This is the test that makes the approximation defensible. Without it the check is a guess
        about someone else's rules, and the first custom `python_classes` setting would make it
        confidently wrong.
        """
        static, live = ctc.compare_with_pytest(REPO_ROOT)

        assert static == live, (
            "the static rule disagrees with pytest about which files contribute tests:\n"
            f"  static says yes, pytest says no: {sorted(static - live)}\n"
            f"  pytest says yes, static says no: {sorted(live - static)}"
        )


class TestMain:
    """The CLI contract `quality.py` depends on: 0 clean, 1 findings, 2 cannot run."""

    def test_exits_one_and_names_the_file(
        self, ctc: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _tree(tmp_path, {"test_hidden.py": _UNPREFIXED_CLASS})
        assert ctc.main(["--root", str(tmp_path)]) == 1
        assert "test_hidden.py" in capsys.readouterr().out

    def test_exits_zero_on_a_clean_tree(self, ctc: ModuleType, tmp_path: Path) -> None:
        _tree(tmp_path, {"test_ok.py": _MODULE_LEVEL_FUNCTION})
        assert ctc.main(["--root", str(tmp_path)]) == 0

    def test_exits_two_when_there_is_no_tests_directory(
        self, ctc: ModuleType, tmp_path: Path
    ) -> None:
        """`TECH-032`: a checker that cannot find its subject says so rather than passing."""
        assert ctc.main(["--root", str(tmp_path / "nowhere")]) == 2

    def test_the_live_repo_is_clean(self, ctc: ModuleType) -> None:
        """Last line of defence, not the evidence — every rule above is proven synthetically."""
        assert ctc.main([]) == 0
