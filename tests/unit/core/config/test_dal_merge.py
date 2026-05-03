from specweaver.commons.enums.dal import DALLevel
from tests.fixtures.db_utils import register_test_project


def test_dal_levels():
    """Verify that all DO-178C compliant DAL levels are correctly instantiated."""
    assert DALLevel.DAL_A == "DAL_A"
    assert DALLevel.DAL_B == "DAL_B"
    assert DALLevel.DAL_C == "DAL_C"
    assert DALLevel.DAL_D == "DAL_D"
    assert DALLevel.DAL_E == "DAL_E"

    # Ensure they can be iterated
    levels = list(DALLevel)
    assert len(levels) == 5
    assert DALLevel.DAL_A in levels


def test_deep_merge_dict():
    """Verify recursive merging logic for configuration dicts."""
    from specweaver.core.config.settings import deep_merge_dict

    base = {"A": 1, "nested": {"B": 2, "deep": {"x": 100}}}
    overlay = {"nested": {"C": 3, "deep": {"x": 999, "y": 200}}, "D": 4}

    result = deep_merge_dict(base, overlay)

    # Primitives merged at root
    assert result["A"] == 1
    assert result["D"] == 4

    # Nested merged safely
    assert result["nested"]["B"] == 2
    assert result["nested"]["C"] == 3

    # Deeply nested merged
    assert result["nested"]["deep"]["x"] == 999  # Overwritten
    assert result["nested"]["deep"]["y"] == 200  # Added


def test_dal_impact_matrix(tmp_path):
    """Verify loading and deep merging of DAL rulesets via load_settings()."""
    import yaml

    from specweaver.commons.enums.dal import DALLevel
    from specweaver.core.config.cli_db_utils import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.core.config.settings import DALImpactMatrix
    from specweaver.core.config.settings_loader import load_settings

    bootstrap_database(str(tmp_path / "test.db"))
    db = Database(tmp_path / "test.db")

    # Register dummy project pointing to our tmp_path
    register_test_project(db, "dummy", str(tmp_path))

    # 1. Create a dummy base structure? Or just assume empty base merges overlay cleanly.
    # Write the project dal_definitions.yaml
    sw_dir = tmp_path / ".specweaver"
    sw_dir.mkdir()

    # Override S01 explicitly for DAL_E to be completely disabled
    overlay = {
        "matrix": {
            "DAL_E": {"overrides": {"S01": {"rule_id": "S01", "enabled": False}}},
            "DAL_A": {"overrides": {"S01": {"rule_id": "S01", "warn_threshold": 0.99}}},
        }
    }

    dal_file = sw_dir / "dal_definitions.yaml"
    dal_file.write_text(yaml.dump(overlay))

    settings = load_settings(db, "dummy")

    # Assert DAL Matrix was parsed & attached
    assert hasattr(settings, "dal_matrix")
    matrix = settings.dal_matrix
    assert isinstance(matrix, DALImpactMatrix)

    # Verify DAL_E has S01 disabled
    dal_e_settings = matrix.matrix[DALLevel.DAL_E]
    assert dal_e_settings.get_override("S01").enabled is False
    assert dal_e_settings.is_enabled("S01") is False

    # Verify DAL_A retains S01 enabled but threshold updated
    dal_a_settings = matrix.matrix[DALLevel.DAL_A]
    assert dal_a_settings.get_override("S01").warn_threshold == 0.99
    assert dal_a_settings.is_enabled("S01") is True


def test_load_settings_missing_dal_file(tmp_path):
    """Verify load_settings() gracefully skips missing dal_definitions.yaml."""
    from specweaver.core.config.cli_db_utils import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.core.config.settings import DALImpactMatrix
    from specweaver.core.config.settings_loader import load_settings

    bootstrap_database(str(tmp_path / "test.db"))
    db = Database(tmp_path / "test.db")
    register_test_project(db, "dummy", str(tmp_path))

    settings = load_settings(db, "dummy")

    # Assert matrix is initialized but empty
    assert isinstance(settings.dal_matrix, DALImpactMatrix)
    assert len(settings.dal_matrix.matrix) == 0


def test_load_settings_invalid_yaml(tmp_path):
    """Verify load_settings() gracefully swallows fundamentally invalid YAML."""
    from specweaver.core.config.cli_db_utils import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.core.config.settings import DALImpactMatrix
    from specweaver.core.config.settings_loader import load_settings

    bootstrap_database(str(tmp_path / "test.db"))
    db = Database(tmp_path / "test.db")
    register_test_project(db, "dummy", str(tmp_path))

    sw_dir = tmp_path / ".specweaver"
    sw_dir.mkdir()
    dal_file = sw_dir / "dal_definitions.yaml"
    dal_file.write_text("matrix:\n  - DAL_A:\n    [this is broken yaml]\n ::")

    settings = load_settings(db, "dummy")

    # Assert matrix degrades to empty gracefully
    assert isinstance(settings.dal_matrix, DALImpactMatrix)
    assert len(settings.dal_matrix.matrix) == 0


def test_load_settings_invalid_schema(tmp_path):
    """Verify load_settings() swallows Pydantic schema validation failures."""
    import yaml

    from specweaver.core.config.cli_db_utils import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.core.config.settings import DALImpactMatrix
    from specweaver.core.config.settings_loader import load_settings

    bootstrap_database(str(tmp_path / "test.db"))
    db = Database(tmp_path / "test.db")
    register_test_project(db, "dummy", str(tmp_path))

    sw_dir = tmp_path / ".specweaver"
    sw_dir.mkdir()

    # Provide a string where a bool (enabled) is expected
    overlay = {
        "matrix": {"DAL_E": {"overrides": {"S01": {"rule_id": "S01", "enabled": "not_a_boolean"}}}}
    }

    dal_file = sw_dir / "dal_definitions.yaml"
    dal_file.write_text(yaml.dump(overlay))

    settings = load_settings(db, "dummy")

    # Assert matrix degrades to empty gracefully due to Pydantic exception inside try/except
    assert isinstance(settings.dal_matrix, DALImpactMatrix)
    assert len(settings.dal_matrix.matrix) == 0
