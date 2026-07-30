#!/usr/bin/env python3
"""Performance optimization gate tests.

Each test verifies that an opt-in env var actually short-circuits the
expensive path it claims to skip. The default (env var unset) MUST keep
running the expensive path so production users are not affected.

These tests intentionally run the wrapper / gcl_runner in subprocess
to exercise the env-var handoff through the bash -> python subprocess
boundary (which is how the integration suite is wired).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "alicloud-gcl-runner-ops" / "scripts"
_WRAPPER = _SCRIPTS / "gcl-runner-harness-wrapper.sh"


def _make_capture_curl_dir(tmp: Path) -> tuple[Path, Path]:
    """Create a mock curl that records every invocation. Returns (bin_dir, log_file)."""
    log = tmp / "curl.log"
    bin_dir = tmp / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    curl = bin_dir / "curl"
    curl.write_text(f"""#!/bin/bash
echo "$@" >> "{str(log)}"
exit 0
""")
    curl.chmod(0o755)
    return bin_dir, log


class _PerfGateBase(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="perf-gate-", dir="/tmp"))

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _env(self, *, extra: dict) -> dict:
        # Minimal env so wrapper / gcl_runner can find its files without
        # hitting real Langfuse.
        env = {
            **os.environ,
            "PATH": f"{self._tmp}/bin:{os.environ.get('PATH', '')}",
            "PYTHONPATH": f"{self._tmp}:{os.environ.get('PYTHONPATH', '')}",
            "SKILLS_DIR": str(_REPO),
            "ALIYUN_SKILLS_ROOT": str(_REPO),
            "ALIYUN_SKILLS_RUNTIME_ROOT": str(_REPO / ".runtime"),
            "HARNESS_SESSION_ID": "perf-gate-session",
            "HARNESS_USER_ID": "perf-gate-user",
            "GCL_CRITIC_MODE": "mechanical",
            "LANGFUSE_BASE_URL": "http://mock.langfuse.local",
            "LANGFUSE_HOST": "http://mock.langfuse.local",
            "LANGFUSE_PUBLIC_KEY": "pk-perf",
            "LANGFUSE_SECRET_KEY": "sk-perf",
            "SKILLOPT_ENABLED": "true",
        }
        env.update(extra)
        return env


class TestSkipValidateGate(_PerfGateBase):
    """SKILLOPT_LANGFUSE_SKIP_VALIDATE=1 must short-circuit
    skillopt_langfuse_validate before it spawns curl."""

    def _run(self, env_extra: dict) -> subprocess.CompletedProcess:
        bin_dir, log = _make_capture_curl_dir(self._tmp)
        env = self._env(extra={
            "SKILLOPT_LANGFUSE_ENABLED": "true",
            **env_extra,
        })
        return subprocess.run(
            ["bash", str(_WRAPPER),
             "--skill", "alicloud-ecs-ops",
             "--op", "DescribeInstances",
             "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
             "--dry-run",
            ],
            env=env, capture_output=True, text=True, timeout=30,
        )

    def test_default_runs_validate_curl(self):
        """Without the gate, validate runs and curl is invoked. This is the
        current production behaviour that we must NOT break."""
        bin_dir, log = _make_capture_curl_dir(self._tmp)
        # Make sure SKILLOPT_LANGFUSE_SKIP_VALIDATE is unset.
        env = self._env(extra={"SKILLOPT_LANGFUSE_ENABLED": "true"})
        env.pop("SKILLOPT_LANGFUSE_SKIP_VALIDATE", None)
        # Re-prepend the mock-curl bin to PATH (we did this in setUp, but be explicit)
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        result = subprocess.run(
            ["bash", str(_WRAPPER),
             "--skill", "alicloud-ecs-ops",
             "--op", "DescribeInstances",
             "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
             "--dry-run",
            ],
            env=env, capture_output=True, text=True, timeout=30,
        )
        # Validate runs curl -> log has at least one entry
        self.assertTrue(log.exists() and log.stat().st_size > 0,
                        f"expected curl to be invoked by default, log={log.read_text() if log.exists() else 'missing'}")
        # The call should be to the Langfuse ingestion endpoint
        log_text = log.read_text()
        self.assertIn("/api/public/ingestion", log_text,
                      f"expected validate curl to hit ingestion endpoint, got: {log_text!r}")
        self.assertIn(result.returncode, (0, 6),
                      f"wrapper should not crash, rc={result.returncode}, stderr={result.stderr[-200:]}")

    def test_skip_validate_skips_curl(self):
        """With SKILLOPT_LANGFUSE_SKIP_VALIDATE=1, validate must short-circuit
        before the credential-probe curl is issued. The probe is the only
        Langfuse call that posts the tiny `{"batch":[]}` body; real trace
        writes always post a non-empty batch. Asserting on the probe body
        shape avoids false positives from the actual trace-write calls
        (which are expected and must keep running)."""
        bin_dir, log = _make_capture_curl_dir(self._tmp)
        env = self._env(extra={
            "SKILLOPT_LANGFUSE_ENABLED": "true",
            "SKILLOPT_LANGFUSE_SKIP_VALIDATE": "1",
        })
        env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
        result = subprocess.run(
            ["bash", str(_WRAPPER),
             "--skill", "alicloud-ecs-ops",
             "--op", "DescribeInstances",
             "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
             "--dry-run",
            ],
            env=env, capture_output=True, text=True, timeout=30,
        )
        # The credential probe body is `{"batch":[]}`. It must NOT appear.
        if log.exists() and log.stat().st_size > 0:
            log_text = log.read_text()
            # Probe posts the empty-batch body; normal ingestion calls post
            # a non-empty batch wrapped in `{"batch": [`.
            self.assertNotIn('-d {"batch":[]}', log_text,
                             f"validate credential probe must be skipped, but it was invoked: {log_text[:2000]!r}")
        # Wrapper still ran the gcl_runner (rc=0 or rc=6 expected)
        self.assertIn(result.returncode, (0, 6),
                      f"wrapper should not crash with gate on, rc={result.returncode}, stderr={result.stderr[-200:]}")


class TestSkipLangfuseInfoGate(_PerfGateBase):
    """GCL_SKIP_LANGFUSE_INFO=1 must short-circuit _print_langfuse_info
    before it tries to import langfuse (the SDK is heavy and DNS-bound)."""

    def _run_gcl_direct(self, env_extra: dict) -> subprocess.CompletedProcess:
        env = self._env(extra=env_extra)
        cmd = [
            sys.executable, str(_SCRIPTS / "gcl_runner.py"),
            "--skill", "alicloud-ecs-ops",
            "--op", "DescribeInstances",
            "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            "--dry-run",
        ]
        return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)

    def test_default_prints_langfuse_info_when_enabled(self):
        """Default behaviour: when SKILLOPT_LANGFUSE_ENABLED=true and the
        org/project are not pre-set, _print_langfuse_info emits the
        [Langfuse] HOST=... line on stderr."""
        env_extra = {
            "SKILLOPT_LANGFUSE_ENABLED": "true",
            "GCL_SKIP_LANGFUSE_INFO": "",  # explicit: gate off
        }
        env_extra.pop("GCL_SKIP_LANGFUSE_INFO", None)  # ensure unset
        result = self._run_gcl_direct(env_extra={
            "SKILLOPT_LANGFUSE_ENABLED": "true",
        })
        # The line is emitted (it can be followed by org/project lookup
        # failure, but the [Langfuse] prefix must be present).
        self.assertIn("[Langfuse]", result.stderr,
                      f"expected [Langfuse] info line by default, stderr={result.stderr[-300:]}")

    def test_skip_info_skips_langfuse_line(self):
        """With GCL_SKIP_LANGFUSE_INFO=1, the [Langfuse] info line must NOT
        be emitted on stderr."""
        result = self._run_gcl_direct(env_extra={
            "SKILLOPT_LANGFUSE_ENABLED": "true",
            "GCL_SKIP_LANGFUSE_INFO": "1",
        })
        self.assertNotIn("[Langfuse]", result.stderr,
                         f"expected [Langfuse] line to be suppressed, stderr={result.stderr[-300:]}")


if __name__ == "__main__":
    unittest.main()
