# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI command: sw serve — start the SpecWeaver REST API server."""

from __future__ import annotations

import logging

import typer

from specweaver.interfaces.cli import _core

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

    db = Database(config_db_path())
    app = create_app(db=db, cors_origins=cors_origins)

    _core.console.print(
        f"[bold]SpecWeaver API[/bold] starting on [cyan]http://{host}:{port}[/cyan]",
    )
    _core.console.print(
        f"Dashboard available at: [green]http://{host}:{port}/dashboard[/green]",
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
