#!/usr/bin/env python3
"""Benchmark dataset — Milestone B smoke loader + SkillOpt SplitDataLoader."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_EVOLUTION_DIR = Path(__file__).resolve().parents[2]
if str(_EVOLUTION_DIR) not in sys.path:
    sys.path.insert(0, str(_EVOLUTION_DIR))

from schema import SPLIT_KEYS, DatasetBySplit, DatasetRow  # noqa: E402

_SPLIT_MAP = {
    "train": "train",
    "heldout": "val",
    "heldout_trigger": "test",
}


def resolve_dataset_path(skills_root: Path, skill: str) -> Path:
    return skills_root / ".runtime" / "skill-evolution" / skill / "dataset.jsonl"


def load_dataset(path: Path) -> DatasetBySplit:
    if not path.is_file():
        raise FileNotFoundError(f"dataset not found: {path}")

    result: DatasetBySplit = {key: [] for key in SPLIT_KEYS}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        row: DatasetRow = json.loads(stripped)
        split = row.get("split")
        if split in result:
            result[split].append(row)
    return result


def normalize_item(row: dict[str, Any], index: int) -> dict[str, Any]:
    query = str(row.get("query") or row.get("question") or "")
    skill = str(row.get("expected_skill") or "alicloud-ecs-ops")
    return {
        "id": str(row.get("id") or f"{skill}-{index:04d}"),
        "question": query,
        "query": query,
        "expected_skill": skill,
        "split": str(row.get("split") or "train"),
        "priority": str(row.get("priority") or "P1"),
        "trajectory_count": int(row.get("trajectory_count") or 0),
        "task_type": "alicloud_ops",
    }


def load_dataset_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            rows.append(normalize_item(json.loads(line), idx))
    return rows


def materialize_skillopt_splits(dataset_path: Path, split_root: Path) -> Path:
    """Write train/val/test/items.json for SkillOpt split_dir mode."""
    buckets: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}
    for row in load_dataset_rows(dataset_path):
        bucket = _SPLIT_MAP.get(str(row.get("split", "train")), "train")
        buckets[bucket].append(row)
    split_root.mkdir(parents=True, exist_ok=True)
    for name, items in buckets.items():
        out_dir = split_root / name
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "items.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return split_root


def build_skillopt_dataloader_class():
    """Return AliCloudOpsDataLoader when skillopt is installed."""
    from skillopt.datasets.base import SplitDataLoader

    class AliCloudOpsDataLoader(SplitDataLoader):
        def load_raw_items(self, data_path: str) -> list[dict]:
            return load_dataset_rows(Path(data_path))

        def load_split_items(self, split_path: str) -> list[dict]:
            items_path = Path(split_path) / "items.json"
            if not items_path.is_file():
                raise FileNotFoundError(f"items.json not found in {split_path}")
            raw = json.loads(items_path.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                raise ValueError(f"expected list in {items_path}")
            return [normalize_item(row, idx) for idx, row in enumerate(raw)]

    return AliCloudOpsDataLoader
