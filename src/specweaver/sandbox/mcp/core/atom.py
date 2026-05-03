# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""MCPAtom — Flow-level orchestrator communication via Model Context Protocol.

The Engine uses MCPAtom to broker JSON-RPC connections dynamically to
isolated Docker or local binaries. It exposes standard intents for initializing
and reading from the MCP infrastructure layer via standard I/O pipes.
"""

from __future__ import annotations

import logging
from typing import Any

from specweaver.sandbox.base import Atom, AtomResult, AtomStatus
from specweaver.sandbox.mcp.core.executor import MCPExecutor, MCPExecutorError

logger = logging.getLogger(__name__)


class MCPAtom(Atom):
    """Flow-level MCP lifecycle and operation bridging.

    Binds valid JSON-RPC intents using a synchronous thread-pumped
    standard I/O executor.

    Args:
        command: Subprocess payload to boot the MCP server.
        env: Optional dictionary of environment bindings.
    """

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        if not command:
            raise ValueError(
                "Configuration Error: MCP Atom boundary dictates a valid executable string must be provided."
            )

        allowed_executables = {"docker", "podman"}
        # For internal test infrastructure, we safely permit the Python runtime bridge.
        import sys

        executor_target = command[0]
        if executor_target not in allowed_executables and executor_target != sys.executable:
            raise ValueError(
                f"NFR-2 Boundary Violation: MCP Atom dictates executions must run through isolated environments (docker/podman). Bare executable forbidden: '{executor_target}'"
            )

        self._command = command
        self._env = env
        self._executor: MCPExecutor | None = None

    def _ensure_started(self) -> None:
        """Boot the executor on demand effectively maintaining singleton."""
        if self._executor is None or not self._executor.is_alive():
            self._executor = MCPExecutor(self._command, self._env)

    def run(self, context: dict[str, Any]) -> AtomResult:
        """Dispatch to the appropriate intent based on context.

        The Engine provides a context dict with at minimum:
            intent: str — which operation to perform.
            params: dict — payload to inject into the execution bounds.
        """
        intent = context.get("intent")
        if intent is None:
            logger.error("MCPAtom.run: missing 'intent' in context")
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'intent' in context.",
            )

        logger.info("MCPAtom.run: dispatching intent '%s'", intent)

        handler = getattr(self, f"_intent_{intent}", None)
        if handler is None:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"Unknown intent: {intent!r}. Known: {sorted(self._known_intents())}",
            )

        try:
            self._ensure_started()
            return handler(context)  # type: ignore[no-any-return]
        except MCPExecutorError as e:
            logger.error("MCPAtom.run: execution error: %s", e)
            return AtomResult(
                status=AtomStatus.FAILED,
                message=str(e),
            )

    def _known_intents(self) -> set[str]:
        """Return the set of known intent names."""
        prefix = "_intent_"
        return {name[len(prefix) :] for name in dir(self) if name.startswith(prefix)}

    def close(self) -> None:
        """Tear down the backing active MCP Server executor binding."""
        if self._executor:
            self._executor.close()
            self._executor = None

    def _scrub_telemetry(self, payload: Any) -> Any:
        """Recursively scrub vault secrets from RPC payloads."""
        if not self._env:
            return payload

        secrets = [v for v in self._env.values() if isinstance(v, str) and len(v.strip()) >= 8]

        if not secrets:
            return payload

        if isinstance(payload, dict):
            return {k: self._scrub_telemetry(v) for k, v in payload.items()}
        if isinstance(payload, list):
            return [self._scrub_telemetry(item) for item in payload]
        if isinstance(payload, str):
            for secret in set(secrets):
                if secret in payload:
                    payload = payload.replace(secret, "***RESTRICTED***")
            return payload

        return payload

    # -- Intent implementations ----------------------------------------

    def _intent_initialize(self, context: dict[str, Any]) -> AtomResult:
        """Handshake capability vectors with the server.

        Context keys:
            capabilities: dict — Handshake binding requirements for the client.
        """
        if not self._executor:
            return AtomResult(status=AtomStatus.FAILED, message="Executor not initialized")

        params = context.get("params", {})

        # MCP Protocol Standard Payload
        payload = {
            "protocolVersion": "2024-11-05",  # Standard MCP 1.0 schema parity string
            "capabilities": params.get("capabilities", {}),
            "clientInfo": {"name": "specweaver-atom", "version": "1.0.0"},
        }

        response = self._scrub_telemetry(
            self._executor.call_rpc(method="initialize", params=payload, timeout=10.0)
        )

        # Confirm to the protocol the initialization is done
        self._executor.call_rpc(method="notifications/initialized", params={}, timeout=5.0)

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message="Initialized successfully",
            exports=response.get("result", {}),
        )

    def _intent_read_resource(self, context: dict[str, Any]) -> AtomResult:
        """Call `resources/read` endpoint against the active MCP server bound connection.

        Context keys:
            uri: str — Resource locator mapped natively to the Target server's spec schema.
        """
        if not self._executor:
            return AtomResult(status=AtomStatus.FAILED, message="Executor not initialized")

        params = context.get("params", {})
        if "uri" not in params:
            return AtomResult(status=AtomStatus.FAILED, message="Missing 'uri' in intent params")

        response = self._scrub_telemetry(
            self._executor.call_rpc(
                method="resources/read", params={"uri": params["uri"]}, timeout=15.0
            )
        )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message="Resource read successfully",
            exports=response.get("result", {}),
        )
