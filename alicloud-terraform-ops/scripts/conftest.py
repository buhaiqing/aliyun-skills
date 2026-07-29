"""Pytest conftest: ensure alicloud_shared is importable."""
import sys
from pathlib import Path

# Add gcl-runner-ops scripts/ to sys.path so 'from alicloud_shared import ...' works
_gcl_scripts = Path(__file__).resolve().parent.parent.parent / "alicloud-gcl-runner-ops" / "scripts"
sys.path.insert(0, str(_gcl_scripts))
