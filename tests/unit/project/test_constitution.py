# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for specweaver.project.constitution — TDD (tests first)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from specweaver.project.constitution import (
    CONSTITUTION_FILENAME,
    DEFAULT_MAX_CONSTITUTION_SIZE,
    ConstitutionInfo,
    check_constitution,
    find_all_constitutions,
    find_constitution,
    generate_constitution,
    generate_constitution_from_standards,
    is_unmodified_starter,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_with_constitution(tmp_path: Path) -> Path:
    """Project root with a valid CONSTITUTION.md."""
    (tmp_path / ".specweaver").mkdir()
    (tmp_path / CONSTITUTION_FILENAME).write_text(
        "# Test Project — Constitution\n\n## 1. Identity\n\nTest project.\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture()
def monorepo(tmp_path: Path) -> Path:
    """Monorepo with root + service-level constitutions."""
    (tmp_path / ".specweaver").mkdir()
    (tmp_path / CONSTITUTION_FILENAME).write_text(
        "# Root Constitution\n\n## 1. Identity\n\nRoot project.\n",
        encoding="utf-8",
    )
    # billing-svc has its own constitution (override)
    billing = tmp_path / "billing-svc"
    billing.mkdir()
    (billing / CONSTITUTION_FILENAME).write_text(
        "# Billing Constitution\n\nGDPR compliance required.\n",
        encoding="utf-8",
    )
    # analytics-svc has NO constitution (inherits root)
    (tmp_path / "analytics-svc").mkdir()
    # auth-svc has a spec but no constitution
    auth = tmp_path / "auth-svc"
    auth.mkdir()
    (auth / "specs").mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# find_constitution — happy path
# ---------------------------------------------------------------------------


class TestFindConstitution:
    """Tests for find_constitution()."""

    def test_finds_root_constitution(
        self,
        project_with_constitution: Path,
    ) -> None:
        """Finds CONSTITUTION.md at project root."""
        result = find_constitution(project_with_constitution)
        assert result is not None
        assert isinstance(result, ConstitutionInfo)
        assert "Test Project" in result.content
        assert result.path == project_with_constitution / CONSTITUTION_FILENAME
        assert result.is_override is False

    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        """Returns None when no CONSTITUTION.md exists."""
        (tmp_path / ".specweaver").mkdir()
        result = find_constitution(tmp_path)
        assert result is None

    def test_returns_size_in_bytes(
        self,
        project_with_constitution: Path,
    ) -> None:
        """ConstitutionInfo.size reflects actual file size."""
        result = find_constitution(project_with_constitution)
        assert result is not None
        expected = len(
            (project_with_constitution / CONSTITUTION_FILENAME).read_bytes(),
        )
        assert result.size == expected


# ---------------------------------------------------------------------------
# find_constitution — walk-up resolution
# ---------------------------------------------------------------------------


class TestFindConstitutionWalkUp:
    """Tests for walk-up resolution from spec_path."""

    def test_service_override_wins(self, monorepo: Path) -> None:
        """Service-level CONSTITUTION.md overrides root."""
        billing_spec = monorepo / "billing-svc" / "some_spec.md"
        result = find_constitution(
            monorepo,
            spec_path=billing_spec,
        )
        assert result is not None
        assert "Billing Constitution" in result.content
        assert result.is_override is True

    def test_inherits_root_when_no_override(self, monorepo: Path) -> None:
        """Service without CONSTITUTION.md inherits root."""
        analytics_spec = monorepo / "analytics-svc" / "some_spec.md"
        result = find_constitution(
            monorepo,
            spec_path=analytics_spec,
        )
        assert result is not None
        assert "Root Constitution" in result.content
        assert result.is_override is False

    def test_walk_up_stops_at_project_root(self, monorepo: Path) -> None:
        """Walk-up never goes above project_path."""
        # Even if there's a constitution above project_path, it's ignored
        deep_spec = monorepo / "auth-svc" / "specs" / "deep_spec.md"
        result = find_constitution(monorepo, spec_path=deep_spec)
        assert result is not None
        assert "Root Constitution" in result.content

    def test_no_spec_path_uses_project_root(
        self,
        project_with_constitution: Path,
    ) -> None:
        """When spec_path is None, checks project root only."""
        result = find_constitution(project_with_constitution)
        assert result is not None
        assert "Test Project" in result.content


# ---------------------------------------------------------------------------
# find_constitution — size handling
# ---------------------------------------------------------------------------


class TestFindConstitutionSize:
    """Tests for size enforcement behavior."""

    def test_oversized_loads_with_warning(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Constitution > max_size loads but logs WARNING."""
        (tmp_path / ".specweaver").mkdir()
        oversized = "x" * (DEFAULT_MAX_CONSTITUTION_SIZE + 100)
        (tmp_path / CONSTITUTION_FILENAME).write_text(
            oversized,
            encoding="utf-8",
        )

        with caplog.at_level(logging.WARNING):
            result = find_constitution(tmp_path)

        assert result is not None  # Loaded anyway
        assert result.content == oversized
        assert "exceeds" in caplog.text.lower() or "size" in caplog.text.lower()

    def test_custom_max_size(self, tmp_path: Path) -> None:
        """Custom max_size is respected."""
        (tmp_path / ".specweaver").mkdir()
        (tmp_path / CONSTITUTION_FILENAME).write_text(
            "x" * 100,
            encoding="utf-8",
        )

        # With a tiny limit, file loads with warning
        result = find_constitution(tmp_path, max_size=50)
        assert result is not None
        assert result.size == 100

    def test_exactly_at_limit_no_warning(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Constitution exactly at max_size does NOT warn."""
        (tmp_path / ".specweaver").mkdir()
        content = "x" * DEFAULT_MAX_CONSTITUTION_SIZE
        (tmp_path / CONSTITUTION_FILENAME).write_text(
            content,
            encoding="utf-8",
        )

        with caplog.at_level(logging.WARNING):
            result = find_constitution(tmp_path)

        assert result is not None
        assert "exceeds" not in caplog.text.lower()


# ---------------------------------------------------------------------------
# find_constitution — encoding edge cases
# ---------------------------------------------------------------------------


class TestFindConstitutionEncoding:
    """Encoding edge cases."""

    def test_utf8_with_bom_stripped(self, tmp_path: Path) -> None:
        """UTF-8 BOM is stripped from constitution content."""
        (tmp_path / ".specweaver").mkdir()
        bom_content = "\ufeff# Constitution with BOM\n"
        (tmp_path / CONSTITUTION_FILENAME).write_text(
            bom_content,
            encoding="utf-8-sig",
        )

        result = find_constitution(tmp_path)
        assert result is not None
        assert not result.content.startswith("\ufeff")
        assert result.content.startswith("# Constitution")

    def test_empty_file_returns_info(self, tmp_path: Path) -> None:
        """Empty constitution file returns ConstitutionInfo with empty content."""
        (tmp_path / ".specweaver").mkdir()
        (tmp_path / CONSTITUTION_FILENAME).write_text("", encoding="utf-8")

        result = find_constitution(tmp_path)
        assert result is not None
        assert result.content == ""
        assert result.size == 0


# ---------------------------------------------------------------------------
# find_all_constitutions
# ---------------------------------------------------------------------------


class TestFindAllConstitutions:
    """Tests for find_all_constitutions()."""

    def test_finds_root_and_overrides(self, monorepo: Path) -> None:
        """Finds root + all service-level constitutions."""
        results = find_all_constitutions(monorepo)
        assert len(results) == 2  # root + billing-svc
        paths = {r.path for r in results}
        assert monorepo / CONSTITUTION_FILENAME in paths
        assert monorepo / "billing-svc" / CONSTITUTION_FILENAME in paths

    def test_empty_project_returns_empty(self, tmp_path: Path) -> None:
        """No constitutions → empty list."""
        results = find_all_constitutions(tmp_path)
        assert results == []

    def test_root_only(
        self,
        project_with_constitution: Path,
    ) -> None:
        """Project with only root constitution → single result."""
        results = find_all_constitutions(project_with_constitution)
        assert len(results) == 1
        assert results[0].is_override is False

    def test_overrides_marked_correctly(self, monorepo: Path) -> None:
        """Service-level constitutions have is_override=True."""
        results = find_all_constitutions(monorepo)
        root = [r for r in results if not r.is_override]
        overrides = [r for r in results if r.is_override]
        assert len(root) == 1
        assert len(overrides) == 1


# ---------------------------------------------------------------------------
# check_constitution
# ---------------------------------------------------------------------------


class TestCheckConstitution:
    """Tests for check_constitution() — CI gate."""

    def test_valid_passes(
        self,
        project_with_constitution: Path,
    ) -> None:
        """Valid constitution passes check with no errors."""
        path = project_with_constitution / CONSTITUTION_FILENAME
        errors = check_constitution(path)
        assert errors == []

    def test_oversized_returns_error(self, tmp_path: Path) -> None:
        """Constitution > max_size returns size error (not warning)."""
        path = tmp_path / CONSTITUTION_FILENAME
        path.write_text("x" * 6000, encoding="utf-8")

        errors = check_constitution(path)
        assert len(errors) >= 1
        assert any("size" in e.lower() or "exceeds" in e.lower() for e in errors)

    def test_custom_max_size_in_check(self, tmp_path: Path) -> None:
        """check_constitution respects custom max_size."""
        path = tmp_path / CONSTITUTION_FILENAME
        path.write_text("x" * 100, encoding="utf-8")

        # Passes with default limit
        assert check_constitution(path) == []

        # Fails with tiny limit
        errors = check_constitution(path, max_size=50)
        assert len(errors) >= 1

    def test_nonexistent_file_returns_error(self, tmp_path: Path) -> None:
        """Checking a nonexistent file returns an error."""
        path = tmp_path / CONSTITUTION_FILENAME
        errors = check_constitution(path)
        assert len(errors) >= 1
        assert any("not found" in e.lower() or "exist" in e.lower() for e in errors)

    def test_empty_file_passes(self, tmp_path: Path) -> None:
        """Empty constitution file is valid (user may not have filled it yet)."""
        path = tmp_path / CONSTITUTION_FILENAME
        path.write_text("", encoding="utf-8")

        errors = check_constitution(path)
        assert errors == []


# ---------------------------------------------------------------------------
# generate_constitution
# ---------------------------------------------------------------------------


class TestGenerateConstitution:
    """Tests for generate_constitution()."""

    def test_creates_file(self, tmp_path: Path) -> None:
        """generate_constitution creates CONSTITUTION.md."""
        result = generate_constitution(tmp_path, "my-app")
        assert result.exists()
        assert result.name == CONSTITUTION_FILENAME

    def test_content_has_template_sections(self, tmp_path: Path) -> None:
        """Generated constitution has all 8 template sections."""
        generate_constitution(tmp_path, "my-app")
        content = (tmp_path / CONSTITUTION_FILENAME).read_text()
        assert "Identity" in content
        assert "Tech Stack" in content
        assert "Architecture Principles" in content
        assert "Coding Standards" in content
        assert "Security Invariants" in content
        assert "Prohibited Actions" in content
        assert "Key Documents" in content
        assert "Agent Instructions" in content

    def test_content_includes_project_name(self, tmp_path: Path) -> None:
        """Generated constitution references the project name."""
        generate_constitution(tmp_path, "my-app")
        content = (tmp_path / CONSTITUTION_FILENAME).read_text()
        assert "my-app" in content

    def test_idempotent_does_not_overwrite(self, tmp_path: Path) -> None:
        """generate_constitution does not overwrite existing file."""
        existing = tmp_path / CONSTITUTION_FILENAME
        existing.write_text("# Custom constitution\n", encoding="utf-8")

        generate_constitution(tmp_path, "my-app")

        assert existing.read_text() == "# Custom constitution\n"

    def test_fits_within_size_budget(self, tmp_path: Path) -> None:
        """Generated template is ≤ max size (should be ~1.5KB)."""
        generate_constitution(tmp_path, "my-app")
        content = (tmp_path / CONSTITUTION_FILENAME).read_bytes()
        assert len(content) <= DEFAULT_MAX_CONSTITUTION_SIZE

    def test_has_todo_placeholders(self, tmp_path: Path) -> None:
        """Template has TODO placeholders for user to fill in."""
        generate_constitution(tmp_path, "my-app")
        content = (tmp_path / CONSTITUTION_FILENAME).read_text()
        assert "TODO" in content


# ---------------------------------------------------------------------------
# Edge cases — critical scenarios
# ---------------------------------------------------------------------------


class TestConstitutionEdgeCases:
    """Critical edge cases for constitution loader."""

    def test_spec_outside_project_root(self, tmp_path: Path) -> None:
        """spec_path outside project_path still finds root constitution."""
        project = tmp_path / "project"
        project.mkdir()
        (project / CONSTITUTION_FILENAME).write_text(
            "# Root",
            encoding="utf-8",
        )
        # spec_path is outside project_path
        outside_spec = tmp_path / "other" / "spec.md"
        result = find_constitution(project, spec_path=outside_spec)
        # Should still find root constitution via fallback
        assert result is not None
        assert "Root" in result.content

    def test_deeply_nested_walk_up(self, tmp_path: Path) -> None:
        """Walk-up from 4 levels deep should still reach project root."""
        (tmp_path / CONSTITUTION_FILENAME).write_text(
            "# Root rules",
            encoding="utf-8",
        )
        deep = tmp_path / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        spec = deep / "spec.md"

        result = find_constitution(tmp_path, spec_path=spec)
        assert result is not None
        assert "Root rules" in result.content
        assert result.is_override is False

    def test_deeply_nested_mid_level_override(self, tmp_path: Path) -> None:
        """Constitution at a mid-level directory wins over root."""
        (tmp_path / CONSTITUTION_FILENAME).write_text(
            "# Root",
            encoding="utf-8",
        )
        mid = tmp_path / "services" / "auth"
        mid.mkdir(parents=True)
        (mid / CONSTITUTION_FILENAME).write_text(
            "# Auth rules",
            encoding="utf-8",
        )
        deep_spec = mid / "specs" / "login_spec.md"

        result = find_constitution(tmp_path, spec_path=deep_spec)
        assert result is not None
        assert "Auth rules" in result.content
        assert result.is_override is True

    def test_find_all_ignores_hidden_directories(self, tmp_path: Path) -> None:
        """find_all_constitutions skips hidden dirs like .git/."""
        (tmp_path / CONSTITUTION_FILENAME).write_text(
            "# Root",
            encoding="utf-8",
        )
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / CONSTITUTION_FILENAME).write_text(
            "# Git junk",
            encoding="utf-8",
        )

        results = find_all_constitutions(tmp_path)
        paths = {r.path for r in results}
        assert tmp_path / CONSTITUTION_FILENAME in paths
        assert git_dir / CONSTITUTION_FILENAME not in paths

    def test_whitespace_only_constitution(self, tmp_path: Path) -> None:
        """Constitution with only whitespace loads as whitespace content."""
        (tmp_path / CONSTITUTION_FILENAME).write_text(
            "   \n\n  \t  \n",
            encoding="utf-8",
        )
        result = find_constitution(tmp_path)
        assert result is not None
        assert result.content.strip() == ""

    def test_unicode_constitution(self, tmp_path: Path) -> None:
        """Constitution with unicode characters loads correctly."""
        content = "# Règles du Projet\n\nUtiliser des accents: é, ü, ñ, 中文\n"
        (tmp_path / CONSTITUTION_FILENAME).write_text(
            content,
            encoding="utf-8",
        )
        result = find_constitution(tmp_path)
        assert result is not None
        assert "Règles" in result.content
        assert "中文" in result.content

    def test_generate_with_special_chars_in_name(self, tmp_path: Path) -> None:
        """Project name with braces doesn't crash format()."""
        # Braces in project_name should not cause KeyError
        result = generate_constitution(tmp_path, "my-{special}-app")
        assert result.exists()
        content = result.read_text()
        assert "my-{special}-app" in content

    def test_check_exactly_at_limit(self, tmp_path: Path) -> None:
        """Constitution exactly at max_size passes check."""
        path = tmp_path / CONSTITUTION_FILENAME
        path.write_text("x" * DEFAULT_MAX_CONSTITUTION_SIZE, encoding="utf-8")

        errors = check_constitution(path)
        assert errors == []

    def test_check_one_byte_over_limit(self, tmp_path: Path) -> None:
        """Constitution one byte over max_size fails check."""
        path = tmp_path / CONSTITUTION_FILENAME
        path.write_text(
            "x" * (DEFAULT_MAX_CONSTITUTION_SIZE + 1),
            encoding="utf-8",
        )

        errors = check_constitution(path, max_size=DEFAULT_MAX_CONSTITUTION_SIZE)
        assert len(errors) >= 1


# ---------------------------------------------------------------------------
# is_unmodified_starter
# ---------------------------------------------------------------------------


class TestIsUnmodifiedStarter:
    """Tests for is_unmodified_starter()."""

    def test_starter_template_is_unmodified(self, tmp_path: Path) -> None:
        """Generated starter template is detected as unmodified."""
        generate_constitution(tmp_path, "my-app")
        path = tmp_path / CONSTITUTION_FILENAME
        assert is_unmodified_starter(path) is True

    def test_edited_template_is_not_unmodified(self, tmp_path: Path) -> None:
        """File with few TODO markers is detected as user-edited."""
        path = tmp_path / CONSTITUTION_FILENAME
        path.write_text("# My Customized Constitution\n\nAll real content.\n")
        assert is_unmodified_starter(path) is False

    def test_partially_edited_with_some_todos(self, tmp_path: Path) -> None:
        """File with 4 TODOs (below threshold of 5) is considered edited."""
        path = tmp_path / CONSTITUTION_FILENAME
        path.write_text("# Real\nTODO\nTODO\nTODO\nTODO\n")
        assert is_unmodified_starter(path) is False

    def test_five_todos_is_unmodified(self, tmp_path: Path) -> None:
        """File with exactly 5 TODOs is considered unmodified."""
        path = tmp_path / CONSTITUTION_FILENAME
        path.write_text("TODO " * 5 + "\n")
        assert is_unmodified_starter(path) is True

    def test_nonexistent_file_returns_false(self, tmp_path: Path) -> None:
        """Nonexistent file returns False."""
        path = tmp_path / CONSTITUTION_FILENAME
        assert is_unmodified_starter(path) is False

    def test_empty_file_returns_false(self, tmp_path: Path) -> None:
        """Empty file returns False (no TODOs = edited)."""
        path = tmp_path / CONSTITUTION_FILENAME
        path.write_text("")
        assert is_unmodified_starter(path) is False


# ---------------------------------------------------------------------------
# generate_constitution_from_standards
# ---------------------------------------------------------------------------


_SAMPLE_STANDARDS = [
    {
        "scope": ".",
        "language": "python",
        "category": "naming",
        "data": {"function_style": "snake_case", "class_style": "PascalCase"},
        "confidence": 0.95,
        "confirmed_by": "hitl",
    },
    {
        "scope": ".",
        "language": "python",
        "category": "error_handling",
        "data": {"pattern": "try_except_specific"},
        "confidence": 0.88,
        "confirmed_by": "hitl",
    },
]


class TestGenerateConstitutionFromStandards:
    """Tests for generate_constitution_from_standards()."""

    def test_creates_file_from_standards(self, tmp_path: Path) -> None:
        """Creates CONSTITUTION.md with standards data."""
        result = generate_constitution_from_standards(
            tmp_path,
            "my-app",
            _SAMPLE_STANDARDS,
            ["python"],
        )
        assert result is not None
        assert result.exists()
        content = result.read_text()
        assert "Auto-Discovered" in content
        assert "Python" in content

    def test_content_has_coding_standards(self, tmp_path: Path) -> None:
        """Generated file includes standards data."""
        generate_constitution_from_standards(
            tmp_path,
            "my-app",
            _SAMPLE_STANDARDS,
            ["python"],
        )
        content = (tmp_path / CONSTITUTION_FILENAME).read_text()
        assert "snake_case" in content
        assert "PascalCase" in content
        assert "try_except_specific" in content

    def test_multi_language_tech_stack(self, tmp_path: Path) -> None:
        """Multiple languages are listed in tech stack."""
        standards = [
            *_SAMPLE_STANDARDS,
            {
                "scope": ".",
                "language": "typescript",
                "category": "naming",
                "data": {"variable_style": "camelCase"},
                "confidence": 0.90,
                "confirmed_by": "hitl",
            },
        ]
        generate_constitution_from_standards(
            tmp_path,
            "my-app",
            standards,
            ["python", "typescript"],
        )
        content = (tmp_path / CONSTITUTION_FILENAME).read_text()
        assert "Python" in content
        assert "TypeScript" in content

    def test_empty_standards_falls_back_to_todo(self, tmp_path: Path) -> None:
        """Empty standards list falls back to TODO placeholders."""
        result = generate_constitution_from_standards(
            tmp_path,
            "my-app",
            [],
            [],
        )
        assert result is not None
        content = result.read_text()
        assert "TODO" in content
        assert "Naming conventions" in content

    def test_skips_user_edited_constitution(self, tmp_path: Path) -> None:
        """Does not overwrite user-edited CONSTITUTION.md."""
        path = tmp_path / CONSTITUTION_FILENAME
        path.write_text("# My custom constitution\nNo TODOs here.\n")

        result = generate_constitution_from_standards(
            tmp_path,
            "my-app",
            _SAMPLE_STANDARDS,
            ["python"],
        )
        assert result is None
        assert "My custom constitution" in path.read_text()

    def test_replaces_unmodified_starter(self, tmp_path: Path) -> None:
        """Auto-replaces the unmodified starter template."""
        generate_constitution(tmp_path, "my-app")
        path = tmp_path / CONSTITUTION_FILENAME
        original = path.read_text()
        assert "TODO" in original  # starter template

        result = generate_constitution_from_standards(
            tmp_path,
            "my-app",
            _SAMPLE_STANDARDS,
            ["python"],
        )
        assert result is not None
        new_content = path.read_text()
        assert "Auto-Discovered" in new_content
        assert new_content != original

    def test_force_overwrites_user_edited(self, tmp_path: Path) -> None:
        """--force overwrites even user-edited constitutions."""
        path = tmp_path / CONSTITUTION_FILENAME
        path.write_text("# My custom constitution\n")

        result = generate_constitution_from_standards(
            tmp_path,
            "my-app",
            _SAMPLE_STANDARDS,
            ["python"],
            force=True,
        )
        assert result is not None
        assert "Auto-Discovered" in path.read_text()

    def test_creates_when_no_file_exists(self, tmp_path: Path) -> None:
        """Creates CONSTITUTION.md when none exists."""
        path = tmp_path / CONSTITUTION_FILENAME
        assert not path.exists()

        result = generate_constitution_from_standards(
            tmp_path,
            "my-app",
            _SAMPLE_STANDARDS,
            ["python"],
        )
        assert result is not None
        assert path.exists()


# ---------------------------------------------------------------------------
# is_unmodified_starter — OSError edge case
# ---------------------------------------------------------------------------


class TestIsUnmodifiedStarterOSError:
    """Test is_unmodified_starter() handles OS-level read errors."""

    def test_oserror_on_read_returns_false(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """OSError during file read → returns False gracefully."""
        path = tmp_path / CONSTITUTION_FILENAME
        path.write_text("TODO " * 10)

        # Monkeypatch Path.read_text to raise OSError
        from pathlib import Path as _Path

        original_read_text = _Path.read_text

        def broken_read_text(self, *args, **kwargs):
            if self.name == CONSTITUTION_FILENAME:
                raise OSError("Permission denied")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(_Path, "read_text", broken_read_text)
        assert is_unmodified_starter(path) is False


# ---------------------------------------------------------------------------
# _build_tech_stack_rows — direct helper tests
# ---------------------------------------------------------------------------


class TestBuildTechStackRows:
    """Tests for _build_tech_stack_rows() helper."""

    def test_empty_languages_returns_todo_row(self) -> None:
        """Empty languages list → single TODO row."""
        from specweaver.project.constitution import _build_tech_stack_rows

        result = _build_tech_stack_rows([])
        assert "TODO" in result
        assert "Language" in result

    def test_unknown_language_gets_fallback(self) -> None:
        """Unknown language → capitalized name with TODO version."""
        from specweaver.project.constitution import _build_tech_stack_rows

        result = _build_tech_stack_rows(["rust"])
        assert "Rust" in result
        assert "TODO" in result

    def test_known_language_gets_info(self) -> None:
        """Known language → specific version and purpose."""
        from specweaver.project.constitution import _build_tech_stack_rows

        result = _build_tech_stack_rows(["python"])
        assert "Python" in result
        assert "3.11+" in result


# ---------------------------------------------------------------------------
# _build_standards_section — edge cases
# ---------------------------------------------------------------------------


class TestBuildStandardsSection:
    """Tests for _build_standards_section() helper."""

    def test_string_data_parsed_as_json(self) -> None:
        """Data stored as JSON string is round-tripped."""
        import json

        from specweaver.project.constitution import _build_standards_section

        standards = [
            {
                "scope": ".",
                "language": "python",
                "category": "naming",
                "data": json.dumps({"style": "snake_case"}),
                "confidence": 0.9,
            }
        ]
        result = _build_standards_section(standards)
        assert "snake_case" in result

    def test_scoped_standards_prefix_format(self) -> None:
        """Standards with scope != '.' get [scope/lang] prefix."""
        from specweaver.project.constitution import _build_standards_section

        standards = [
            {
                "scope": "backend",
                "language": "python",
                "category": "naming",
                "data": {"style": "snake_case"},
                "confidence": 0.85,
            }
        ]
        result = _build_standards_section(standards)
        assert "[backend/python]" in result

    def test_root_scope_prefix_format(self) -> None:
        """Standards with scope == '.' get [lang] prefix."""
        from specweaver.project.constitution import _build_standards_section

        standards = [
            {
                "scope": ".",
                "language": "python",
                "category": "naming",
                "data": {"style": "snake_case"},
                "confidence": 0.85,
            }
        ]
        result = _build_standards_section(standards)
        assert "[python]" in result
        assert "[./python]" not in result
