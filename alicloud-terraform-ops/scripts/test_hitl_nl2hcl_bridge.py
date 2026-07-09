#!/usr/bin/env python3
"""NL2HCL → HITL Mode A 衔接单元测试。"""

import tempfile
import unittest
from pathlib import Path

from hitl_mode_a import CheckpointType, create_checkpoint
from nl2hcl_generator import NL2HCLGenerator, intent_to_hitl_resources


class TestHitlNl2hclBridge(unittest.TestCase):
    def test_intent_to_hitl_resources(self):
        gen = NL2HCLGenerator("dev", "cn-hangzhou")
        intent = gen.parse_intent("创建 VPC、2台 ECS、RDS MySQL")
        resources = intent_to_hitl_resources(intent)
        types = {r["type"] for r in resources}
        self.assertIn("vpc", types)
        self.assertIn("ecs", types)
        self.assertIn("rds", types)
        ecs = next(r for r in resources if r["type"] == "ecs")
        self.assertEqual(ecs["attributes"]["count"], 2)

    def test_create_checkpoint_carries_generation(self):
        cp = create_checkpoint(
            CheckpointType.NL2HCL,
            "dev",
            resources=[{"type": "vpc", "name": "vpc"}],
            generated_files={"main.tf": 'module "web_stack" {}'},
            user_inputs={"request": "创建 VPC", "output_dir": "/tmp/out"},
        )
        self.assertIn("main.tf", cp.generated_files)
        self.assertEqual(cp.user_inputs["request"], "创建 VPC")
        self.assertEqual(cp.steps[0].data.get("intent"), "创建 VPC")

    def test_prepare_generation_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            gen = NL2HCLGenerator("dev", "cn-hangzhou")
            request = "创建 VPC 和两个交换机"
            files = gen.generate(request, output_dir=out)
            for name, content in files.items():
                (out / name).write_text(content, encoding="utf-8")
            self.assertTrue((out / "main.tf").exists())
            self.assertTrue((out / "modules" / "vpc-network" / "main.tf").exists())


if __name__ == "__main__":
    unittest.main()
