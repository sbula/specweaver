# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for custom rule loader — discovers and registers Rule subclasses
from external directories.
"""

from __future__ import annotations

from pathlib import Path

from specweaver.validation.loader import load_rules_from_directory
from specweaver.validation.registry import RuleRegistry

# ---------------------------------------------------------------------------
# Test fixtures using tmp_path
# ---------------------------------------------------------------------------


def _write_rule_file(directory: Path, filename: str, content: str) -> Path:
    """Write a .py file with rule content."""
    filepath = directory / filename
    filepath.write_text(content, encoding="utf-8")
    return filepath


_VALID_RULE = """
from specweaver.validation.models import Rule, RuleResult, Status
from pathlib import Path

class SchemaCheckRule(Rule):
    @property
    def rule_id(self) -> str:
        return "D01"

    @property
    def name(self) -> str:
        return "Schema Check"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        return self._pass("ok")
"""

_VALID_RULE_2 = """
from specweaver.validation.models import Rule, RuleResult, Status
from pathlib import Path

class ApiContractRule(Rule):
    @property
    def rule_id(self) -> str:
        return "D02"

    @property
    def name(self) -> str:
        return "API Contract"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        return self._pass("ok")
"""

_NON_RULE_MODULE = '''
class NotARule:
    """Regular class, not a Rule subclass."""
    pass
'''

_BROKEN_MODULE = """
raise ImportError("intentionally broken")
"""

_BAD_PREFIX = """
from specweaver.validation.models import Rule, RuleResult, Status
from pathlib import Path

class BadRule(Rule):
    @property
    def rule_id(self) -> str:
        return "X01"  # Bad prefix -- not D-prefixed

    @property
    def name(self) -> str:
        return "Bad Prefix"

    def check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult:
        return self._pass("ok")
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadRulesFromDirectory:
    """Test load_rules_from_directory()."""

    def test_load_single_rule(self, tmp_path):
        """Discovers and returns a valid D-prefixed rule."""
        _write_rule_file(tmp_path, "d01_schema.py", _VALID_RULE)
        reg = RuleRegistry()
        loaded = load_rules_from_directory(tmp_path, registry=reg)
        assert "D01" in loaded
        assert reg.get("D01") is not None

    def test_load_multiple_rules(self, tmp_path):
        """Discovers multiple rules from a directory."""
        _write_rule_file(tmp_path, "d01_schema.py", _VALID_RULE)
        _write_rule_file(tmp_path, "d02_api.py", _VALID_RULE_2)
        reg = RuleRegistry()
        loaded = load_rules_from_directory(tmp_path, registry=reg)
        assert len(loaded) == 2
        assert "D01" in loaded
        assert "D02" in loaded

    def test_non_rule_class_ignored(self, tmp_path):
        """Files without Rule subclasses are silently ignored."""
        _write_rule_file(tmp_path, "helper.py", _NON_RULE_MODULE)
        reg = RuleRegistry()
        loaded = load_rules_from_directory(tmp_path, registry=reg)
        assert loaded == []

    def test_broken_module_skipped(self, tmp_path):
        """Broken .py files are skipped (not crashed)."""
        _write_rule_file(tmp_path, "broken.py", _BROKEN_MODULE)
        _write_rule_file(tmp_path, "d01_schema.py", _VALID_RULE)
        reg = RuleRegistry()
        loaded = load_rules_from_directory(tmp_path, registry=reg)
        # Only the valid rule loaded
        assert loaded == ["D01"]

    def test_bad_prefix_skipped(self, tmp_path):
        """Rules without D-prefix are skipped with a warning."""
        _write_rule_file(tmp_path, "x01_bad.py", _BAD_PREFIX)
        reg = RuleRegistry()
        loaded = load_rules_from_directory(tmp_path, registry=reg)
        assert loaded == []

    def test_empty_directory(self, tmp_path):
        """Empty directory returns empty list."""
        reg = RuleRegistry()
        loaded = load_rules_from_directory(tmp_path, registry=reg)
        assert loaded == []

    def test_nonexistent_directory(self):
        """Nonexistent directory returns empty list."""
        reg = RuleRegistry()
        loaded = load_rules_from_directory(Path("/nonexistent"), registry=reg)
        assert loaded == []

    def test_non_py_files_ignored(self, tmp_path):
        """Non-.py files are ignored."""
        (tmp_path / "readme.md").write_text("not a python file")
        reg = RuleRegistry()
        loaded = load_rules_from_directory(tmp_path, registry=reg)
        assert loaded == []

    def test_init_py_ignored(self, tmp_path):
        """__init__.py is ignored."""
        (tmp_path / "__init__.py").write_text("# init")
        reg = RuleRegistry()
        loaded = load_rules_from_directory(tmp_path, registry=reg)
        assert loaded == []
