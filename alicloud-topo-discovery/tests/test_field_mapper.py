"""Tests for field_mapper core (JSON → HCL conversion)."""
import pytest

from scripts.lib.field_mapper import (
    FieldMapper,
    MappingRule,
    MappingSpec,
    _slugify,
)


@pytest.fixture
def mapper():
    return FieldMapper()


def test_map_simple_string_field(mapper):
    """Simple string field maps to HCL string literal."""
    spec = MappingSpec(
        resource_type="vpc",
        terraform_type="alicloud_vpc",
        rules=[MappingRule(hcl_attr="vpc_name", path="VpcName", type="string")],
    )
    hcl = mapper.map_resource(
        resource_type="vpc",
        resource_data={"VpcName": "my-vpc"},
        spec=spec,
        block_name="my_vpc",
    )
    assert 'resource "alicloud_vpc" "my_vpc"' in hcl
    assert 'vpc_name = "my-vpc"' in hcl


def test_map_integer_field(mapper):
    """Integer field maps to HCL number."""
    spec = MappingSpec(
        resource_type="ecs",
        terraform_type="alicloud_instance",
        rules=[MappingRule(hcl_attr="bandwidth", path="Bandwidth", type="int")],
    )
    hcl = mapper.map_resource(
        resource_type="ecs",
        resource_data={"Bandwidth": 100},
        spec=spec,
        block_name="ecs_1",
    )
    assert "bandwidth = 100" in hcl


def test_map_boolean_field(mapper):
    """Boolean field maps to true/false."""
    spec = MappingSpec(
        resource_type="vpc",
        terraform_type="alicloud_vpc",
        rules=[MappingRule(hcl_attr="is_default", path="IsDefault", type="bool")],
    )
    hcl = mapper.map_resource(
        resource_type="vpc",
        resource_data={"IsDefault": True},
        spec=spec,
        block_name="vpc_1",
    )
    assert "is_default = true" in hcl


def test_map_missing_field_skipped(mapper):
    """Missing optional fields are silently skipped."""
    spec = MappingSpec(
        resource_type="vpc",
        terraform_type="alicloud_vpc",
        rules=[
            MappingRule(hcl_attr="vpc_name", path="VpcName"),
            MappingRule(hcl_attr="description", path="Description", required=False),
        ],
    )
    hcl = mapper.map_resource(
        resource_type="vpc",
        resource_data={"VpcName": "prod"},
        spec=spec,
        block_name="vpc_prod",
    )
    assert "description" not in hcl


def test_map_sensitive_field_includes_sensitive_directive(mapper):
    """Sensitive fields get 'sensitive = true' appended."""
    spec = MappingSpec(
        resource_type="rds",
        terraform_type="alicloud_db_instance",
        rules=[
            MappingRule(hcl_attr="instance_name", path="DBInstanceDescription"),
            MappingRule(hcl_attr="password", path="AccountPassword", sensitive=True),
        ],
    )
    hcl = mapper.map_resource(
        resource_type="rds",
        resource_data={"DBInstanceDescription": "prod-db", "AccountPassword": "secret"},
        spec=spec,
        block_name="rds_prod_db",
    )
    assert "instance_name = \"prod-db\"" in hcl
    assert "password = ${var.rds_password}" in hcl
    assert "sensitive = true" in hcl


def test_format_value_dict():
    """Dict values format as HCL object blocks."""
    assert FieldMapper._format_value({"env": "prod", "team": "platform"}, "dict") == \
           '{ env = "prod", team = "platform" }'


def test_format_value_list():
    """List values format as HCL list literals."""
    assert FieldMapper._format_value(["sg-1", "sg-2"], "list") == \
           '["sg-1", "sg-2"]'


def test_format_value_none():
    """None formats as HCL null."""
    assert FieldMapper._format_value(None, "string") == "null"


def test_slugify_special_chars():
    """Special characters become underscores, multiple underscores collapse."""
    assert _slugify("my-vpc-prod") == "my_vpc_prod"
    assert _slugify("vsw.1") == "vsw_1"
    assert _slugify("123_start") == "r_123_start"
    assert _slugify("---") == "unnamed"


def test_generate_block_name_uses_name_field():
    """Block name uses the resource's Name field by default."""
    spec = MappingSpec(resource_type="vpc", terraform_type="alicloud_vpc")
    data = {"VpcName": "prod-vpc", "VpcId": "vpc-xxx"}
    name = FieldMapper.generate_block_name("alicloud_vpc", data, spec)
    assert name == "prod_vpc"


def test_generate_block_name_falls_back_to_id():
    """If Name field missing, fall back to ID."""
    spec = MappingSpec(resource_type="vpc", terraform_type="alicloud_vpc")
    data = {"VpcId": "vpc-xxx"}
    name = FieldMapper.generate_block_name("alicloud_vpc", data, spec)
    assert name == "vpc_xxx"
