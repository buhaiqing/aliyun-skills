#!/usr/bin/env python3
"""Tests for rollout.py."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rollout import process_one, resolve_skills_root, run_batch, run_rollout

REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE_TRAJ = Path(__file__).resolve().parent / "fixtures" / "trajectories.jsonl"


class RolloutTests(unittest.TestCase):
    def test_mock_mode_via_param(self) -> None:
        result = run_rollout("创建 ECS", "# skill", mock=True, trajectories=[])
        self.assertEqual(result["status"], "mock")
        self.assertTrue(result["skill_loaded"])
        self.assertEqual(result["operation"], "CreateInstance")
        self.assertIn("trajectory_memory_context", result)

    def test_mock_mode_via_env(self) -> None:
        with mock.patch.dict(os.environ, {"SKILL_EVOLUTION_MOCK_ROLLOUT": "1"}, clear=False):
            result = run_rollout("query", "content", mock=None)
        self.assertEqual(result["status"], "mock")
        self.assertTrue(result["skill_loaded"])

    def test_mock_empty_skill_md_not_loaded(self) -> None:
        result = run_rollout("query", "   ", mock=True)
        self.assertEqual(result["status"], "mock")
        self.assertFalse(result["skill_loaded"])

    def test_mock_false_wrapper_missing(self) -> None:
        with mock.patch.dict(os.environ, {"SKILL_EVOLUTION_MOCK_ROLLOUT": "1"}, clear=False):
            result = run_rollout(
                "查看 ECS 实例",
                "# skill",
                mock=False,
                skill="alicloud-ecs-ops",
                skills_root=REPO_ROOT / "nonexistent-skills-root",
            )
        self.assertEqual(result["status"], "failed")
        self.assertIn("harness wrapper not found", result["message"])
        self.assertIn("trajectory_memory_context", result)

    def test_unsupported_skill_skipped(self) -> None:
        result = run_rollout(
            "创建一台 RDS",
            "# skill",
            mock=False,
            skill="alicloud-rds-ops",
            skills_root=REPO_ROOT,
            trajectories=[],
        )
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["operation"], "unknown")

    def test_rollout_redacts_secrets_in_previews(self) -> None:
        fake_wrapper = REPO_ROOT / "alicloud-ecs-ops/scripts/ecs-harness-wrapper.sh"
        harness_out = {
            "exit_code": 0,
            "stdout": '{"Code":200}\nAccessKeySecret=LTAIbogusSecret12345',
            "stderr": "AccessKeySecret=foo",
            "rubric_pass": True,
            "api_payload": {"Code": 200},
        }
        with mock.patch("rollout._find_harness_wrapper", return_value=fake_wrapper):
            with mock.patch("rollout._run_harness", return_value=harness_out):
                result = run_rollout(
                    "查看 ECS 实例",
                    "# ecs",
                    mock=False,
                    skill="alicloud-ecs-ops",
                    skills_root=REPO_ROOT,
                    trajectories=[],
                )
        self.assertNotIn("LTAIbogusSecret", result.get("stdout_preview", ""))
        self.assertIn("****", result.get("stdout_preview", ""))

    def test_rubric_fail_exit_zero_without_api_json_on_mutating(self) -> None:
        fake_wrapper = REPO_ROOT / "alicloud-ecs-ops/scripts/ecs-harness-wrapper.sh"
        harness_out = {
            "exit_code": 0,
            "stdout": "plain text no json",
            "stderr": "",
            "rubric_pass": False,
            "api_payload": {},
        }
        with mock.patch("rollout._find_harness_wrapper", return_value=fake_wrapper):
            with mock.patch("rollout._run_harness", return_value=harness_out):
                result = run_rollout(
                    "创建一台 ECS",
                    "# ecs",
                    mock=False,
                    skill="alicloud-ecs-ops",
                    skills_root=REPO_ROOT,
                    trajectories=[],
                    allow_mutating=True,
                )
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["rubric_pass"])

    def test_persisted_rollout_json_is_redacted(self) -> None:
        fake_wrapper = REPO_ROOT / "alicloud-ecs-ops/scripts/ecs-harness-wrapper.sh"
        harness_out = {
            "exit_code": 0,
            "stdout": '{"Code":200}\nSecretKey=leaked-value',
            "stderr": "",
            "rubric_pass": True,
            "api_payload": {"Code": 200},
        }
        item = {"id": "redact-1", "question": "查看 ECS", "expected_skill": "alicloud-ecs-ops"}
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("rollout._find_harness_wrapper", return_value=fake_wrapper):
                with mock.patch("rollout._run_harness", return_value=harness_out):
                    process_one(item, "# seed", tmp, mock=False, skills_root=REPO_ROOT, trajectories=[])
            saved = json.loads((Path(tmp) / "predictions" / "redact-1" / "rollout.json").read_text(encoding="utf-8"))
        self.assertNotIn("leaked-value", json.dumps(saved))
        self.assertIn("****", saved.get("stdout_preview", ""))

    def test_run_batch_empty_items(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results = run_batch([], "# seed", tmp, mock=True, skills_root=REPO_ROOT)
            self.assertEqual(results, [])
            self.assertEqual(json.loads((Path(tmp) / "rollouts.json").read_text(encoding="utf-8")), [])

    def test_mutating_blocked_without_flag(self) -> None:
        result = run_rollout(
            "创建一台 ECS",
            "# ecs",
            mock=False,
            skill="alicloud-ecs-ops",
            skills_root=REPO_ROOT,
            trajectories=[],
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["operation"], "CreateInstance")
        self.assertIn("mutating operation blocked", result["message"])

    def test_real_mode_harness_with_stub_aliyun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "aliyun"
            stub.write_text('#!/bin/bash\necho \'{"Code":200}\'\n', encoding="utf-8")
            stub.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{tmp}:{env.get('PATH', '')}"
            env["SKILL_EVOLUTION_ALLOW_MUTATING"] = "0"
            with mock.patch.dict(os.environ, env, clear=True):
                result = run_rollout(
                    "查看 ECS 实例",
                    "# ecs",
                    mock=False,
                    skill="alicloud-ecs-ops",
                    skills_root=REPO_ROOT,
                    trajectories_path=_FIXTURE_TRAJ,
                )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["operation"], "DescribeInstances")
        self.assertIn("ecs-harness-wrapper.sh", result["wrapper_path"])

    def test_run_batch_writes_rollouts_json(self) -> None:
        items = [{"id": "t1", "question": "查看 ECS", "expected_skill": "alicloud-ecs-ops"}]
        with tempfile.TemporaryDirectory() as tmp:
            results = run_batch(
                items,
                "# seed",
                tmp,
                mock=True,
                skills_root=REPO_ROOT,
                trajectories_path=_FIXTURE_TRAJ,
            )
            self.assertEqual(len(results), 1)
            self.assertTrue((Path(tmp) / "rollouts.json").is_file())

    def test_resolve_skills_root_defaults_to_repo(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ALIYUN_SKILLS_ROOT", None)
            os.environ.pop("SKILLS_DIR", None)
            root = resolve_skills_root()
        self.assertEqual(root, REPO_ROOT)


if __name__ == "__main__":
    unittest.main()
