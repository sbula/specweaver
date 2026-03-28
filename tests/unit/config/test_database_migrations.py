# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for database schema migrations (v2-v7)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Return a temporary DB path (file does not exist yet)."""
    return tmp_path / ".specweaver" / "specweaver.db"


@pytest.fixture()
def db(db_path: Path):
    """Create a fresh database and return its Database instance."""
    from specweaver.config.database import Database

    return Database(db_path)


# ---------------------------------------------------------------------------
# Schema v2 migration — context_limit
# ---------------------------------------------------------------------------


class TestSchemaV2Migration:
    """Test the v1→v2 schema migration (context_limit column)."""

    def test_context_limit_column_exists(self, db):
        """context_limit column is present after migration."""
        with db.connect() as conn:
            row = conn.execute(
                "SELECT context_limit FROM llm_profiles WHERE name='review'"
            ).fetchone()
        assert row is not None

    def test_context_limit_default_value(self, db):
        """Default context_limit is 128000."""
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT context_limit FROM llm_profiles"
            ).fetchall()
        for row in rows:
            assert row[0] == 128_000

    def test_v1_to_v2_upgrade(self, db_path: Path):
        """Simulate a v1 DB and verify v2 migration applies correctly."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import _SCHEMA_V1, Database

        # Create a v1-only DB manually (without v2 migration)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (1, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO llm_profiles "
            "(name, is_global, model, temperature, max_output_tokens, response_format) "
            "VALUES ('review', 1, 'gemini-2.5-flash', 0.3, 4096, 'text')"
        )
        conn.commit()
        conn.close()

        # Now open with Database — should apply v2 migration
        db = Database(db_path)
        with db.connect() as conn2:
            row = conn2.execute(
                "SELECT context_limit FROM llm_profiles WHERE name='review'"
            ).fetchone()
            version = conn2.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()

        assert row[0] == 128_000  # default from ALTER TABLE
        assert version[0] == 10  # V2, V3, V4, V5, V6, V7, V8 all applied

    def test_idempotent_v2_migration(self, db_path: Path):
        """Running Database() twice doesn't fail on duplicate ALTER TABLE."""
        from specweaver.config.database import Database

        Database(db_path)
        db2 = Database(db_path)  # should not raise
        with db2.connect() as conn:
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
        assert version[0] == 10  # V2, V3, V4, V5, V6, V7, V8 all applied


# ---------------------------------------------------------------------------
# Validation Override UPSERT edge cases
# ---------------------------------------------------------------------------


class TestValidationOverrideUpsert:
    """Edge cases for set_validation_override partial-update logic."""

    def test_load_validation_settings_no_overrides(self, db, tmp_path: Path):
        """Project with zero overrides returns empty ValidationSettings."""
        db.register_project("clean", str(tmp_path / "clean"))
        settings = db.load_validation_settings("clean")
        assert settings.overrides == {}

    def test_set_and_load_override(self, db, tmp_path: Path):
        """Set an override, then load it back."""
        db.register_project("proj", str(tmp_path / "proj"))
        db.set_validation_override(
            "proj", "S01",
            enabled=True, warn_threshold=5.0, fail_threshold=3.0,
        )
        settings = db.load_validation_settings("proj")
        assert "S01" in settings.overrides
        assert settings.overrides["S01"].warn_threshold == 5.0
        assert settings.overrides["S01"].fail_threshold == 3.0

    def test_partial_update_preserves_existing(self, db, tmp_path: Path):
        """Updating only warn_threshold should preserve fail_threshold."""
        db.register_project("proj", str(tmp_path / "proj"))
        db.set_validation_override(
            "proj", "S02",
            enabled=True, warn_threshold=8.0, fail_threshold=5.0,
        )
        # Update only warn_threshold
        db.set_validation_override("proj", "S02", warn_threshold=6.0)
        settings = db.load_validation_settings("proj")
        override = settings.overrides["S02"]
        assert override.warn_threshold == 6.0
        assert override.fail_threshold == 5.0  # preserved

    def test_disable_rule(self, db, tmp_path: Path):
        """Can disable a rule via override."""
        db.register_project("proj", str(tmp_path / "proj"))
        db.set_validation_override("proj", "S03", enabled=False)
        settings = db.load_validation_settings("proj")
        assert settings.overrides["S03"].enabled is False

    def test_is_enabled_defaults_true(self, db, tmp_path: Path):
        """Rules without overrides default to enabled."""
        db.register_project("proj", str(tmp_path / "proj"))
        settings = db.load_validation_settings("proj")
        assert settings.is_enabled("S99") is True


