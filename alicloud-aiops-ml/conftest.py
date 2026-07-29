"""Pytest conftest: ensure alicloud_shared is importable."""
import sys
from pathlib import Path

_gcl_scripts = (
    Path(__file__).resolve().parent.parent
    / "alicloud-gcl-runner-ops"
    / "scripts"
)
sys.path.insert(0, str(_gcl_scripts))