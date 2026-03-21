# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for pipeline parser — YAML loading and template resolution."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from unittest.mock import patch
import pytest

from specweaver.flow.models import (
    GateCondition,
    OnFailAction,
    StepAction,
    StepTarget,
)
from specweaver.flow.parser import list_bundled_pipelines, load_pipeline

# ---------------------------------------------------------------------------
# load_pipeline — from file path
# ---------------------------------------------------------------------------


class TestLoadPipeline:
    """Tests for loading pipelines from YAML files."""

    def test_load_minimal_yaml(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "simple.yaml"
        yaml_file.write_text(
            dedent("""\
            name: simple
            steps:
              - name: check_spec
                action: validate
                target: spec
        """)
        )
        p = load_pipeline(yaml_file)
        assert p.name == "simple"
        assert len(p.steps) == 1
        assert p.steps[0].action == StepAction.VALIDATE
        assert p.steps[0].target == StepTarget.SPEC

    def test_load_with_gates(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "gated.yaml"
        yaml_file.write_text(
            dedent("""\
            name: gated
            description: "Pipeline with gates"
            version: "2.0"
            steps:
              - name: check_spec
                action: validate
                target: spec
                gate:
                  type: auto
                  condition: all_passed
                  on_fail: abort
              - name: review_spec
                action: review
                target: spec
                gate:
                  type: auto
                  condition: accepted
                  on_fail: loop_back
                  loop_target: check_spec
                  max_retries: 5
        """)
        )
        p = load_pipeline(yaml_file)
        assert p.name == "gated"
        assert p.description == "Pipeline with gates"
        assert p.version == "2.0"
        assert len(p.steps) == 2

        gate = p.steps[1].gate
        assert gate is not None
        assert gate.condition == GateCondition.ACCEPTED
        assert gate.on_fail == OnFailAction.LOOP_BACK
        assert gate.loop_target == "check_spec"
        assert gate.max_retries == 5

    def test_load_with_params(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "params.yaml"
        yaml_file.write_text(
            dedent("""\
            name: params_test
            steps:
              - name: strict_check
                action: validate
                target: spec
                params:
                  strict: true
                  include_llm: false
        """)
        )
        p = load_pipeline(yaml_file)
        assert p.steps[0].params["strict"] is True
        assert p.steps[0].params["include_llm"] is False

    def test_load_nonexistent_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_pipeline(Path("/nonexistent/pipeline.yaml"))

    def test_load_invalid_yaml(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("name: bad\nsteps: not_a_list\n")
        with pytest.raises(ValueError):
            load_pipeline(yaml_file)

    def test_load_missing_required_field(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "no_name.yaml"
        yaml_file.write_text(
            dedent("""\
            steps:
              - name: s1
                action: validate
                target: spec
        """)
        )
        with pytest.raises(ValueError):
            load_pipeline(yaml_file)

    def test_load_invalid_action(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "bad_action.yaml"
        yaml_file.write_text(
            dedent("""\
            name: bad
            steps:
              - name: s1
                action: explode
                target: spec
        """)
        )
        with pytest.raises(ValueError):
            load_pipeline(yaml_file)

    def test_load_invalid_target(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "bad_target.yaml"
        yaml_file.write_text(
            dedent("""\
            name: bad
            steps:
              - name: s1
                action: validate
                target: database
        """)
        )
        with pytest.raises(ValueError):
            load_pipeline(yaml_file)


# ---------------------------------------------------------------------------
# Bundled templates
# ---------------------------------------------------------------------------


class TestBundledTemplates:
    """Tests for bundled pipeline templates."""

    def test_list_bundled_pipelines(self) -> None:
        names = list_bundled_pipelines()
        assert "new_feature" in names
        assert "validate_only" in names

    def test_load_new_feature_template(self) -> None:
        p = load_pipeline(Path("new_feature"))
        assert p.name == "new_feature"
        assert (
            len(p.steps) >= 6
        )  # at least: draft, validate, review, gen code, gen tests, validate code

        # Check step actions cover the core loop
        actions = [(s.action, s.target) for s in p.steps]
        assert (StepAction.DRAFT, StepTarget.SPEC) in actions
        assert (StepAction.VALIDATE, StepTarget.SPEC) in actions
        assert (StepAction.REVIEW, StepTarget.SPEC) in actions
        assert (StepAction.GENERATE, StepTarget.CODE) in actions
        assert (StepAction.GENERATE, StepTarget.TESTS) in actions
        assert (StepAction.VALIDATE, StepTarget.CODE) in actions

    def test_load_validate_only_template(self) -> None:
        p = load_pipeline(Path("validate_only"))
        assert p.name == "validate_only"
        assert len(p.steps) == 1
        assert p.steps[0].action == StepAction.VALIDATE
        assert p.steps[0].target == StepTarget.SPEC

    def test_new_feature_has_gates(self) -> None:
        p = load_pipeline(Path("new_feature"))
        gated_steps = [s for s in p.steps if s.gate is not None]
        assert len(gated_steps) >= 2  # at least review steps should have gates

    def test_new_feature_validates_cleanly(self) -> None:
        p = load_pipeline(Path("new_feature"))
        errors = p.validate_flow()
        assert errors == []

    def test_validate_only_validates_cleanly(self) -> None:
        p = load_pipeline(Path("validate_only"))
        errors = p.validate_flow()
        assert errors == []

    def test_load_pipeline_importlib_handling(self) -> None:
        """Test that FileNotFoundError is successfully trapped and re-raised upon importlib throwing TypeError."""
        with pytest.raises(FileNotFoundError, match="Pipeline not found"):
            import importlib
            with patch.object(importlib.resources, "as_file", side_effect=TypeError("mock type error")):
                load_pipeline(Path("nonexistent_pipeline_name"))


# ---------------------------------------------------------------------------
# Parser edge cases
# ---------------------------------------------------------------------------


class TestParserEdgeCases:
    """Edge case tests for the YAML parser."""

    def test_load_empty_yaml_file(self, tmp_path: Path) -> None:
        """Empty YAML file should raise ValueError (not a dict)."""
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        with pytest.raises(ValueError, match="mapping"):
            load_pipeline(yaml_file)

    def test_load_yaml_with_only_comments(self, tmp_path: Path) -> None:
        """YAML file with only comments → null → ValueError."""
        yaml_file = tmp_path / "comments.yaml"
        yaml_file.write_text("# just a comment\n# nothing here\n")
        with pytest.raises(ValueError, match="mapping"):
            load_pipeline(yaml_file)

    def test_load_yaml_list_not_mapping(self, tmp_path: Path) -> None:
        """YAML file containing a list (not a mapping) → ValueError."""
        yaml_file = tmp_path / "list.yaml"
        yaml_file.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="mapping"):
            load_pipeline(yaml_file)

    def test_load_by_name_without_suffix(self, tmp_path: Path) -> None:
        """Loading by name (no .yaml) where <name>.yaml exists on disk."""
        yaml_file = tmp_path / "custom.yaml"
        yaml_file.write_text(
            dedent("""\
            name: custom
            steps:
              - name: s1
                action: validate
                target: spec
        """)
        )
        p = load_pipeline(tmp_path / "custom")
        assert p.name == "custom"

    def test_load_with_extra_fields_ignored(self, tmp_path: Path) -> None:
        """Extra fields in YAML should not cause errors (forward compat)."""
        yaml_file = tmp_path / "extra.yaml"
        yaml_file.write_text(
            dedent("""\
            name: extra
            future_field: some_value
            steps:
              - name: s1
                action: validate
                target: spec
                unknown_field: ignored
        """)
        )
        # Pydantic by default ignores extra fields — verify this works
        p = load_pipeline(yaml_file)
        assert p.name == "extra"

    def test_load_step_missing_action(self, tmp_path: Path) -> None:
        """Step without an action field → ValueError."""
        yaml_file = tmp_path / "no_action.yaml"
        yaml_file.write_text(
            dedent("""\
            name: bad
            steps:
              - name: s1
                target: spec
        """)
        )
        with pytest.raises(ValueError):
            load_pipeline(yaml_file)
