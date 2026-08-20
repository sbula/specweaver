# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A failure reaches the caller as a typed error, not as a stack trace.

Proves: D-UI-01 FR-5

Every consumer of this API is a program: a dashboard, a VS Code extension, an IntelliJ plugin.
A program cannot branch on English, so the failure has to carry a stable `error_code` beside the
human sentence. And because the server runs the whole engine — pipelines, sandboxes, the config
database — an unhandled exception would otherwise return a traceback that names filesystem paths
and module layout to whoever asked.

`SpecWeaverAPIError` and its handler existed with no test at all.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from specweaver.interfaces.api.errors import SpecWeaverAPIError, specweaver_error_handler


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.add_exception_handler(SpecWeaverAPIError, specweaver_error_handler)  # type: ignore[arg-type]

    @app.get("/boom")
    async def boom() -> None:
        raise SpecWeaverAPIError(
            detail="project 'ghost' is not registered",
            error_code="PROJECT_NOT_FOUND",
            status_code=404,
        )

    return TestClient(app)


def test_the_status_code_is_the_one_the_error_declared(client: TestClient) -> None:
    assert client.get("/boom").status_code == 404


def test_the_caller_gets_a_machine_readable_code(client: TestClient) -> None:
    """The half a human-readable message cannot serve: a client branches on this."""
    assert client.get("/boom").json()["error_code"] == "PROJECT_NOT_FOUND"


def test_the_caller_also_gets_a_readable_reason(client: TestClient) -> None:
    assert "ghost" in client.get("/boom").json()["detail"]


def test_the_response_carries_no_traceback(client: TestClient) -> None:
    """The control that matters. A handler that simply re-raised would still return a 4xx under
    some server configurations, and would leak module paths with it."""
    body = client.get("/boom").text

    assert "Traceback" not in body
    assert "specweaver/interfaces" not in body


def test_the_default_status_is_a_client_error() -> None:
    """An error whose status was left unstated must not be reported as a server fault — a 5xx
    tells the caller to retry something that will fail identically every time."""
    assert SpecWeaverAPIError("bad input", error_code="BAD_INPUT").status_code == 400