# ---------------------------------------------------------------------------
# Schema v3 migration — log_level column
# ---------------------------------------------------------------------------


class TestSchemaV3Migration:
    """Test the v2→v3 schema migration (log_level column on projects)."""

    def test_log_level_column_exists(self, db, tmp_path: Path):
        """log_level column is present after migration."""
        db.register_project("myapp", str(tmp_path))
        with db.connect() as conn:
            row = conn.execute(
                "SELECT log_level FROM projects WHERE name='myapp'"
            ).fetchone()
        assert row is not None

    def test_log_level_default_is_debug(self, db, tmp_path: Path):
        """Default log_level is DEBUG."""
        db.register_project("myapp", str(tmp_path))
        assert db.get_log_level("myapp") == "DEBUG"

    def test_get_log_level_nonexistent_project_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.get_log_level("nonexistent")

    def test_set_log_level(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_log_level("myapp", "WARNING")
        assert db.get_log_level("myapp") == "WARNING"

    def test_set_log_level_case_insensitive(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_log_level("myapp", "info")
        assert db.get_log_level("myapp") == "INFO"

    def test_set_log_level_invalid_raises(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        with pytest.raises(ValueError, match="Invalid log level"):
            db.set_log_level("myapp", "VERBOSE")

    def test_set_log_level_nonexistent_project_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.set_log_level("nonexistent", "DEBUG")

    def test_all_valid_levels(self, db, tmp_path: Path):
        """All 5 standard levels can be set and retrieved."""
        db.register_project("myapp", str(tmp_path))
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            db.set_log_level("myapp", level)
            assert db.get_log_level("myapp") == level

    def test_v2_to_v3_upgrade(self, db_path: Path):
        """Simulate a v2 DB and verify v3 migration applies correctly."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import _SCHEMA_V1, _SCHEMA_V2, Database

        # Create a v2-only DB manually
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) "
            "VALUES (2, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO projects (name, root_path, created_at, last_used_at) "
            "VALUES ('legacy', '/tmp/legacy', '2026-01-01', '2026-01-01')"
        )
        conn.commit()
        conn.close()

        # Open with Database — should apply v3 migration
        db = Database(db_path)
        assert db.get_log_level("legacy") == "DEBUG"  # default from ALTER
        with db.connect() as conn2:
            version = conn2.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
        assert version[0] == 10  # v3, v4, v5, v6, v7, v8 all applied


# ---------------------------------------------------------------------------
# Schema v4 migration — constitution_max_size column
# ---------------------------------------------------------------------------


class TestSchemaV4Migration:
    """Test the v3→v4 schema migration (constitution_max_size on projects)."""

    def test_constitution_max_size_column_exists(self, db, tmp_path: Path):
        """constitution_max_size column is present after migration."""
        db.register_project("myapp", str(tmp_path))
        with db.connect() as conn:
            row = conn.execute(
                "SELECT constitution_max_size FROM projects WHERE name='myapp'"
            ).fetchone()
        assert row is not None

    def test_constitution_max_size_default_is_5120(self, db, tmp_path: Path):
        """Default constitution_max_size is 5120 (5 KB)."""
        db.register_project("myapp", str(tmp_path))
        assert db.get_constitution_max_size("myapp") == 5120

    def test_get_constitution_max_size_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.get_constitution_max_size("nonexistent")

    def test_set_constitution_max_size(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_constitution_max_size("myapp", 8192)
        assert db.get_constitution_max_size("myapp") == 8192

    def test_set_constitution_max_size_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.set_constitution_max_size("nonexistent", 8192)

    def test_set_constitution_max_size_zero_raises(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        with pytest.raises(ValueError, match=r"[Ii]nvalid.*size|must be positive"):
            db.set_constitution_max_size("myapp", 0)

    def test_schema_version_is_4(self, db):
        """Schema version is at least 4 after v4 migration (v5 also applied)."""
        with db.connect() as conn:
            row = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            assert row[0] >= 4

    def test_set_constitution_max_size_negative_raises(self, db, tmp_path: Path):
        """Negative constitution_max_size is rejected."""
        db.register_project("myapp", str(tmp_path))
        with pytest.raises(ValueError, match=r"[Ii]nvalid.*size|must be positive"):
            db.set_constitution_max_size("myapp", -100)

    def test_set_constitution_max_size_to_one(self, db, tmp_path: Path):
        """Setting constitution_max_size to 1 succeeds (minimum valid)."""
        db.register_project("myapp", str(tmp_path))
        db.set_constitution_max_size("myapp", 1)
        assert db.get_constitution_max_size("myapp") == 1

    def test_constitution_max_size_persists_across_connections(self, db, tmp_path: Path):
        """constitution_max_size value survives reconnection."""
        db.register_project("myapp", str(tmp_path))
        db.set_constitution_max_size("myapp", 10240)

        # Re-open database (simulates restart)
        from specweaver.config.database import Database

        db2 = Database(db._db_path)
        assert db2.get_constitution_max_size("myapp") == 10240


class TestSchemaV3ToV4Upgrade:
    """Simulate opening a v3-only DB and verify v4 migration kicks in."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v3_v4.db"

    def test_v3_to_v4_upgrade(self, db_path: Path):
        """Simulate a v3 DB and verify v4 migration applies correctly."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            Database,
        )

        # Create a v3-only DB manually (no v4 migration)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) "
            "VALUES (3, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO projects (name, root_path, created_at, last_used_at, log_level) "
            "VALUES ('legacy', '/tmp/legacy', '2026-01-01', '2026-01-01', 'INFO')"
        )
        conn.commit()
        conn.close()

        # Open with Database — should apply v4 migration
        db = Database(db_path)
        assert db.get_constitution_max_size("legacy") == 5120  # default from ALTER
        assert db.get_log_level("legacy") == "INFO"  # preserved from v3
        with db.connect() as conn2:
            version = conn2.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
        assert version[0] == 10  # v4, v5, v6, v7, v8 all applied


# ===========================================================================
# Domain Profile Methods (Feature 3.3)
# ===========================================================================


class TestDomainProfile:
    """Tests for domain profile storage and application."""

    def test_get_domain_profile_default_is_none(self, db, tmp_path: Path):
        """New project has no domain profile set."""
        db.register_project("myapp", str(tmp_path))
        assert db.get_domain_profile("myapp") is None

    def test_set_and_get_domain_profile(self, db, tmp_path: Path):
        """Setting a profile stores the name."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")
        assert db.get_domain_profile("myapp") == "web-app"

    def test_set_domain_profile_overwrites_previous(self, db, tmp_path: Path):
        """Setting a new profile replaces the previous one."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")
        db.set_domain_profile("myapp", "library")
        assert db.get_domain_profile("myapp") == "library"

    def test_clear_domain_profile(self, db, tmp_path: Path):
        """Clearing the profile resets to None."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")
        db.clear_domain_profile("myapp")
        assert db.get_domain_profile("myapp") is None

    def test_set_domain_profile_does_not_write_overrides(
        self, db, tmp_path: Path,
    ):
        """set_domain_profile MUST NOT write validation_overrides rows.

        Profile = pipeline YAML selector only. Per-rule DB overrides are
        a separate layer managed via 'sw config set <RULE>'.
        """
        db.register_project("myapp", str(tmp_path))
        # Set some overrides manually FIRST
        db.set_validation_override("myapp", "S08", warn_threshold=99)
        db.set_validation_override("myapp", "C04", fail_threshold=99)
        assert len(db.get_validation_overrides("myapp")) == 2

        # Apply profile — must NOT change or clear existing overrides
        db.set_domain_profile("myapp", "web-app")
        overrides = db.get_validation_overrides("myapp")
        assert len(overrides) == 2  # unchanged — profile didn't touch overrides
        assert overrides[0]["rule_id"] in {"S08", "C04"}

    def test_set_domain_profile_does_not_clear_previous_overrides(
        self, db, tmp_path: Path,
    ):
        """Switching profiles preserves all per-rule DB overrides."""
        db.register_project("myapp", str(tmp_path))
        db.set_validation_override("myapp", "S11", warn_threshold=5)
        db.set_domain_profile("myapp", "web-app")
        db.set_domain_profile("myapp", "library")
        # S11 override must still be there (profile switch doesn't touch DB overrides)
        overrides = db.get_validation_overrides("myapp")
        assert any(o["rule_id"] == "S11" for o in overrides)

    def test_clear_domain_profile_preserves_overrides(
        self, db, tmp_path: Path,
    ):
        """clear_domain_profile only clears the profile name, not overrides."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")
        db.set_validation_override("myapp", "S08", fail_threshold=3)
        assert len(db.get_validation_overrides("myapp")) == 1

        db.clear_domain_profile("myapp")
        # Profile is cleared
        assert db.get_domain_profile("myapp") is None
        # But the per-rule override is preserved!
        overrides = db.get_validation_overrides("myapp")
        assert len(overrides) == 1
        assert overrides[0]["rule_id"] == "S08"

    def test_set_domain_profile_unknown_raises(self, db, tmp_path: Path):
        """Setting an unknown profile name raises ValueError."""
        db.register_project("myapp", str(tmp_path))
        with pytest.raises(ValueError, match=r"[Uu]nknown.*profile"):
            db.set_domain_profile("myapp", "quantum-computing")

    def test_set_domain_profile_unregistered_project_raises(self, db):
        """Setting a profile on an unregistered project raises ValueError."""
        with pytest.raises(ValueError, match=r"not found"):
            db.set_domain_profile("nonexistent", "web-app")

    def test_domain_profile_persists_across_connections(self, db, tmp_path: Path):
        """domain_profile value survives reconnection."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "data-pipeline")

        from specweaver.config.database import Database

        db2 = Database(db._db_path)
        assert db2.get_domain_profile("myapp") == "data-pipeline"

    def test_get_domain_profile_unregistered_raises(self, db):
        """Getting profile on unregistered project raises ValueError."""
        with pytest.raises(ValueError, match=r"not found"):
            db.get_domain_profile("nonexistent")

    def test_clear_domain_profile_unregistered_raises(self, db):
        """Clearing profile on unregistered project raises ValueError."""
        with pytest.raises(ValueError, match=r"not found"):
            db.clear_domain_profile("nonexistent")

    def test_clear_domain_profile_idempotent(self, db, tmp_path: Path):
        """Clearing when no profile is set is idempotent (no error)."""
        db.register_project("myapp", str(tmp_path))
        db.clear_domain_profile("myapp")  # should not raise
        assert db.get_domain_profile("myapp") is None

    def test_set_domain_profile_case_insensitive(self, db, tmp_path: Path):
        """Profile name is accepted case-insensitively (stored normalised)."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "WEB-APP")
        # The profile is stored (case-insensitive lookup succeeded)
        assert db.get_domain_profile("myapp") == "WEB-APP"

    def test_schema_version_is_latest(self, db):
        """Schema version is 9 after all migrations."""
        with db.connect() as conn:
            row = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            assert row[0] == 10


class TestSchemaV4ToV5Upgrade:
    """Simulate opening a v4-only DB and verify v5 migration kicks in."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v4_v5.db"

    def test_v4_to_v5_upgrade(self, db_path: Path):
        """Simulate a v4 DB and verify v5 migration applies correctly."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            _SCHEMA_V4,
            Database,
        )

        # Create a v4-only DB manually (no v5 migration)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.executescript(_SCHEMA_V4)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) "
            "VALUES (4, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO projects (name, root_path, created_at, last_used_at, "
            "log_level, constitution_max_size) "
            "VALUES ('legacy', '/tmp/legacy', '2026-01-01', '2026-01-01', "
            "'INFO', 5120)"
        )
        conn.commit()
        conn.close()

        # Open with Database — should apply v5 migration
        db = Database(db_path)
        assert db.get_domain_profile("legacy") is None  # default
        assert db.get_constitution_max_size("legacy") == 5120  # preserved
        with db.connect() as conn2:
            version = conn2.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
        assert version[0] == 10  # v5, v6, v7, v8 all applied


# ===========================================================================
# Schema v7 — auto_bootstrap_constitution
# ===========================================================================


class TestSchemaV7AutoBootstrap:
    """Tests for auto_bootstrap_constitution column and accessors."""

    def test_auto_bootstrap_default_is_prompt(self, db, tmp_path: Path):
        """Default auto_bootstrap_constitution is 'prompt'."""
        db.register_project("myapp", str(tmp_path))
        assert db.get_auto_bootstrap("myapp") == "prompt"

    def test_set_auto_bootstrap_off(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_auto_bootstrap("myapp", "off")
        assert db.get_auto_bootstrap("myapp") == "off"

    def test_set_auto_bootstrap_auto(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_auto_bootstrap("myapp", "auto")
        assert db.get_auto_bootstrap("myapp") == "auto"

    def test_set_auto_bootstrap_prompt(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_auto_bootstrap("myapp", "off")
        db.set_auto_bootstrap("myapp", "prompt")
        assert db.get_auto_bootstrap("myapp") == "prompt"

    def test_set_auto_bootstrap_case_insensitive(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_auto_bootstrap("myapp", "AUTO")
        assert db.get_auto_bootstrap("myapp") == "auto"

    def test_set_auto_bootstrap_invalid_raises(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        with pytest.raises(ValueError, match=r"Invalid auto-bootstrap mode"):
            db.set_auto_bootstrap("myapp", "always")

    def test_get_auto_bootstrap_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match=r"not found"):
            db.get_auto_bootstrap("nonexistent")

    def test_set_auto_bootstrap_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match=r"not found"):
            db.set_auto_bootstrap("nonexistent", "off")

    def test_auto_bootstrap_persists_across_connections(self, db, tmp_path: Path):
        db.register_project("myapp", str(tmp_path))
        db.set_auto_bootstrap("myapp", "auto")

        from specweaver.config.database import Database

        db2 = Database(db._db_path)
        assert db2.get_auto_bootstrap("myapp") == "auto"


class TestSchemaV6ToV7Upgrade:
    """Simulate opening a v6-only DB and verify v7 migration kicks in."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v6_v7.db"

    def test_v6_to_v7_upgrade(self, db_path: Path):
        """Simulate a v6 DB and verify v7 migration applies correctly."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            _SCHEMA_V4,
            _SCHEMA_V5,
            _SCHEMA_V6,
            Database,
        )

        # Create a v6-only DB manually (no v7 migration)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.executescript(_SCHEMA_V4)
        conn.executescript(_SCHEMA_V5)
        conn.executescript(_SCHEMA_V6)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) "
            "VALUES (6, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO projects (name, root_path, created_at, last_used_at, "
            "log_level, constitution_max_size, domain_profile) "
            "VALUES ('legacy', '/tmp/legacy', '2026-01-01', '2026-01-01', "
            "'INFO', 5120, NULL)"
        )
        conn.commit()
        conn.close()

        # Open with Database — should apply v7 migration
        db = Database(db_path)
        assert db.get_auto_bootstrap("legacy") == "prompt"  # default
        assert db.get_log_level("legacy") == "INFO"  # preserved
        assert db.get_constitution_max_size("legacy") == 5120  # preserved
        with db.connect() as conn2:
            version = conn2.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
        assert version[0] == 10


class TestSchemaV7ToV8Upgrade:
    """Simulate opening a v7-only DB and verify v8 migration kicks in."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v7_v8.db"

    def test_v7_to_v8_upgrade(self, db_path: Path):
        """Simulate a v7 DB and verify v8 migration applies correctly."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            _SCHEMA_V4,
            _SCHEMA_V5,
            _SCHEMA_V6,
            _SCHEMA_V7,
            Database,
        )

        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.executescript(_SCHEMA_V4)
        conn.executescript(_SCHEMA_V5)
        conn.executescript(_SCHEMA_V6)
        conn.executescript(_SCHEMA_V7)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) "
            "VALUES (7, '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO projects (name, root_path, created_at, last_used_at, "
            "log_level, constitution_max_size, domain_profile, auto_bootstrap_constitution) "
            "VALUES ('legacy', '/tmp/legacy', '2026-01-01', '2026-01-01', "
            "'INFO', 5120, NULL, 'prompt')"
        )
        conn.commit()
        conn.close()

        # Open with Database — should apply v8 migration
        db = Database(db_path)
        assert db.get_stitch_mode("legacy") == "off"  # default from ALTER
        with db.connect() as conn2:
            version = conn2.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
        assert version[0] == 10


class TestSchemaV8ToV9Upgrade:
    """Simulate opening a v8-only DB and verify v9 migration kicks in."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v8_v9.db"

    def test_v8_to_v9_upgrade(self, db_path: Path):
        """Simulate a v8 DB and verify v9 migration creates usage tables."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            _SCHEMA_V4,
            _SCHEMA_V5,
            _SCHEMA_V6,
            _SCHEMA_V7,
            _SCHEMA_V8,
            Database,
        )

        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.executescript(_SCHEMA_V4)
        conn.executescript(_SCHEMA_V5)
        conn.executescript(_SCHEMA_V6)
        conn.executescript(_SCHEMA_V7)
        conn.executescript(_SCHEMA_V8)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) "
            "VALUES (8, '2026-01-01T00:00:00Z')"
        )
        conn.commit()
        conn.close()

        db = Database(db_path)
        with db.connect() as conn2:
            version = conn2.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
            tables = conn2.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('llm_usage_log', 'llm_cost_overrides')"
            ).fetchall()
        assert version[0] == 10
        table_names = {r[0] for r in tables}
        assert "llm_usage_log" in table_names
        assert "llm_cost_overrides" in table_names


class TestUsageLogCrud:
    """Tests for log_usage() and query methods."""

    def test_log_usage_insert(self, db):
        db.log_usage({
            "timestamp": "2026-03-27T00:00:00Z",
            "project_name": "proj",
            "task_type": "draft",
            "model": "gemini-3-flash-preview",
            "provider": "gemini",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "estimated_cost_usd": 0.0003,
            "duration_ms": 500,
        })
        with db.connect() as conn:
            rows = conn.execute("SELECT * FROM llm_usage_log").fetchall()
        assert len(rows) == 1
        assert rows[0]["model"] == "gemini-3-flash-preview"

    def test_log_usage_multiple_rows(self, db):
        for i in range(3):
            db.log_usage({
                "timestamp": f"2026-03-27T00:0{i}:00Z",
                "project_name": "proj",
                "task_type": "review",
                "model": "model-x",
                "provider": "p",
            })
        with db.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM llm_usage_log").fetchone()[0]
        assert count == 3

    def test_get_usage_summary_all(self, db):
        db.log_usage({
            "timestamp": "2026-03-27T00:00:00Z",
            "project_name": "p1",
            "task_type": "draft",
            "model": "model-a",
            "provider": "x",
            "total_tokens": 100,
            "estimated_cost_usd": 0.01,
        })
        db.log_usage({
            "timestamp": "2026-03-27T00:01:00Z",
            "project_name": "p1",
            "task_type": "draft",
            "model": "model-a",
            "provider": "x",
            "total_tokens": 200,
            "estimated_cost_usd": 0.02,
        })
        result = db.get_usage_summary()
        assert len(result) == 1
        assert result[0]["call_count"] == 2
        assert result[0]["total_tokens"] == 300

    def test_get_usage_summary_filtered_by_project(self, db):
        db.log_usage({"timestamp": "2026-03-27T00:00:00Z", "project_name": "p1",
                      "task_type": "draft", "model": "m", "provider": "x"})
        db.log_usage({"timestamp": "2026-03-27T00:01:00Z", "project_name": "p2",
                      "task_type": "draft", "model": "m", "provider": "x"})
        result = db.get_usage_summary(project="p1")
        assert len(result) == 1
        assert result[0]["call_count"] == 1

    def test_get_usage_by_task_type(self, db):
        db.log_usage({"timestamp": "2026-03-27T00:00:00Z", "project_name": "p1",
                      "task_type": "draft", "model": "m", "provider": "x",
                      "total_tokens": 100, "estimated_cost_usd": 0.01})
        db.log_usage({"timestamp": "2026-03-27T00:01:00Z", "project_name": "p1",
                      "task_type": "review", "model": "m", "provider": "x",
                      "total_tokens": 200, "estimated_cost_usd": 0.03})
        result = db.get_usage_by_task_type("p1")
        assert len(result) == 2
        types = {r["task_type"] for r in result}
        assert types == {"draft", "review"}

    def test_get_usage_summary_empty(self, db):
        assert db.get_usage_summary() == []


class TestCostOverrideCrud:
    """Tests for cost override CRUD methods."""

    def test_get_cost_overrides_empty(self, db):
        assert db.get_cost_overrides() == {}

    def test_set_and_get_override(self, db):
        db.set_cost_override("gpt-4o", 0.005, 0.015)
        overrides = db.get_cost_overrides()
        assert "gpt-4o" in overrides
        assert overrides["gpt-4o"] == (0.005, 0.015)

    def test_override_upsert(self, db):
        db.set_cost_override("gpt-4o", 0.005, 0.015)
        db.set_cost_override("gpt-4o", 0.010, 0.030)
        overrides = db.get_cost_overrides()
        assert overrides["gpt-4o"] == (0.010, 0.030)

    def test_delete_override(self, db):
        db.set_cost_override("gpt-4o", 0.005, 0.015)
        db.delete_cost_override("gpt-4o")
        assert db.get_cost_overrides() == {}

    def test_delete_nonexistent_is_noop(self, db):
        db.delete_cost_override("nonexistent")  # Should not raise

    def test_multiple_overrides(self, db):
        db.set_cost_override("gpt-4o", 0.005, 0.015)
        db.set_cost_override("claude-3", 0.003, 0.012)
        overrides = db.get_cost_overrides()
        assert len(overrides) == 2


# ---------------------------------------------------------------------------
# Stories 1, 20, 21: Usage log gap tests
# ---------------------------------------------------------------------------


class TestUsageLogGaps:
    """Additional DB mixin tests for uncovered scenarios."""

    @pytest.fixture()
    def db(self, tmp_path: Path):
        from specweaver.config.database import Database

        return Database(tmp_path / ".specweaver" / "specweaver.db")

    def test_get_usage_summary_since_filter(self, db):
        """Story 1: get_usage_summary filters by 'since' timestamp."""
        db.log_usage({"timestamp": "2026-03-01T00:00:00Z", "project_name": "p1",
                      "task_type": "draft", "model": "m", "provider": "x",
                      "total_tokens": 100, "estimated_cost_usd": 0.01})
        db.log_usage({"timestamp": "2026-03-20T00:00:00Z", "project_name": "p1",
                      "task_type": "draft", "model": "m", "provider": "x",
                      "total_tokens": 200, "estimated_cost_usd": 0.02})
        result = db.get_usage_summary(since="2026-03-15T00:00:00Z")
        assert len(result) == 1
        assert result[0]["call_count"] == 1
        assert result[0]["total_tokens"] == 200

    def test_get_usage_summary_combined_project_and_since(self, db):
        """Story 20: both project AND since filters applied together."""
        db.log_usage({"timestamp": "2026-03-01T00:00:00Z", "project_name": "p1",
                      "task_type": "draft", "model": "m", "provider": "x"})
        db.log_usage({"timestamp": "2026-03-20T00:00:00Z", "project_name": "p1",
                      "task_type": "draft", "model": "m", "provider": "x"})
        db.log_usage({"timestamp": "2026-03-20T00:00:00Z", "project_name": "p2",
                      "task_type": "draft", "model": "m", "provider": "x"})

        result = db.get_usage_summary(project="p1", since="2026-03-15T00:00:00Z")
        assert len(result) == 1
        assert result[0]["call_count"] == 1  # Only p1 after cutoff

    def test_log_usage_missing_optional_keys_uses_defaults(self, db):
        """Story 21: log_usage with only required keys — optionals default to 0."""
        db.log_usage({
            "timestamp": "2026-03-27T00:00:00Z",
            "project_name": "proj",
            "task_type": "draft",
            "model": "m",
            "provider": "x",
            # No prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd, duration_ms
        })
        with db.connect() as conn:
            row = conn.execute("SELECT * FROM llm_usage_log").fetchone()
        assert row["prompt_tokens"] == 0
        assert row["completion_tokens"] == 0
        assert row["total_tokens"] == 0
        assert row["estimated_cost"] == 0.0
        assert row["duration_ms"] == 0


# ===========================================================================
# Schema v10 — provider column on llm_profiles
# ===========================================================================


class TestSchemaV10Migration:
    """Test the v9→v10 migration (provider column on llm_profiles)."""

    @pytest.fixture()
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "upgrade_v9_v10.db"

    def test_provider_column_exists(self, db):
        """provider column is present on llm_profiles after migration."""
        with db.connect() as conn:
            row = conn.execute(
                "SELECT provider FROM llm_profiles WHERE name='review'"
            ).fetchone()
        assert row is not None

    def test_provider_default_is_gemini(self, db):
        """Default provider on seed profiles is 'gemini'."""
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT provider FROM llm_profiles"
            ).fetchall()
        for row in rows:
            assert row[0] == "gemini"

    def test_create_profile_with_provider(self, db):
        """create_llm_profile accepts provider parameter."""
        profile_id = db.create_llm_profile(
            "openai-draft",
            model="gpt-4o",
            provider="openai",
        )
        profile = db.get_llm_profile(profile_id)
        assert profile["provider"] == "openai"

    def test_create_profile_provider_defaults_to_gemini(self, db):
        """create_llm_profile defaults provider to 'gemini'."""
        profile_id = db.create_llm_profile(
            "legacy-profile",
            model="gemini-2.0-flash",
        )
        profile = db.get_llm_profile(profile_id)
        assert profile["provider"] == "gemini"

    def test_default_profiles_include_provider(self, db):
        """Seed DEFAULT_PROFILES include provider='gemini' for all entries."""
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT name, provider FROM llm_profiles WHERE is_global = 1"
            ).fetchall()
        assert len(rows) >= 4
        for row in rows:
            assert row["provider"] == "gemini"

    def test_schema_version_is_10(self, db):
        """Schema version is 10 after all migrations."""
        with db.connect() as conn:
            row = conn.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()
        assert row[0] == 10

    def test_v9_to_v10_upgrade(self, db_path: Path):
        """Simulate a v9 DB and verify v10 migration adds provider column."""
        import sqlite3 as _sqlite3

        from specweaver.config.database import (
            _SCHEMA_V1,
            _SCHEMA_V2,
            _SCHEMA_V3,
            _SCHEMA_V4,
            _SCHEMA_V5,
            _SCHEMA_V6,
            _SCHEMA_V7,
            _SCHEMA_V8,
            _SCHEMA_V9,
            Database,
        )

        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(db_path))
        conn.executescript(_SCHEMA_V1)
        conn.executescript(_SCHEMA_V2)
        conn.executescript(_SCHEMA_V3)
        conn.executescript(_SCHEMA_V4)
        conn.executescript(_SCHEMA_V5)
        conn.executescript(_SCHEMA_V6)
        conn.executescript(_SCHEMA_V7)
        conn.executescript(_SCHEMA_V8)
        conn.executescript(_SCHEMA_V9)
        conn.execute(
            "INSERT INTO schema_version (version, applied_at) "
            "VALUES (9, '2026-01-01T00:00:00Z')"
        )
        # Insert a v9 profile (no provider column)
        conn.execute(
            "INSERT INTO llm_profiles "
            "(name, is_global, model, temperature, max_output_tokens, "
            "response_format, context_limit) "
            "VALUES ('review', 1, 'gemini-2.5-flash', 0.3, 4096, 'text', 128000)"
        )
        conn.commit()
        conn.close()

        db = Database(db_path)
        with db.connect() as conn2:
            row = conn2.execute(
                "SELECT provider FROM llm_profiles WHERE name='review'"
            ).fetchone()
            version = conn2.execute(
                "SELECT MAX(version) FROM schema_version"
            ).fetchone()

        assert row[0] == "gemini"  # default from ALTER TABLE
        assert version[0] == 10

