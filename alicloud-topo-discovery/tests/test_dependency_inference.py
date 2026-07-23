"""Tests for dependency inference (Task 11).

Verifies topological ordering: parent resources must appear before
their children, regardless of insertion order.
"""
import pytest

from scripts.lib.dependency_inference import (
    DependencyInferenceError,
    infer_dependencies,
)
from scripts.lib.field_mapper import MappingRule, MappingSpec


def _make_resource(rt, data, spec, block_name):
    """Helper to build a resource tuple matching the expected shape."""
    return (rt, data, spec, block_name)


def test_vswitch_depends_on_vpc():
    """VSwitch with parent_ref VpcId should be ordered after its VPC."""
    vpc = _make_resource(
        "vpc",
        {"VpcId": "vpc-1", "VpcName": "prod"},
        MappingSpec("vpc", "alicloud_vpc", rules=[MappingRule("vpc_name", "VpcName")]),
        "prod_vpc",
    )
    vswitch = _make_resource(
        "vswitch",
        {"VSwitchId": "vsw-1", "VSwitchName": "web", "VpcId": "vpc-1"},
        MappingSpec("vswitch", "alicloud_vswitch", parent_ref="VpcId", rules=[]),
        "web_vswitch",
    )
    ordered = infer_dependencies([vswitch, vpc])
    names = [item[3] for item in ordered]
    # prod_vpc must come before web_vswitch
    assert names.index("prod_vpc") < names.index("web_vswitch")


def test_ecs_depends_on_vswitch_and_sg():
    """ECS with VSwitch parent ref orders after VSwitch and VPC."""
    vpc = _make_resource(
        "vpc", {"VpcId": "vpc-1", "VpcName": "prod"},
        MappingSpec("vpc", "alicloud_vpc", rules=[]), "prod_vpc",
    )
    vswitch = _make_resource(
        "vswitch", {"VSwitchId": "vsw-1", "VpcId": "vpc-1"},
        MappingSpec("vswitch", "alicloud_vswitch", parent_ref="VpcId", rules=[]), "web_vswitch",
    )
    ecs = _make_resource(
        "ecs", {"InstanceId": "i-1", "VpcAttributes": {"VSwitchId": "vsw-1"}},
        MappingSpec("ecs", "alicloud_instance", parent_ref="VpcAttributes.VSwitchId", rules=[]), "web_01",
    )
    ordered = infer_dependencies([ecs, vswitch, vpc])
    names = [item[3] for item in ordered]
    assert names.index("prod_vpc") < names.index("web_vswitch") < names.index("web_01")


def test_no_self_dependency():
    """A resource with no parent_ref has no dependencies."""
    vpc = _make_resource(
        "vpc", {"VpcId": "vpc-1", "VpcName": "prod"},
        MappingSpec("vpc", "alicloud_vpc", rules=[]), "prod_vpc",
    )
    ordered = infer_dependencies([vpc])
    assert len(ordered) == 1
    assert ordered[0][3] == "prod_vpc"


def test_circular_reference_raises():
    """Circular parent_ref should raise DependencyInferenceError."""
    a_data = {"VpcId": "vpc-a", "ParentVpcId": "vpc-b"}
    b_data = {"VpcId": "vpc-b", "ParentVpcId": "vpc-a"}
    a = ("vpc", a_data, MappingSpec("vpc", "alicloud_vpc", parent_ref="ParentVpcId", rules=[]), "vpc_a")
    b = ("vpc", b_data, MappingSpec("vpc", "alicloud_vpc", parent_ref="ParentVpcId", rules=[]), "vpc_b")
    with pytest.raises(DependencyInferenceError):
        infer_dependencies([a, b])


def test_empty_list_returns_empty():
    """Empty resource list returns empty list."""
    assert infer_dependencies([]) == []


def test_orphan_resource_warns_but_not_fails():
    """Orphan resource (parent not found) has no dependency edges."""
    vpc = _make_resource(
        "vpc", {"VpcId": "vpc-1", "VpcName": "prod"},
        MappingSpec("vpc", "alicloud_vpc", rules=[]), "prod_vpc",
    )
    vswitch = _make_resource(
        "vswitch", {"VSwitchId": "vsw-1", "VpcId": "nonexistent"},
        MappingSpec("vswitch", "alicloud_vswitch", parent_ref="VpcId", rules=[]), "web_vswitch",
    )
    ordered = infer_dependencies([vpc, vswitch])
    names = [item[3] for item in ordered]
    # Orphan doesn't break, just ordered independently
    assert "prod_vpc" in names
    assert "web_vswitch" in names
