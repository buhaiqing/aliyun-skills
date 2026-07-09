#!/usr/bin/env python3
"""Tests for scripts/runtime_cleanup.py memory-layer maintain hooks."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runtime_cleanup import run_memory_layer_maintain  # noqa: E402


def _stub_gcl_scripts(skills_dir: Path) -> None:
    gcl = skills_dir / "alicloud-gcl-runner-ops" / "scripts"
    gcl.mkdir(parents=True)
    (gcl / "gcl_memory.py").write_text("# stub\n", encoding="utf-8")
    (gcl / "gcl_reflexion.py").write_text("# stub\n", encoding="utf-8")


def _cmd_argv(cmd: list[str]) -> list[str]:
    return list(cmd)


class MaintainReflexionReportTests(unittest.TestCase):
    @patch("runtime_cleanup.run_trace_layer_maintain", return_value=0)
    @patch("runtime_cleanup.subprocess.run")
    def test_report_runs_when_env_set_and_apply(self, mock_run: MagicMock, _trace: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp)
            _stub_gcl_scripts(skills)
            with patch.dict(os.environ, {"GCL_REFLEXION_REPORT_ON_MAINTAIN": "true"}, clear=False):
                rc = run_memory_layer_maintain(skills, apply=True)
            self.assertEqual(rc, 0)
            argv_lists = [_cmd_argv(c.args[0]) for c in mock_run.call_args_list]
            self.assertTrue(any(len(a) > 2 and a[2] == "report" for a in argv_lists))
            self.assertTrue(any(len(a) > 2 and a[2] == "success-report" for a in argv_lists))
            self.assertTrue(any(len(a) > 2 and a[2] == "aggregate-generalized" for a in argv_lists))

    @patch("runtime_cleanup.run_trace_layer_maintain", return_value=0)
    @patch("runtime_cleanup.subprocess.run")
    def test_report_skipped_on_dry_run(self, mock_run: MagicMock, _trace: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp)
            _stub_gcl_scripts(skills)
            with patch.dict(os.environ, {"GCL_REFLEXION_REPORT_ON_MAINTAIN": "true"}, clear=False):
                run_memory_layer_maintain(skills, apply=False)
            argv_lists = [_cmd_argv(c.args[0]) for c in mock_run.call_args_list]
            self.assertFalse(any("report" in argv for argv in argv_lists))

    @patch("runtime_cleanup.run_trace_layer_maintain", return_value=0)
    @patch("runtime_cleanup.subprocess.run")
    def test_report_skipped_when_env_false(self, mock_run: MagicMock, _trace: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp)
            _stub_gcl_scripts(skills)
            with patch.dict(os.environ, {"GCL_REFLEXION_REPORT_ON_MAINTAIN": "false"}, clear=False):
                run_memory_layer_maintain(skills, apply=True)
            argv_lists = [_cmd_argv(c.args[0]) for c in mock_run.call_args_list]
            self.assertFalse(any("report" in argv for argv in argv_lists))


if __name__ == "__main__":
    unittest.main()
