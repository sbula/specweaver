# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for specweaver.workspace.project.scaffold — TDD (tests first)."""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specweaver.workspace.project.scaffold import scaffold_project

# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestScaffoldProject:
    """Test project scaffold creation."""

    def test_creates_specweaver_dir(self, tmp_path: Path) -> None:
        """scaffold_project creates .specweaver/ directory."""
        scaffold_project(tmp_path)
        assert (tmp_path / ".specweaver").is_dir()

    def test_creates_specs_dir(self, tmp_path: Path) -> None:
        """scaffold_project creates specs/ directory."""
        scaffold_project(tmp_path)
        assert (tmp_path / "specs").is_dir()

    def test_specweaver_dir_is_marker_only(self, tmp_path: Path) -> None:
        """scaffold_project creates .specweaver/ as marker-only (no config.yaml)."""
        scaffold_project(tmp_path)
        assert not (tmp_path / ".specweaver" / "config.yaml").exists()

    def test_creates_templates_dir_with_component_spec(self, tmp_path: Path) -> None:
        """scaffold_project creates .specweaver/templates/ with component_spec.md."""
        scaffold_project(tmp_path)
        tmpl = tmp_path / ".specweaver" / "templates" / "component_spec.md"
        assert tmpl.is_file()
        content = tmpl.read_text()
        assert "Purpose" in content
        assert "Contract" in content
        assert "Protocol" in content

    def test_creates_root_context_yaml(self, tmp_path: Path) -> None:
        """scaffold_project creates a root context.yaml boundary manifest."""
        scaffold_project(tmp_path)
        context_path = tmp_path / "context.yaml"
        assert context_path.is_file()
        yaml = YAML()
        data = yaml.load(context_path)
        assert data["level"] == "system"
        assert data["archetype"] == "orchestrator"

    def test_context_yaml_uses_directory_name(self, tmp_path: Path) -> None:
        """context.yaml name field is derived from the project directory name."""
        scaffold_project(tmp_path)
        yaml = YAML()
        data = yaml.load(tmp_path / "context.yaml")
        expected_name = tmp_path.name.lower().replace(" ", "-")
        assert data["name"] == expected_name

    def test_returns_created_paths(self, tmp_path: Path) -> None:
        """scaffold_project returns a summary of what was created."""
        result = scaffold_project(tmp_path)
        assert result.project_path == tmp_path
        assert result.specweaver_dir == tmp_path / ".specweaver"
        assert result.specs_dir == tmp_path / "specs"
        assert result.context_file == tmp_path / "context.yaml"

    def test_creates_specweaverignore_with_polyglot_defaults(self, tmp_path: Path) -> None:
        """scaffold_project gathers all polyglot exclusions globally and seeds .specweaverignore."""
        result = scaffold_project(tmp_path)
        ignore_path = tmp_path / ".specweaverignore"
        assert ignore_path.is_file()
        assert ".specweaverignore" in result.created

        content = ignore_path.read_text(encoding="utf-8")
        # Assert specific default outputs from Python/TypeScript/Java parsers
        assert "__pycache__/" in content
        assert "node_modules/" in content
        assert "target/" in content


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------


