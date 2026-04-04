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
        from_bases = interface.get("from", [])
        if not from_bases:
            # Fallback for old tach syntax if any
            module_base = interface.get("module")
            if module_base:
                from_bases = [module_base]

        for module_base in from_bases:
            base_parts = module_base.split(".")
            for exposed_path in interface.get("expose", []):
                parts = exposed_path.split(".")
                relative_path = Path(*base_parts) / Path(*parts)
                physical_dir = root_dir / relative_path
                physical_file = physical_dir.with_suffix(".py")

                assert physical_dir.exists() or physical_file.exists(), (
                    f"Tach explicit boundary violation risk! "
                    f"The interface {exposed_path} for module {module_base} listed in tach.toml does not map "
                    f"to any physical directory or file in the filesystem. Tach may silently ignore this."
                )


def test_tach_keeps_runner_soft_deprecated() -> None:
    """
    Integration Regression Guard:
    Ensures that the legacy 'runner' module is explicitly omitted from the 'src.specweaver.validation'
    expose list in tach.toml. This prevents accidental soft-deprecation regressions where a future 
    developer might silently re-expose it, bypassing the architectural deprecation boundary.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    tach_path = root_dir / "tach.toml"
    assert tach_path.exists()

    with tach_path.open("rb") as f:
        config = tomllib.load(f)

    for interface in config.get("interfaces", []):
        from_bases = interface.get("from", [])
        if "src.specweaver.validation" in from_bases:
            exposed = interface.get("expose", [])
            assert "runner" not in exposed, (
                "CRITICAL: The 'runner' module must remain soft-deprecated! "
                "Do NOT add 'runner' to the validation interfaces in tach.toml."
            )
