#!/usr/bin/env python3
"""Score benchmark rollout results."""

from __future__ import annotations

from typing import Any

_RUBRIC_BUMP = 0.2


def _rubric_pass(rollout: dict[str, Any]) -> bool:
    if rollout.get("rubric_pass") is True:
        return True
    meta = rollout.get("metadata")
    return isinstance(meta, dict) and meta.get("rubric_pass") is True


def score_rollout(rollout: dict[str, Any], expected_skill: str = "alicloud-ecs-ops") -> float:
    status = rollout.get("status")
    score = 0.0

    if status == "mock":
        score = 1.0 if rollout.get("skill_loaded") else 0.0
    elif status == "ok":
        score = 0.8
        if rollout.get("skill") == expected_skill:
            score = min(1.0, score + 0.1)
        if rollout.get("skill_loaded"):
            score = min(1.0, score + 0.1)
    elif status == "failed":
        score = 0.0
    else:
        score = 0.0

    if _rubric_pass(rollout):
        score = min(1.0, score + _RUBRIC_BUMP)

    return max(0.0, min(1.0, score))
