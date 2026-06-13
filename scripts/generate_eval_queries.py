#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch generate eval_queries.json files for missing skills."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# Evaluation queries for each skill type
EVAL_QUERIES_TEMPLATES = {
    "alicloud-ecs-ops": {
        "queries": [
            {"query": "创建一台 ECS 实例", "expected_skill": "alicloud-ecs-ops", "priority": "P0"},
            {"query": "启动云服务器", "expected_skill": "alicloud-ecs-ops", "priority": "P0"},
            {"query": "停止我的 ECS", "expected_skill": "alicloud-ecs-ops", "priority": "P0"},
            {"query": "扩容云盘", "expected_skill": "alicloud-ecs-ops", "priority": "P1"},
            {"query": "创建磁盘快照", "expected_skill": "alicloud-ecs-ops", "priority": "P1"},
            {"query": "查看安全组规则", "expected_skill": "alicloud-ecs-ops", "priority": "P1"},
            {"query": "通过云助手执行命令", "expected_skill": "alicloud-ecs-ops", "priority": "P1"},
            {"query": "更换操作系统镜像", "expected_skill": "alicloud-ecs-ops", "priority": "P2"},
        ]
    },
    "alicloud-rds-ops": {
        "queries": [
            {"query": "创建 RDS MySQL 实例", "expected_skill": "alicloud-rds-ops", "priority": "P0"},
            {"query": "备份数据库", "expected_skill": "alicloud-rds-ops", "priority": "P0"},
            {"query": "创建数据库账号", "expected_skill": "alicloud-rds-ops", "priority": "P1"},
            {"query": "修改数据库配置参数", "expected_skill": "alicloud-rds-ops", "priority": "P1"},
            {"query": "查看慢 SQL", "expected_skill": "alicloud-rds-ops", "priority": "P1"},
            {"query": "扩容数据库磁盘", "expected_skill": "alicloud-rds-ops", "priority": "P1"},
        ]
    },
    "alicloud-redis-ops": {
        "queries": [
            {"query": "创建 Redis 实例", "expected_skill": "alicloud-redis-ops", "priority": "P0"},
            {"query": "清空 Redis 数据", "expected_skill": "alicloud-redis-ops", "priority": "P0"},
            {"query": "查看 Redis 内存使用情况", "expected_skill": "alicloud-redis-ops", "priority": "P1"},
            {"query": "修改 Redis 密码", "expected_skill": "alicloud-redis-ops", "priority": "P1"},
            {"query": "Redis 备份恢复", "expected_skill": "alicloud-redis-ops", "priority": "P1"},
        ]
    },
    "alicloud-vpc-ops": {
        "queries": [
            {"query": "创建 VPC", "expected_skill": "alicloud-vpc-ops", "priority": "P0"},
            {"query": "创建交换机", "expected_skill": "alicloud-vpc-ops", "priority": "P0"},
            {"query": "配置路由表", "expected_skill": "alicloud-vpc-ops", "priority": "P1"},
            {"query": "查看 VPC 网络拓扑", "expected_skill": "alicloud-vpc-ops", "priority": "P1"},
            {"query": "创建安全组并添加规则", "expected_skill": "alicloud-vpc-ops", "priority": "P1"},
        ]
    },
    "alicloud-ram-ops": {
        "queries": [
            {"query": "创建 RAM 用户", "expected_skill": "alicloud-ram-ops", "priority": "P0"},
            {"query": "创建访问策略", "expected_skill": "alicloud-ram-ops", "priority": "P0"},
            {"query": "给用户授权", "expected_skill": "alicloud-ram-ops", "priority": "P1"},
            {"query": "创建 RAM 角色", "expected_skill": "alicloud-ram-ops", "priority": "P1"},
            {"query": "禁用 AccessKey", "expected_skill": "alicloud-ram-ops", "priority": "P1"},
        ]
    },
    "alicloud-ack-ops": {
        "queries": [
            {"query": "创建 Kubernetes 集群", "expected_skill": "alicloud-ack-ops", "priority": "P0"},
            {"query": "扩容 ACK 节点", "expected_skill": "alicloud-ack-ops", "priority": "P0"},
            {"query": "部署应用到 ACK", "expected_skill": "alicloud-ack-ops", "priority": "P1"},
            {"query": "查看 Pod 日志", "expected_skill": "alicloud-ack-ops", "priority": "P1"},
            {"query": "配置 ACK 自动伸缩", "expected_skill": "alicloud-ack-ops", "priority": "P2"},
        ]
    },
    "alicloud-eip-ops": {
        "queries": [
            {"query": "申请弹性公网 IP", "expected_skill": "alicloud-eip-ops", "priority": "P0"},
            {"query": "绑定 EIP 到 ECS", "expected_skill": "alicloud-eip-ops", "priority": "P0"},
            {"query": "释放 EIP", "expected_skill": "alicloud-eip-ops", "priority": "P1"},
            {"query": "修改 EIP 带宽", "expected_skill": "alicloud-eip-ops", "priority": "P1"},
        ]
    },
    "alicloud-nat-ops": {
        "queries": [
            {"query": "创建 NAT 网关", "expected_skill": "alicloud-nat-ops", "priority": "P0"},
            {"query": "配置 SNAT 规则", "expected_skill": "alicloud-nat-ops", "priority": "P0"},
            {"query": "配置 DNAT 规则", "expected_skill": "alicloud-nat-ops", "priority": "P1"},
            {"query": "查看 NAT 网关监控", "expected_skill": "alicloud-nat-ops", "priority": "P1"},
        ]
    },
    "alicloud-mongodb-ops": {
        "queries": [
            {"query": "创建 MongoDB 实例", "expected_skill": "alicloud-mongodb-ops", "priority": "P0"},
            {"query": "MongoDB 备份", "expected_skill": "alicloud-mongodb-ops", "priority": "P1"},
            {"query": "重置 MongoDB 密码", "expected_skill": "alicloud-mongodb-ops", "priority": "P1"},
        ]
    },
    "alicloud-das-ops": {
        "queries": [
            {"query": "查看数据库性能", "expected_skill": "alicloud-das-ops", "priority": "P0"},
            {"query": "分析慢 SQL", "expected_skill": "alicloud-das-ops", "priority": "P0"},
            {"query": "开启 SQL 审计", "expected_skill": "alicloud-das-ops", "priority": "P1"},
        ]
    },
    "alicloud-resourcemanager-ops": {
        "queries": [
            {"query": "创建资源目录文件夹", "expected_skill": "alicloud-resourcemanager-ops", "priority": "P0"},
            {"query": "创建资源组", "expected_skill": "alicloud-resourcemanager-ops", "priority": "P0"},
            {"query": "配置管控策略", "expected_skill": "alicloud-resourcemanager-ops", "priority": "P1"},
        ]
    },
}


def main():
    """Generate eval_queries.json for configured skills."""
    generated = []
    skipped = []

    for skill_name, template in EVAL_QUERIES_TEMPLATES.items():
        skill_dir = REPO_ROOT / skill_name
        assets_dir = skill_dir / "assets"
        target_file = assets_dir / "eval_queries.json"

        if not skill_dir.exists():
            skipped.append(f"{skill_name}: directory not found")
            continue

        if target_file.exists():
            skipped.append(f"{skill_name}: already exists")
            continue

        # Create assets directory if needed
        assets_dir.mkdir(exist_ok=True)

        # Write JSON file
        target_file.write_text(
            json.dumps(template, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        generated.append(skill_name)

    # Print report
    print("=" * 60)
    print("Eval Queries Generation Report")
    print("=" * 60)
    print(f"\nGenerated: {len(generated)} files")
    for skill in generated:
        print(f"  ✓ {skill}")

    if skipped:
        print(f"\nSkipped: {len(skipped)}")
        for reason in skipped:
            print(f"  - {reason}")

    print("\n" + "=" * 60)
    return 0 if generated else 1


if __name__ == "__main__":
    sys.exit(main())
