#!/usr/bin/env python3
"""terraform_executor 单元测试。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from terraform_executor import (
    TerraformExecutor,
    plan_summary_to_resources,
    seed_plan_step_data,
)
from terraform_plan_runner import PlanRunResult


class TestTerraformExecutorHelpers(unittest.TestCase):
    def test_plan_summary_to_resources(self):
        resources = plan_summary_to_resources({"delete": 3, "create": 0})
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["attributes"]["delete_count"], 3)

    def test_seed_plan_step_data_success(self):
        result = PlanRunResult(
            success=True,
            plan_stdout="Plan: 1 to add.",
            summary={"create": 1, "update": 0, "delete": 0, "source": "terraform plan"},
        )
        data = seed_plan_step_data(result)
        self.assertTrue(data["plan_executed"])
        self.assertEqual(data["plan_source"], "terraform plan")
        self.assertEqual(data["plan"]["create"], 1)


class TestTerraformExecutor(unittest.TestCase):
    @mock.patch("terraform_executor.shutil.which", return_value=None)
    def test_state_backup_missing_terraform(self, _which):
        with tempfile.TemporaryDirectory() as tmp:
            result = TerraformExecutor().state_backup(Path(tmp))
            self.assertFalse(result.success)

    @mock.patch("terraform_executor.subprocess.run")
    @mock.patch("terraform_executor.shutil.which", return_value="/usr/bin/terraform")
    def test_state_backup_writes_file(self, _which, mock_run):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = '{"version": 4}'
        mock_run.return_value.stderr = ""
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "main.tf").write_text('resource "null_resource" "x" {}\n', encoding="utf-8")
            result = TerraformExecutor().state_backup(work)
            self.assertTrue(result.success)
            self.assertTrue(result.state_backup.is_file())


class TestApplyDestroyBridge(unittest.TestCase):
    @mock.patch("hitl_mode_a.CLIController")
    @mock.patch("terraform_executor.TerraformExecutor")
    def test_run_apply_with_hitl_executes_after_checkpoint(self, mock_exec_cls, mock_controller_cls):
        import terraform_ops
        from hitl_mode_a import CheckpointStatus
        from terraform_executor import ExecRunResult

        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "main.tf").write_text("# stub\n", encoding="utf-8")

            mock_exec = mock_exec_cls.return_value
            mock_exec.plan_apply.return_value = PlanRunResult(
                success=True,
                plan_stdout="Plan: 1 to add.",
                summary={"create": 1, "update": 0, "delete": 0, "source": "terraform plan"},
            )
            mock_exec.apply.return_value = ExecRunResult(success=True, stdout="Apply complete!")

            checkpoint = mock_controller_cls.return_value.run.return_value
            checkpoint.status = CheckpointStatus.COMPLETED

            args = mock.Mock(
                work_dir=work,
                output_dir=None,
                environment="dev",
                region="cn-hangzhou",
                offline=True,
                gcl_check=False,
            )
            rc = terraform_ops._run_apply_with_hitl(args)
            self.assertEqual(rc, 0)
            mock_exec.apply.assert_called_once()


class TestRuntimeWorkDir(unittest.TestCase):
    def test_ensure_runtime_work_dir_seeds_from_template(self):
        from unittest.mock import patch

        import terraform_ops

        with tempfile.TemporaryDirectory() as tmp:
            skill_root = Path(tmp)
            template_dev = skill_root / "environments" / "dev"
            template_dev.mkdir(parents=True)
            (template_dev / "main.tf").write_text(
                'module "x" { source = "../../modules/web-stack" }\n',
                encoding="utf-8",
            )
            runtime_env_root = skill_root / ".runtime" / "terraform-ops" / "environments"

            with patch.object(terraform_ops, "template_env_root", return_value=skill_root / "environments"), patch.object(
                terraform_ops,
                "default_env_runtime",
                side_effect=lambda env: runtime_env_root / env,
            ):
                work_dir = terraform_ops._ensure_runtime_work_dir("dev")

            self.assertEqual(work_dir, (runtime_env_root / "dev").resolve())
            content = (work_dir / "main.tf").read_text(encoding="utf-8")
            self.assertIn("../../../modules/web-stack", content)


if __name__ == "__main__":
    unittest.main()
