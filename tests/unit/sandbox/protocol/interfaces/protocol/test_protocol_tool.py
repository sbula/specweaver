import json

from specweaver.sandbox.protocol.interfaces.tool import ProtocolTool


def test_protocol_tool_extract_endpoints(tmp_path):
    proto_file = tmp_path / "test.proto"
    proto_file.write_text('syntax = "proto3"; service S { rpc Ping (Req) returns (Resp) {} }')

    tool = ProtocolTool()
    result = tool.extract_schema_endpoints(str(proto_file))

    assert result["status"] == "success"
    assert "S/Ping" in json.dumps(result)


def test_protocol_tool_extract_messages(tmp_path):
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text("openapi: 3.0.0\ncomponents:\n  schemas:\n    User:\n      type: object")

    tool = ProtocolTool()
    result = tool.extract_schema_messages(str(yaml_file))

    assert result["status"] == "success"
    assert "User" in json.dumps(result)


def test_protocol_tool_definitions():
    tool = ProtocolTool()
    defs = tool.definitions()
    assert len(defs) == 2
    assert defs[0].name == "extract_schema_endpoints"


def test_protocol_tool_file_not_found():
    tool = ProtocolTool()
    result = tool.extract_schema_endpoints("missing.proto")

    assert result["status"] == "error"
    assert "not found" in result["error"].lower()
