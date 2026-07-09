#!/usr/bin/env python3
"""
gcl_memory_test_rg.py — Independent test file for WT-3 Layer 1 RG/Tags
indexing. Does NOT modify the existing gcl_memory_test.py (zero-regression
on the 84 existing tests).

Covers:
- memory_store_lite auto-extracts RG/Tags from command when no explicit args
- memory_store_lite honors explicit resource_group_id / tags / missing_dimensions
- _build_memory_entry produces the new fields from the generator command
- missing_dimensions computation: True iff RG None AND tags empty
- warning/suggestion only populated when missing_dimensions=True
- CLI store-lite parses --tags-json + --resource-group-id + --missing-dimensions

Python 3.10+ stdlib only.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import gcl_memory  # noqa: E402
from gcl_memory import (  # noqa: E402
    _build_memory_entry,
    _extract_resource_dimensions_from_command,
    memory_store_lite,
)


class TestExtractResourceDimensionsFromCommand(unittest.TestCase):
    """The gcl_memory-side helper delegates to WT-1 parser."""

    def test_command_with_rg_and_repeatlist(self) -> None:
        cmd = "aliyun ecs DescribeInstances --ResourceGroupId rg-x " \
              "--Tag.1.Key env --Tag.1.Value prod"
        rd = _extract_resource_dimensions_from_command(cmd)
        self.assertEqual(rd["resource_group_id"], "rg-x")
        self.assertEqual(rd["tags"], [{"key": "env", "value": "prod"}])
        self.assertFalse(rd["missing_dimensions"])

    def test_command_with_no_rg_no_tags(self) -> None:
        rd = _extract_resource_dimensions_from_command(
            "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
        )
        self.assertIsNone(rd["resource_group_id"])
        self.assertEqual(rd["tags"], [])
        self.assertTrue(rd["missing_dimensions"])
        self.assertIsNotNone(rd["warning"])
        self.assertIsNotNone(rd["suggestion"])

    def test_empty_command(self) -> None:
        rd = _extract_resource_dimensions_from_command("")
        self.assertTrue(rd["missing_dimensions"])

    def test_json_tags_form(self) -> None:
        """JSON Tags array, parsed as single shell-token (no surrounding
        quotes — those are stripped by shell before the wrapper sees them)."""
        cmd = 'aliyun rds DescribeDBInstances --Tags [{"key":"env","value":"prod"}]'
        rd = _extract_resource_dimensions_from_command(cmd)
        self.assertEqual(rd["tags"], [{"key": "env", "value": "prod"}])
        self.assertFalse(rd["missing_dimensions"])


class TestMemoryStoreLiteResourceDimensions(unittest.TestCase):
    """memory_store_lite auto-extracts RG/Tags from command by default."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.skill = "alicloud-ecs-ops"
        self.op = "DescribeInstances"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _last_entry(self) -> dict:
        files = list((self.root / self.skill).glob("*.jsonl"))
        self.assertEqual(len(files), 1, f"expected 1 file, got {files}")
        lines = files[0].read_text(encoding="utf-8").splitlines()
        return json.loads(lines[-1])

    def test_auto_extract_rg_and_tags(self) -> None:
        cmd = "aliyun ecs DescribeInstances --ResourceGroupId rg-test " \
              "--Tag.1.Key env --Tag.1.Value prod"
        rc = memory_store_lite(
            skill=self.skill, operation=self.op, command=cmd,
            memory_root=self.root,
        )
        self.assertEqual(rc, 0)
        e = self._last_entry()
        self.assertEqual(e["resource_group_id"], "rg-test")
        self.assertEqual(e["tags"], [{"key": "env", "value": "prod"}])
        self.assertFalse(e["missing_dimensions"])
        self.assertNotIn("warning", e)
        self.assertNotIn("suggestion", e)

    def test_auto_extract_missing_both_dims(self) -> None:
        cmd = "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
        rc = memory_store_lite(
            skill=self.skill, operation=self.op, command=cmd,
            memory_root=self.root,
        )
        self.assertEqual(rc, 0)
        e = self._last_entry()
        self.assertIsNone(e["resource_group_id"])
        self.assertEqual(e["tags"], [])
        self.assertTrue(e["missing_dimensions"])
        # warning + suggestion only present when missing
        self.assertIn("warning", e)
        self.assertIn("suggestion", e)

    def test_auto_extract_only_rg(self) -> None:
        cmd = "aliyun ecs DescribeInstances --ResourceGroupId rg-only"
        rc = memory_store_lite(
            skill=self.skill, operation=self.op, command=cmd,
            memory_root=self.root,
        )
        self.assertEqual(rc, 0)
        e = self._last_entry()
        self.assertEqual(e["resource_group_id"], "rg-only")
        self.assertFalse(e["missing_dimensions"])
        self.assertNotIn("warning", e)

    def test_auto_extract_only_tags(self) -> None:
        cmd = "aliyun ecs DescribeInstances --Tag.1.Key env --Tag.1.Value prod"
        rc = memory_store_lite(
            skill=self.skill, operation=self.op, command=cmd,
            memory_root=self.root,
        )
        self.assertEqual(rc, 0)
        e = self._last_entry()
        self.assertIsNone(e["resource_group_id"])
        self.assertEqual(e["tags"], [{"key": "env", "value": "prod"}])
        self.assertFalse(e["missing_dimensions"])

    def test_explicit_args_override_command(self) -> None:
        """When caller passes explicit RG, don't re-parse command."""
        cmd = "aliyun ecs DescribeInstances --ResourceGroupId rg-cmd-arg"
        rc = memory_store_lite(
            skill=self.skill, operation=self.op, command=cmd,
            memory_root=self.root,
            resource_group_id="rg-explicit-override",
            tags=[{"key": "x", "value": "y"}],
            missing_dimensions=False,
        )
        self.assertEqual(rc, 0)
        e = self._last_entry()
        self.assertEqual(e["resource_group_id"], "rg-explicit-override")
        self.assertEqual(e["tags"], [{"key": "x", "value": "y"}])
        self.assertFalse(e["missing_dimensions"])

    def test_explicit_missing_dimensions_override(self) -> None:
        """Caller can force missing_dimensions=True to flag a command."""
        cmd = "aliyun ecs DescribeInstances --ResourceGroupId rg-x"
        rc = memory_store_lite(
            skill=self.skill, operation=self.op, command=cmd,
            memory_root=self.root,
            missing_dimensions=True,
        )
        self.assertEqual(rc, 0)
        e = self._last_entry()
        # RG set but caller claims missing → reflects caller's intent.
        self.assertTrue(e["missing_dimensions"])

    def test_empty_command_path(self) -> None:
        rc = memory_store_lite(
            skill=self.skill, operation="unknown", command="",
            memory_root=self.root,
        )
        self.assertEqual(rc, 0)
        e = self._last_entry()
        self.assertTrue(e["missing_dimensions"])

    def test_unicode_tags_persisted(self) -> None:
        cmd = "aliyun ecs DescribeInstances --Tag.1.Key 业务线 --Tag.1.Value 核心"
        rc = memory_store_lite(
            skill=self.skill, operation=self.op, command=cmd,
            memory_root=self.root,
        )
        self.assertEqual(rc, 0)
        e = self._last_entry()
        self.assertEqual(e["tags"], [{"key": "业务线", "value": "核心"}])

    def test_existing_fields_still_present(self) -> None:
        """Zero-regression: original entry fields unchanged."""
        rc = memory_store_lite(
            skill=self.skill, operation=self.op,
            command="aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            exit_code=0, duration_ms=42, status="success",
            execution_path="wrapper",
            memory_root=self.root,
        )
        self.assertEqual(rc, 0)
        e = self._last_entry()
        self.assertEqual(e["skill"], self.skill)
        self.assertEqual(e["operation"], self.op)
        self.assertEqual(e["exit_code"], 0)
        self.assertEqual(e["duration_ms"], 42)
        self.assertEqual(e["source"], "skillopt-wrapper")
        self.assertIn("timestamp", e)
        # new fields
        self.assertIn("resource_group_id", e)
        self.assertIn("tags", e)
        self.assertIn("missing_dimensions", e)


