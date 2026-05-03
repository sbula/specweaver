import re
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.parser import ParserError
from ruamel.yaml.scanner import ScannerError

from specweaver.sandbox.protocol.core.asyncapi_parser import AsyncAPIParser
from specweaver.sandbox.protocol.core.grpc_parser import GRPCParser
from specweaver.sandbox.protocol.core.openapi_parser import OpenAPIParser
from specweaver.sandbox.protocol.core.protocol_interfaces import (
    ProtocolSchemaError,
    ProtocolSchemaInterface,
)


class ProtocolParserFactory:
    """
    Factory for instantiating the correct ProtocolSchemaInterface based on the payload.
    """

    @staticmethod
    def create_parser(payload: str) -> ProtocolSchemaInterface:
        """
        Inspects the string payload and returns the appropriate parser instance.
        """
        payload_stripped = payload.strip()
        if not payload_stripped:
            raise ProtocolSchemaError("Unable to determine protocol schema type: empty payload")

        # 1. Check for gRPC (.proto)
        # Typically begins with syntax = "proto3" or "proto2"
        if re.search(r'syntax\s*=\s*["\']proto[23]["\']', payload):
            return GRPCParser()

        # 2. Check for YAML (OpenAPI or AsyncAPI)
        yaml = YAML(typ="safe")
        try:
            parsed: Any = yaml.load(payload)
        except (ParserError, ScannerError) as e:
            raise ProtocolSchemaError(f"Unable to parse schema payload: {e}") from e

        if isinstance(parsed, dict):
            if "openapi" in parsed or "swagger" in parsed:
                return OpenAPIParser()
            if "asyncapi" in parsed:
                return AsyncAPIParser()

        raise ProtocolSchemaError(
            "Unable to determine protocol schema type: missing 'openapi', 'asyncapi', or proto syntax tokens"
        )
