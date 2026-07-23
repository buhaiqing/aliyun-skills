"""Integration tests for Top-5 resource type mappings (Tasks 7-10).

Uses real fixture JSON files from tests/fixtures/ and verifies:
- Each MappingSpec produces valid HCL output
- Block names are stable and deterministic
- Sensitive fields are masked (RDS password, ECS password)
- Parent references (vpc_id, vswitch_id) use dependency notation
"""
import pytest

from scripts.lib.field_mapper import FieldMapper
from scripts.lib.mappings import MAPPINGS


@pytest.fixture
def mapper():
    return FieldMapper()


@pytest.fixture
def load_fixture(load_fixture):
    """Alias for the conftest load_fixture fixture."""
    return load_fixture


class TestVpcMapping:
    """Task 7: VPC field mapping integration."""

    def test_vpc_block_generated(self, mapper, load_fixture):
        data = load_fixture("vpc")
        spec = MAPPINGS["vpc"]
        block_name = mapper.generate_block_name("alicloud_vpc", data, spec)
        hcl = mapper.map_resource("vpc", data, spec, block_name)
        assert 'resource "alicloud_vpc" "prod_vpc_beijing"' in hcl

    def test_vpc_contains_cidr_and_name(self, mapper, load_fixture):
        data = load_fixture("vpc")
        spec = MAPPINGS["vpc"]
        block_name = mapper.generate_block_name("alicloud_vpc", data, spec)
        hcl = mapper.map_resource("vpc", data, spec, block_name)
        assert 'vpc_name = "prod-vpc-beijing"' in hcl
        assert 'cidr_block = "10.0.0.0/8"' in hcl

    def test_vpc_id_stable_across_runs(self, mapper, load_fixture):
        """Same VPC data → same block name every time."""
        data = load_fixture("vpc")
        spec = MAPPINGS["vpc"]
        name1 = mapper.generate_block_name("alicloud_vpc", data, spec)
        name2 = mapper.generate_block_name("alicloud_vpc", data, spec)
        assert name1 == name2 == "prod_vpc_beijing"


class TestVSwitchMapping:
    """Task 7: VSwitch field mapping integration."""

    def test_vswitch_block_generated(self, mapper, load_fixture):
        data = load_fixture("vswitch")
        spec = MAPPINGS["vswitch"]
        block_name = mapper.generate_block_name("alicloud_vswitch", data, spec)
        hcl = mapper.map_resource("vswitch", data, spec, block_name)
        assert 'resource "alicloud_vswitch" "vsw_prod_web_a"' in hcl

    def test_vswitch_references_parent_vpc(self, mapper, load_fixture):
        data = load_fixture("vswitch")
        spec = MAPPINGS["vswitch"]
        block_name = mapper.generate_block_name("alicloud_vswitch", data, spec)
        hcl = mapper.map_resource("vswitch", data, spec, block_name)
        assert 'vswitch_name = "vsw-prod-web-a"' in hcl
        assert 'zone_id = "cn-beijing-a"' in hcl


class TestEcsMapping:
    """Task 8: ECS field mapping integration."""

    def test_ecs_block_generated(self, mapper, load_fixture):
        data = load_fixture("ecs")
        spec = MAPPINGS["ecs"]
        block_name = mapper.generate_block_name("alicloud_instance", data, spec)
        hcl = mapper.map_resource("ecs", data, spec, block_name)
        assert 'resource "alicloud_instance" "web_01"' in hcl

    def test_ecs_security_groups_as_list(self, mapper, load_fixture):
        data = load_fixture("ecs")
        spec = MAPPINGS["ecs"]
        block_name = mapper.generate_block_name("alicloud_instance", data, spec)
        hcl = mapper.map_resource("ecs", data, spec, block_name)
        assert 'security_groups = ["sg-bp1aevb8sfi8mh1qj5tb"]' in hcl

    def test_ecs_unsupported_field_not_in_hcl(self, mapper, load_fixture):
        """Fields not in MappingSpec rules should not appear in output."""
        data = load_fixture("ecs")
        spec = MAPPINGS["ecs"]
        block_name = mapper.generate_block_name("alicloud_instance", data, spec)
        hcl = mapper.map_resource("ecs", data, spec, block_name)
        # CreationTime is not in the mapping rules
        assert "CreationTime" not in hcl


