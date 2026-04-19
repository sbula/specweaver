# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path
from typing import TYPE_CHECKING

from specweaver.workspace.parsers.exclusions import SpecWeaverIgnoreParser

if TYPE_CHECKING:
    import pathspec

import pytest


def test_ignore_parser_scaffolds_defaults(tmp_path: Path):
    parser = SpecWeaverIgnoreParser(tmp_path)
    ignore_file = tmp_path / ".specweaverignore"

    # Run scaffolding
    parser.ensure_scaffolded(["node_modules/", "target/"])

    assert ignore_file.exists()
    content = ignore_file.read_text(encoding="utf-8")
    assert "node_modules/" in content
    assert "target/" in content

def test_ignore_parser_preserves_existing_content_on_scaffold(tmp_path: Path):
    ignore_file = tmp_path / ".specweaverignore"
    ignore_file.write_text("my_custom_dir/\n", encoding="utf-8")

    parser = SpecWeaverIgnoreParser(tmp_path)
    parser.ensure_scaffolded(["node_modules/"])

    content = ignore_file.read_text(encoding="utf-8")
    assert "my_custom_dir/" in content
    assert "node_modules/" in content

def test_ignore_parser_compiles_spec(tmp_path: Path):
    ignore_file = tmp_path / ".specweaverignore"
    ignore_file.write_text("*.log\ntmp/\n", encoding="utf-8")

    parser = SpecWeaverIgnoreParser(tmp_path)
    # Add runtime exclusions (like binary patterns)
    spec: pathspec.PathSpec = parser.get_compiled_spec(["*.pyc"])

    assert spec.match_file("error.log") is True
    assert spec.match_file("tmp/cache.txt") is True
    assert spec.match_file("main.pyc") is True
    assert spec.match_file("main.py") is False

def test_ignore_parser_compiles_spec_if_file_missing(tmp_path: Path):
    parser = SpecWeaverIgnoreParser(tmp_path)
    spec = parser.get_compiled_spec(["*.pyc"])

    assert spec.match_file("main.pyc") is True
    assert spec.match_file("main.py") is False

def test_ensure_scaffolded_handles_whitespace_gracefully(tmp_path: Path):
    ignore_file = tmp_path / ".specweaverignore"
    ignore_file.write_text("node_modules/ \n", encoding="utf-8")

    parser = SpecWeaverIgnoreParser(tmp_path)
    # This should not duplicate node_modules/ because the engine strips whitespace
    parser.ensure_scaffolded(["node_modules/"])

    lines = ignore_file.read_text(encoding="utf-8").splitlines()
    assert lines.count("node_modules/ ") == 1
    assert "node_modules/" not in lines

def test_ensure_scaffolded_safely_handles_0_byte_file(tmp_path: Path):
    ignore_file = tmp_path / ".specweaverignore"
    ignore_file.write_text("", encoding="utf-8")

    parser = SpecWeaverIgnoreParser(tmp_path)
    parser.ensure_scaffolded(["target/"])
    content = ignore_file.read_text(encoding="utf-8")
    assert "target/" in content

def test_get_compiled_spec_prioritizes_user_overrides_fr3(tmp_path: Path):
    ignore_file = tmp_path / ".specweaverignore"
    # User negative override
    ignore_file.write_text("!vital.pyc\n", encoding="utf-8")

    parser = SpecWeaverIgnoreParser(tmp_path)
    spec: pathspec.PathSpec = parser.get_compiled_spec(["*.pyc"])

    assert spec.match_file("cache.pyc") is True
    # The negative override !vital.pyc MUST prevail because it's processed after
    assert spec.match_file("vital.pyc") is False

def test_get_compiled_spec_handles_nested_wildcards_fr3(tmp_path: Path):
    ignore_file = tmp_path / ".specweaverignore"
    # Double asterisks are standard gitignore
    ignore_file.write_text("**/dist/\n", encoding="utf-8")

    parser = SpecWeaverIgnoreParser(tmp_path)
    spec: pathspec.PathSpec = parser.get_compiled_spec([])

    assert spec.match_file("frontend/dist/bundle.js") is True
    assert spec.match_file("dist/index.html") is True

def test_parser_fallback_if_specweaverignore_is_directory_security(tmp_path: Path):
    # Setup directory instead of file
    ignore_dir = tmp_path / ".specweaverignore"
    ignore_dir.mkdir()

    parser = SpecWeaverIgnoreParser(tmp_path)

    # Should not crash, should just log and return
    parser.ensure_scaffolded(["node_modules/"])

    spec: pathspec.PathSpec = parser.get_compiled_spec(["*.pyc"])
    assert spec.match_file("main.pyc") is True

def test_get_compiled_spec_handles_empty_runtime_patterns(tmp_path: Path):
    parser = SpecWeaverIgnoreParser(tmp_path)
    spec: pathspec.PathSpec = parser.get_compiled_spec([])
    assert spec.match_file("anything.pyc") is False


@pytest.mark.skip(reason="Deferred to SF-4")
def test_deferred_integration_orchestrator_initializes_ignores_sf4():
    pass

@pytest.mark.skip(reason="Deferred to SF-4")
def test_deferred_e2e_topological_spec_bypass_hidden_binary_sf4():
    pass
