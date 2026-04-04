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



def test_tach_interfaces_map_to_valid_namespaces() -> None:
    """
    Edge Case: Prevention of Silent Namespace Ignore by Tach.
    Since __init__.py files were deleted (SF-4), these directories became Implicit Namespace Packages.
    Tach might silently skip checking a route if the dir has no __init__.py and doesn't map correctly.
    We formally assert that every path declared in [[interfaces]] exists as a physical directory or file.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    tach_path = root_dir / "tach.toml"
    assert tach_path.exists()

    with tach_path.open("rb") as f:
        config = tomllib.load(f)

    for interface in config.get("interfaces", []):
        module_base = interface.get("module")
        if not module_base:
            continue

        base_parts = module_base.split(".")
        for exposed_path in interface.get("expose", []):
            parts = exposed_path.split(".")
            # Convert import path to physical path (e.g. src.specweaver.project + constitution)
            # Tach syntax means `expose = ["constitution"]` inside `module = "src.x"` maps to `src.x.constitution`
            relative_path = Path(*base_parts) / Path(*parts)
            physical_dir = root_dir / relative_path
            physical_file = physical_dir.with_suffix(".py")

            assert physical_dir.exists() or physical_file.exists(), (
                f"Tach explicit boundary violation risk! "
                f"The interface {exposed_path} for module {module_base} listed in tach.toml does not map "
                f"to any physical directory or file in the filesystem. Tach may silently ignore this."
            )