class TestScaffoldIdempotency:
    """Scaffold must be safe to run multiple times."""

    def test_running_twice_does_not_error(self, tmp_path: Path) -> None:
        """Running scaffold_project twice on the same dir should not raise."""
        scaffold_project(tmp_path)
        scaffold_project(tmp_path)  # should not raise

    def test_does_not_overwrite_existing_context(self, tmp_path: Path) -> None:
        """If context.yaml already exists with custom content, don't overwrite."""
        context_path = tmp_path / "context.yaml"
        context_path.write_text("# custom context\nname: my-app\nlevel: system\n")

        scaffold_project(tmp_path)

        content = context_path.read_text()
        assert "my-app" in content  # preserved, not overwritten

    def test_does_not_overwrite_existing_context_yaml(self, tmp_path: Path) -> None:
        """If context.yaml already exists, don't overwrite it."""
        context_path = tmp_path / "context.yaml"
        context_path.write_text("name: my-custom-project\nlevel: system\n")

        scaffold_project(tmp_path)

        content = context_path.read_text()
        assert "my-custom-project" in content  # preserved, not overwritten

    def test_does_not_overwrite_existing_template(self, tmp_path: Path) -> None:
        """If templates/component_spec.md exists with custom content, don't overwrite."""
        tmpl_dir = tmp_path / ".specweaver" / "templates"
        tmpl_dir.mkdir(parents=True)
        tmpl = tmpl_dir / "component_spec.md"
        tmpl.write_text("# My custom template\n")

        scaffold_project(tmp_path)

        assert tmpl.read_text() == "# My custom template\n"

    def test_does_not_overwrite_existing_specweaverignore_patterns(self, tmp_path: Path) -> None:
        """Existing .specweaverignore files should gracefully append missing defaults without erasing user rules."""
        ignore_path = tmp_path / ".specweaverignore"
        ignore_path.write_text("my_custom_binary.bin\n", encoding="utf-8")

        result = scaffold_project(tmp_path)
        content = ignore_path.read_text(encoding="utf-8")

        assert "my_custom_binary.bin" in content
        assert "node_modules/" in content  # Missing polyglot defaults appended
        # We did not strictly 'create' it, but we appended. Check result lists.
        # It's an interesting semantic whether it counts as "created" if modified.
        # For our architecture, since the file physically existed, it is NOT in created array.
        assert ".specweaverignore" not in result.created

    def test_partial_existing_structure(self, tmp_path: Path) -> None:
        """Scaffold fills in missing parts of partially existing structure."""
        # Only .specweaver/ exists, but no specs/ or templates
        (tmp_path / ".specweaver").mkdir()
        scaffold_project(tmp_path)

        assert (tmp_path / "specs").is_dir()
        assert (tmp_path / ".specweaver" / "templates" / "component_spec.md").is_file()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestScaffoldEdgeCases:
    """Edge cases for scaffold."""

    def test_existing_specs_files_preserved(self, tmp_path: Path) -> None:
        """If specs/ already contains files, they are not deleted."""
        specs = tmp_path / "specs"
        specs.mkdir()
        existing = specs / "existing_spec.md"
        existing.write_text("# Existing spec\n")

        scaffold_project(tmp_path)

        assert existing.exists()
        assert existing.read_text() == "# Existing spec\n"

    def test_template_has_sections(self, tmp_path: Path) -> None:
        """Default template should have standard spec sections."""
        scaffold_project(tmp_path)
        content = (tmp_path / ".specweaver" / "templates" / "component_spec.md").read_text()
        assert "Purpose" in content
        assert "Contract" in content

    def test_nonexistent_project_path_raises(self) -> None:
        """Trying to scaffold a nonexistent directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            scaffold_project(Path("/nonexistent/scaffold/path"))


# ---------------------------------------------------------------------------
# Scaffold — behavioral tests (unexpected input, idempotency)
# ---------------------------------------------------------------------------


class TestScaffoldBehavioral:
    """Behavioral tests: unexpected input, idempotency."""

    def test_path_is_file_not_directory(self, tmp_path: Path) -> None:
        """Unexpected input: path points to a file → error."""
        file_path = tmp_path / "somefile.txt"
        file_path.write_text("content", encoding="utf-8")

        with pytest.raises((FileNotFoundError, NotADirectoryError, OSError)):
            scaffold_project(file_path)

    def test_second_run_returns_empty_created(self, tmp_path: Path) -> None:
        """Idempotency: second run creates nothing new."""
        first = scaffold_project(tmp_path)
        assert len(first.created) > 0

        second = scaffold_project(tmp_path)
        assert len(second.created) == 0

    def test_marker_dir_has_no_config(self, tmp_path: Path) -> None:
        """Security: .specweaver/ should NOT contain any config (config in DB)."""
        scaffold_project(tmp_path)
        sw_dir = tmp_path / ".specweaver"
        # Only templates dir should exist inside .specweaver/
        children = [p.name for p in sw_dir.iterdir()]
        assert "config.yaml" not in children


# ---------------------------------------------------------------------------
# Scaffold — constitution integration
# ---------------------------------------------------------------------------


class TestScaffoldConstitution:
    """Scaffold creates CONSTITUTION.md starter template."""

    def test_creates_constitution(self, tmp_path: Path) -> None:
        """scaffold_project creates CONSTITUTION.md at project root."""
        scaffold_project(tmp_path)
        assert (tmp_path / "CONSTITUTION.md").is_file()

    def test_constitution_in_result(self, tmp_path: Path) -> None:
        """ScaffoldResult includes constitution_file."""
        result = scaffold_project(tmp_path)
        assert result.constitution_file == tmp_path / "CONSTITUTION.md"

    def test_constitution_in_created_list(self, tmp_path: Path) -> None:
        """CONSTITUTION.md is in the created list on first run."""
        result = scaffold_project(tmp_path)
        assert "CONSTITUTION.md" in result.created

    def test_does_not_overwrite_existing_constitution(self, tmp_path: Path) -> None:
        """Existing CONSTITUTION.md is NOT overwritten."""
        constitution = tmp_path / "CONSTITUTION.md"
        constitution.write_text("# My custom constitution\n", encoding="utf-8")

        result = scaffold_project(tmp_path)

        assert constitution.read_text() == "# My custom constitution\n"
        assert "CONSTITUTION.md" not in result.created
