from specweaver.sandbox.protocol.core.atom import ProtocolAtom


def test_atom_extract_endpoints_success(tmp_path):
    proto_file = tmp_path / "test.proto"
    proto_file.write_text('syntax = "proto3"; service S { rpc Ping (Req) returns (Resp) {} }')

    atom = ProtocolAtom()
    result = atom.run(
        context={"action": "extract_schema_endpoints", "file_path": str(proto_file)}
    ).exports
    assert result["status"] == "success"
    assert len(result["data"]) == 1
    assert result["data"][0]["path"] == "S/Ping"
    assert result["data"][0]["method"] == "RPC"


def test_atom_extract_messages_success(tmp_path):
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text("openapi: 3.0.0\ncomponents:\n  schemas:\n    User:\n      type: object")

    atom = ProtocolAtom()
    result = atom.run(
        context={"action": "extract_schema_messages", "file_path": str(yaml_file)}
    ).exports
    assert result["status"] == "success"
    assert len(result["data"]) == 1
    assert result["data"][0]["name"] == "User"


def test_atom_invalid_file_fallback(tmp_path):
    bad_file = tmp_path / "test.txt"
    bad_file.write_text("random garbage")

    atom = ProtocolAtom()
    result = atom.run(
        context={"action": "extract_schema_endpoints", "file_path": str(bad_file)}
    ).exports
    assert result["status"] == "error"
    assert "Unable to determine protocol schema" in result["error"]


def test_atom_unknown_action(tmp_path):
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text("openapi: 3.0.0")
    atom = ProtocolAtom()
    result = atom.run(context={"action": "unknown_action", "file_path": str(yaml_file)}).exports
    assert result["status"] == "error"
    assert "Unknown intent: unknown_action" in result["error"]
