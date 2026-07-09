#!/usr/bin/env python3
"""Shared TypedDict schemas for skill_evolution Milestone A/B artifacts."""

from __future__ import annotations

from typing import Literal, TypedDict

DATASET_SCHEMA_VERSION = "1.0"

Split = Literal["train", "heldout", "heldout_trigger"]

SPLIT_KEYS: tuple[Split, ...] = ("train", "heldout", "heldout_trigger")


class DatasetRow(TypedDict):
    """One line of Milestone A ``dataset.jsonl`` — MS SkillOpt ``alicloud_ops`` benchmark input.

    Fields
    ------
    schema_version:
        Dataset row schema revision; currently ``"1.0"``.
    query:
        Natural-language user request from ``assets/eval_queries.json``.
    expected_skill:
        Skill that should be triggered, e.g. ``alicloud-ecs-ops``.
    split:
        ``train`` — positive queries for training;
        ``heldout`` — last N positive queries held out for validation;
        ``heldout_trigger`` — negative queries (wrong-skill trigger tests).
    priority:
        Eval priority from eval_queries (``P0`` / ``P1``).
    trajectory_count:
        Count of exported L1 trajectories for this skill. Rollout/reflect consume
        ``trajectories.jsonl`` at ``.runtime/skill-evolution/{skill}/``.
    """

    schema_version: str
    query: str
    expected_skill: str
    split: Split
    priority: str
    trajectory_count: int


class DatasetBySplit(TypedDict):
    """``load_dataset()`` return shape — rows grouped by ``split``."""

    train: list[DatasetRow]
    heldout: list[DatasetRow]
    heldout_trigger: list[DatasetRow]


def make_dataset_row(
    *,
    query: str,
    expected_skill: str,
    split: Split,
    priority: str = "P1",
    trajectory_count: int = 0,
) -> DatasetRow:
    return {
        "schema_version": DATASET_SCHEMA_VERSION,
        "query": query,
        "expected_skill": expected_skill,
        "split": split,
        "priority": priority,
        "trajectory_count": trajectory_count,
    }
