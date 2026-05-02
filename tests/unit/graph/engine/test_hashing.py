import pytest

from specweaver.graph.engine.hashing import SemanticHasher


def test_hash_file_happy_path():
    """[Happy Path] Generates stable hash for a file path."""
    hasher = SemanticHasher()
    hash1 = hasher.hash_file("src/main.py")
    hash2 = hasher.hash_file("src/main.py")
    assert hash1 == hash2
    assert isinstance(hash1, str)
    assert len(hash1) > 0

def test_hash_node_happy_path():
    """[Happy Path] Generates stable hash for a specific node in a file."""
    hasher = SemanticHasher()
    hash1 = hasher.hash_node("src/main.py", "MyClass")
    hash2 = hasher.hash_node("src/main.py", "MyClass")
    assert hash1 == hash2
    assert hash1 != hasher.hash_file("src/main.py")

def test_hash_boundary_os_normalization():
    """[Boundary] Windows and Linux paths must generate the identical hash."""
    hasher = SemanticHasher()
    hash_win = hasher.hash_file("src\\utils\\helpers.py")
    hash_lin = hasher.hash_file("src/utils/helpers.py")
    assert hash_win == hash_lin

def test_hash_hostile_empty_inputs():
    """[Hostile] Empty strings or None should raise ValueError to prevent collision on root."""
    hasher = SemanticHasher()

    with pytest.raises(ValueError, match="Cannot hash empty"):
        hasher.hash_file("")

    with pytest.raises(ValueError, match="Cannot hash empty"):
        hasher.hash_node("src/main.py", "")

def test_hash_id_prefix():
    """[Happy Path] Generates hashes with microservice ID prefix (AD-17)."""
    hasher = SemanticHasher(id_prefix="billing")
    hash_f = hasher.hash_file("src/main.py")
    hash_n = hasher.hash_node("src/main.py", "MyClass")
    
    assert hash_f.startswith("billing:")
    assert hash_n.startswith("billing:")
