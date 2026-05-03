from typing import Any

from specweaver.sandbox.protocol.core.atom import ProtocolAtom
from specweaver.infrastructure.llm.models import ToolDefinition, ToolParameter


class ProtocolTool:
    """
    Native intent-based wrapper tool targeting Protocol extraction safely via the Atom layer.
    """

    def definitions(self) -> list[ToolDefinition]:
        """Provides the schema for LLMs to invoke this tool."""
        return [
            ToolDefinition(
                name="extract_schema_endpoints",
                description="Extracts structural backend intents out of OpenAPI, AsyncAPI, or gRPC definitions.",
                parameters=[
                    ToolParameter(
                        name="file_path",
                        type="string",
                        description="The absolute or relative path to the OpenAPI, AsyncAPI, or Protocol Buffers definition file to extract.",
                        required=True,
                    )
                ],
            ),
            ToolDefinition(
                name="extract_schema_messages",
                description="Extracts data payload structures from API contracts.",
                parameters=[
                    ToolParameter(
                        name="file_path",
                        type="string",
                        description="The absolute or relative path to the schema definition.",
                        required=True,
                    )
                ],
            ),
        ]

    def extract_schema_endpoints(self, file_path: str) -> dict[str, Any]:
        """Invokes the enclosed Atom strictly mapping the string bounds."""
        atom = ProtocolAtom()
        try:
            result = atom.run(
                context={"action": "extract_schema_endpoints", "file_path": file_path}
            )
            return result.exports
        except Exception as e:
            return {"status": "error", "error": f"Tool boundary exception: {e}"}

    def extract_schema_messages(self, file_path: str) -> dict[str, Any]:
        """Invokes the enclosed Atom strictly mapping the string bounds."""
        atom = ProtocolAtom()
        try:
            result = atom.run(context={"action": "extract_schema_messages", "file_path": file_path})
            return result.exports
        except Exception as e:
            return {"status": "error", "error": f"Tool boundary exception: {e}"}
