"""Common pytest fixtures for alicloud-topo-discovery Phase 1 tests.

Also configures sys.path so tests can do
`from scripts.lib.<module> import ...` (the canonical import path for
this skill's internal library). The skill's root directory
(alicloud-topo-discovery/) is added to sys.path, making the `scripts/`
subdir importable as a package.
"""
import json
import sys
from pathlib import Path
import pytest

# Make `scripts.lib.*` imports work in tests.
# Adding the skill dir to sys.path means `scripts` resolves to
# alicloud-topo-discovery/scripts/, NOT the repo-root scripts/ dir
# (which contains gcl_runner.py for the project meta-skill).
SKILL_DIR = Path(__file__).parent.parent
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Self-bootstrap: ensure fixtures directory exists so smoke tests pass in
# fresh clones. Real fixtures are added in Task 2+.
FIXTURES_DIR.mkdir(exist_ok=True)


@pytest.fixture
def fixtures_dir():
    """Returns the path to the tests/fixtures/ directory."""
    return FIXTURES_DIR


@pytest.fixture
def load_fixture():
    """Returns a function that loads a JSON fixture by name (without .json extension)."""
    def _load(name: str) -> dict:
        path = FIXTURES_DIR / f"{name}.json"
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return _load


@pytest.fixture
def temp_output_dir(tmp_path):
    """Returns a fresh temp directory for output files."""
    output = tmp_path / "hcl-export"
    output.mkdir()
    return output
