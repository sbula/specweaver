# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from typing import TYPE_CHECKING

from specweaver.workspace.parsers.exclusions import SpecWeaverIgnoreParser

if TYPE_CHECKING:
    import pathspec

from pathlib import Path

import pytest


class MockIgnoreIOHandler:
    def __init__(self, content: str = "", exists: bool = True, is_file: bool = True) -> None:
        self._content = content
        self._exists = exists
        self._is_file = is_file
        self.appended_lines: list[str] = []

    def exists(self) -> bool:
        return self._exists

    def is_file(self) -> bool:
        return self._is_file

    def read_text(self) -> str:
        return self._content

    def append_lines(self, lines: list[str]) -> None:
        if not self._exists:
            self._exists = True
            self._is_file = True
        self.appended_lines.extend(lines)
        self._content += "".join(f"{line}\n" for line in lines)


def test_ignore_parser_scaffolds_defaults() -> None:
    io_handler = MockIgnoreIOHandler(exists=False)
    parser = SpecWeaverIgnoreParser(io_handler)

    # Run scaffolding
    parser.ensure_scaffolded(["node_modules/", "target/"])

    assert io_handler.exists()
    assert "node_modules/" in io_handler.read_text()
    assert "target/" in io_handler.read_text()
    assert io_handler.appended_lines == ["node_modules/", "target/"]


def test_ignore_parser_preserves_existing_content_on_scaffold() -> None:
    io_handler = MockIgnoreIOHandler(content="my_custom_dir/\n")
    parser = SpecWeaverIgnoreParser(io_handler)

    parser.ensure_scaffolded(["node_modules/"])

    assert "my_custom_dir/" in io_handler.read_text()
    assert "node_modules/" in io_handler.read_text()


def test_ignore_parser_compiles_spec() -> None:
    io_handler = MockIgnoreIOHandler(content="*.log\ntmp/\n")
    parser = SpecWeaverIgnoreParser(io_handler)

    # Add runtime exclusions (like binary patterns)
    spec: pathspec.PathSpec = parser.get_compiled_spec(["*.pyc"])

    assert spec.match_file("error.log") is True
    assert spec.match_file("tmp/cache.txt") is True
    assert spec.match_file("main.pyc") is True
    assert spec.match_file("main.py") is False


def test_ignore_parser_compiles_spec_if_file_missing() -> None:
    io_handler = MockIgnoreIOHandler(exists=False)
    parser = SpecWeaverIgnoreParser(io_handler)
    spec = parser.get_compiled_spec(["*.pyc"])

    assert spec.match_file("main.pyc") is True
    assert spec.match_file("main.py") is False


def test_ensure_scaffolded_handles_whitespace_gracefully() -> None:
    io_handler = MockIgnoreIOHandler(content="node_modules/ \n")
    parser = SpecWeaverIgnoreParser(io_handler)

    # This should not duplicate node_modules/ because the engine strips whitespace
    parser.ensure_scaffolded(["node_modules/"])

    lines = io_handler.read_text().splitlines()
    assert lines.count("node_modules/ ") == 1
    assert "node_modules/" not in io_handler.appended_lines


def test_ensure_scaffolded_safely_handles_0_byte_file() -> None:
    io_handler = MockIgnoreIOHandler(content="")
    parser = SpecWeaverIgnoreParser(io_handler)

    parser.ensure_scaffolded(["target/"])
    assert "target/" in io_handler.read_text()


def test_get_compiled_spec_prioritizes_user_overrides_fr3() -> None:
    io_handler = MockIgnoreIOHandler(content="!vital.pyc\n")
    parser = SpecWeaverIgnoreParser(io_handler)

    spec: pathspec.PathSpec = parser.get_compiled_spec(["*.pyc"])

    assert spec.match_file("cache.pyc") is True
    # The negative override !vital.pyc MUST prevail because it's processed after
    assert spec.match_file("vital.pyc") is False


def test_get_compiled_spec_handles_nested_wildcards_fr3() -> None:
    io_handler = MockIgnoreIOHandler(content="**/dist/\n")
    parser = SpecWeaverIgnoreParser(io_handler)
    spec: pathspec.PathSpec = parser.get_compiled_spec([])

    assert spec.match_file("frontend/dist/bundle.js") is True
    assert spec.match_file("dist/index.html") is True


def test_parser_fallback_if_specweaverignore_is_directory_security() -> None:
    io_handler = MockIgnoreIOHandler(is_file=False)
    parser = SpecWeaverIgnoreParser(io_handler)

    # Should not crash, should just log and return
    parser.ensure_scaffolded(["node_modules/"])

    spec: pathspec.PathSpec = parser.get_compiled_spec(["*.pyc"])
    assert spec.match_file("main.pyc") is True


def test_get_compiled_spec_handles_empty_runtime_patterns() -> None:
    io_handler = MockIgnoreIOHandler(exists=False)
    parser = SpecWeaverIgnoreParser(io_handler)
    spec: pathspec.PathSpec = parser.get_compiled_spec([])
    assert spec.match_file("anything.pyc") is False


@pytest.fixture
def tmp_path_fixture(tmp_path: Path):
    return tmp_path


def test_integration_orchestrator_initializes_ignores_sf4(tmp_path: Path) -> None:
    from specweaver.workspace.analyzers.factory import AnalyzerFactory
    from specweaver.workspace.project.scaffold import NativeIgnoreIOHandler

    io_handler = NativeIgnoreIOHandler(tmp_path / ".specweaverignore")
    parser = SpecWeaverIgnoreParser(io_handler)

    default_dirs = set()
    for a in AnalyzerFactory.get_all_analyzers():
        default_dirs.update(a.get_default_directory_ignores())

    parser.ensure_scaffolded(list(default_dirs))

    assert (tmp_path / ".specweaverignore").exists()
    content = (tmp_path / ".specweaverignore").read_text()
    assert ".venv/" in content
    assert "node_modules/" in content


def test_e2e_topological_spec_bypass_hidden_binary_sf4(tmp_path: Path) -> None:
    from specweaver.workspace.analyzers.factory import AnalyzerFactory
    from specweaver.workspace.project.scaffold import NativeIgnoreIOHandler

    io_handler = NativeIgnoreIOHandler(tmp_path / ".specweaverignore")
    parser = SpecWeaverIgnoreParser(io_handler)

    bin_patterns = set()
    for a in AnalyzerFactory.get_all_analyzers():
        bin_patterns.update(a.get_binary_ignore_patterns())

    compiled_spec = parser.get_compiled_spec(list(bin_patterns))

    assert compiled_spec.match_file("src/main.class") is True
    assert compiled_spec.match_file("target/release/lib.so") is True
    assert compiled_spec.match_file("src/api/handler.pyc") is True
    assert compiled_spec.match_file("src/main.py") is False
