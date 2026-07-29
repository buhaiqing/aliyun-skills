"""Pytest conftest: ensure scripts/ is on sys.path for tests."""
import sys
from pathlib import Path

# Add scripts/ dir to sys.path so 'from alicloud_shared import ...' works
_scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(_scripts_dir))