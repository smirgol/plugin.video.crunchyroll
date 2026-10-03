"""Tests ensuring legacy model/utils facades are no longer imported internally."""

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
RESOURCES_LIB = PROJECT_ROOT / "resources" / "lib"
TESTS_DIR = PROJECT_ROOT / "tests"


# Whitelist: the two facade files themselves are allowed to re-export.
LEGACY_FACADE_FILES = {
    RESOURCES_LIB / "model.py",
    RESOURCES_LIB / "utils.py",
}


@pytest.mark.parametrize(
    "pattern,path_root,exclude",
    [
        (
            r"from\s+\.model\s+import",
            RESOURCES_LIB,
            LEGACY_FACADE_FILES,
        ),
        (
            r"from\s+\.utils\s+import",
            RESOURCES_LIB,
            LEGACY_FACADE_FILES,
        ),
        (r"from\s+resources\.lib\.model\s+import", TESTS_DIR, set()),
        (r"from\s+resources\.lib\.utils\s+import", TESTS_DIR, set()),
    ],
)
def test_no_legacy_facade_imports(pattern, path_root, exclude):
    """After Phase 9a, no file except the facade itself imports the legacy paths."""
    failures = []
    for path in path_root.rglob("*.py"):
        if path in exclude:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(pattern, text):
            failures.append(str(path.relative_to(PROJECT_ROOT)))
    assert not failures, f"Legacy facade imports found in: {failures}"
