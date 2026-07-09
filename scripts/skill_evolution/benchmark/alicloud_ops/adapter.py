#!/usr/bin/env python3
"""SkillOpt EnvAdapter for alicloud_ops benchmark."""

from __future__ import annotations

import os
from pathlib import Path

from dataloader import build_skillopt_dataloader_class, materialize_skillopt_splits
from reflect import run_reflect
from rollout import resolve_skills_root, run_batch
from trajectories import resolve_trajectories_path

from skillopt.datasets.base import BatchSpec
from skillopt.envs.base import EnvAdapter


class AliCloudOpsAdapter(EnvAdapter):
    def __init__(
        self,
        split_dir: str = "",
        data_path: str = "",
        skills_root: str = "",
        skill: str = "alicloud-ecs-ops",
        trajectories_path: str = "",
        split_mode: str = "split_dir",
        split_ratio: str = "2:1:7",
        split_seed: int = 42,
        split_output_dir: str = "",
        workers: int = 1,
        analyst_workers: int = 1,
        failure_only: bool = False,
        minibatch_size: int = 4,
        edit_budget: int = 2,
        seed: int = 42,
        limit: int = 0,
    ) -> None:
        self.skills_root = skills_root
        self.skill = skill
        self.trajectories_path = trajectories_path
        self.workers = workers
        self.analyst_workers = analyst_workers
        self.failure_only = failure_only
        self.minibatch_size = minibatch_size
        self.edit_budget = edit_budget
        LoaderCls = build_skillopt_dataloader_class()
        self.dataloader = LoaderCls(
            split_dir=split_dir,
            data_path=data_path,
            split_mode=split_mode,
            split_ratio=split_ratio,
            split_seed=split_seed,
            split_output_dir=split_output_dir,
            seed=seed,
            limit=limit,
        )

    def setup(self, cfg: dict) -> None:
        super().setup(cfg)
        root = resolve_skills_root(self.skills_root or cfg.get("skills_root"))
        skill = str(cfg.get("skill") or self.skill)
        dataset = Path(cfg.get("data_path") or self.dataloader.data_path)
        if not dataset.is_file():
            dataset = root / ".runtime" / "skill-evolution" / skill / "dataset.jsonl"
        split_root = Path(cfg.get("split_dir") or self.dataloader.split_dir or root / ".runtime" / "skill-evolution" / skill / "splits")
        materialize_skillopt_splits(dataset, split_root)
        cfg = dict(cfg)
        cfg["split_dir"] = str(split_root)
        cfg["split_mode"] = "split_dir"
        cfg["data_path"] = str(dataset)
        self.dataloader.split_dir = str(split_root)
        self.dataloader.split_mode = "split_dir"
        self.dataloader.data_path = str(dataset)
        self.dataloader.setup(cfg)
        if not self.trajectories_path:
            self.trajectories_path = str(resolve_trajectories_path(cfg.get("trajectories_path"), root, skill))

    def get_dataloader(self):
        return self.dataloader

    def build_env_from_batch(self, batch: BatchSpec, **kwargs):
        return list(batch.payload or [])

    def build_train_env(self, batch_size: int, seed: int, **kwargs):
        batch = self.dataloader.build_train_batch(batch_size=batch_size, seed=seed, **kwargs)
        return self.build_env_from_batch(batch, **kwargs)

    def build_eval_env(self, env_num: int, split: str, seed: int, **kwargs):
        batch = self.dataloader.build_eval_batch(env_num=env_num, split=split, seed=seed, **kwargs)
        return self.build_env_from_batch(batch, **kwargs)

    def rollout(self, env_manager, skill_content: str, out_dir: str, **kwargs) -> list[dict]:
        items: list[dict] = env_manager
        return run_batch(
            items=items,
            skill_content=skill_content,
            out_root=out_dir,
            skills_root=self.skills_root,
            trajectories_path=self.trajectories_path,
        )

    def reflect(self, results: list[dict], skill_content: str, out_dir: str, **kwargs) -> list[dict | None]:
        return run_reflect(
            results,
            skill_content,
            out_dir,
            trajectories_path=self.trajectories_path,
            skills_root=self.skills_root,
            skill=self.skill,
            workers=self.analyst_workers,
            failure_only=self.failure_only,
            minibatch_size=self.minibatch_size,
            edit_budget=self.edit_budget,
            random_seed=kwargs.get("random_seed"),
            error_system=self.get_error_minibatch_prompt(),
            success_system=self.get_success_minibatch_prompt(),
            step_buffer_context=kwargs.get("step_buffer_context", ""),
            meta_skill_context=kwargs.get("meta_skill_context", ""),
            prediction_dir=kwargs.get("prediction_dir", os.path.join(out_dir, "predictions")),
            patches_dir=kwargs.get("patches_dir", os.path.join(out_dir, "patches")),
            cfg=getattr(self, "_cfg", {}),
        )

    def get_task_types(self) -> list[str]:
        return ["alicloud_ops"]
