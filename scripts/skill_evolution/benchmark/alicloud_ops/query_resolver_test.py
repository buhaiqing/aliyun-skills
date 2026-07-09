#!/usr/bin/env python3
"""Tests for query_resolver.py."""

from __future__ import annotations

import unittest

from query_resolver import resolve_operation


class QueryResolverTests(unittest.TestCase):
    def test_create_maps_to_create_instance(self) -> None:
        op, argv, mut = resolve_operation("创建一台 ECS 实例", "alicloud-ecs-ops")
        self.assertEqual(op, "CreateInstance")
        self.assertTrue(mut)

    def test_security_group_describe(self) -> None:
        op, _, mut = resolve_operation("查看安全组规则", "alicloud-ecs-ops")
        self.assertEqual(op, "DescribeSecurityGroups")
        self.assertFalse(mut)

    def test_trajectory_boost_when_keywords_ambiguous(self) -> None:
        trajectories = [
            {
                "skill": "alicloud-ecs-ops",
                "operation": "RunCommand",
                "command": "aliyun ecs RunCommand --RegionId cn-hangzhou",
                "rubric_pass": True,
            }
        ]
        op, _, _ = resolve_operation("帮我处理一下", "alicloud-ecs-ops", trajectories=trajectories)
        self.assertEqual(op, "RunCommand")

    def test_unsupported_skill_returns_unknown(self) -> None:
        op, argv, mut = resolve_operation("创建一台 RDS MySQL 实例", "alicloud-rds-ops")
        self.assertEqual(op, "unknown")
        self.assertEqual(argv, [])
        self.assertFalse(mut)


if __name__ == "__main__":
    unittest.main()
