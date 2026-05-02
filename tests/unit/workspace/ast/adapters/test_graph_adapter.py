import pytest

from specweaver.workspace.ast.adapters.graph_adapter import extract_ast_dict


def test_extract_ast_dict_happy_path(tmp_path):
    """[Happy Path] Extracts classes and functions from a python file."""
    py_file = tmp_path / "test.py"
    py_file.write_text(
        """
class MyClass:
    def my_method(self):
        pass

def my_function():
    pass
""",
        encoding="utf-8",
    )

    ast_data = extract_ast_dict(str(py_file))
    assert ast_data["type"] == "module"

    children = ast_data["children"]
    assert len(children) == 3

    names = [c["name"] for c in children]
    assert "MyClass" in names
    assert "MyClass.my_method" in names
    assert "my_function" in names

    for c in children:
        if c["name"] == "MyClass":
            assert c["type"] == "class_definition"
        elif c["name"] == "my_function":
            assert c["type"] == "function_definition"


def test_extract_ast_dict_boundary_empty(tmp_path):
    """[Boundary] Empty file returns module with 0 children."""
    py_file = tmp_path / "empty.py"
    py_file.write_text("", encoding="utf-8")

    ast_data = extract_ast_dict(str(py_file))
    assert ast_data["type"] == "module"
    assert ast_data["children"] == []


def test_extract_ast_dict_hostile_unsupported(tmp_path):
    """[Hostile] Unsupported file extension returns empty children."""
    xyz_file = tmp_path / "test.xyz"
    xyz_file.write_text("random stuff", encoding="utf-8")

    ast_data = extract_ast_dict(str(xyz_file))
    assert ast_data["type"] == "module"
    assert ast_data["children"] == []


def test_extract_ast_dict_hostile_missing():
    """[Hostile] Missing file returns empty children."""
    ast_data = extract_ast_dict("does_not_exist.py")
    assert ast_data["type"] == "module"
    assert ast_data["children"] == []


def test_extract_ast_dict_hostile_crash(tmp_path, monkeypatch):
    """[Hostile] Underlying parser crash returns empty children instead of failing."""
    py_file = tmp_path / "crash.py"
    py_file.write_text("def valid_code(): pass", encoding="utf-8")

    # Mock the parser factory to throw an exception
    def mock_get_parsers():
        class CrashParser:
            def list_symbols(self, code):
                raise RuntimeError("TreeSitter fatal crash")

            def extract_framework_markers(self, code):
                return {}

        return {(".py",): CrashParser()}

    monkeypatch.setattr(
        "specweaver.workspace.ast.adapters.graph_adapter.get_default_parsers", mock_get_parsers
    )

    ast_data = extract_ast_dict(str(py_file))
    assert ast_data["type"] == "module"
    assert ast_data["children"] == []


def test_extract_ast_dict_boundary_symlink(tmp_path):
    """[Boundary] OS Symlinks are explicitly ignored to prevent recursion loops."""
    py_file = tmp_path / "real.py"
    py_file.write_text("def valid_code(): pass", encoding="utf-8")

    symlink_file = tmp_path / "fake.py"
    try:
        symlink_file.symlink_to(py_file)
    except OSError:
        # Windows requires admin privileges for symlinks sometimes
        pytest.skip("OS does not support symlinks without elevation")

    ast_data = extract_ast_dict(str(symlink_file))
    assert ast_data["type"] == "module"
    assert ast_data["children"] == []
