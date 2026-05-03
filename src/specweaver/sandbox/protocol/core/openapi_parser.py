# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from specweaver.sandbox.protocol.core.protocol_interfaces import (
    ProtocolSchemaError,
    ProtocolSchemaInterface,
)
from specweaver.sandbox.protocol.core.models import ProtocolEndpoint, ProtocolMessage


class OpenAPIParser(ProtocolSchemaInterface):
    """Parses OpenAPI 3.x yaml into strictly typed protocol nodes."""

    def __init__(self) -> None:
        self.yaml = YAML(typ="safe")

    def _parse(self, raw_schema: str) -> dict[str, Any]:
        try:
            parsed = self.yaml.load(raw_schema)
            if not isinstance(parsed, dict):
                raise ProtocolSchemaError("Schema root must be a dictionary.")
            if "openapi" not in parsed:
                raise ProtocolSchemaError("Missing 'openapi' spec version key.")
            return parsed
        except YAMLError as e:
            raise ProtocolSchemaError(f"Malformed YAML: {e!s}") from e

    def extract_endpoints(self, raw_schema: str) -> list[ProtocolEndpoint]:
        parsed = self._parse(raw_schema)

        if "paths" not in parsed:
            raise ProtocolSchemaError("Missing 'paths' key in OpenAPI schema.")

        paths = parsed["paths"]
        if not isinstance(paths, dict):
            raise ProtocolSchemaError("'paths' must be a dictionary.")

        endpoints: list[ProtocolEndpoint] = []
        for path_key, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, details in methods.items():
                endpoints.append(
                    ProtocolEndpoint(
                        method=method.upper(),
                        path=path_key,
                        properties=details if isinstance(details, dict) else {},
                    )
                )
        return endpoints

    def extract_messages(self, raw_schema: str) -> list[ProtocolMessage]:
        parsed = self._parse(raw_schema)

        components = parsed.get("components", {})
        if not isinstance(components, dict):
            return []

        schemas = components.get("schemas", {})
        if not isinstance(schemas, dict):
            return []

        messages: list[ProtocolMessage] = []
        for name, props in schemas.items():
            if isinstance(props, dict):
                messages.append(ProtocolMessage(name=name, properties=props))

        return messages
