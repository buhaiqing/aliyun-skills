#!/usr/bin/env python3
"""Tests for Git backend (Plan 2 Task 1)."""
import json
import subprocess
from datetime import date

import pytest

from scripts.lib.baseline_git import GitBackend


@pytest.fixture
def git_repo(tmp_path):
    """Create a temporary git repo for testing."""
    subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(tmp_path), "checkout", "-b", "main"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "test"], capture_output=True, check=True)
    return tmp_path


@pytest.fixture
def snapshot(tmp_path):
    """Create a minimal snapshot directory."""
    import shutil
    snap = tmp_path / ".snapshot"
    snap.mkdir(parents=True, exist_ok=True)
    (snap / "manifest.json").write_text(json.dumps({
        "resource_count": 5, "by_type": {"vpc": 1, "ecs": 4},
        "schema_version": "1.0", "generator": "test", "generator_version": "1.0.0",
        "generated_at": "2026-06-04T00:00:00Z", "account_id": "123",
        "region": "cn-hangzhou", "scope": "all", "provider_version": "1.220.0",
        "sensitive_masked": [], "unsupported_types": [],
        "import_ids_stable": True, "execution_time_ms": 0,
    }))
    (snap / "main.tf").write_text("resource")
    (snap / "provider.tf").write_text("terraform {}")
    yield snap
    shutil.rmtree(str(snap), ignore_errors=True)


def test_git_init_repo(git_repo):
    """GitBackend initializes a git repo in root_dir."""
    GitBackend(root_dir=git_repo, remote_url=None, push=False)
    assert (git_repo / ".git").exists()


def test_write_baseline_creates_commit(git_repo, snapshot):
    """write_baseline creates a commit in the baselines/ directory."""
    backend = GitBackend(root_dir=git_repo, remote_url=None, push=False)
    sha = backend.write_baseline(snapshot)
    assert sha is not None and len(sha) == 40

    today = date.today().isoformat()
    assert (git_repo / "baselines" / today).exists()
    assert (git_repo / "baselines" / today / "main.tf").read_text() == "resource"


def test_list_baselines_returns_dates(git_repo, snapshot):
    """list_baselines returns dates from baselines/ directory."""
    backend = GitBackend(root_dir=git_repo, remote_url=None, push=False)
    backend.write_baseline(snapshot)

    dates = backend.list_baselines()
    assert len(dates) == 1
    assert dates[0] == date.today()


def test_get_latest_returns_most_recent(git_repo, snapshot):
    """get_latest returns path to most recent baseline."""
    backend = GitBackend(root_dir=git_repo, remote_url=None, push=False)
    backend.write_baseline(snapshot)

    latest = backend.get_latest()
    assert latest is not None
    assert latest.name == date.today().isoformat()


def test_empty_repo_returns_empty_list(git_repo):
    """Empty repo returns empty list."""
    backend = GitBackend(root_dir=git_repo, remote_url=None, push=False)
    assert backend.list_baselines() == []
    assert backend.get_latest() is None


def test_commit_message_contains_date(git_repo, snapshot):
    """Commit message contains the baseline date."""
    backend = GitBackend(root_dir=git_repo, remote_url=None, push=False)
    backend.write_baseline(snapshot)

    result = subprocess.run(
        ["git", "-C", str(git_repo), "log", "-1", "--pretty=%B"],
        capture_output=True, text=True, check=True,
    )
    assert date.today().isoformat() in result.stdout
    assert "5 resources" in result.stdout


def test_commit_author(git_repo, snapshot):
    """Commit author is configurable."""
    backend = GitBackend(
        root_dir=git_repo, remote_url=None, push=False,
        commit_user="batman", commit_email="batman@wayne.com",
    )
    backend.write_baseline(snapshot)

    result = subprocess.run(
        ["git", "-C", str(git_repo), "log", "-1", "--pretty=%an <%ae>"],
        capture_output=True, text=True, check=True,
    )
    assert "batman" in result.stdout
    assert "batman@wayne.com" in result.stdout
