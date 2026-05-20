import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def check_lineage(src_dir: Path) -> list[str]:
    """Scan the source directory for Python files missing artifact tags.

    Returns a list of absolute paths to files that are missing the '# sw-artifact:' tag.
    """
    orphans: list[str] = []

    if not src_dir.exists() or not src_dir.is_dir():
        return orphans

    # Directories to skip
    excluded_dirs = {".tmp", ".venv", "__pycache__", ".git", ".pytest_cache"}

    # Iterate through all .py files in src_dir
    for py_file in src_dir.rglob("*.py"):
        # Check if the file is inside any excluded directory
        is_excluded = False
        for part in py_file.parts:
            if part in excluded_dirs:
                is_excluded = True
                break

        if is_excluded:
            continue

        # Read the file and check for the tag
        try:
            content = py_file.read_text(encoding="utf-8")
            if "# sw-artifact:" not in content:
                orphans.append(str(py_file.resolve()))
        except Exception as e:
            logger.warning("Could not read file %s: %s", py_file, e)

    return sorted(orphans)
