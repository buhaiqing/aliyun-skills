"""Local file-system backend for baseline management.

Stores export-hcl output in date-stamped directories under a root dir.
Implements: write, list, retention (mark expired, never delete).
"""
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional


class LocalBackend:
    """Manages baseline snapshots on the local filesystem.

    Directory layout:
        {root_dir}/{YYYY-MM-DD}/
            provider.tf
            main.tf
            variables.tf
            outputs.tf
            terraform.tfstate
            import.sh
            unsupported.tf
            manifest.json

    Expired baseline dirs are renamed with a '.expired' suffix.
    Actual directory deletion is intentionally omitted (user decides).
    """

    def __init__(self, root_dir: Path):
        self.root = root_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def write_baseline(self, snapshot: Path) -> Path:
        """Copy a completed export directory into a date-stamped baseline.

        Args:
            snapshot: Directory containing the export-hcl output to archive.

        Returns:
            Path to the new baseline directory.
        """
        today = date.today()
        dst = self.root / today.isoformat()
        if dst.exists():
            shutil.rmtree(str(dst))
        shutil.copytree(str(snapshot), str(dst))
        return dst

    def list_baselines(self) -> List[date]:
        """Return sorted list of baseline dates (excluding expired)."""
        dates = []
        for entry in sorted(self.root.iterdir()):
            if entry.name.endswith(".expired"):
                continue
            try:
                dates.append(date.fromisoformat(entry.name))
            except (ValueError, TypeError):
                continue
        return sorted(dates)

    def get_latest(self) -> Optional[Path]:
        """Return path to most recent baseline directory, or None."""
        baselines = self.list_baselines()
        if not baselines:
            return None
        return self.root / baselines[-1].isoformat()

    def apply_retention(self, retention_days: int, today: Optional[date] = None) -> List[str]:
        """Mark directories older than retention_days with '.expired' suffix.

        Args:
            retention_days: Number of days to keep.
            today: Reference date (default: today).

        Returns:
            List of dirs that were marked expired.
        """
        if today is None:
            today = date.today()
        cutoff = today - timedelta(days=retention_days)
        expired = []
        for entry in sorted(self.root.iterdir()):
            if not entry.is_dir():
                continue
            try:
                d = date.fromisoformat(entry.name.rstrip(".expired"))
            except (ValueError, TypeError):
                continue
            if d < cutoff and not entry.name.endswith(".expired"):
                entry.rename(self.root / (entry.name + ".expired"))
                expired.append(entry.name)
        return expired