from specweaver.loom.tools.code_structure.definitions import get_code_structure_schema


def test_code_structure_schema_valid() -> None:
    schema = get_code_structure_schema()
    names = [s.name for s in schema]

    assert "read_file_structure" in names
    assert "list_symbols" in names
    assert "read_symbol" in names
    assert "read_symbol_body" in names

    # Write Side Intents (SF-2)
    assert "replace_symbol" in names
    assert "replace_symbol_body" in names
    assert "add_symbol" in names
    assert "delete_symbol" in names

    for tool_def in schema:
        assert tool_def.description is not None
        assert isinstance(tool_def.parameters, list)
