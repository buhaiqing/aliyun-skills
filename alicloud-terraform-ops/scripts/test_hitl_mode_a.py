#!/usr/bin/env python3
"""HITL Mode A 单元测试 — CP3 terraform plan + 检查点/策略。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from hitl_mode_a import (
    Action,
    CheckpointStore,
    CheckpointType,
    CLIController,
    Environment,
    EnvironmentPolicy,
    Step,
    StepType,
    create_checkpoint,
)
from terraform_plan_runner import (
    PlanRunResult,
    TerraformPlanRunner,
    summary_from_plan_stdout,
)


class FakePlanRunner:
    """可注入的 plan runner，用于 CP3 单测。"""

    def __init__(self, result: PlanRunResult):
        self.result = result
        self.calls: list[Path] = []

    def run(self, work_dir: Path) -> PlanRunResult:
        self.calls.append(work_dir.resolve())
        return self.result


class TestSummaryFromPlanStdout(unittest.TestCase):
    def test_parses_add_change_destroy(self):
        stdout = (
            "Plan: 3 to add, 1 to change, 2 to destroy.\n"
            "# alicloud_vpc.main will be created\n"
        )
        data = summary_from_plan_stdout(stdout)
        self.assertEqual(data["create"], 3)
        self.assertEqual(data["update"], 1)
        self.assertEqual(data["delete"], 2)
        self.assertEqual(data["source"], "terraform plan")
        self.assertIn("销毁 2 个资源", data["risks"][0])

    def test_empty_stdout_returns_zeros(self):
        data = summary_from_plan_stdout("")
        self.assertEqual(data["create"], 0)
        self.assertEqual(data["source"], "terraform plan")


class TestTerraformPlanRunner(unittest.TestCase):
    def test_missing_work_dir(self):
        runner = TerraformPlanRunner()
        result = runner.run(Path("/nonexistent/path/for/tf-plan"))
        self.assertFalse(result.success)
        self.assertIn("不存在", result.error or "")

    @mock.patch("terraform_plan_runner.shutil.which", return_value=None)
    def test_missing_terraform_binary(self, _which):
        with tempfile.TemporaryDirectory() as tmp:
            runner = TerraformPlanRunner()
            result = runner.run(Path(tmp))
            self.assertFalse(result.success)
            self.assertIn("terraform CLI", result.error or "")


class TestEnvironmentPolicy(unittest.TestCase):
    def test_dev_cp3_requires_plan_dry_run(self):
        policy = EnvironmentPolicy.get_policy(Environment.DEV, StepType.CONFIRM_PLAN)
        self.assertTrue(policy.required)
        self.assertTrue(policy.dry_run)

    def test_int_auto_approve_enabled(self):
        policy = EnvironmentPolicy.get_policy(Environment.INT, StepType.CONFIRM_PLAN)
        self.assertTrue(policy.auto_approve)

    def test_production_cp2_required(self):
        policy = EnvironmentPolicy.get_policy(Environment.PRODUCTION, StepType.REVIEW_CONFIG)
        self.assertTrue(policy.required)
        self.assertFalse(policy.allow_skip)


class TestCreateCheckpoint(unittest.TestCase):
    def test_nl2hcl_step_order(self):
        cp = create_checkpoint(CheckpointType.NL2HCL, Environment.DEV)
        types = [s.type for s in cp.steps]
        self.assertEqual(
            types,
            [StepType.CONFIRM_INTENT, StepType.REVIEW_CONFIG, StepType.CONFIRM_PLAN],
        )

    def test_destroy_single_step(self):
        cp = create_checkpoint(CheckpointType.DESTROY, Environment.PRODUCTION)
        self.assertEqual(len(cp.steps), 1)
        self.assertEqual(cp.steps[0].type, StepType.CONFIRM_DESTROY)


class TestConfirmPlan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.work_dir = Path(self.tmp) / "generated"
        self.work_dir.mkdir()
        (self.work_dir / "main.tf").write_text('resource "null_resource" "demo" {}\n')

        plan_stdout = (
            "Plan: 2 to add, 0 to change, 0 to destroy.\n"
            "# alicloud_vpc.main will be created\n"
            "# alicloud_vswitch.main[0] will be created\n"
        )
        self.fake_runner = FakePlanRunner(
            PlanRunResult(
                success=True,
                plan_stdout=plan_stdout,
                summary=summary_from_plan_stdout(plan_stdout),
            )
        )
        self.cp = create_checkpoint(
            CheckpointType.NL2HCL,
            Environment.DEV,
            resources=[
                {"type": "vpc", "name": "vpc", "status": "pending"},
                {"type": "ecs", "name": "ecs", "status": "pending"},
            ],
            user_inputs={
                "request": "创建 VPC 和 ECS",
                "output_dir": str(self.work_dir),
            },
        )
        self.step = Step(type=StepType.CONFIRM_PLAN)
        self.store = CheckpointStore(base_path=Path(self.tmp) / "checkpoints")
        self.controller = CLIController(
            self.cp,
            self.store,
            use_color=False,
            plan_runner=self.fake_runner,
        )
        self.policy = EnvironmentPolicy.get_policy(
            Environment.DEV, StepType.CONFIRM_PLAN
        )

    def test_ensure_plan_data_runs_terraform_once(self):
        plan_data = self.controller._ensure_plan_data(self.step)
        self.assertEqual(plan_data["create"], 2)
        self.assertEqual(self.step.data["plan_source"], "terraform plan")
        self.assertEqual(len(self.fake_runner.calls), 1)
        self.controller._ensure_plan_data(self.step)
        self.assertEqual(len(self.fake_runner.calls), 1)

    def test_confirm_plan_accepts_on_yes(self):
        self.controller.ui.prompt = lambda *a, **k: "Y"
        result = self.controller._confirm_plan(self.step, self.policy)
        self.assertEqual(result.action, Action.CONTINUE)
        self.assertEqual(result.data["plan"]["create"], 2)

    def test_confirm_plan_aborts_on_no(self):
        self.controller.ui.prompt = lambda *a, **k: "n"
        result = self.controller._confirm_plan(self.step, self.policy)
        self.assertEqual(result.action, Action.ABORT)

    def test_confirm_plan_details_retry(self):
        calls: list[str] = []

        def fake_prompt(*args, **kwargs):
            calls.append(kwargs.get("default", ""))
            return "details" if len(calls) == 1 else "Y"

        self.controller.ui.prompt = fake_prompt
        result = self.controller._confirm_plan(self.step, self.policy)
        self.assertEqual(result.action, Action.RETRY)
        self.assertTrue(self.step.data.get("show_plan_details"))

        result2 = self.controller._confirm_plan(self.step, self.policy)
        self.assertEqual(result2.action, Action.CONTINUE)

    def test_fallback_when_no_output_dir(self):
        cp = create_checkpoint(CheckpointType.NL2HCL, Environment.DEV, resources=[
            {"type": "vpc", "name": "vpc", "status": "pending"},
        ])
        ctrl = CLIController(cp, use_color=False, plan_runner=self.fake_runner)
        step = Step(type=StepType.CONFIRM_PLAN)
        plan_data = ctrl._ensure_plan_data(step)
        self.assertEqual(plan_data["source"], "resource_estimate")
        self.assertEqual(plan_data["create"], 1)
        self.assertEqual(len(self.fake_runner.calls), 0)

    def test_plan_failure_falls_back_to_estimate(self):
        fail_runner = FakePlanRunner(
            PlanRunResult(success=False, error="PLAN 失败 (exit 1): error")
        )
        ctrl = CLIController(
            self.cp,
            use_color=False,
            plan_runner=fail_runner,
        )
        step = Step(type=StepType.CONFIRM_PLAN)
        plan_data = ctrl._ensure_plan_data(step)
        self.assertEqual(plan_data["source"], "resource_estimate")
        self.assertIn("plan_error", step.data.get("plan", {}))


class TestCheckpointStoreRoundtrip(unittest.TestCase):
    def test_save_load_preserves_generated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CheckpointStore(base_path=Path(tmp))
            cp = create_checkpoint(
                CheckpointType.NL2HCL,
                Environment.DEV,
                generated_files={"main.tf": "module {}"},
                user_inputs={"output_dir": "/tmp/out"},
            )
            store.save(cp)
            loaded = store.load(cp.id)
            assert loaded is not None
            self.assertEqual(loaded.generated_files["main.tf"], "module {}")
            self.assertEqual(loaded.user_inputs["output_dir"], "/tmp/out")


if __name__ == "__main__":
    unittest.main()
