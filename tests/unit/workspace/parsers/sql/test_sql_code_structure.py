from specweaver.workspace.parsers.sql.codestructure import SqlCodeStructure


def test_sql_parser_initializes() -> None:
    parser = SqlCodeStructure()
    assert parser is not None

def test_sql_list_symbols() -> None:
    parser = SqlCodeStructure()
    code = """
    CREATE TABLE users (id INT);
    CREATE VIEW active_users AS SELECT * FROM users;
    CREATE FUNCTION get_user() RETURNS INT AS $$ SELECT 1; $$ LANGUAGE SQL;
    """
    symbols = parser.list_symbols(code)
    assert set(symbols) == {"users", "active_users", "get_user"}

def test_sql_extract_skeleton() -> None:
    parser = SqlCodeStructure()
    code = """
CREATE TABLE users (
    id INT,
    name VARCHAR
);
CREATE FUNCTION get_user() RETURNS INT AS $$
BEGIN
    RETURN 1;
END;
$$ LANGUAGE SQL;
"""
    skeleton = parser.extract_skeleton(code)
    assert "id INT" not in skeleton
    assert "RETURN 1" not in skeleton
    assert "CREATE TABLE users (" in skeleton
    assert "CREATE FUNCTION get_user" in skeleton

def test_sql_extract_replace_symbol() -> None:
    parser = SqlCodeStructure()
    code = """
CREATE TABLE users (
    id INT
);
CREATE VIEW active_users AS SELECT * FROM users;
"""
    # Extract
    sym_code = parser.extract_symbol(code, "active_users")
    assert "CREATE VIEW active_users" in sym_code
    assert "CREATE TABLE users" not in sym_code

    # Replace
    new_view = "CREATE VIEW active_users AS SELECT id FROM users;"
    replaced = parser.replace_symbol(code, "active_users", new_view)
    assert "SELECT id FROM users;" in replaced
    assert "SELECT * FROM users;" not in replaced
    assert "CREATE TABLE users" in replaced

def test_sql_edge_cases() -> None:
    parser = SqlCodeStructure()

    assert parser.extract_framework_markers("CREATE TABLE users (id INT);") == {}
    assert parser.supported_parameters() == []
    assert "skeleton" in parser.supported_intents()

    # Syntax error resilience (tree-sitter parses what it can)
    code = "CREATE TABLE users (id INT; CREATE VIEW v AS SELECT 1;"
    symbols = parser.list_symbols(code)
    # the parser might see nothing valid, but it shouldn't crash
    assert isinstance(symbols, list)

