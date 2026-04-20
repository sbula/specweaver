# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path

from specweaver.assurance.graph.hasher import _ensure_gitignore
from specweaver.workspace.analyzers.factory import AnalyzerFactory


def test_ensure_gitignore_creates_file_if_not_exists(tmp_path: Path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    # We pass the project root to `_ensure_gitignore`
    # It should look for .git and append /.specweaver/ to the .gitignore next to it.
    _ensure_gitignore(tmp_path)

    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    assert "/.specweaver/\n" in gitignore.read_text(encoding="utf-8")


def test_ensure_gitignore_appends_only_if_not_present(tmp_path: Path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("node_modules/\n", encoding="utf-8")

    _ensure_gitignore(tmp_path)

    content = gitignore.read_text(encoding="utf-8")
    assert "node_modules/\n" in content
    assert "/.specweaver/\n" in content

    # Calling it again shouldn't duplicate
    _ensure_gitignore(tmp_path)
    lines = gitignore.read_text(encoding="utf-8").splitlines()
    specweaver_entries = [line for line in lines if line == "/.specweaver/"]
    assert len(specweaver_entries) == 1


def test_ensure_gitignore_finds_git_in_parent(tmp_path: Path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    nested_dir = tmp_path / "src" / "deeply" / "nested"
    nested_dir.mkdir(parents=True)

    _ensure_gitignore(nested_dir)

    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    assert "/.specweaver/\n" in gitignore.read_text(encoding="utf-8")


def test_ensure_gitignore_no_git_dir(tmp_path: Path):
    # Should not crash if no .git is found up the tree
    _ensure_gitignore(tmp_path)

    gitignore = tmp_path / ".gitignore"
    assert not gitignore.exists()


def test_dependency_hasher_compute_hashes(tmp_path: Path):

    from specweaver.assurance.graph.hasher import DependencyHasher

    src_dir = tmp_path / "src"
    src_dir.mkdir()

    file1 = src_dir / "foo.py"
    file1.write_text("import os\nfrom pathlib import Path\n")

    file2 = src_dir / "bar.py"
    file2.write_text("import sys\n")

    manifest = src_dir / "context.yaml"
    manifest.write_text("name: src\n")

    hasher = DependencyHasher(tmp_path, analyzer_factory=AnalyzerFactory)
    result = hasher.compute_hashes([manifest])

    assert "src" in result
    bound_res = result["src"]
    assert "merkle_root" in bound_res
    assert "rendered_payload" in bound_res

    rendered = bound_res["rendered_payload"]
    assert "foo.py" in rendered
    assert "bar.py" in rendered

    file2.write_text("import requests\nfrom pydantic import BaseModel\n")

    result2 = hasher.compute_hashes([manifest])
    bound_res2 = result2["src"]
    rendered2 = bound_res2["rendered_payload"]
    assert "requests" in rendered2
    assert "pydantic" in rendered2
    assert bound_res["merkle_root"] != bound_res2["merkle_root"]


def test_dependency_hasher_determinism(tmp_path: Path):
    from specweaver.assurance.graph.hasher import DependencyHasher

    src_dir = tmp_path / "src"
    src_dir.mkdir()

    file1 = src_dir / "a.py"
    file1.write_text("import requests\n")

    file2 = src_dir / "b.py"
    file2.write_text("import yaml\n")

    manifest = src_dir / "context.yaml"
    manifest.write_text("name: src\n")

    hasher = DependencyHasher(tmp_path, analyzer_factory=AnalyzerFactory)
    res1 = hasher.compute_hashes([manifest])
    res2 = hasher.compute_hashes([manifest])

    assert res1["src"]["merkle_root"] == res2["src"]["merkle_root"]


def test_dependency_hasher_caching_and_pruning(tmp_path: Path):
    from specweaver.assurance.graph.hasher import DependencyHasher

    dir1 = tmp_path / "mod1"
    dir1.mkdir()
    m1 = dir1 / "context.yaml"
    m1.write_text("name: mod1\n")
    (dir1 / "code.py").write_text("import os\n")

    dir2 = tmp_path / "mod2"
    dir2.mkdir()
    m2 = dir2 / "context.yaml"
    m2.write_text("name: mod2\n")

    hasher = DependencyHasher(tmp_path, analyzer_factory=AnalyzerFactory)
    state = hasher.compute_hashes([m1, m2])
    hasher.save_cache(state)

    assert "mod1" in state
    assert "mod2" in state
    assert hasher.cache_path.exists()

    # Reload from disk
    hasher2 = DependencyHasher(tmp_path, analyzer_factory=AnalyzerFactory)
    cache = hasher2.load_cache()
    assert "mod1" in cache
    assert cache["mod1"]["merkle_root"] == state["mod1"]["merkle_root"]

    # Prune mod2 by only passing m1
    new_state = hasher2.compute_hashes([m1])
    hasher2.save_cache(new_state)
    assert "mod1" in new_state
    assert "mod2" not in new_state

    # Validate cache file is trimmed
    final_cache = hasher2.load_cache()
    assert "mod2" not in final_cache


def test_hash_file_oserror(tmp_path: Path, monkeypatch):
    from specweaver.assurance.graph.hasher import DependencyHasher

    file_path = tmp_path / "bad.txt"
    file_path.write_text("test")

    def mock_open(*args, **kwargs):
        raise OSError("Permission denied dummy")

    monkeypatch.setattr(Path, "open", mock_open)

    # Should not crash but return empty string
    res = DependencyHasher._hash_file(file_path)
    assert res == ""


def test_dependency_hasher_hidden_files_bypass(tmp_path: Path):
    from specweaver.assurance.graph.hasher import DependencyHasher

    src_dir = tmp_path / "src"
    src_dir.mkdir()

    (src_dir / "valid.py").write_text("import os\n")

    secrets_dir = src_dir / ".secrets"
    secrets_dir.mkdir()
    (secrets_dir / "keys.txt").write_text("should_be_skipped")

    hasher = DependencyHasher(tmp_path, analyzer_factory=AnalyzerFactory)
    result = hasher._hash_directory(src_dir)
    rendered = result["rendered_payload"]

    assert "valid.py" in rendered
    assert ".secrets" not in rendered
    assert "keys.txt" not in rendered


def test_dependency_hasher_symlink_traversal_halt(tmp_path: Path):
    import os

    from specweaver.assurance.graph.hasher import DependencyHasher

    src_dir = tmp_path / "src"
    src_dir.mkdir()

    (src_dir / "valid.py").write_text("import os\n")

    try:
        os.symlink(str(src_dir), str(src_dir / "recursive_link"))
    except OSError:
        # Gracefully handle Windows dev environments lacking symlink privs
        pass
    else:
        hasher = DependencyHasher(tmp_path, analyzer_factory=AnalyzerFactory)
        result = hasher._hash_directory(src_dir)
        rendered = result["rendered_payload"]

        assert "valid.py" in rendered
        assert "recursive_link" not in rendered


def test_dependency_hasher_corrupt_cache(tmp_path: Path):
    from specweaver.assurance.graph.hasher import DependencyHasher

    hasher = DependencyHasher(tmp_path, analyzer_factory=AnalyzerFactory)
    hasher.cache_dir.mkdir()
    hasher.cache_path.write_text('{"broken_json_without_end_bracket', encoding="utf-8")

    state = hasher.load_cache()
    assert state == {}


def test_dependency_hasher_os_lock_save(tmp_path: Path, monkeypatch):
    from specweaver.assurance.graph.hasher import DependencyHasher

    hasher = DependencyHasher(tmp_path, analyzer_factory=AnalyzerFactory)

    def mock_write_text(*args, **kwargs):
        raise OSError("Permission locked dummy")

    monkeypatch.setattr(Path, "write_text", mock_write_text)

    # Needs to safely eat the exception
    hasher.save_cache({"dummy": {"merkle_root": "123"}})


def test_ensure_gitignore_os_lock(tmp_path: Path, monkeypatch):
    from specweaver.assurance.graph.hasher import _ensure_gitignore

    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    def mock_exists(*args, **kwargs):
        raise OSError("Dummy lock")

    monkeypatch.setattr(Path, "exists", mock_exists)

    # Should safely complete the fallback
    _ensure_gitignore(tmp_path)


def test_dependency_hasher_path_slash_agnosticism(tmp_path: Path):
    from specweaver.assurance.graph.hasher import DependencyHasher

    src_dir = tmp_path / "src"
    src_dir.mkdir()

    nested = src_dir / "deep"
    nested.mkdir()

    (nested / "valid.py").write_text("import os\n")

    manifest = src_dir / "context.yaml"
    manifest.write_text("name: src\n")

    hasher = DependencyHasher(tmp_path, analyzer_factory=AnalyzerFactory)
    res = hasher.compute_hashes([manifest])
    rendered = res["src"]["rendered_payload"]

    # Windows native path would be "deep\\valid.py", Posix is "deep/valid.py"
    # We insist it converts physically to posix.
    assert "deep/valid.py" in rendered
    assert "deep\\\\valid.py" not in rendered
