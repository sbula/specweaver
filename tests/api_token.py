# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The token a test's API app is built with, and the header that carries it (`D-UI-01` FR-6).

Build the app with `create_app(token=TEST_TOKEN, ...)` and the client with
`TestClient(app, headers=AUTH)`; a test about the guard itself builds its own.
"""

TEST_TOKEN = "test-token-for-the-suite"
AUTH = {"Authorization": f"Bearer {TEST_TOKEN}"}
