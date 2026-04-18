# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for the validation schema injection logic."""

from unittest.mock import MagicMock, patch

from specweaver.workflows.evaluators.loader import load_evaluator_schemas


def test_load_evaluator_schemas_empty() -> None:
    """Test loading schemas when the directory is completely empty or missing."""
    with patch("importlib.resources.files") as mock_files:
        mock_files.side_effect = FileNotFoundError()
        schemas = load_evaluator_schemas()
        assert schemas == {}


def test_load_evaluator_schemas_success() -> None:
    """Test that valid YAMLs are parsed and merged by framework."""
    mock_frameworks_dir = MagicMock()

    mock_yaml_file = MagicMock()
    mock_yaml_file.is_file.return_value = True
    mock_yaml_file.name = "spring-boot.yaml"
    mock_yaml_file.read_text.return_value = '''
modifiers:
  public: "This is public"
decorators:
  RestController: "Marks REST"
'''

    # Another framework to ensure loop works
    mock_py_file = MagicMock()
    mock_py_file.is_file.return_value = True
    mock_py_file.name = "fastapi.yaml"
    mock_py_file.read_text.return_value = '''
decorators:
  app.get: "GET route"
'''

    mock_frameworks_dir.iterdir.return_value = [mock_yaml_file, mock_py_file]

    with patch("importlib.resources.files", return_value=mock_frameworks_dir):
        schemas = load_evaluator_schemas()

        assert "spring-boot" in schemas
        assert "fastapi" in schemas

        sb_schema = schemas["spring-boot"]
        assert sb_schema["decorators"]["RestController"] == "Marks REST"
        assert sb_schema["modifiers"]["public"] == "This is public"

        py_schema = schemas["fastapi"]
        assert py_schema["decorators"]["app.get"] == "GET route"


def test_load_evaluator_schemas_project_override() -> None:
    """Test that a user-supplied project configuration deep-merges over the packaged default."""
    mock_frameworks_dir = MagicMock()

    mock_yaml_file = MagicMock()
    mock_yaml_file.is_file.return_value = True
    mock_yaml_file.name = "spring-boot.yaml"
    mock_yaml_file.read_text.return_value = '''
modifiers:
  public: "This is public"
decorators:
  RestController: "System Default"
'''
    mock_frameworks_dir.iterdir.return_value = [mock_yaml_file]

    # Mock project directory
    mock_project_dir = MagicMock()
    mock_local_dir = MagicMock()
    mock_project_dir.__truediv__.return_value.__truediv__.return_value = mock_local_dir
    mock_local_dir.is_dir.return_value = True

    mock_override_file = MagicMock()
    mock_override_file.stem = "spring-boot"
    mock_override_file.read_text.return_value = '''
decorators:
  RestController: "User Override"
  UserCustom: "Local Only"
'''
    mock_local_dir.glob.return_value = [mock_override_file]

    with patch("importlib.resources.files", return_value=mock_frameworks_dir):
        schemas = load_evaluator_schemas(project_dir=mock_project_dir)

        assert "spring-boot" in schemas
        sb_schema = schemas["spring-boot"]

        # Original unmodified key should persist
        assert sb_schema["modifiers"]["public"] == "This is public"

        # User override should win
        assert sb_schema["decorators"]["RestController"] == "User Override"

        # New user key should be appended
        assert sb_schema["decorators"]["UserCustom"] == "Local Only"


def test_load_evaluator_schemas_malformed_skips_gracefully() -> None:
    """Test that malformed YAML files (e.g. invalid syntax) do not crash the loader."""
    mock_frameworks_dir = MagicMock()
    mock_frameworks_dir.iterdir.return_value = []

    # Mock project directory with a corrupt file
    mock_project_dir = MagicMock()
    mock_local_dir = MagicMock()
    mock_project_dir.__truediv__.return_value.__truediv__.return_value = mock_local_dir
    mock_local_dir.is_dir.return_value = True

    mock_corrupt_file = MagicMock()
    mock_corrupt_file.stem = "spring-boot"
    mock_corrupt_file.name = "spring-boot.yaml"
    mock_corrupt_file.read_text.return_value = '''
modifiers:
  public: "This is public"
decorators:
  - list instead of dict
  : invalid syntax ] } [
'''
    mock_local_dir.glob.return_value = [mock_corrupt_file]

    with patch("importlib.resources.files", return_value=mock_frameworks_dir):
        schemas = load_evaluator_schemas(project_dir=mock_project_dir)
        # Should gracefully return empty schemas because it fails to parse
        assert schemas == {}


def test_load_evaluator_schemas_skips_invalid_files() -> None:
    """Test that non-yaml files or __pycache__ are skipped safely."""
    mock_frameworks_dir = MagicMock()

    # __pycache__ dir
    mock_pycache = MagicMock()
    mock_pycache.is_file.return_value = False
    mock_pycache.name = "__pycache__"

    mock_txt_file = MagicMock()
    mock_txt_file.is_file.return_value = True
    mock_txt_file.name = "readme.txt"
    mock_txt_file.read_text.return_value = "hello"

    mock_frameworks_dir.iterdir.return_value = [mock_pycache, mock_txt_file]

    with patch("importlib.resources.files", return_value=mock_frameworks_dir):
        schemas = load_evaluator_schemas()
        assert schemas == {}  # pycache and txt skipped
