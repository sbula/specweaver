from pathlib import Path

from specweaver.core.config.database import Database
from specweaver.core.config.settings import load_settings


def test_load_settings_toml_overrides_defaults(tmp_path: Path):
    # Setup mock db and project
    db = Database(tmp_path / "specweaver.db")
    project_path = tmp_path / "my_project"
    project_path.mkdir()
    db.register_project("my_project", str(project_path))

    # Write specweaver.toml with standards best_practice
    toml_path = project_path / "specweaver.toml"
    toml_path.write_text('[standards]\nmode = "best_practice"\n', encoding="utf-8")

    # Load settings
    settings = load_settings(db, "my_project", llm_role="review")

    # Assert
    assert hasattr(settings, "standards")
    assert settings.standards.mode == "best_practice"


def test_load_settings_toml_absent_keeps_defaults(tmp_path: Path):
    db = Database(tmp_path / "specweaver.db")
    project_path = tmp_path / "my_project"
    project_path.mkdir()
    db.register_project("my_project", str(project_path))

    settings = load_settings(db, "my_project", llm_role="review")
    assert hasattr(settings, "standards")
    assert settings.standards.mode == "mimicry"
