"""Local file-system backend for baseline management.

Stores export-hcl output in date-stamped directories under a root dir.
Implements: write, list, retention (mark expired, never delete).
"""
import shutil
from datetime import date, timedelta
from pathlib import Path


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

    def list_baselines(self) -> list[date]:
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

    def get_latest(self) -> Path | None:
        """Return path to most recent baseline directory, or None."""
        baselines = self.list_baselines()
        if not baselines:
            return None
        return self.root / baselines[-1].isoformat()

    def get_by_date(self, date_str: str) -> Path | None:
        """Return path to baseline directory for the given date, or None.

        Args:
            date_str: Date string in YYYY-MM-DD format (ISO 8601).

        Returns:
            Path to baseline directory, or None if not found.
            Returns None (not raises) on invalid format for graceful error handling.
        """
        try:
            target = date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None
        candidate = self.root / target.isoformat()
        if candidate.is_dir():
            return candidate
        return None

    # ── Sprint 17: 重采样工具 ──────────────────────────────

    def copy_baseline(self, src_date: str, dst_date: str, force: bool = False) -> Path | None:
        """Copy a baseline directory from src_date to dst_date (resample).

        Copies manifest.json + inventory.json. Rewrites generated_at in
        manifest.json to match dst_date.

        Args:
            src_date: Source date string (YYYY-MM-DD).
            dst_date: Target date string (YYYY-MM-DD).
            force: Allow overwriting existing dst_date directory.

        Returns:
            Path to new baseline directory, or None on failure.
        """
        src = self.get_by_date(src_date)
        if src is None:
            return None

        dst = self.root / dst_date
        if dst.exists():
            if not force:
                return None
            shutil.rmtree(str(dst))

        # Copy manifest + inventory (the core data files)
        dst.mkdir(parents=True)
        for fname in ["manifest.json", "inventory.json"]:
            src_f = src / fname
            if src_f.exists():
                dst_f = dst / fname
                dst_f.write_text(src_f.read_text(encoding="utf-8"), encoding="utf-8")

        # Rewrite generated_at in manifest to dst date
        manifest_path = dst / "manifest.json"
        if manifest_path.exists():
            import json
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["generated_at"] = f"{dst_date}T00:00:00Z"
                manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            except (json.JSONDecodeError, OSError):
                pass

        # Copy summary and TF stubs if present
        for fname in ["summary.md", "provider.tf", "main.tf", "outputs.tf", "variables.tf"]:
            src_f = src / fname
            if src_f.exists():
                dst_f = dst / fname
                dst_f.write_text(src_f.read_text(encoding="utf-8"), encoding="utf-8")

        return dst

    def list_gaps(self, start: str, end: str) -> list[str]:
        """List dates in [start, end] range that have no baseline directory.

        Args:
            start: Start date (YYYY-MM-DD), inclusive.
            end: End date (YYYY-MM-DD), inclusive.

        Returns:
            Sorted list of ISO date strings for missing dates.
        """
        try:
            d_start = date.fromisoformat(start)
            d_end = date.fromisoformat(end)
        except (ValueError, TypeError):
            return []

        existing = {d.isoformat() for d in self.list_baselines()}
        gaps = []
        current = d_start
        while current <= d_end:
            if current.isoformat() not in existing:
                gaps.append(current.isoformat())
            current += timedelta(days=1)
        return gaps

    def fill_gaps(self, src_date: str, start: str, end: str, force: bool = False) -> list[str]:
        """Fill all gaps in [start, end] range by copying from src_date.

        Args:
            src_date: Source baseline date to copy from.
            start: Start date (inclusive).
            end: End date (inclusive).
            force: Overwrite existing baseline directories if True.

        Returns:
            List of dates that were actually created.
        """
        gaps = self.list_gaps(start, end)
        created = []
        for gap_date in gaps:
            result = self.copy_baseline(src_date, gap_date, force=force)
            if result is not None:
                created.append(gap_date)
        return created

    def apply_retention(self, retention_days: int, today: date | None = None) -> list[str]:
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