class TestBuildMemoryEntryResourceDimensions(unittest.TestCase):
    """_build_memory_entry (GCL full-trace path) extracts from gen.command."""

    def _trace(self, command: str) -> dict:
        return {
            "skill": "alicloud-ecs-ops",
            "operation": "DescribeInstances",
            "rubric_version": "v1",
            "final": {"status": "PASS"},
            "iterations": [
                {
                    "generator": {"command": command, "exit_code": 0,
                                  "execution_path": "aliyun",
                                  "duration_ms": 10},
                    "critic": {"scores": {"correctness": 1.0}},
                }
            ],
        }

    def test_rg_and_tags_in_full_trace(self) -> None:
        cmd = "aliyun ecs DescribeInstances --ResourceGroupId rg-x " \
              "--Tag.1.Key env --Tag.1.Value prod"
        entry = _build_memory_entry(self._trace(cmd), None, None)
        self.assertEqual(entry["resource_group_id"], "rg-x")
        self.assertEqual(entry["tags"], [{"key": "env", "value": "prod"}])
        self.assertFalse(entry["missing_dimensions"])

    def test_missing_dimensions_in_full_trace(self) -> None:
        cmd = "aliyun ecs DescribeInstances --RegionId cn-hangzhou"
        entry = _build_memory_entry(self._trace(cmd), None, None)
        self.assertIsNone(entry["resource_group_id"])
        self.assertEqual(entry["tags"], [])
        self.assertTrue(entry["missing_dimensions"])
        self.assertIn("warning", entry)
        self.assertIn("suggestion", entry)


