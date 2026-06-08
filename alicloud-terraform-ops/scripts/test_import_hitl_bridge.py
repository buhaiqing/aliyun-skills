#!/usr/bin/env python3
"""Import → HITL Mode A 衔接单元测试。"""

from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import terraform_ops
from hitl_mode_a import CheckpointType, create_checkpoint
from reverse_engineering import collect_output_previews, import_resources_for_hitl


class TestImportHitlBridge(unittest.TestCase):
    def test_import_resources_for_hitl(self):
        resources = [
            {"type": "vpc", "tf_name": "imported_vpc_bp1abc12", "id": "vpc-bp1abc123456"},
            {
                "type": "disk_attachment",
                "tf_name": "attach_bp1disk01",
                "id": "d-bp1:i-bp1",
            },
        ]
        hitl = import_resources_for_hitl(resources)
        self.assertEqual(len(hitl), 2)
        self.assertEqual(hitl[1]["type"], "disk_attachment")

    def test_collect_output_previews(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "vpc.tf").write_text("# vpc\n", encoding="utf-8")
            (out / "import.sh").write_text("#!/bin/bash\n", encoding="utf-8")
            previews = collect_output_previews(out)
            self.assertIn("vpc.tf", previews)
            self.assertIn("import.sh", previews)

    def test_create_import_checkpoint(self):
        cp = create_checkpoint(
            CheckpointType.IMPORT,
            "dev",
            resources=[{"type": "vpc", "name": "imported_vpc_bp1abc12", "id": "vpc-bp1"}],
            generated_files={"vpc.tf": "# vpc"},
            user_inputs={"request": "导入 vpc: vpc-bp1", "output_dir": "/tmp/out"},
        )
        step_types = [s.type.value for s in cp.steps]
        self.assertEqual(step_types, ["cp1_intent", "cp4_import", "cp3_plan"])
        self.assertEqual(cp.steps[0].data.get("intent"), "导入 vpc: vpc-bp1")

    @patch("hitl_mode_a.CLIController")
    @patch("reverse_engineering.ReverseEngineering")
    def test_run_import_with_hitl(self, mock_re_cls, mock_controller_cls):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "generated"
            out.mkdir()
            (out / "vpc.tf").write_text("# vpc\n", encoding="utf-8")
            (out / "import.sh").write_text("#!/bin/bash\n", encoding="utf-8")

            mock_engine = MagicMock()
            mock_engine.run.return_value = (
                True,
                [{
                    "type": "vpc",
                    "tf_name": "imported_vpc_bp1abc12",
                    "id": "vpc-bp1abc123456",
                    "tf_type": "alicloud_vpc",
                }],
            )
            mock_re_cls.return_value = mock_engine
            mock_controller_cls.return_value.run.return_value = None

            args = argparse.Namespace(
                resource_type="vpc",
                resource_id="vpc-bp1abc123456",
                resource_ids=None,
                region="cn-hangzhou",
                environment="dev",
                output_dir=out,
                discover_associated=False,
                skip_preflight=True,
            )
            rc = terraform_ops._run_import_with_hitl(args)
            self.assertEqual(rc, 0)
            mock_engine.run.assert_called_once_with(
                resource_type="vpc",
                resource_ids=["vpc-bp1abc123456"],
                discover_associated=False,
                dry_run=False,
            )
            mock_controller_cls.assert_called_once()


if __name__ == "__main__":
    unittest.main()
