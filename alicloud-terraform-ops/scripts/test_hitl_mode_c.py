#!/usr/bin/env python3
"""HITL Mode C 单元测试 — 暂停/恢复/过期/漂移检测"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from hitl_common import AuditLogger, HITLConfig
from hitl_mode_a import (
    CheckpointStatus,
    CheckpointType,
    Environment,
    ResourceInfo,
    create_checkpoint,
)
from hitl_mode_c import (
    BatchSelector,
    CheckpointExpirationManager,
    CheckpointStoreWithBackup,
    DriftDetector,
    ResourceClassification,
    ResourceClassifier,
    SessionRecovery,
)


class TestResourceClassifier(unittest.TestCase):
    def setUp(self):
        self.audit = AuditLogger(base_path=Path(tempfile.mkdtemp()) / "audit")
        self.classifier = ResourceClassifier(self.audit)

    def test_pass_classification(self):
        resources = [ResourceInfo(resource_type="vpc", name="main", id="vpc-1")]
        result = self.classifier.classify(resources)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].classification, ResourceClassification.PASS)
        self.assertTrue(result[0].selected)

    def test_warn_classification(self):
        resources = [ResourceInfo(resource_type="rds", name="db", id="rm-1")]
        result = self.classifier.classify(resources)
        self.assertEqual(result[0].classification, ResourceClassification.WARN)
        self.assertFalse(result[0].selected)

    def test_skip_classification(self):
        resources = [ResourceInfo(resource_type="snapshot", name="snap", id="s-1")]
        result = self.classifier.classify(resources)
        self.assertEqual(result[0].classification, ResourceClassification.SKIP)


class TestDriftDetector(unittest.TestCase):
    def setUp(self):
        self.audit = AuditLogger(base_path=Path(tempfile.mkdtemp()) / "audit")
        self.detector = DriftDetector(self.audit)

    def test_no_drift_when_empty(self):
        cp = create_checkpoint(CheckpointType.IMPORT, Environment.DEV)
        report = self.detector.detect(cp, current_resources=None)
        self.assertFalse(report.has_drift)

    def test_detect_missing_resource(self):
        cp = create_checkpoint(CheckpointType.IMPORT, Environment.DEV, resources=[
            {"type": "vpc", "name": "main", "id": "vpc-old"},
        ])
        current = [ResourceInfo(resource_type="vpc", name="main", id="vpc-new")]
        report = self.detector.detect(cp, current_resources=current)
        self.assertTrue(report.has_drift)
        self.assertIn("vpc-old", report.missing_resources)
        self.assertIn("vpc-new", report.unexpected_resources)

    def test_detect_attribute_change(self):
        cp = create_checkpoint(CheckpointType.IMPORT, Environment.DEV, resources=[
            {"type": "vpc", "name": "main", "id": "vpc-1", "attributes": {"cidr": "10.0.0.0/16"}},
        ])
        current = [ResourceInfo(
            resource_type="vpc", name="main", id="vpc-1",
            attributes={"cidr": "10.1.0.0/16"},
        )]
        report = self.detector.detect(cp, current_resources=current)
        self.assertTrue(report.has_drift)
        self.assertIn("vpc-1", report.attribute_changes)


class TestSessionRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.audit = AuditLogger(base_path=self.tmp / "audit")
        self.store = CheckpointStoreWithBackup(base_path=self.tmp / "checkpoints")
        self.recovery = SessionRecovery(
            store=self.store,
            drift_detector=DriftDetector(self.audit),
            audit=self.audit,
        )

    def test_resume_active_checkpoint(self):
        cp = create_checkpoint(CheckpointType.NL2HCL, Environment.DEV)
        cp.expires_at = datetime.now() + timedelta(days=1)
        self.store.save(cp)

        result = self.recovery.resume(cp.id)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.checkpoint)
        self.assertTrue(result.can_resume)

    def test_resume_expired_checkpoint(self):
        cp = create_checkpoint(CheckpointType.NL2HCL, Environment.DEV)
        cp.expires_at = datetime.now() - timedelta(hours=1)
        self.store.save(cp)

        result = self.recovery.resume(cp.id)
        self.assertFalse(result.success)
        self.assertIn("过期", result.error or "")

    def test_resume_missing_checkpoint(self):
        result = self.recovery.resume("cp-nonexistent")
        self.assertFalse(result.success)


class TestCheckpointExpiration(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.audit = AuditLogger(base_path=self.tmp / "audit")
        self.store = CheckpointStoreWithBackup(base_path=self.tmp / "checkpoints")
        self.config = HITLConfig()
        self.manager = CheckpointExpirationManager(self.store, self.config, self.audit)

    def test_cleanup_expired_dry_run(self):
        cp = create_checkpoint(CheckpointType.IMPORT, Environment.DEV)
        cp.expires_at = datetime.now() - timedelta(hours=1)
        cp.status = CheckpointStatus.PAUSED
        self.store.save(cp)

        expired = self.manager.cleanup_expired(dry_run=True)
        self.assertIn(cp.id, expired)
        self.assertTrue((self.store.base_path / f"{cp.id}.json").exists())

    def test_cleanup_expired_delete(self):
        cp = create_checkpoint(CheckpointType.IMPORT, Environment.DEV)
        cp.expires_at = datetime.now() - timedelta(hours=1)
        cp.status = CheckpointStatus.PAUSED
        self.store.save(cp)

        expired = self.manager.cleanup_expired(dry_run=False)
        self.assertIn(cp.id, expired)
        self.assertFalse((self.store.base_path / f"{cp.id}.json").exists())

    def test_extend_ttl(self):
        cp = create_checkpoint(CheckpointType.IMPORT, Environment.DEV)
        cp.expires_at = datetime.now() + timedelta(hours=1)
        self.store.save(cp)
        ok = self.manager.extend_ttl(cp.id, "7d")
        self.assertTrue(ok)
        loaded = self.store.load(cp.id)
        self.assertGreater(loaded.expires_at, datetime.now() + timedelta(days=6))


class TestBatchSelector(unittest.TestCase):
    def setUp(self):
        self.audit = AuditLogger(base_path=Path(tempfile.mkdtemp()) / "audit")
        self.selector = BatchSelector(self.audit, use_color=False)

    def test_select_defaults(self):
        from hitl_mode_c import ClassifiedResource
        classified = [
            ClassifiedResource(
                resource=ResourceInfo("vpc", "main", "vpc-1"),
                classification=ResourceClassification.PASS,
                selected=True,
            ),
            ClassifiedResource(
                resource=ResourceInfo("rds", "db", "rm-1"),
                classification=ResourceClassification.WARN,
                selected=False,
            ),
        ]
        result = self.selector._select_all_pass(classified)
        self.assertEqual(len(result.selected_resources), 1)
        self.assertEqual(result.selected_resources[0].resource.id, "vpc-1")


def run_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in (
        TestResourceClassifier,
        TestDriftDetector,
        TestSessionRecovery,
        TestCheckpointExpiration,
        TestBatchSelector,
    ):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
