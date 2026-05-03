from pathlib import Path


def test_polyglot_sql_ast_integration(tmp_path: Path) -> None:
    sql_file = tmp_path / "schema.sql"
    sql_file.write_text(
        """
CREATE TABLE users (
    id INT,
    name VARCHAR
);

CREATE VIEW active_users AS SELECT * FROM users;

CREATE FUNCTION get_user() RETURNS INT AS $$
BEGIN
    RETURN 1;
END;
$$ LANGUAGE SQL;
""",
        encoding="utf-8",
    )

    from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom

    atom = CodeStructureAtom(cwd=tmp_path)

    # Test skeleton
    res = atom.run({"intent": "skeletonize", "path": "schema.sql"})
    skeleton = res.exports["structure"]
    assert "CREATE TABLE users" in skeleton
    assert "id INT" not in skeleton

    # Test list symbols
    res = atom.run({"intent": "list_symbols", "path": "schema.sql"})
    symbols = res.exports["symbols"]
    assert "users" in symbols
    assert "active_users" in symbols
    assert "get_user" in symbols

    # Test read_symbol
    res = atom.run({"intent": "read_symbol", "path": "schema.sql", "symbol_name": "active_users"})
    assert "CREATE VIEW active_users" in res.exports["symbol"]
    assert "CREATE TABLE" not in res.exports["symbol"]

    # Test replace_symbol
    new_view = "CREATE VIEW active_users AS SELECT id FROM users;"
    res = atom.run(
        {
            "intent": "replace_symbol",
            "path": "schema.sql",
            "symbol_name": "active_users",
            "new_code": new_view,
        }
    )
    assert res.status.value == "SUCCESS"
    assert "SELECT id FROM users" in sql_file.read_text("utf-8")

    # Test delete_symbol
    res = atom.run({"intent": "delete_symbol", "path": "schema.sql", "symbol_name": "get_user"})
    assert res.status.value == "SUCCESS"
    assert "get_user" not in sql_file.read_text("utf-8")

    # Test add_symbol
    new_func = "CREATE FUNCTION new_func() RETURNS INT AS $$ SELECT 2; $$ LANGUAGE SQL;"
    res = atom.run({"intent": "add_symbol", "path": "schema.sql", "new_code": new_func})
    assert res.status.value == "SUCCESS"
    assert "new_func" in sql_file.read_text("utf-8")

    # Test extract_framework_markers
    res = atom.run({"intent": "extract_framework_markers", "path": "schema.sql"})
    assert res.status.value == "SUCCESS"
    assert res.exports["markers"] == {}
