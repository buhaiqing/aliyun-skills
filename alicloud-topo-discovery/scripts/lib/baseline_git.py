#!/usr/bin/env python3
"""Git backend for baseline management.

Stores baselines as commits in a git repo. Each write_baseline creates
a commit under baselines/YYYY-MM-DD/. Pushes if remote configured.

Usage:
    backend = GitBackend(root_dir=Path("./infra-baseline"))
    sha = backend.write_baseline(snapshot_path)
"""
import os
import subprocess
from datetime import date
from pathlib import Path


class GitBackend:
    """Manages baselines via git commits.

    The root_dir is the git working tree. Baselines are committed into
    baselines/YYYY-MM-DD/ sub-path within the repo.
    """

    def __init__(
        self,
        root_dir: Path,
        remote_url: str | None = None,
        branch: str = "main",
        commit_user: str = "topo-discovery",
        commit_email: str = "topo@alicloud.com",
        push: bool = True,
    ):
        self.root = root_dir
        self.remote_url = remote_url
        self.branch = branch
        self.commit_user = f"{commit_user} <{commit_email}>"
        self.push = push

        # Initialize git repo if not already
        if not (root_dir / ".git").exists():
            self._run("init")
            self._run("checkout", "-b", branch)
        if remote_url and not self._has_remote():
            self._run("remote", "add", "origin", remote_url)

    def write_baseline(self, snapshot: Path) -> str:
        """Copy snapshot into baselines/YYYY-MM-DD/ and commit.

        Returns commit SHA.
        """
        today = date.today().isoformat()
        dest = self.root / "baselines" / today
        if dest.exists():
            import shutil
            shutil.rmtree(str(dest))
        import shutil
        shutil.copytree(str(snapshot), str(dest))

        # Git add, commit, (optional push)
        self._run("add", str(dest))
        meta_file = dest / "manifest.json"
        resource_count = "unknown"
        if meta_file.exists():
            import json
            resource_count = str(json.loads(meta_file.read_text()).get("resource_count", "unknown"))
        commit_msg = f"baseline: {today} ({resource_count} resources)"
        env = {"GIT_AUTHOR_NAME": self.commit_user.split(" <")[0],
               "GIT_AUTHOR_EMAIL": self.commit_user.split("<")[1].rstrip(">"),
               "GIT_COMMITTER_NAME": self.commit_user.split(" <")[0],
               "GIT_COMMITTER_EMAIL": self.commit_user.split("<")[1].rstrip(">")}
        self._run("commit", "-m", commit_msg, extra_env=env)
        sha = self._run("rev-parse", "HEAD").strip()

        if self.push and self._has_remote():
            result = self._run("push", "origin", self.branch, check=False)
            if result.returncode != 0:
                import warnings
                warnings.warn(f"Push failed: {result.stderr}. Baseline committed locally.")

        return sha

    def list_baselines(self) -> list[date]:
        """Return sorted list of baseline dates from the baselines/ dir."""
        base = self.root / "baselines"
        if not base.exists():
            return []
        dates = []
        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            try:
                dates.append(date.fromisoformat(entry.name))
            except (ValueError, TypeError):
                continue
        return sorted(dates)

    def get_latest(self) -> Path | None:
        dates = self.list_baselines()
        if not dates:
            return None
        return self.root / "baselines" / dates[-1].isoformat()

    def _run(self, *args, check=True, extra_env=None):
        cmd_env = os.environ.copy() if extra_env else None
        if extra_env:
            cmd_env.update(extra_env)
        cmd = ["git", "-C", str(self.root)] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=cmd_env)
        if check and result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
        return result.stdout

    def _has_remote(self) -> bool:
        output = self._run("remote", "-v", check=False)
        return "origin" in output
