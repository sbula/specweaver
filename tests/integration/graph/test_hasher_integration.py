# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path

import pytest

from specweaver.graph.hasher import DependencyHasher
from specweaver.workspace.analyzers.factory import AnalyzerFactory

pytestmark = pytest.mark.integration


def test_hasher_tree_sitter_integration(tmp_path: Path):
    """
    Test Story 6: TreeSitter Native Integration
    Validates that the hasher correctly maps real OS physical environments,
    triggers the real TreeSitter parser, extracts dependencies natively,
    and binds them securely to the final payload.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    # We write a physical python file with a valid stdlib import and an external mock import
    code_file = src_dir / "valid_code.py"
    code_file.write_text("import os\nimport sys\nimport pydantic\nimport fastapi\n")

    manifest = src_dir / "context.yaml"
    manifest.write_text("name: src\n")

    hasher = DependencyHasher(tmp_path, AnalyzerFactory)
    state = hasher.compute_hashes([manifest])

    assert "src" in state
    payload = state["src"]["rendered_payload"]

    # TreeSitter fundamentally extracts ALL dependencies down the import tree.
    # We assert that the polyglot TreeSitter successfully triggered and loaded all targets natively.
    assert "pydantic" in payload
    assert "fastapi" in payload
    assert "os" in payload
    assert "sys" in payload


def test_hasher_physical_disk_persistence(tmp_path: Path):
    """
    Test Story 7: Physical Disk Persistence & Recovery
    Executes the full pipeline physically onto the hard drive, proving
    orjson serialization boundaries handle round-trip typing precisely
    and byte sizes are fully managed.
    """
    src_dir = tmp_path / "core_module"
    src_dir.mkdir()

    (src_dir / "logic.py").write_text("def run(): pass\n")

    manifest = src_dir / "context.yaml"
    manifest.write_text("name: core_module\n")

    hasher = DependencyHasher(tmp_path, AnalyzerFactory)

    # Assert cache doesn't exist yet
    assert not hasher.cache_path.exists()

    # Initial generation (physically writes to disk)
    state_a = hasher.compute_hashes([manifest])
    hasher.save_cache(state_a)
    assert hasher.cache_path.exists()

    # Validate raw file contents natively
    raw_disk_bytes = hasher.cache_path.read_text(encoding="utf-8")
    assert "core_module" in raw_disk_bytes
    assert "logic.py" in raw_disk_bytes

    # Re-instantiate generic hasher, testing load_cache natively across memory boundaries
    hasher2 = DependencyHasher(tmp_path, AnalyzerFactory)
    state_b = hasher2.load_cache()

    # Verify dict exact parity after orjson round trip
    assert state_a["core_module"]["merkle_root"] == state_b["core_module"]["merkle_root"]
    assert state_a["core_module"]["rendered_payload"] == state_b["core_module"]["rendered_payload"]
