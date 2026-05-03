from pathlib import Path

from specweaver.core.config.database import Database
from specweaver.interfaces.cli.settings_loader import load_settings, migrate_legacy_config


def test_migrate_legacy_config_happy_path(tmp_path: Path):
    from specweaver.core.config.cli_db_utils import bootstrap_database

    db_path = tmp_path / "specweaver.db"
    bootstrap_database(str(db_path))
    db = Database(db_path)

    project_path = tmp_path / "my_legacy_project"
    config_dir = project_path / ".specweaver"
    config_dir.mkdir(parents=True)

    config_yaml = config_dir / "config.yaml"
    config_yaml.write_text(
        """
llm:
  model: "gemini-1.5-pro"
  temperature: 0.5
""",
        encoding="utf-8",
    )

    # Run migration
    success = migrate_legacy_config(db, "my_legacy_project", str(project_path))
    assert success is True

    # Verify settings load with the migrated profile
    settings = load_settings(db, "my_legacy_project", llm_role="review")
    assert settings.llm.model == "gemini-1.5-pro"
    assert settings.llm.temperature == 0.5


def test_migrate_legacy_config_missing_file(tmp_path: Path):
    from specweaver.core.config.cli_db_utils import bootstrap_database

    db_path = tmp_path / "specweaver.db"
    bootstrap_database(str(db_path))
    db = Database(db_path)

    project_path = tmp_path / "empty_project"
    project_path.mkdir(parents=True)

    success = migrate_legacy_config(db, "empty_project", str(project_path))
    assert success is False


def test_migrate_legacy_config_degradation_corrupt_file(tmp_path: Path):
    from specweaver.core.config.cli_db_utils import bootstrap_database

    db_path = tmp_path / "specweaver.db"
    bootstrap_database(str(db_path))
    db = Database(db_path)

    project_path = tmp_path / "corrupt_project"
    config_dir = project_path / ".specweaver"
    config_dir.mkdir(parents=True)

    config_yaml = config_dir / "config.yaml"
    config_yaml.write_text(
        """
llm:
  model: [unclosed list
""",
        encoding="utf-8",
    )

    # Migration handles parsing errors gracefully and uses defaults
    success = migrate_legacy_config(db, "corrupt_project", str(project_path))
    assert success is True

    settings = load_settings(db, "corrupt_project", llm_role="review")
    # Should fall back to the system default model
    assert settings.llm.model == "gemini-2.5-pro"
