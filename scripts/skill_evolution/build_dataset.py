#!/usr/bin/env python3
"""Build SkillOpt-ready dataset from eval_queries + trajectories (Milestone A)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, cast

from schema import DatasetRow, Split, make_dataset_row

HELDOUT_POSITIVE_TAIL = 2


def resolve_skills_root(explicit: str | Path | None = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("ALIYUN_SKILLS_ROOT") or os.environ.get("SKILLS_DIR")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2]


def load_eval_queries(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    positives = list(data.get("queries") or [])
    negatives = list(data.get("negative_queries") or [])
    return positives, negatives


def count_trajectories(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def assign_splits(
    positives: list[dict[str, Any]],
    negatives: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    n_held = min(HELDOUT_POSITIVE_TAIL, len(positives))
    train_pos = positives[:-n_held] if n_held else positives
    held_pos = positives[-n_held:] if n_held else []

    for item in train_pos:
        rows.append({**item, "split": "train"})
    for item in held_pos:
        rows.append({**item, "split": "heldout"})
    for item in negatives:
        rows.append({**item, "split": "heldout_trigger"})
    return rows


def build_dataset_rows(
    eval_path: Path,
    trajectories_path: Path,
    skill: str,
) -> list[DatasetRow]:
    positives, negatives = load_eval_queries(eval_path)
    traj_count = count_trajectories(trajectories_path)
    rows: list[DatasetRow] = []
    for item in assign_splits(positives, negatives):
        if item.get("expected_skill") != skill and item.get("split") != "heldout_trigger":
            continue
        rows.append(
            make_dataset_row(
                query=item.get("query", ""),
                expected_skill=item.get("expected_skill", skill),
                split=cast(Split, item["split"]),
                priority=item.get("priority", "P1"),
                trajectory_count=traj_count if item.get("expected_skill") == skill else 0,
            )
        )
    return rows


def write_dataset(rows: list[DatasetRow], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build SkillOpt dataset JSONL")
    p.add_argument("--skill", required=True)
    p.add_argument("--skills-root", default=None)
    p.add_argument("--eval-queries", default=None)
    p.add_argument("--trajectories", default=None)
    p.add_argument("--out", default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    skills_root = resolve_skills_root(args.skills_root)
    base = skills_root / ".runtime" / "skill-evolution" / args.skill
    eval_path = Path(args.eval_queries) if args.eval_queries else skills_root / args.skill / "assets/eval_queries.json"
    traj_path = Path(args.trajectories) if args.trajectories else base / "trajectories.jsonl"
    out = Path(args.out) if args.out else base / "dataset.jsonl"

    if not eval_path.is_file():
        print(f"[ERROR] eval_queries not found: {eval_path}", file=sys.stderr)
        return 1

    rows = build_dataset_rows(eval_path, traj_path, args.skill)
    write_dataset(rows, out)
    print(f"[SUMMARY] skill={args.skill} dataset_rows={len(rows)} out={out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