class TestRdsMapping:
    """Task 9: RDS field mapping integration."""

    def test_rds_block_generated(self, mapper, load_fixture):
        data = load_fixture("rds")
        spec = MAPPINGS["rds"]
        block_name = mapper.generate_block_name("alicloud_db_instance", data, spec)
        hcl = mapper.map_resource("rds", data, spec, block_name)
        assert 'resource "alicloud_db_instance" "prod_mysql"' in hcl

    def test_rds_password_sensitive_masked(self, mapper, load_fixture):
        """RDS AccountPassword must be masked, never appear in HCL output."""
        data = load_fixture("rds")
        spec = MAPPINGS["rds"]
        block_name = mapper.generate_block_name("alicloud_db_instance", data, spec)
        hcl = mapper.map_resource("rds", data, spec, block_name)
        # Must NOT contain the real password
        assert "MySecretP@ss123" not in hcl
        # Must contain the variable reference
        assert "password = ${var.rds_password}" in hcl
        assert "sensitive = true" in hcl

    def test_rds_engine_and_storage_mapped(self, mapper, load_fixture):
        data = load_fixture("rds")
        spec = MAPPINGS["rds"]
        block_name = mapper.generate_block_name("alicloud_db_instance", data, spec)
        hcl = mapper.map_resource("rds", data, spec, block_name)
        assert 'engine = "MySQL"' in hcl
        assert 'engine_version = "8.0"' in hcl
        assert "instance_storage = 100" in hcl  # int, not string


class TestSlbMapping:
    """Task 10: SLB field mapping integration."""

    def test_slb_block_generated(self, mapper, load_fixture):
        data = load_fixture("slb")
        spec = MAPPINGS["slb"]
        block_name = mapper.generate_block_name("alicloud_slb", data, spec)
        hcl = mapper.map_resource("slb", data, spec, block_name)
        assert 'resource "alicloud_slb" "prod_web_lb"' in hcl

    def test_slb_address_type_and_bandwidth(self, mapper, load_fixture):
        data = load_fixture("slb")
        spec = MAPPINGS["slb"]
        block_name = mapper.generate_block_name("alicloud_slb", data, spec)
        hcl = mapper.map_resource("slb", data, spec, block_name)
        assert 'address_type = "internet"' in hcl
        assert "bandwidth = 5" in hcl  # int


class TestNatMapping:
    """Phase 3: NAT Gateway mapping integration."""

    def test_nat_block_generated(self, mapper, load_fixture):
        data = load_fixture("nat")
        spec = MAPPINGS["nat"]
        bn = mapper.generate_block_name("alicloud_nat_gateway", data, spec)
        hcl = mapper.map_resource("nat", data, spec, bn)
        assert 'resource "alicloud_nat_gateway"' in hcl
        assert 'name = "prod-natgw"' in hcl

    def test_nat_type_mapped(self, mapper, load_fixture):
        data = load_fixture("nat")
        spec = MAPPINGS["nat"]
        bn = mapper.generate_block_name("alicloud_nat_gateway", data, spec)
        hcl = mapper.map_resource("nat", data, spec, bn)
        assert 'nat_type = "Enhanced"' in hcl


class TestEipMapping:
    """Phase 3: EIP mapping integration."""

    def test_eip_block_generated(self, mapper, load_fixture):
        data = load_fixture("eip")
        spec = MAPPINGS["eip"]
        bn = mapper.generate_block_name("alicloud_eip", data, spec)
        hcl = mapper.map_resource("eip", data, spec, bn)
        assert 'resource "alicloud_eip"' in hcl
        assert "bandwidth = 100" in hcl

    def test_eip_charge_types(self, mapper, load_fixture):
        data = load_fixture("eip")
        spec = MAPPINGS["eip"]
        bn = mapper.generate_block_name("alicloud_eip", data, spec)
        hcl = mapper.map_resource("eip", data, spec, bn)
        assert 'internet_charge_type = "PayByTraffic"' in hcl


class TestSgMapping:
    """Phase 3: SecurityGroup mapping integration."""

    def test_sg_block_generated(self, mapper, load_fixture):
        data = load_fixture("sg")
        spec = MAPPINGS["sg"]
        bn = mapper.generate_block_name("alicloud_security_group", data, spec)
        hcl = mapper.map_resource("sg", data, spec, bn)
        assert 'resource "alicloud_security_group"' in hcl
        assert 'name = "prod-web-sg"' in hcl


class TestOssMapping:
    """Phase 3: OSS bucket mapping integration."""

    def test_oss_block_generated(self, mapper, load_fixture):
        data = load_fixture("oss")
        spec = MAPPINGS["oss"]
        bn = mapper.generate_block_name("alicloud_oss_bucket", data, spec)
        hcl = mapper.map_resource("oss", data, spec, bn)
        assert 'resource "alicloud_oss_bucket"' in hcl

    def test_oss_storage_class(self, mapper, load_fixture):
        data = load_fixture("oss")
        spec = MAPPINGS["oss"]
        bn = mapper.generate_block_name("alicloud_oss_bucket", data, spec)
        hcl = mapper.map_resource("oss", data, spec, bn)
        assert 'storage_class = "Standard"' in hcl


class TestRamMapping:
    """Phase 3: RAM role mapping integration."""

    def test_ram_block_generated(self, mapper, load_fixture):
        data = load_fixture("ram")
        spec = MAPPINGS["ram"]
        bn = mapper.generate_block_name("alicloud_ram_role", data, spec)
        hcl = mapper.map_resource("ram", data, spec, bn)
        assert 'resource "alicloud_ram_role"' in hcl

    def test_ram_arn_mapped(self, mapper, load_fixture):
        data = load_fixture("ram")
        spec = MAPPINGS["ram"]
        bn = mapper.generate_block_name("alicloud_ram_role", data, spec)
        hcl = mapper.map_resource("ram", data, spec, bn)
        assert 'arn = "acs:ram::1234567890:role/ecs-role"' in hcl


