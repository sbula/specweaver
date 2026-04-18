import pytest

from specweaver.core.loom.commons.protocol.asyncapi_parser import AsyncAPIParser
from specweaver.core.loom.commons.protocol.interfaces import ProtocolSchemaError


def test_extract_endpoints_success():
    yaml_content = """
    asyncapi: '3.0.0'
    channels:
      user/signedup:
        address: kafka://users
        messages:
          userSignedUp:
            $ref: '#/components/messages/UserSignedUp'
      user/login:
        address: kafka://auth
    """
    parser = AsyncAPIParser()
    endpoints = parser.extract_endpoints(yaml_content)
    assert len(endpoints) == 2
    paths = {e.path for e in endpoints}
    assert paths == {"user/signedup", "user/login"}
    # AsyncAPI endpoints don't have HTTP methods natively like OpenAPI, we can use "CHANNEL" or similar
    assert all(e.method == "CHANNEL" for e in endpoints)

def test_extract_messages_success():
    yaml_content = """
    asyncapi: '3.0.0'
    components:
      messages:
        UserSignedUp:
          payload:
            type: object
            properties:
              userId:
                type: string
        UserLogin:
          payload:
            type: object
    """
    parser = AsyncAPIParser()
    messages = parser.extract_messages(yaml_content)
    assert len(messages) == 2
    names = {m.name for m in messages}
    assert names == {"UserSignedUp", "UserLogin"}

def test_parse_catches_non_dictionary_root():
    yaml_content = "just a string"
    parser = AsyncAPIParser()
    with pytest.raises(ProtocolSchemaError, match="must be a dictionary"):
        parser.extract_endpoints(yaml_content)

def test_extract_endpoints_missing_channels():
    yaml_content = "asyncapi: '3.0.0'"
    parser = AsyncAPIParser()
    with pytest.raises(ProtocolSchemaError, match="Missing 'channels'"):
        parser.extract_endpoints(yaml_content)

def test_extract_endpoints_channels_is_list():
    yaml_content = "asyncapi: '3.0.0'\nchannels: []"
    parser = AsyncAPIParser()
    with pytest.raises(ProtocolSchemaError, match="'channels' must be a dictionary"):
        parser.extract_endpoints(yaml_content)

def test_extract_messages_missing_components():
    yaml_content = "asyncapi: '3.0.0'"
    parser = AsyncAPIParser()
    assert len(parser.extract_messages(yaml_content)) == 0

def test_extract_messages_components_is_string():
    yaml_content = "asyncapi: '3.0.0'\ncomponents: 'not a dict'"
    parser = AsyncAPIParser()
    assert len(parser.extract_messages(yaml_content)) == 0

def test_extract_messages_messages_is_list():
    yaml_content = "asyncapi: '3.0.0'\ncomponents:\n  messages: []"
    parser = AsyncAPIParser()
    assert len(parser.extract_messages(yaml_content)) == 0

def test_extract_messages_skips_non_dict_message():
    yaml_content = """
    asyncapi: '3.0.0'
    components:
      messages:
        ValidMessage:
          payload: {}
        InvalidMessage: "string instead of object"
    """
    parser = AsyncAPIParser()
    messages = parser.extract_messages(yaml_content)
    assert len(messages) == 1
    assert messages[0].name == "ValidMessage"