class TestStoreLiteCLIResourceDimensions(unittest.TestCase):
    """CLI store-lite accepts --resource-group-id / --tags-json / --missing-dimensions."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.skill = "alicloud-ecs-ops"
        self.op = "DescribeInstances"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _read_last(self) -> dict:
        files = list((self.root / self.skill).glob("*.jsonl"))
        self.assertEqual(len(files), 1)
        return json.loads(files[0].read_text(encoding="utf-8").splitlines()[-1])

    def test_cli_with_resource_group_id(self) -> None:
        rc = gcl_memory.main([
            "store-lite",
            "--skill", self.skill,
            "--operation", self.op,
            "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            "--resource-group-id", "rg-cli-test",
            "--memory-root", str(self.root),
        ])
        self.assertEqual(rc, 0)
        e = self._read_last()
        self.assertEqual(e["resource_group_id"], "rg-cli-test")
        self.assertFalse(e["missing_dimensions"])

    def test_cli_with_tags_json(self) -> None:
        tags = json.dumps([{"key": "env", "value": "prod"}])
        rc = gcl_memory.main([
            "store-lite",
            "--skill", self.skill,
            "--operation", self.op,
            "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            "--tags-json", tags,
            "--memory-root", str(self.root),
        ])
        self.assertEqual(rc, 0)
        e = self._read_last()
        self.assertEqual(e["tags"], [{"key": "env", "value": "prod"}])
        self.assertFalse(e["missing_dimensions"])

    def test_cli_with_missing_dimensions_override_true(self) -> None:
        """Even with RG set, caller can flag missing_dimensions=true."""
        rc = gcl_memory.main([
            "store-lite",
            "--skill", self.skill,
            "--operation", self.op,
            "--command", "aliyun ecs DescribeInstances --RegionId cn-hangzhou",
            "--resource-group-id", "rg-cli",
            "--missing-dimensions", "true",
            "--memory-root", str(self.root),
        ])
        self.assertEqual(rc, 0)
        e = self._read_last()
        self.assertTrue(e["missing_dimensions"])

    def test_cli_with_invalid_tags_json_falls_back(self) -> None:
        """Invalid JSON in --tags-json → falls back to command parsing."""
        cmd = "aliyun ecs DescribeInstances --ResourceGroupId rg-fallback"
        rc = gcl_memory.main([
            "store-lite",
            "--skill", self.skill,
            "--operation", self.op,
            "--command", cmd,
            "--tags-json", "this is not json",
            "--memory-root", str(self.root),
        ])
        self.assertEqual(rc, 0)
        e = self._read_last()
        # Fallback succeeded: RG parsed from command.
        self.assertEqual(e["resource_group_id"], "rg-fallback")

    def test_cli_backward_compatible_no_new_args(self) -> None:
        """Old callers with no new args still work, RG auto-extracted from cmd."""
        cmd = "aliyun ecs DescribeInstances --ResourceGroupId rg-old-style " \
              "--Tag.1.Key env --Tag.1.Value prod"
        rc = gcl_memory.main([
            "store-lite",
            "--skill", self.skill,
            "--operation", self.op,
            "--command", cmd,
            "--memory-root", str(self.root),
        ])
        self.assertEqual(rc, 0)
        e = self._read_last()
        self.assertEqual(e["resource_group_id"], "rg-old-style")
        self.assertEqual(e["tags"], [{"key": "env", "value": "prod"}])
        self.assertFalse(e["missing_dimensions"])


if __name__ == "__main__":
    unittest.main()