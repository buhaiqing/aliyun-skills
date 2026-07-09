#!/usr/bin/env python3
"""Tests for module_coverage.py — gate + verify."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from module_coverage import (
    check_nl2hcl_coverage,
    detect_keyword_resources,
    load_manifest,
    verify_manifest,
)
from nl2hcl_generator import CoverageGapError, NL2HCLGenerator


class ModuleCoverageGateTest(unittest.TestCase):
    def test_vpc_only_passes(self):
        gen = NL2HCLGenerator()
        intent = gen.parse_intent("创建一个 VPC，两个可用区")
        report = check_nl2hcl_coverage(intent, "创建一个 VPC，两个可用区")
        self.assertFalse(report.must_halt)

    def test_mongodb_now_passes(self):
        gen = NL2HCLGenerator()
        request = "创建 VPC 和 MongoDB 集群"
        intent = gen.parse_intent(request)
        report = check_nl2hcl_coverage(intent, request)
        self.assertFalse(report.must_halt,
                         "MongoDB now has addon-mongodb module, should pass")

    def test_oss_now_passes(self):
        request = "创建 OSS 存储桶"
        intent = NL2HCLGenerator().parse_intent(request)
        report = check_nl2hcl_coverage(intent, request)
        self.assertFalse(report.must_halt,
                         "OSS now has addon-oss module, should pass")

    def test_elasticsearch_keyword_halts(self):
        request = "部署 Elasticsearch 集群"
        hits = detect_keyword_resources(request)
        self.assertIn("alicloud_elasticsearch_instance", hits)

    def test_generate_raises_on_gap(self):
        gen = NL2HCLGenerator()
        with self.assertRaises(CoverageGapError):
            gen.generate("创建 Elasticsearch 集群")


class ModuleCoverageVerifyTest(unittest.TestCase):
    def test_verify_manifest_passes(self):
        errors = verify_manifest(load_manifest())
        self.assertEqual(errors, [], msg="\n".join(errors))


if __name__ == "__main__":
    unittest.main()
