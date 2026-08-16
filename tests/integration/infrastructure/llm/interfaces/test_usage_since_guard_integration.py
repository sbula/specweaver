# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The `--since` guard agrees with the column it protects. TECH-052.

Proves: TECH-052 FR-1

The unit tests prove the guard rejects what it should. They cannot prove it rejects **the right
things**, because the reason a naive timestamp is refused lives in a different module: the
`llm_usage_log.timestamp` column is a `StrictISODateTime`, which raises
*"StrictISODateTime must be timezone-aware"* from inside SQLAlchemy. That is the seam — a CLI guard
whose condition is a restatement of a database type's contract — and per `ADR-003` it belongs to the
boundary that creates it.

**What breaks without this test.** Relax the column to accept naive datetimes and the guard becomes
over-strict, refusing input the database would now take. Tighten it further and the guard becomes
too loose. Neither shows up in a unit test of either side; both show up here.

Integration tier because it uses a real database and a real repository query. Mocking either would
test the mock, and the mock is precisely the thing whose agreement is in question.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import anyio
import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.interfaces.cli import _parse_since
from specweaver.infrastructure.llm.store import LlmRepository
from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.integration


@pytest.fixture()
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database

    data_dir = tmp_path / ".specweaver-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    bootstrap_database(str(data_dir / "specweaver.db"))
    instance = Database(data_dir / "specweaver.db")
    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", lambda: instance)
    return instance


def _query(db, since: datetime | None) -> list[dict]:
    async def _run():
        async with db.async_session_scope() as session:
            return await LlmRepository(session).get_usage_summary(project=None, since=since)

    return anyio.run(_run)


class TestTheGuardMatchesTheColumn:
    """FR-1 — the guard's condition is the column's requirement, not a guess about it."""

    def test_what_the_guard_accepts_the_query_also_accepts(self, db) -> None:
        """[Happy] an aware timestamp passes the guard and reaches the database intact."""
        parsed = _parse_since("2026-03-27T11:00:00+02:00")

        assert parsed is not None
        assert _query(db, parsed) == []  # no rows seeded; the point is that it did not raise

    def test_what_the_guard_rejects_the_query_would_also_reject(self, db) -> None:
        """[Hostile] the naive value the guard refuses is exactly what the column refuses.

        This is the agreement the guard is a restatement of. If the column ever stopped caring,
        this test fails and the guard becomes over-strict — which no unit test on either side would
        notice.
        """
        naive = datetime(2026, 3, 27, 11, 0, 0)

        with pytest.raises(Exception, match="timezone-aware"):
            _query(db, naive)

    def test_the_command_never_lets_that_error_reach_the_user(self, db) -> None:
        """[Graceful degradation] end to end: the same input, through the real command.

        The unit test asserts the message. This asserts that the message is what happens *instead
        of* the SQLAlchemy failure above, with a real database underneath — the two halves of the
        claim in one place.
        """
        from tests.fixtures.db_utils import register_test_project, set_test_active_project

        register_test_project(db, "since_guard_proj", "/tmp/since-guard")
        set_test_active_project(db, "since_guard_proj")

        result = runner.invoke(app, ["usage", "--since", "2026-03-27"])

        assert result.exit_code == 1
        assert shows(result.output, "timezone")
        assert not shows(result.output, "StrictISODateTime")
        assert not shows(result.output, "Traceback")

    def test_an_aware_value_reaches_the_query_through_the_command(self, db) -> None:
        """[Boundary] the guard is not simply refusing everything with a nice message."""
        from tests.fixtures.db_utils import register_test_project, set_test_active_project

        register_test_project(db, "since_guard_proj", "/tmp/since-guard")
        set_test_active_project(db, "since_guard_proj")

        result = runner.invoke(app, ["usage", "--since", datetime.now(UTC).isoformat()])

        assert result.exit_code == 0, result.output
        assert shows(result.output, "No usage data recorded")
