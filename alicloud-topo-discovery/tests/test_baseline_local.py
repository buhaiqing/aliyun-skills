"""Tests for local baseline backend (Task 15)."""
from datetime import date

from scripts.lib.baseline_local import LocalBackend


def test_write_baseline_creates_date_dir(temp_baseline_root):
    """write_baseline copies snapshot into a date-stamped directory."""
    backend = LocalBackend(root_dir=temp_baseline_root)
    snapshot = temp_baseline_root / ".snapshot"
    snapshot.mkdir()
    (snapshot / "manifest.json").write_text("{}")
    (snapshot / "main.tf").write_text("resource")

    result = backend.write_baseline(snapshot)
    today = date.today().isoformat()
    assert result.name == today
    assert (result / "manifest.json").read_text() == "{}"
    assert (result / "main.tf").read_text() == "resource"


def test_list_baselines_returns_sorted_dates(temp_baseline_root):
    """list_baselines returns sorted date strings."""
    root = temp_baseline_root
    (root / "2026-06-01").mkdir()
    (root / "2026-06-02").mkdir()
    (root / "2026-06-03").mkdir()

    backend = LocalBackend(root_dir=root)
    dates = backend.list_baselines()
    assert dates == [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)]


def test_get_latest_returns_most_recent(temp_baseline_root):
    """get_latest returns path to most recent baseline."""
    root = temp_baseline_root
    (root / "2026-06-01").mkdir()
    (root / "2026-06-03").mkdir()
    (root / "2026-06-02").mkdir()

    backend = LocalBackend(root_dir=root)
    latest = backend.get_latest()
    assert latest is not None
    assert latest.name == "2026-06-03"


def test_get_latest_empty_root_returns_none(temp_baseline_root):
    """get_latest on empty root returns None."""
    backend = LocalBackend(root_dir=temp_baseline_root)
    assert backend.get_latest() is None


def test_retention_marks_expired_dirs(temp_baseline_root):
    """Directories older than retention_days get .expired suffix."""
    root = temp_baseline_root
    today = date(2026, 6, 15)
    (root / "2026-06-01").mkdir()  # 14 days old
    (root / "2026-06-10").mkdir()  # 5 days old
    (root / "2026-06-14").mkdir()  # 1 day old

    backend = LocalBackend(root_dir=root)
    expired = backend.apply_retention(retention_days=7, today=today)
    assert "2026-06-01" in expired
    assert (root / "2026-06-01.expired").exists()
    assert (root / "2026-06-10").exists()  # still within 7 days
    assert (root / "2026-06-14").exists()  # still within 7 days


def test_retention_does_not_delete(temp_baseline_root):
    """Expired dirs are renamed, NOT deleted."""
    root = temp_baseline_root
    (root / "2026-06-01").mkdir()
    (root / "2026-06-01/manifest.json").write_text("{}")

    backend = LocalBackend(root_dir=root)
    backend.apply_retention(retention_days=1, today=date(2026, 6, 15))
    assert (root / "2026-06-01.expired").exists()
    assert (root / "2026-06-01.expired" / "manifest.json").read_text() == "{}"


def test_expired_dirs_not_in_list(temp_baseline_root):
    """list_baselines excludes expired directories."""
    root = temp_baseline_root
    (root / "2026-06-01.expired").mkdir()
    (root / "2026-06-15").mkdir()

    backend = LocalBackend(root_dir=root)
    dates = backend.list_baselines()
    assert len(dates) == 1
    assert dates[0] == date(2026, 6, 15)


def test_write_baseline_overwrites_existing(temp_baseline_root):
    """Writing a baseline on the same date overwrites the old one."""
    backend = LocalBackend(root_dir=temp_baseline_root)
    snapshot = temp_baseline_root / ".snapshot"
    snapshot.mkdir()
    (snapshot / "manifest.json").write_text("old")
    backend.write_baseline(snapshot)

    (snapshot / "manifest.json").write_text("new")
    backend.write_baseline(snapshot)

    today = date.today().isoformat()
    assert (temp_baseline_root / today / "manifest.json").read_text() == "new"
