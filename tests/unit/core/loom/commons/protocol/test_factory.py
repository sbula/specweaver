import pytest

from specweaver.core.loom.commons.protocol.interfaces import ProtocolSchemaError
from specweaver.core.loom.commons.protocol.factory import ProtocolParserFactory
from specweaver.core.loom.commons.protocol.openapi_parser import OpenAPIParser
from specweaver.core.loom.commons.protocol.asyncapi_parser import AsyncAPIParser
from specweaver.core.loom.commons.protocol.grpc_parser import GRPCParser


def test_factory_detects_openapi():
    payload = """
    openapi: 3.0.0
    info:
      title: Test API
    paths: {}
    """
    parser = ProtocolParserFactory.create_parser(payload)
    assert isinstance(parser, OpenAPIParser)


def test_factory_detects_asyncapi():
    payload = """
    asyncapi: 3.0.0
    info:
      title: Test Events
    channels: {}
    """
    parser = ProtocolParserFactory.create_parser(payload)
    assert isinstance(parser, AsyncAPIParser)


def test_factory_detects_grpc_proto3():
    payload = """
    syntax = "proto3";
    service Greeter {}
    """
    parser = ProtocolParserFactory.create_parser(payload)
    assert isinstance(parser, GRPCParser)


def test_factory_detects_grpc_proto2():
    payload = """
    syntax = "proto2";
    message OldSchool {}
    """
    parser = ProtocolParserFactory.create_parser(payload)
    assert isinstance(parser, GRPCParser)


def test_factory_raises_on_unknown():
    payload = "some random text file that is neither yaml nor proto"
    with pytest.raises(ProtocolSchemaError, match="Unable to determine protocol schema type"):
        ProtocolParserFactory.create_parser(payload)


def test_factory_raises_on_invalid_yaml_without_proto_hints():
    payload = "openapi: [this is broken yaml } {"
    with pytest.raises(ProtocolSchemaError):
        ProtocolParserFactory.create_parser(payload)
