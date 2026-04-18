import pytest

from specweaver.core.loom.commons.protocol.grpc_parser import GRPCParser
from specweaver.core.loom.commons.protocol.interfaces import ProtocolSchemaError


def test_extract_endpoints_success():
    proto_content = """
    syntax = "proto3";
    package gateway;

    service Greeter {
      rpc SayHello (HelloRequest) returns (HelloReply) {}
      rpc StreamLogs (LogRequest) returns (stream LogReply) {}
    }

    service SecondaryService {
      rpc Ping (PingReq) returns (PingResp) {}
    }
    """
    parser = GRPCParser()
    endpoints = parser.extract_endpoints(proto_content)
    assert len(endpoints) == 3
    paths = {e.path for e in endpoints}
    assert paths == {"Greeter/SayHello", "Greeter/StreamLogs", "SecondaryService/Ping"}
    assert all(e.method == "RPC" for e in endpoints)

    hello_rpc = next(e for e in endpoints if e.path == "Greeter/SayHello")
    assert hello_rpc.properties["request_type"] == "HelloRequest"
    assert hello_rpc.properties["response_type"] == "HelloReply"


def test_extract_messages_success():
    proto_content = """
    syntax = "proto3";

    message SearchRequest {
      string query = 1;
      int32 page_number = 2;
      int32 result_per_page = 3;
    }

    message SearchResponse {
      repeated string results = 1;
    }
    """
    parser = GRPCParser()
    messages = parser.extract_messages(proto_content)
    assert len(messages) == 2
    names = {m.name for m in messages}
    assert names == {"SearchRequest", "SearchResponse"}
    search_req = next(m for m in messages if m.name == "SearchRequest")
    assert len(search_req.properties["fields"]) == 3
    assert search_req.properties["fields"][0]["name"] == "query"


def test_parse_catches_invalid_syntax():
    proto_content = "this is not valid protobuf syntax at all {} {"
    parser = GRPCParser()
    with pytest.raises(ProtocolSchemaError, match="Failed to parse gRPC schema"):
        parser.extract_endpoints(proto_content)


def test_extract_endpoints_no_services():
    proto_content = "syntax = 'proto3'; message Empty {}"
    parser = GRPCParser()
    endpoints = parser.extract_endpoints(proto_content)
    assert len(endpoints) == 0


def test_extract_messages_no_messages():
    proto_content = "syntax = 'proto3'; service Search {}"
    parser = GRPCParser()
    messages = parser.extract_messages(proto_content)
    assert len(messages) == 0
