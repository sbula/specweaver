# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for specweaver.project.scaffold — TDD (tests first)."""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specweaver.project.scaffold import scaffold_project

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

    def test_creates_default_config_yaml(self, tmp_path: Path) -> None:
        """scaffold_project creates .specweaver/config.yaml with defaults."""
        scaffold_project(tmp_path)
        config_path = tmp_path / ".specweaver" / "config.yaml"
        assert config_path.is_file()
        yaml = YAML()
        data = yaml.load(config_path)
        assert "llm" in data
        assert data["llm"]["model"] is not None

    def test_creates_templates_dir_with_component_spec(self, tmp_path: Path) -> None:
        """scaffold_project creates .specweaver/templates/ with component_spec.md."""
        scaffold_project(tmp_path)
        tmpl = tmp_path / ".specweaver" / "templates" / "component_spec.md"
        assert tmpl.is_file()
        content = tmpl.read_text()
        assert "Purpose" in content
        assert "Contract" in content
        assert "Protocol" in content

    def test_returns_created_paths(self, tmp_path: Path) -> None:
        """scaffold_project returns a summary of what was created."""
        result = scaffold_project(tmp_path)
        assert result.project_path == tmp_path
        assert result.specweaver_dir == tmp_path / ".specweaver"
        assert result.specs_dir == tmp_path / "specs"
        assert result.config_file == tmp_path / ".specweaver" / "config.yaml"


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------


class TestScaffoldIdempotency:
    """Scaffold must be safe to run multiple times."""

    def test_running_twice_does_not_error(self, tmp_path: Path) -> None:
        """Running scaffold_project twice on the same dir should not raise."""
        scaffold_project(tmp_path)
        scaffold_project(tmp_path)  # should not raise

    def test_does_not_overwrite_existing_config(self, tmp_path: Path) -> None:
        """If .specweaver/config.yaml already exists with custom content, don't overwrite."""
        sw_dir = tmp_path / ".specweaver"
        sw_dir.mkdir()
        config_path = sw_dir / "config.yaml"
        config_path.write_text("# custom config\nllm:\n  model: my-custom-model\n")

        scaffold_project(tmp_path)

        content = config_path.read_text()
        assert "my-custom-model" in content  # preserved, not overwritten

    def test_does_not_overwrite_existing_template(self, tmp_path: Path) -> None:
        """If templates/component_spec.md exists with custom content, don't overwrite."""
        tmpl_dir = tmp_path / ".specweaver" / "templates"
        tmpl_dir.mkdir(parents=True)
        tmpl = tmpl_dir / "component_spec.md"
        tmpl.write_text("# My custom template\n")

        scaffold_project(tmp_path)

        assert tmpl.read_text() == "# My custom template\n"

    def test_partial_existing_structure(self, tmp_path: Path) -> None:
        """Scaffold fills in missing parts of partially existing structure."""
        # Only .specweaver/ exists, but no specs/ or config.yaml
        (tmp_path / ".specweaver").mkdir()
        scaffold_project(tmp_path)

        assert (tmp_path / "specs").is_dir()
        assert (tmp_path / ".specweaver" / "config.yaml").is_file()


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

    def test_config_yaml_has_comments(self, tmp_path: Path) -> None:
        """Default config.yaml should have explanatory comments."""
        scaffold_project(tmp_path)
        content = (tmp_path / ".specweaver" / "config.yaml").read_text()
        assert "#" in content  # has at least one comment

    def test_nonexistent_project_path_raises(self) -> None:
        """Trying to scaffold a nonexistent directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            scaffold_project(Path("/nonexistent/scaffold/path"))
