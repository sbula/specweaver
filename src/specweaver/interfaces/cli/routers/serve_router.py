# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI command: sw serve — start the SpecWeaver REST API server."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import typer

from specweaver.interfaces.cli import _core

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


serve_cli = typer.Typer(no_args_is_help=True)


@serve_cli.command(name="serve")
def serve(
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port to listen on.",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Host to bind to.",
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        help="Enable auto-reload on file changes (development).",
    ),
    cors_origins: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--cors-origins",
        help="Additional allowed CORS origins.",
    ),
) -> None:
    """Start the SpecWeaver REST API server.

    Requires 'pip install specweaver[serve]' for FastAPI and Uvicorn.
    """
    logger.debug("Executing serve command (host=%s, port=%s)", host, port)
    try:
        import uvicorn
        from fastapi import FastAPI  # noqa: F401
    except ImportError:
        _core.console.print(
            "[red]Error:[/red] FastAPI and Uvicorn are required to run the API server.\n"
            "  Install them with: [bold]pip install specweaver[serve][/bold]",
        )
        raise typer.Exit(code=1) from None

    from specweaver.core.config.database import Database
    from specweaver.core.config.paths import config_db_path
    from specweaver.interfaces.api.app import create_app
    from specweaver.interfaces.api.auth import make_token

    token = make_token()
    token_file = _write_token(token)
    db = Database(config_db_path())
    app = create_app(db=db, token=token, cors_origins=cors_origins)

    _core.console.print(
        f"[bold]SpecWeaver API[/bold] starting on [cyan]http://{host}:{port}[/cyan]",
    )
    # Never wrapped or cut: an address with half a token opens nothing.
    _core.console.print("Dashboard available at:")
    _core.console.print(
        f"http://{host}:{port}/dashboard?token={token}",
        soft_wrap=True,
        highlight=False,
        markup=False,
    )
    _core.console.print(
        f"[dim]Programs send the token from {token_file} as `Authorization: Bearer`.[/dim]"
    )
    _core.console.print("[dim]OpenAPI docs: /docs  |  Health: /healthz[/dim]")

    import uvicorn

    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


def _write_token(token: str) -> Path:
    """Keep this start's token beside the settings, readable by its owner only."""
    import os

    from specweaver.core.config.paths import specweaver_root

    path = specweaver_root() / "serve.token"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")
    return path
