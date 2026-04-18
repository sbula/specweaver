from typing import Any

from proto_schema_parser.ast import Message, Service
from proto_schema_parser.parser import Parser

from specweaver.core.loom.commons.protocol.interfaces import (
    ProtocolSchemaError,
    ProtocolSchemaInterface,
)
from specweaver.core.loom.commons.protocol.models import (
    ProtocolEndpoint,
    ProtocolMessage,
)


class GRPCParser(ProtocolSchemaInterface):
    """
    Native Python extractor for gRPC (.proto) format documents.
    """

    def _parse_proto(self, payload: str) -> Any:
        try:
            ast = Parser().parse(payload)
            if getattr(ast, "syntax", None) is None and not getattr(ast, "file_elements", []) and payload.strip():
                raise ProtocolSchemaError("Failed to parse gRPC schema: No elements parsed from non-empty string")
            return ast
        except Exception as e:
            if isinstance(e, ProtocolSchemaError):
                raise
            raise ProtocolSchemaError(f"Failed to parse gRPC schema: {e}") from e

    def extract_endpoints(self, payload: str) -> list[ProtocolEndpoint]:
        """
        Extract 'service' & 'rpc' elements from the .proto document into ProtocolEndpoints.
        """
        ast = self._parse_proto(payload)
        endpoints: list[ProtocolEndpoint] = []

        for element in ast.file_elements:
            if isinstance(element, Service):
                service_name = element.name
                for rpc in element.elements:
                    if type(rpc).__name__ == "Method":  # proto-schema-parser 'Method' class
                        input_type_obj = getattr(rpc, "input_type", None)
                        output_type_obj = getattr(rpc, "output_type", None)
                        path = f"{service_name}/{getattr(rpc, 'name', 'unknown')}"
                        properties = {
                            "request_type": getattr(input_type_obj, "type", str(input_type_obj)),
                            "response_type": getattr(output_type_obj, "type", str(output_type_obj)),
                            "client_streaming": getattr(input_type_obj, "stream", False),
                            "server_streaming": getattr(output_type_obj, "stream", False),
                        }
                        endpoints.append(
                            ProtocolEndpoint(
                                path=path,
                                method="RPC",
                                properties=properties,
                            )
                        )
        return endpoints

    def extract_messages(self, payload: str) -> list[ProtocolMessage]:
        """
        Extract 'message' elements from the .proto document into ProtocolMessages.
        """
        ast = self._parse_proto(payload)
        messages: list[ProtocolMessage] = []

        for element in ast.file_elements:
            if isinstance(element, Message):
                msg_name = element.name
                fields = []
                for field in element.elements:
                    if type(field).__name__ == "Field":
                        fields.append({
                            "name": getattr(field, "name", ""),
                            "type": getattr(field, "type", ""),
                            "number": getattr(field, "number", 0),
                        })
                messages.append(
                    ProtocolMessage(
                        name=msg_name,
                        properties={"fields": fields},
                    )
                )
        return messages
