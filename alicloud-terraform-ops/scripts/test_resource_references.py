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

    def test_external_comment_when_batch_has_entries(self):
        refs = ResourceReferenceRegistry()
        refs.register("vpc-bp1abc123456", "alicloud_vpc", "imported_vpc_bp1abc12")
        value = refs.hcl_value("vsw-bp1unknown")
        self.assertIn('"vsw-bp1unknown"', value)
        self.assertIn("# external: not in import batch", value)


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

    def test_ecs_references_security_groups_in_batch(self):
        sg_id = "sg-bp1sg000001"
        sg_tf = make_tf_name("security_group", sg_id)
        self.refs.register(sg_id, "alicloud_security_group", sg_tf)
        data = {
            "Instances": {
                "Instance": [{
                    "InstanceId": "i-bp1ecs000001",
                    "InstanceName": "web-1",
                    "InstanceType": "ecs.t5-lc1m1.small",
                    "ImageId": "m-bp1img001",
                    "VpcAttributes": {"VSwitchId": self.vswitch_id},
                    "SecurityGroupIds": {"SecurityGroupId": [sg_id]},
                }]
            }
        }
        tf_name = make_tf_name("ecs", "i-bp1ecs000001")
        hcl = self.mapper.to_hcl("ecs", data, tf_name=tf_name, refs=self.refs)
        self.assertIn(f"alicloud_security_group.{sg_tf}.id", hcl)

    def test_ecs_external_security_group_comment(self):
        sg_id = "sg-bp1external01"
        data = {
            "Instances": {
                "Instance": [{
                    "InstanceId": "i-bp1ecs000001",
                    "InstanceName": "web-1",
                    "InstanceType": "ecs.t5-lc1m1.small",
                    "ImageId": "m-bp1img001",
                    "VpcAttributes": {"VSwitchId": self.vswitch_id},
                    "SecurityGroupIds": {"SecurityGroupId": [sg_id]},
                }]
            }
        }
        tf_name = make_tf_name("ecs", "i-bp1ecs000001")
        hcl = self.mapper.to_hcl("ecs", data, tf_name=tf_name, refs=self.refs)
        self.assertIn("# external: not in import batch", hcl)
        self.assertIn(sg_id, hcl)


class TestDiskAttachmentReferences(unittest.TestCase):
    def setUp(self):
        self.mapper = ResourceMapper()
        self.disk_id = "d-bp1disk00001"
        self.instance_id = "i-bp1ecs000001"
        self.disk_tf = make_tf_name("disk", self.disk_id)
        self.ecs_tf = make_tf_name("ecs", self.instance_id)
        self.refs = ResourceReferenceRegistry()
        self.refs.register(self.disk_id, "alicloud_disk", self.disk_tf)
        self.refs.register(self.instance_id, "alicloud_instance", self.ecs_tf)

    def test_extract_attached_instance_id(self):
        data = {"Disk": {"DiskId": self.disk_id, "InstanceId": self.instance_id}}
        self.assertEqual(
            ResourceMapper.extract_attached_instance_id(data),
            self.instance_id,
        )

    def test_disk_attachment_hcl_uses_refs(self):
        hcl = self.mapper.disk_attachment_to_hcl(
            self.disk_id,
            self.instance_id,
            self.disk_tf,
            refs=self.refs,
        )
        self.assertIn(f"alicloud_disk.{self.disk_tf}.id", hcl)
        self.assertIn(f"alicloud_instance.{self.ecs_tf}.id", hcl)
        self.assertIn('resource "alicloud_disk_attachment"', hcl)

    def test_import_script_includes_disk_attachment(self):
        resources = [{
            "type": "disk_attachment",
            "tf_type": "alicloud_disk_attachment",
            "tf_name": "attach_bp1disk01",
            "id": f"{self.disk_id}:{self.instance_id}",
        }]
        script = self.mapper.generate_import_script(resources)
        self.assertIn(
            f"terraform import alicloud_disk_attachment.attach_bp1disk01 "
            f"{self.disk_id}:{self.instance_id}",
            script,
        )


if __name__ == "__main__":
    unittest.main()
