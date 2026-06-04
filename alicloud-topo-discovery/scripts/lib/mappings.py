"""MappingSpec registry for all supported Aliyun resource types.

This module exports MAPPINGS: a dict from resource_type string to
MappingSpec instance. Used by export-hcl.py to know how to convert
each Describe* API response into HCL resource blocks.

Phase 1 covers Top-5 resource types:
  vpc, vswitch, ecs, rds, slb

Phase 3 (Plan 3) will add the remaining 13 types.
"""
from scripts.lib.field_mapper import MappingSpec, MappingRule


MAPPINGS = {
    "vpc": MappingSpec(
        resource_type="vpc",
        terraform_type="alicloud_vpc",
        rules=[
            MappingRule(hcl_attr="vpc_name", path="VpcName"),
            MappingRule(hcl_attr="cidr_block", path="CidrBlock"),
            MappingRule(hcl_attr="description", path="Description", required=False),
        ],
    ),
    "vswitch": MappingSpec(
        resource_type="vswitch",
        terraform_type="alicloud_vswitch",
        parent_ref="VpcId",
        rules=[
            MappingRule(hcl_attr="vswitch_name", path="VSwitchName"),
            MappingRule(hcl_attr="cidr_block", path="CidrBlock"),
            MappingRule(hcl_attr="zone_id", path="ZoneId"),
            MappingRule(hcl_attr="description", path="Description", required=False),
            # vpc_id is set via parent_ref (dependency inference)
        ],
    ),
    "ecs": MappingSpec(
        resource_type="ecs",
        terraform_type="alicloud_instance",
        rules=[
            MappingRule(hcl_attr="instance_name", path="InstanceName"),
            MappingRule(hcl_attr="instance_type", path="InstanceType"),
            MappingRule(hcl_attr="image_id", path="ImageId"),
            MappingRule(hcl_attr="host_name", path="HostName", required=False),
            MappingRule(hcl_attr="password", path="Password", sensitive=True),
            MappingRule(hcl_attr="vswitch_id", path="VpcAttributes.VSwitchId"),
            MappingRule(hcl_attr="security_groups", path="SecurityGroupIds.SecurityGroupId", type="list"),
        ],
    ),
    "rds": MappingSpec(
        resource_type="rds",
        terraform_type="alicloud_db_instance",
        rules=[
            MappingRule(hcl_attr="instance_name", path="DBInstanceDescription"),
            MappingRule(hcl_attr="engine", path="Engine"),
            MappingRule(hcl_attr="engine_version", path="EngineVersion"),
            MappingRule(hcl_attr="instance_type", path="DBInstanceClass"),
            MappingRule(hcl_attr="instance_storage", path="DBInstanceStorage", type="int"),
            MappingRule(hcl_attr="port", path="Port", type="int"),
            MappingRule(hcl_attr="vswitch_id", path="VSwitchId"),
            MappingRule(hcl_attr="password", path="AccountPassword", sensitive=True),
        ],
    ),
    "slb": MappingSpec(
        resource_type="slb",
        terraform_type="alicloud_slb",
        rules=[
            MappingRule(hcl_attr="name", path="LoadBalancerName"),
            MappingRule(hcl_attr="specification", path="LoadBalancerSpec"),
            MappingRule(hcl_attr="address_type", path="AddressType"),
            MappingRule(hcl_attr="internet_charge_type", path="InternetChargeType"),
            MappingRule(hcl_attr="bandwidth", path="Bandwidth", type="int"),
            MappingRule(hcl_attr="vswitch_id", path="VSwitchId"),
        ],
    ),
}
