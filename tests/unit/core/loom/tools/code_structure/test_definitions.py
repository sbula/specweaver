from specweaver.core.loom.tools.code_structure.definitions import get_code_structure_schema


def test_code_structure_schema_valid() -> None:
    schema = get_code_structure_schema()
    names = [s.name for s in schema]

    assert "read_file_structure" in names
    assert "list_symbols" in names
    assert "read_symbol" in names
    assert "read_symbol_body" in names
    assert "read_unrolled_symbol" in names

    # Write Side Intents (SF-2)
    assert "replace_symbol" in names
    assert "replace_symbol_body" in names
    assert "add_symbol" in names
    assert "delete_symbol" in names

    for tool_def in schema:
        assert tool_def.description is not None
        assert isinstance(tool_def.parameters, list)


def test_code_structure_schema_prunes_unsupported_intents() -> None:
    # Omit "framework_markers"
    supported_intents = {"skeleton", "symbol", "list", "replace", "add", "delete"}
    schema = get_code_structure_schema(supported_intents=supported_intents)
    names = [s.name for s in schema]

    assert "read_unrolled_symbol" not in names
    assert "read_file_structure" in names


def test_code_structure_schema_prunes_unsupported_params() -> None:
    # Omit "decorator_filter" from list_symbols
    supported_intents = {"list"}
    supported_params = {"list_symbols": {"visibility"}}

    schema = get_code_structure_schema(
        supported_intents=supported_intents,
        supported_params=supported_params,
    )

    assert len(schema) == 1
    list_schema = schema[0]
    assert list_schema.name == "list_symbols"

    param_names = [p.name for p in list_schema.parameters]
    assert "visibility" in param_names
    assert "path" in param_names
    assert "decorator_filter" not in param_names
