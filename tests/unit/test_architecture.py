import subprocess
import tomllib
from pathlib import Path


def test_tach_architectural_boundaries() -> None:
    """
    Ensures that the Tach domain boundaries defined in tach.toml are strictly respected.
    This guarantees that the Layer Cake structure (Base -> Resource -> Capability -> Orchestrator)
    has no forbidden upstream dependencies, replacing the deleted __init__.py manual encapsulation.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    result = subprocess.run(
        ["tach", "check"],
        cwd=root_dir,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Architecture boundary violation detected by tach:\n{result.stdout}\n{result.stderr}"

def test_tach_toml_enforces_resource_layer_modules() -> None:
    """
    Ensures that tach.toml explicitly binds the core resource layer modules.
    If the configuration file loses these bounds, the CI could falsely pass without catching loose layers.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    tach_path = root_dir / "tach.toml"
    assert tach_path.exists(), "tach.toml missing from project root!"

    with tach_path.open("rb") as f:
        config = tomllib.load(f)

    modules = [mod.get("path") for mod in config.get("modules", [])]

    required_modules = [
        "src.specweaver.project",
        "src.specweaver.context",
        "src.specweaver.llm",
        "src.specweaver.api",
        "src.specweaver.cli",
    ]

    for req in required_modules:
        assert req in modules, f"Layer boundary logic missing for {req} in tach.toml!"

def test_core_layers_never_depend_on_presentation() -> None:
    """
    Critical Edge Case:
    Ensures that no lower capability/resource module explicitly adds `api` or `cli`
    to their `depends_on` graph in tach.toml. This serves as a secondary defense
    to prevent developers from silently overriding the boundary config.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    tach_path = root_dir / "tach.toml"
    
    with tach_path.open("rb") as f:
        config = tomllib.load(f)
        
    modules = config.get("modules", [])
    presentation_layers = ["src.specweaver.api", "src.specweaver.cli"]
    
    for mod in modules:
        path = mod.get("path")
        if path not in presentation_layers:
            depends_on = mod.get("depends_on", [])
            if depends_on and isinstance(depends_on[0], str):
                deps_paths = depends_on
            elif depends_on and isinstance(depends_on[0], dict):
                deps_paths = [d.get("path") for d in depends_on]
            else:
                deps_paths = []
                
            for p_layer in presentation_layers:
                assert p_layer not in deps_paths, f"CRITICAL ARCHITECTURAL VIOLATION: {path} illegally depends on {p_layer} in tach.toml!"
