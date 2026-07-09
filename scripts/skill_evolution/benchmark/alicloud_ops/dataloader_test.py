#!/usr/bin/env python3
"""Tests for dataloader.py."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dataloader import load_dataset, materialize_skillopt_splits

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class DataloaderTests(unittest.TestCase):
    def test_load_dataset_splits(self) -> None:
        data = load_dataset(FIXTURES / "dataset.jsonl")
        self.assertEqual(len(data["train"]), 2)
        self.assertEqual(len(data["heldout"]), 1)
        self.assertEqual(len(data["heldout_trigger"]), 1)
        self.assertEqual(data["train"][0]["query"], "创建一台 ECS 实例")
        self.assertEqual(data["heldout_trigger"][0]["expected_skill"], "alicloud-rds-ops")

    def test_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_dataset(Path("/nonexistent/dataset.jsonl"))

    def test_empty_heldout_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dataset.jsonl"
            row = {
                "schema_version": "1.0",
                "query": "only train",
                "expected_skill": "alicloud-ecs-ops",
                "split": "train",
                "priority": "P1",
                "trajectory_count": 0,
            }
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            data = load_dataset(path)
            self.assertEqual(len(data["train"]), 1)
            self.assertEqual(data["heldout"], [])
            self.assertEqual(data["heldout_trigger"], [])

    def test_materialize_skillopt_splits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            split_root = Path(tmp) / "splits"
            materialize_skillopt_splits(FIXTURES / "dataset.jsonl", split_root)
            train = json.loads((split_root / "train" / "items.json").read_text(encoding="utf-8"))
            val = json.loads((split_root / "val" / "items.json").read_text(encoding="utf-8"))
            test = json.loads((split_root / "test" / "items.json").read_text(encoding="utf-8"))
            self.assertEqual(len(train), 2)
            self.assertEqual(len(val), 1)
            self.assertEqual(len(test), 1)
            self.assertEqual(test[0]["expected_skill"], "alicloud-rds-ops")


if __name__ == "__main__":
    unittest.main()
