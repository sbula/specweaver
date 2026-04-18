import pytest

from specweaver.core.loom.commons.protocol.interfaces import (
    ProtocolSchemaError,
    ProtocolSchemaInterface,
)
from specweaver.core.loom.commons.protocol.models import (
    ProtocolEndpoint,
    ProtocolMessage,
    ProtocolSchemaSet,
)


def test_protocol_endpoint_instantiation():
    endpoint = ProtocolEndpoint(method="GET", path="/users")
    assert endpoint.method == "GET"
    assert endpoint.path == "/users"

def test_protocol_message_instantiation():
    msg = ProtocolMessage(name="UserResponse", properties={"id": "string", "name": "string"})
    assert msg.name == "UserResponse"
    assert "id" in msg.properties

def test_protocol_schema_set():
    schema = ProtocolSchemaSet(
        endpoints=[ProtocolEndpoint(method="GET", path="/users")],
        messages=[ProtocolMessage(name="UserResponse", properties={"name": "string"})]
    )
    assert len(schema.endpoints) == 1
    assert len(schema.messages) == 1

def test_protocol_interface_abstract():
    with pytest.raises(TypeError):
        ProtocolSchemaInterface()

def test_schema_error():
    err = ProtocolSchemaError("Malformed schema paths")
    assert "Malformed schema paths" in str(err)
