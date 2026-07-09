#!/usr/bin/env python3
"""Run SkillOpt train smoke (mock rollout + stub reflect) and assert best_skill.md."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

_BENCH = Path(__file__).resolve().parent / "benchmark" / "alicloud_ops"
_REPO = Path(__file__).resolve().parents[2]
_FIXTURES = _BENCH / "fixtures"


def _prepare_workspace(tmp: Path) -> tuple[Path, Path, Path]:
    sys.path.insert(0, str(_BENCH))
    from dataloader import materialize_skillopt_splits

    dataset = _FIXTURES / "dataset.jsonl"
    trajectories = _FIXTURES / "trajectories.jsonl"
    out_root = tmp / "skillopt_out"
    split_root = tmp / "splits"
    out_root.mkdir(parents=True, exist_ok=True)
    materialize_skillopt_splits(dataset, split_root)
    return out_root, split_root, trajectories


def build_ci_cfg(out_root: Path, split_root: Path, trajectories: Path) -> dict:
    return {
        "env": "alicloud_ops",
        "out_root": str(out_root),
        "skill_init": str(_FIXTURES / "trainable_seed.md"),
        "data_path": str(_FIXTURES / "dataset.jsonl"),
        "split_dir": str(split_root),
        "split_mode": "split_dir",
        "skills_root": str(_REPO),
        "skill": "alicloud-ecs-ops",
        "trajectories_path": str(trajectories),
        "num_epochs": 1,
        "batch_size": 2,
        "accumulation": 1,
        "merge_batch_size": 2,
        "train_size": 2,
        "sel_env_num": 1,
        "test_env_num": 1,
        "eval_test": False,
        "minibatch_size": 2,
        "edit_budget": 1,
        "min_edit_budget": 1,
        "seed": 42,
        "optimizer_model": "mock-optimizer",
        "target_model": "mock-target",
        "optimizer_backend": "openai_chat",
        "target_backend": "openai_chat",
        "model_backend": "openai_chat",
        "lr_scheduler": "constant",
        "skill_update_mode": "patch",
        "use_meta_skill": False,
        "use_slow_update": False,
        "failure_only": True,
        "workers": 1,
        "analyst_workers": 1,
        "lr_control_mode": "fixed",
        "limit": 4,
    }


def run_train_smoke() -> Path:
    os.environ.setdefault("SKILL_EVOLUTION_MOCK_ROLLOUT", "1")
    os.environ.setdefault("ALIYUN_SKILLS_ROOT", str(_REPO))

    with tempfile.TemporaryDirectory(prefix="skillopt-ci-") as tmpdir:
        tmp = Path(tmpdir)
        out_root, split_root, trajectories = _prepare_workspace(tmp)
        cfg = build_ci_cfg(out_root, split_root, trajectories)

        sys.path.insert(0, str(_BENCH))
        from adapter import AliCloudOpsAdapter
        from skillopt.engine.trainer import ReflACTTrainer

        adapter = AliCloudOpsAdapter(
            split_dir=str(split_root),
            data_path=str(_FIXTURES / "dataset.jsonl"),
            skills_root=str(_REPO),
            skill="alicloud-ecs-ops",
            trajectories_path=str(trajectories),
            workers=1,
            analyst_workers=1,
            failure_only=True,
            minibatch_size=2,
            edit_budget=1,
            limit=4,
        )

        def _noop_reflect(*args, **kwargs):
            return []

        with mock.patch.object(adapter, "reflect", side_effect=_noop_reflect):
            trainer = ReflACTTrainer(cfg, adapter)
            trainer.train()

        best_skill = out_root / "best_skill.md"
        if not best_skill.is_file():
            raise SystemExit(f"[ERROR] best_skill.md not found: {best_skill}")
        content = best_skill.read_text(encoding="utf-8").strip()
        if not content:
            raise SystemExit("[ERROR] best_skill.md is empty")
        # ponytail: persist path for caller tests — copy to stable tmp under repo .runtime
        stable = _REPO / ".runtime" / "skill-evolution" / "_ci_smoke" / "best_skill.md"
        stable.parent.mkdir(parents=True, exist_ok=True)
        stable.write_text(content, encoding="utf-8")
        print(f"[SUMMARY] best_skill.md bytes={len(content)} out={best_skill}")
        return stable


def main() -> int:
    try:
        run_train_smoke()
    except ImportError as exc:
        print(f"[ERROR] skillopt not installed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