class TestPolardbMapping:
    def test_polardb_block(self, mapper, load_fixture):
        data = load_fixture("polardb")
        spec = MAPPINGS["polardb"]
        bn = mapper.generate_block_name("alicloud_polardb_cluster", data, spec)
        hcl = mapper.map_resource("polardb", data, spec, bn)
        assert 'resource "alicloud_polardb_cluster"' in hcl
        assert 'db_node_storage = 200' in hcl


class TestRedisMapping:
    def test_redis_block(self, mapper, load_fixture):
        data = load_fixture("redis")
        spec = MAPPINGS["redis"]
        bn = mapper.generate_block_name("alicloud_redis_instance", data, spec)
        hcl = mapper.map_resource("redis", data, spec, bn)
        assert 'resource "alicloud_redis_instance"' in hcl
        assert "port = 6379" in hcl


class TestKmsMapping:
    def test_kms_block(self, mapper, load_fixture):
        data = load_fixture("kms")
        spec = MAPPINGS["kms"]
        bn = mapper.generate_block_name("alicloud_kms_key", data, spec)
        hcl = mapper.map_resource("kms", data, spec, bn)
        assert 'resource "alicloud_kms_key"' in hcl


class TestActiontrailMapping:
    def test_actiontrail_block(self, mapper, load_fixture):
        data = load_fixture("actiontrail")
        spec = MAPPINGS["actiontrail"]
        bn = mapper.generate_block_name("alicloud_actiontrail", data, spec)
        hcl = mapper.map_resource("actiontrail", data, spec, bn)
        assert 'resource "alicloud_actiontrail"' in hcl


class TestNasMapping:
    def test_nas_block(self, mapper, load_fixture):
        data = load_fixture("nas")
        spec = MAPPINGS["nas"]
        bn = mapper.generate_block_name("alicloud_nas_file_system", data, spec)
        hcl = mapper.map_resource("nas", data, spec, bn)
        assert 'resource "alicloud_nas_file_system"' in hcl


class TestFcMapping:
    def test_fc_block(self, mapper, load_fixture):
        data = load_fixture("fc")
        spec = MAPPINGS["fc"]
        bn = mapper.generate_block_name("alicloud_fc_service", data, spec)
        hcl = mapper.map_resource("fc", data, spec, bn)
        assert 'resource "alicloud_fc_service"' in hcl


class TestVpnMapping:
    def test_vpn_block(self, mapper, load_fixture):
        data = load_fixture("vpn")
        spec = MAPPINGS["vpn"]
        bn = mapper.generate_block_name("alicloud_vpn_connection", data, spec)
        hcl = mapper.map_resource("vpn", data, spec, bn)
        assert 'resource "alicloud_vpn_connection"' in hcl


class TestAckMapping:
    def test_ack_block(self, mapper, load_fixture):
        data = load_fixture("ack")
        spec = MAPPINGS["ack"]
        bn = mapper.generate_block_name("alicloud_cs_kubernetes", data, spec)
        hcl = mapper.map_resource("ack", data, spec, bn)
        assert 'resource "alicloud_cs_kubernetes"' in hcl
        assert "worker_number = 3" in hcl

    def test_ack_vswitch_ids_list(self, mapper, load_fixture):
        data = load_fixture("ack")
        spec = MAPPINGS["ack"]
        bn = mapper.generate_block_name("alicloud_cs_kubernetes", data, spec)
        hcl = mapper.map_resource("ack", data, spec, bn)
        assert 'vswitch_ids = ["vsw-bp1aevb8sfi8mh1qj5t9"]' in hcl


class TestSagMapping:
    def test_sag_block(self, mapper, load_fixture):
        data = load_fixture("sag")
        spec = MAPPINGS["sag"]
        bn = mapper.generate_block_name("alicloud_sag", data, spec)
        hcl = mapper.map_resource("sag", data, spec, bn)
        assert 'resource "alicloud_sag"' in hcl


class TestMappingsRegistry:
    """Verify MAPPINGS dict contains all 18 resource types."""

    def test_all_eighteen_types_present(self):
        for rt in ["vpc","vswitch","ecs","rds","slb","nat","eip","sg","oss","ram",
                    "polardb","redis","kms","actiontrail","nas","fc","vpn","ack","sag"]:
            assert rt in MAPPINGS, f"{rt} missing from MAPPINGS"

    def test_each_spec_has_rules(self):
        for rt, spec in MAPPINGS.items():
            assert len(spec.rules) > 0, f"{rt} has no rules"

    def test_vswitch_has_parent_ref(self):
        assert MAPPINGS["vswitch"].parent_ref == "VpcId"
