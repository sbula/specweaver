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


def _scrub(payload: Any, secrets: set[str]) -> Any:
    """`payload` with every secret replaced, walking dicts and lists."""
    if isinstance(payload, dict):
        return {k: _scrub(v, secrets) for k, v in payload.items()}
    if isinstance(payload, list):
        return [_scrub(item, secrets) for item in payload]
    if isinstance(payload, str):
        for secret in secrets:
            payload = payload.replace(secret, "***RESTRICTED***")
        return payload
    return payload


#: The only runtimes NFR-2 permits. Names, because that is what a config declares.
_ALLOWED_RUNTIMES = ("docker", "podman")

#: Arguments that hand the container the host. `argv[0]` is still `docker` for every one of them, so
#: a guard reading only the executable calls a host takeover compliant.
#:
#: Prefix-matched, because each has a `=` form and a separate-word form, and matching a whole token
#: would let `--network=host` past a check written for `--network`.
_ESCAPING_ARGUMENTS = (
    "--privileged",
    "--network=host",
    "--net=host",
    "--pid=host",
    "--ipc=host",
    "--uts=host",
    "--userns=host",
    "--cap-add",
    "--security-opt",
    "--device",
)

#: Host paths a mount may never expose. The socket is the whole daemon; `/` is the whole machine.
_FORBIDDEN_MOUNT_SOURCES = ("/", "/var/run/docker.sock", "/run/docker.sock", "/etc", "/root")

#: Flags whose value is a bind mount.
_MOUNT_FLAGS = ("-v", "--volume", "--mount")

#: The test seam that replaces a production hole.
#:
#: The interpreter used to be permitted unconditionally, with a comment saying it was "for internal
#: test infrastructure" — and the condition ran on every construction, so a `context.yaml` naming the
#: exact interpreter path (`.venv/bin/python` is conventional and discoverable) got arbitrary code
#: with the boundary reporting compliance.
#:
#: A test needs a stdio server it can start without an image, a registry or a network. It gets one by
#: patching this, which takes in-process code execution — something configuration cannot do, and
#: something an attacker who already has it does not need.
_ALLOW_INTERPRETER = False


def _refuse(reason: str) -> None:
    raise ValueError(
        "NFR-2 Boundary Violation: MCP executions must run through an isolated container "
        f"environment. {reason}"
    )


def _reject_escaping_arguments(arguments: list[str]) -> None:
    """Refuse a command that asks the runtime to hand back the host."""
    for index, argument in enumerate(arguments):
        if any(argument.startswith(flag) for flag in _ESCAPING_ARGUMENTS):
            _refuse(f"Argument '{argument}' removes the isolation the runtime provides.")
        if argument in _MOUNT_FLAGS:
            value = arguments[index + 1] if index + 1 < len(arguments) else ""
            source = value.split(":", 1)[0]
            if source in _FORBIDDEN_MOUNT_SOURCES:
                _refuse(f"Mount '{value}' exposes host path '{source}' to the container.")


def _resolved_runtime_command(command: list[str]) -> list[str]:
    """The command to execute, with the runtime resolved from the TRUSTED environment.

    `Popen` resolves `argv[0]` through the PATH of the `env` it is handed, and that `env` comes from
    the analysed project's own `context.yaml`. So a guard comparing `command[0]` to a NAME validated
    nothing the config could not redirect: a directory holding a script called `docker`, declared as
    the config's PATH, satisfied the old check and ran. That was reproduced before this was written.

    Resolving here — once, from this process's environment — makes `argv[0]` an absolute path, and a
    config's PATH can no longer decide what it means.
    """
    import shutil
    import sys

    name = command[0]
    if _ALLOW_INTERPRETER and name == sys.executable:
        return list(command)
    if name not in _ALLOWED_RUNTIMES:
        _refuse(f"Bare executable '{name}' forbidden.")

    _reject_escaping_arguments(command[1:])

    resolved = shutil.which(name)
    if resolved is None:
        _refuse(f"Container runtime '{name}' is not installed on this machine.")
    return [str(resolved), *command[1:]]


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

        self._command = _resolved_runtime_command(command)
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
        """Recursively scrub vault secrets from RPC payloads.

        Only values of 8+ characters are treated as secrets: a short vault entry (a port, a flag
        like "true") would otherwise match everywhere and redact ordinary telemetry.
        """
        if not self._env:
            return payload
        secrets = {v for v in self._env.values() if isinstance(v, str) and len(v.strip()) >= 8}
        return _scrub(payload, secrets) if secrets else payload

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
