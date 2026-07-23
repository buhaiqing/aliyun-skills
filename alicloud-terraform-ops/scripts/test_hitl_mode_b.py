#!/usr/bin/env python3
"""HITL Mode B 单元测试 — PR 创建/审批/拒绝/错误恢复"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from hitl_common import AuditLogger, HITLConfig, NotificationManager, PRErrorHandler
from hitl_mode_a import CheckpointType, Environment, create_checkpoint
from hitl_mode_b import (
    CommentAction,
    CommentCommandParser,
    GitError,
    LocalGitProvider,
    PRFile,
    PRFileGenerator,
    PRManager,
    PRStatus,
)


class TestCommentCommandParser(unittest.TestCase):
    def setUp(self):
        self.audit = AuditLogger(base_path=Path(tempfile.mkdtemp()) / "audit")
        self.parser = CommentCommandParser(self.audit)

    def test_approve_command(self):
        result = self.parser.parse("/approve", user="reviewer1", user_role="reviewer")
        self.assertEqual(result.action, CommentAction.APPROVE)

    def test_reject_requires_reason(self):
        result = self.parser.parse("/reject", user="reviewer1", user_role="reviewer")
        self.assertEqual(result.action, CommentAction.UNKNOWN)
        self.assertIn("需要参数", result.error or "")

    def test_reject_with_reason(self):
        result = self.parser.parse("/reject 配置有风险", user="reviewer1", user_role="reviewer")
        self.assertEqual(result.action, CommentAction.REJECT)
        self.assertEqual(result.args, ["配置有风险"])

    def test_unknown_command(self):
        result = self.parser.parse("/foobar", user="u", user_role="reviewer")
        self.assertEqual(result.action, CommentAction.UNKNOWN)

    def test_non_command_comment(self):
        result = self.parser.parse("LGTM", user="u", user_role="reviewer")
        self.assertEqual(result.action, CommentAction.NONE)


class TestLocalGitProvider(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store_dir = Path(self.tmp) / ".pr-store"
        self.audit = AuditLogger(base_path=Path(self.tmp) / "audit")
        self.config = HITLConfig()
        self.provider = LocalGitProvider(self.config, self.audit, store_dir=self.store_dir)

    def test_branch_create_and_exists(self):
        self.provider.create_branch("main", "feature/test")
        self.assertTrue(self.provider.branch_exists("feature/test"))

    def test_branch_already_exists(self):
        self.provider.create_branch("main", "feature/dup")
        with self.assertRaises(GitError) as ctx:
            self.provider.create_branch("main", "feature/dup")
        self.assertEqual(ctx.exception.code, "branch_already_exists")

    def test_commit_and_get_file(self):
        self.provider.create_branch("main", "feature/files")
        sha = self.provider.commit_files(
            "feature/files",
            [PRFile(path="main.tf", content='resource "alicloud_vpc" "x" {}')],
            "init",
        )
        self.assertEqual(len(sha), 8)
        content = self.provider.get_file("feature/files", "main.tf")
        self.assertIn("alicloud_vpc", content or "")

    def test_pr_lifecycle(self):
        self.provider.create_branch("main", "terraform/nl2hcl-dev")
        pr = self.provider.create_pr(
            title="Test PR",
            body="body",
            head="terraform/nl2hcl-dev",
            base="main",
            labels=["terraform"],
            reviewers=["alice", "bob"],
        )
        self.assertEqual(pr.status, PRStatus.OPEN)
        self.assertEqual(pr.number, 1)

        self.provider.approve_pr(pr.id, "alice")
        pr = self.provider.get_pr(pr.id)
        self.assertIn("alice", pr.approvals)

        self.provider.approve_pr(pr.id, "bob")
        pr = self.provider.get_pr(pr.id)
        self.assertEqual(pr.status, PRStatus.APPROVED)

        self.provider.merge_pr(pr.id)
        pr = self.provider.get_pr(pr.id)
        self.assertEqual(pr.status, PRStatus.MERGED)

    def test_pr_reject(self):
        self.provider.create_branch("main", "terraform/reject")
        pr = self.provider.create_pr(
            title="Reject me", body="", head="terraform/reject", base="main",
            labels=[], reviewers=["alice"],
        )
        self.provider.reject_pr(pr.id, "alice", "unsafe change")
        pr = self.provider.get_pr(pr.id)
        self.assertEqual(pr.status, PRStatus.CHANGES_REQUESTED)
        self.assertEqual(len(pr.rejections), 1)


class TestPRManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store_dir = Path(self.tmp) / ".pr-store"
        self.audit = AuditLogger(base_path=Path(self.tmp) / "audit")
        self.config = HITLConfig(pr_provider="local")
        self.notification = NotificationManager(self.config, self.audit)
        self.provider = LocalGitProvider(self.config, self.audit, store_dir=self.store_dir)
        self.manager = PRManager(
            provider=self.provider,
            file_generator=PRFileGenerator("dev"),
            parser=CommentCommandParser(self.audit),
            audit=self.audit,
            notification=self.notification,
            error_handler=PRErrorHandler(self.audit),
        )

    def test_create_terraform_pr(self):
        cp = create_checkpoint(CheckpointType.NL2HCL, Environment.DEV, resources=[
            {"type": "vpc", "name": "main"},
        ])
        hcl = {"main.tf": 'resource "alicloud_vpc" "main" { vpc_name = "test" cidr_block = "10.0.0.0/16" }'}
        pr = self.manager.create_terraform_pr(hcl, cp, reviewers=["alice"])
        self.assertTrue(pr.id.startswith("pr-"))
        plan_content = self.provider.get_file(pr.branch, "PLAN.md") or ""
        self.assertIn("Terraform Plan", plan_content)

    def test_duplicate_pr_fails(self):
        cp = create_checkpoint(CheckpointType.NL2HCL, Environment.DEV)
        branch = self.provider.generate_branch_name(cp)
        self.provider.create_branch("main", branch)
        self.provider.create_pr("t", "b", branch, "main", [], [])
        with self.assertRaises(GitError):
            self.provider.create_pr("t2", "b2", branch, "main", [], [])


def run_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestCommentCommandParser))
    suite.addTests(loader.loadTestsFromTestCase(TestLocalGitProvider))
    suite.addTests(loader.loadTestsFromTestCase(TestPRManager))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
