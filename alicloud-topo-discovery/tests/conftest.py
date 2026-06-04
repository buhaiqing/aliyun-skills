"""Common pytest fixtures for alicloud-topo-discovery Phase 1 tests."""
import json
from pathlib import Path
import pytest

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
