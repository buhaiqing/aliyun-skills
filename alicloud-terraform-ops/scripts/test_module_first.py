#!/usr/bin/env python3
"""Module-first NL2HCL 单元测试"""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from execution_trace import CommandRecord
from module_catalog import MODULES_ROOT, copy_modules, modules_for_trace, plan_modules
import nl2hcl_generator
from nl2hcl_generator import NL2HCLGenerator, lint_hcl


class TestModuleFirst(unittest.TestCase):
    def test_ecs_uses_web_stack(self):
        gen = NL2HCLGenerator(environment="int", region="cn-hangzhou")
        intent = gen.parse_intent("创建一台1核2G的ECS")
        plan = plan_modules(intent, gen.defaults)
        self.assertTrue(plan.use_web_stack)
        self.assertTrue(plan.enable_ecs)
        files = gen.generate("创建一台1核2G的ECS")
        self.assertIn('module "web_stack"', files["main.tf"])
        self.assertIn("ecs.t6-c1m2.large", files["main.tf"])
        self.assertNotIn('resource "alicloud_vpc"', files["main.tf"])

    def test_vpc_only_uses_vpc_network(self):
        gen = NL2HCLGenerator(environment="dev")
        files = gen.generate("创建一个VPC，包含两个可用区的交换机")
        self.assertIn('module "vpc_network"', files["main.tf"])
        self.assertNotIn('module "web_stack"', files["main.tf"])

    def test_copy_modules_to_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            dest = copy_modules(out)
            self.assertTrue((dest / "web-stack" / "main.tf").exists())
            self.assertTrue((dest / "vpc-network" / "main.tf").exists())
            self.assertEqual(MODULES_ROOT.name, "modules")

    def test_full_stack_flags(self):
        gen = NL2HCLGenerator(environment="dev")
        intent = gen.parse_intent("创建 VPC、2台 ECS、SLB 和 RDS MySQL")
        plan = plan_modules(intent, gen.defaults)
        self.assertTrue(plan.use_web_stack)
        self.assertTrue(plan.enable_ecs)
        self.assertTrue(plan.enable_slb)
        self.assertTrue(plan.enable_rds)
        files = gen.generate("创建 VPC、2台 ECS、SLB 和 RDS MySQL")
        self.assertIn("enable_slb          = true", files["main.tf"])
        self.assertIn("enable_rds          = true", files["main.tf"])

    def test_dry_run_generates_ecs_and_rds_stack(self):
        """Dry-run generation covers a multi-resource ECS + RDS stack."""
        request = "创建 VPC、2台 1核1G ECS 和 RDS MySQL 数据库"
        gen = NL2HCLGenerator(environment="dev", region="cn-hangzhou")
        intent = gen.parse_intent(request)
        plan = plan_modules(intent, gen.defaults)

        self.assertTrue(plan.use_web_stack)
        self.assertTrue(plan.enable_ecs)
        self.assertTrue(plan.enable_rds)
        self.assertEqual(plan.ecs_count, 2)
        self.assertEqual(plan.instance_type, "ecs.t6-c1m1.large")
        self.assertIn({"module": "compute-ecs", "strategy": "module-first"}, modules_for_trace(plan))
        self.assertIn({"module": "addon-rds", "strategy": "module-first"}, modules_for_trace(plan))

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            files = gen.generate(request, output_dir=out)
            for filename, content in files.items():
                (out / filename).write_text(content, encoding="utf-8")

            lint = lint_hcl(out)

        self.assertTrue(lint["ok"], lint)
        self.assertEqual([], lint["errors"])
        self.assertIn('module "web_stack"', files["main.tf"])
        self.assertIn("enable_ecs          = true", files["main.tf"])
        self.assertIn("enable_rds          = true", files["main.tf"])
        self.assertIn('ecs_instance_type   = "ecs.t6-c1m1.large"', files["main.tf"])
        self.assertIn("ecs_count           = 2", files["main.tf"])
        self.assertIn("rds_instance_id", files["outputs.tf"])
        self.assertIn("ecs_instance_ids", files["outputs.tf"])

    def _run_cli(self, extra_args, stream_calls, registry_calls, allow_credentials=False, registry_available=True):
        credential_calls = []

        def fake_check_registry():
            registry_calls.append(True)
            return registry_available

        def fake_stream_cmd(phase, cmd, cwd, timeout=60):
            stream_calls.append((phase, tuple(cmd)))
            return CommandRecord(
                phase=phase,
                command=" ".join(cmd),
                working_directory=str(cwd),
                exit_code=0,
                stdout_excerpt="Plan: 0 to add, 0 to change, 0 to destroy" if phase == "PLAN" else "ok",
                stderr_excerpt="",
                duration_ms=1,
            )

        def fake_detect_credentials():
            credential_calls.append(True)
            if not allow_credentials:
                raise AssertionError("credential probe should be flag-gated")
            return {"mode": "none", "source": None}

        with tempfile.TemporaryDirectory(prefix="tf-test-output-") as tmp_out:
            argv = [
                "nl2hcl_generator.py",
                "--request",
                "创建 VPC、2台 1核1G ECS 和 RDS MySQL 数据库",
                "--environment",
                "dev",
                "--region",
                "cn-hangzhou",
                "--output-dir",
                tmp_out,
                *extra_args,
            ]
            out = io.StringIO()
            exit_code = 0
            with patch.object(nl2hcl_generator.sys, "argv", argv), \
                    patch.object(nl2hcl_generator, "check_registry", side_effect=fake_check_registry), \
                    patch.object(nl2hcl_generator, "stream_cmd", side_effect=fake_stream_cmd), \
                    patch.object(nl2hcl_generator, "detect_credentials", side_effect=fake_detect_credentials), \
                    redirect_stdout(out):
                try:
                    nl2hcl_generator.main()
                except SystemExit as exc:
                    exit_code = exc.code if isinstance(exc.code, int) else 1

        return {"stdout": out.getvalue(), "exit_code": exit_code, "credential_calls": credential_calls}

    def test_default_dry_run_skips_registry_credentials_and_terraform(self):
        stream_calls = []
        registry_calls = []

        result = self._run_cli([], stream_calls, registry_calls)

        self.assertEqual(0, result["exit_code"])
        self.assertEqual([], registry_calls)
        self.assertEqual([], stream_calls)
        self.assertEqual([], result["credential_calls"])

    def test_with_validate_runs_init_and_validate_only(self):
        stream_calls = []
        registry_calls = []

        result = self._run_cli(["--with-validate"], stream_calls, registry_calls)

        self.assertEqual(0, result["exit_code"])
        self.assertEqual([True], registry_calls)
        self.assertEqual(
            [
                ("INIT", ("terraform", "init", "-backend=false")),
                ("VALIDATE", ("terraform", "validate")),
            ],
            stream_calls,
        )

    def test_with_plan_runs_init_validate_and_plan(self):
        stream_calls = []
        registry_calls = []

        result = self._run_cli(["--with-plan"], stream_calls, registry_calls, allow_credentials=True)

        self.assertEqual(0, result["exit_code"])
        self.assertEqual([True], registry_calls)
        self.assertEqual([True], result["credential_calls"])
        self.assertEqual(
            [
                ("INIT", ("terraform", "init", "-backend=false")),
                ("VALIDATE", ("terraform", "validate")),
                ("PLAN", ("terraform", "plan", "-input=false", "-no-color")),
            ],
            stream_calls,
        )

    def test_with_validate_registry_unreachable_exits_nonzero_without_terraform(self):
        stream_calls = []
        registry_calls = []

        result = self._run_cli(["--with-validate"], stream_calls, registry_calls, registry_available=False)

        self.assertEqual(3, result["exit_code"])
        self.assertEqual([True], registry_calls)
        self.assertEqual([], stream_calls)
        self.assertIn("部分通过", result["stdout"])
        self.assertIn("registry.terraform.io 不可达", result["stdout"])
        self.assertIn("请求的 Terraform 校验未执行", result["stdout"])

    def test_with_plan_registry_unreachable_probes_credentials_but_exits_nonzero_without_terraform(self):
        stream_calls = []
        registry_calls = []

        result = self._run_cli(["--with-plan"], stream_calls, registry_calls, allow_credentials=True, registry_available=False)

        self.assertEqual(3, result["exit_code"])
        self.assertEqual([True], registry_calls)
        self.assertEqual([True], result["credential_calls"])
        self.assertEqual([], stream_calls)
        self.assertIn("部分通过", result["stdout"])
        self.assertIn("registry.terraform.io 不可达", result["stdout"])


if __name__ == "__main__":
    unittest.main()
