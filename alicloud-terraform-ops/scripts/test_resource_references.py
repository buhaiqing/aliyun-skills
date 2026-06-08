#!/usr/bin/env python3
"""逆向工程资源引用关联单元测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from reverse_engineering import (
    ResourceMapper,
    ResourceReferenceRegistry,
    make_tf_name,
)


class TestResourceReferenceRegistry(unittest.TestCase):
    def test_reference_when_registered(self):
        refs = ResourceReferenceRegistry()
        refs.register("vpc-bp1abc123456", "alicloud_vpc", "imported_vpc_bp1abc12")
        self.assertEqual(
            refs.reference("vpc-bp1abc123456"),
            "alicloud_vpc.imported_vpc_bp1abc12.id",
        )
        self.assertEqual(
            refs.hcl_value("vpc-bp1abc123456"),
            "alicloud_vpc.imported_vpc_bp1abc12.id",
        )

    def test_literal_when_not_registered(self):
        refs = ResourceReferenceRegistry()
        self.assertEqual(refs.hcl_value("vpc-bp1unknown"), '"vpc-bp1unknown"')


class TestCrossResourceReferences(unittest.TestCase):
    def setUp(self):
        self.mapper = ResourceMapper()
        self.vpc_id = "vpc-bp1abc123456"
        self.vswitch_id = "vsw-bp1def678901"
        self.vpc_tf = make_tf_name("vpc", self.vpc_id)
        self.vsw_tf = make_tf_name("vswitch", self.vswitch_id)
        self.refs = ResourceReferenceRegistry()
        self.refs.register(self.vpc_id, "alicloud_vpc", self.vpc_tf)
        self.refs.register(self.vswitch_id, "alicloud_vswitch", self.vsw_tf)

    def test_vswitch_references_vpc_in_batch(self):
        data = {
            "VSwitch": {
                "VSwitchId": self.vswitch_id,
                "VSwitchName": "private-a",
                "CidrBlock": "10.0.1.0/24",
                "VpcId": self.vpc_id,
                "ZoneId": "cn-hangzhou-b",
            }
        }
        hcl = self.mapper.to_hcl("vswitch", data, tf_name=self.vsw_tf, refs=self.refs)
        self.assertIn(f"vpc_id       = alicloud_vpc.{self.vpc_tf}.id", hcl)
        self.assertNotIn("TODO: Reference", hcl)

    def test_vswitch_literal_without_vpc_in_batch(self):
        data = {
            "VSwitch": {
                "VSwitchId": self.vswitch_id,
                "VSwitchName": "private-a",
                "CidrBlock": "10.0.1.0/24",
                "VpcId": self.vpc_id,
                "ZoneId": "cn-hangzhou-b",
            }
        }
        hcl = self.mapper.to_hcl("vswitch", data, tf_name=self.vsw_tf, refs=None)
        self.assertIn(f'vpc_id       = "{self.vpc_id}"', hcl)

    def test_rds_references_vswitch(self):
        data = {
            "Items": {
                "DBInstanceAttribute": [{
                    "DBInstanceId": "rm-bp1xyz000001",
                    "DBInstanceDescription": "app-db",
                    "Engine": "MySQL",
                    "EngineVersion": "8.0",
                    "DBInstanceClass": "rds.mysql.s1.small",
                    "VSwitchId": self.vswitch_id,
                    "ZoneId": "cn-hangzhou-b",
                    "DBInstanceStorage": 20,
                }]
            }
        }
        tf_name = make_tf_name("rds", "rm-bp1xyz000001")
        hcl = self.mapper.to_hcl("rds", data, tf_name=tf_name, refs=self.refs)
        self.assertIn(f"vswitch_id           = alicloud_vswitch.{self.vsw_tf}.id", hcl)

    def test_route_table_references_vpc(self):
        data = {
            "RouteTable": {
                "RouteTableId": "vtb-bp1rt000001",
                "RouteTableName": "main-rt",
                "VpcId": self.vpc_id,
                "Description": "main",
            }
        }
        tf_name = make_tf_name("route_table", "vtb-bp1rt000001")
        hcl = self.mapper.to_hcl("route_table", data, tf_name=tf_name, refs=self.refs)
        self.assertIn(f"vpc_id           = alicloud_vpc.{self.vpc_tf}.id", hcl)

    def test_tf_name_matches_import_script_convention(self):
        self.assertEqual(make_tf_name("vpc", self.vpc_id), "imported_vpc_bp1abc12")
        self.assertEqual(make_tf_name("vswitch", self.vswitch_id), "imported_vswitch_bp1def67")


if __name__ == "__main__":
    unittest.main()
