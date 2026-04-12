# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for specweaver.core.config.paths — centralized data path resolution."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest


class TestSpecweaverRoot:
    """Test specweaver_root() resolution logic."""

    def test_default_is_home_dot_specweaver(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without env var, returns ~/.specweaver."""
        monkeypatch.delenv("SPECWEAVER_DATA_DIR", raising=False)
        from specweaver.core.config.paths import specweaver_root

        result = specweaver_root()
        assert result == Path.home() / ".specweaver"

    def test_env_var_overrides_default(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """SPECWEAVER_DATA_DIR env var takes precedence."""
        custom = tmp_path / "custom-sw"
        monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(custom))
        from specweaver.core.config.paths import specweaver_root

        result = specweaver_root()
        assert result == custom

    def test_env_var_empty_string_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty env var falls back to default."""
        monkeypatch.setenv("SPECWEAVER_DATA_DIR", "")
        from specweaver.core.config.paths import specweaver_root

        result = specweaver_root()
        assert result == Path.home() / ".specweaver"

    def test_env_var_whitespace_only_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Whitespace-only env var falls back to default."""
        monkeypatch.setenv("SPECWEAVER_DATA_DIR", "   ")
        from specweaver.core.config.paths import specweaver_root

        result = specweaver_root()
        assert result == Path.home() / ".specweaver"

    def test_returns_path_object(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Return type is always Path."""
        monkeypatch.delenv("SPECWEAVER_DATA_DIR", raising=False)
        from specweaver.core.config.paths import specweaver_root

        assert isinstance(specweaver_root(), Path)


class TestConfigDbPath:
    """Test config_db_path() returns specweaver.db under root."""

    def test_default_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPECWEAVER_DATA_DIR", raising=False)
        from specweaver.core.config.paths import config_db_path

        assert config_db_path() == Path.home() / ".specweaver" / "specweaver.db"

    def test_custom_root(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path / "data"))
        from specweaver.core.config.paths import config_db_path

        assert config_db_path() == tmp_path / "data" / "specweaver.db"


class TestStateDbPath:
    """Test state_db_path() returns pipeline_state.db under root."""

    def test_default_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPECWEAVER_DATA_DIR", raising=False)
        from specweaver.core.config.paths import state_db_path

        assert state_db_path() == Path.home() / ".specweaver" / "pipeline_state.db"

    def test_custom_root(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path / "data"))
        from specweaver.core.config.paths import state_db_path

        assert state_db_path() == tmp_path / "data" / "pipeline_state.db"


class TestLogsDir:
    """Test logs_dir() returns logs directory under root."""

    def test_default_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPECWEAVER_DATA_DIR", raising=False)
        from specweaver.core.config.paths import logs_dir

        assert logs_dir() == Path.home() / ".specweaver" / "logs"

    def test_custom_root(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path / "data"))
        from specweaver.core.config.paths import logs_dir

        assert logs_dir() == tmp_path / "data" / "logs"


class TestPathConsistency:
    """All path functions must derive from the same root."""

    def test_all_paths_share_root(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path / "shared"))
        from specweaver.core.config.paths import config_db_path, logs_dir, specweaver_root, state_db_path

        root = specweaver_root()
        assert config_db_path().parent == root
        assert state_db_path().parent == root
        assert logs_dir().parent == root
