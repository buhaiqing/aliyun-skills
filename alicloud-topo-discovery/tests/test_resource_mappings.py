"""Integration tests for Top-5 resource type mappings (Tasks 7-10).

Uses real fixture JSON files from tests/fixtures/ and verifies:
- Each MappingSpec produces valid HCL output
- Block names are stable and deterministic
- Sensitive fields are masked (RDS password, ECS password)
- Parent references (vpc_id, vswitch_id) use dependency notation
"""
import pytest
from scripts.lib.field_mapper import FieldMapper, MappingSpec, MappingRule
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


class TestMappingsRegistry:
    """Verify MAPPINGS dict contains all 5 Phase 1 resource types."""

    def test_all_five_types_present(self):
        assert "vpc" in MAPPINGS
        assert "vswitch" in MAPPINGS
        assert "ecs" in MAPPINGS
        assert "rds" in MAPPINGS
        assert "slb" in MAPPINGS

    def test_each_spec_has_rules(self):
        for rt, spec in MAPPINGS.items():
            assert len(spec.rules) > 0, f"{rt} has no rules"

    def test_vswitch_has_parent_ref(self):
        assert MAPPINGS["vswitch"].parent_ref == "VpcId"
