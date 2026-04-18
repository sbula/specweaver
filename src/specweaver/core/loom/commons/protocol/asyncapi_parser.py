from typing import Any

import ruamel.yaml

from specweaver.core.loom.commons.protocol.models import (
    ProtocolEndpoint,
    ProtocolMessage,
)
from specweaver.core.loom.commons.protocol.interfaces import (
    ProtocolSchemaError,
    ProtocolSchemaInterface,
)


class AsyncAPIParser(ProtocolSchemaInterface):
    """
    Native Python extractor for AsyncAPI format documents.
    """

    def _parse_yaml(self, payload: str) -> dict[str, Any]:
        """Parse YAML into a dict, raising ProtocolSchemaError on structural issues."""
        yaml = ruamel.yaml.YAML(typ="safe")
        try:
            doc = yaml.load(payload)
        except Exception as e:
            raise ProtocolSchemaError(f"Failed to parse AsyncAPI YAML: {e}") from e

        if not isinstance(doc, dict):
            raise ProtocolSchemaError("AsyncAPI root must be a dictionary")
        return doc

    def extract_endpoints(self, payload: str) -> list[ProtocolEndpoint]:
        """
        Extract 'channels' from the AsyncAPI document into ProtocolEndpoints.
        """
        doc = self._parse_yaml(payload)
        channels = doc.get("channels")

        if channels is None:
            raise ProtocolSchemaError("Missing 'channels' block in AsyncAPI document")
        if not isinstance(channels, dict):
            raise ProtocolSchemaError("'channels' must be a dictionary")

        endpoints: list[ProtocolEndpoint] = []
        for channel_name, channel_item in channels.items():
            if not isinstance(channel_item, dict):
                continue

            endpoints.append(
                ProtocolEndpoint(
                    path=str(channel_name),
                    method="CHANNEL",  # Semantic equivalent for AsyncAPI
                    properties=channel_item,
                )
            )

        return endpoints

    def extract_messages(self, payload: str) -> list[ProtocolMessage]:
        """
        Extract 'components.messages' from the AsyncAPI document.
        """
        doc = self._parse_yaml(payload)
        components = doc.get("components")

        if not isinstance(components, dict):
            return []

        messages_dict = components.get("messages")
        if not isinstance(messages_dict, dict):
            return []

        messages: list[ProtocolMessage] = []
        for msg_name, msg_item in messages_dict.items():
            if not isinstance(msg_item, dict):
                continue

            messages.append(
                ProtocolMessage(
                    name=str(msg_name),
                    properties=msg_item,
                )
            )

        return messages
