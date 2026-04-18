import pytest

from specweaver.core.loom.commons.protocol.interfaces import ProtocolSchemaError
from specweaver.core.loom.commons.protocol.openapi_parser import OpenAPIParser


def test_extract_endpoints_success():
    yaml_content = """
    openapi: "3.0.0"
    paths:
      /users:
        get:
          description: "Get users"
        post:
          description: "Create user"
    """
    parser = OpenAPIParser()
    endpoints = parser.extract_endpoints(yaml_content)
    assert len(endpoints) == 2
    assert {"method": "GET", "path": "/users"} in [{"method": e.method, "path": e.path} for e in endpoints]
    assert {"method": "POST", "path": "/users"} in [{"method": e.method, "path": e.path} for e in endpoints]

def test_extract_endpoints_missing_paths():
    yaml_content = "openapi: '3.0.0'"
    parser = OpenAPIParser()
    with pytest.raises(ProtocolSchemaError):
        parser.extract_endpoints(yaml_content)

def test_extract_messages_success():
    yaml_content = """
    openapi: "3.0.0"
    components:
      schemas:
        User:
          type: object
        Error:
          type: object
    """
    parser = OpenAPIParser()
    messages = parser.extract_messages(yaml_content)
    assert len(messages) == 2
    names = {m.name for m in messages}
    assert names == {"User", "Error"}

def test_extract_messages_missing_components():
    yaml_content = "openapi: '3.0.0'"
    parser = OpenAPIParser()
    # It shouldn't crash, just return 0 messages
    assert len(parser.extract_messages(yaml_content)) == 0

def test_parse_catches_non_dictionary_root():
    yaml_content = "just a string"
    parser = OpenAPIParser()
    with pytest.raises(ProtocolSchemaError, match="must be a dictionary"):
        parser.extract_endpoints(yaml_content)

def test_extract_endpoints_paths_is_list():
    yaml_content = "openapi: '3.0.0'\npaths: []"
    parser = OpenAPIParser()
    with pytest.raises(ProtocolSchemaError, match="'paths' must be a dictionary"):
        parser.extract_endpoints(yaml_content)

def test_extract_endpoints_ignores_non_dict_methods():
    yaml_content = """
    openapi: "3.0.0"
    paths:
      /users:
        - get: {}
    """
    parser = OpenAPIParser()
    endpoints = parser.extract_endpoints(yaml_content)
    assert len(endpoints) == 0

def test_extract_messages_components_is_string():
    yaml_content = "openapi: '3.0.0'\ncomponents: 'not a dict'"
    parser = OpenAPIParser()
    messages = parser.extract_messages(yaml_content)
    assert len(messages) == 0

def test_extract_messages_schemas_is_list():
    yaml_content = "openapi: '3.0.0'\ncomponents:\n  schemas: []"
    parser = OpenAPIParser()
    messages = parser.extract_messages(yaml_content)
    assert len(messages) == 0

def test_extract_messages_skips_non_dict_schema():
    yaml_content = """
    openapi: "3.0.0"
    components:
      schemas:
        User:
          type: object
        InvalidSchema: "just a string"
    """
    parser = OpenAPIParser()
    messages = parser.extract_messages(yaml_content)
    assert len(messages) == 1
    assert messages[0].name == "User"
