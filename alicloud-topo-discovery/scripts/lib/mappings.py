"""MappingSpec registry for all supported Aliyun resource types.

This module exports MAPPINGS: a dict from resource_type string to
MappingSpec instance. Used by export-hcl.py to know how to convert
each Describe* API response into HCL resource blocks.

Phase 1 covers Top-5 resource types:
  vpc, vswitch, ecs, rds, slb

Phase 3 (Plan 3) will add the remaining 13 types.
"""
from scripts.lib.field_mapper import MappingRule, MappingSpec

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
    "nat": MappingSpec(
        resource_type="nat",
        terraform_type="alicloud_nat_gateway",
        rules=[
            MappingRule(hcl_attr="name", path="Name"),
            MappingRule(hcl_attr="description", path="Description", required=False),
            MappingRule(hcl_attr="nat_type", path="NatType"),
            MappingRule(hcl_attr="internet_charge_type", path="InternetChargeType"),
        ],
    ),
    "eip": MappingSpec(
        resource_type="eip",
        terraform_type="alicloud_eip",
        rules=[
            MappingRule(hcl_attr="name", path="Name"),
            MappingRule(hcl_attr="bandwidth", path="Bandwidth", type="int"),
            MappingRule(hcl_attr="internet_charge_type", path="InternetChargeType"),
            MappingRule(hcl_attr="instance_charge_type", path="InstanceChargeType"),
        ],
    ),
    "sg": MappingSpec(
        resource_type="sg",
        terraform_type="alicloud_security_group",
        rules=[
            MappingRule(hcl_attr="name", path="SecurityGroupName"),
            MappingRule(hcl_attr="description", path="Description", required=False),
        ],
    ),
    "oss": MappingSpec(
        resource_type="oss",
        terraform_type="alicloud_oss_bucket",
        rules=[
            MappingRule(hcl_attr="bucket", path="Name"),
            MappingRule(hcl_attr="storage_class", path="StorageClass"),
        ],
    ),
    "ram": MappingSpec(
        resource_type="ram",
        terraform_type="alicloud_ram_role",
        rules=[
            MappingRule(hcl_attr="name", path="RoleName"),
            MappingRule(hcl_attr="description", path="Description", required=False),
            MappingRule(hcl_attr="arn", path="Arn"),
            MappingRule(hcl_attr="assume_role_policy", path="AssumeRolePolicyDocument"),
        ],
    ),
    "polardb": MappingSpec(
        resource_type="polardb",
        terraform_type="alicloud_polardb_cluster",
        rules=[
            MappingRule(hcl_attr="description", path="DBClusterDescription"),
            MappingRule(hcl_attr="db_type", path="DBType"),
            MappingRule(hcl_attr="db_version", path="DBVersion"),
            MappingRule(hcl_attr="db_node_class", path="DBNodeClass"),
            MappingRule(hcl_attr="db_node_storage", path="DBNodeStorage", type="int"),
            MappingRule(hcl_attr="vswitch_id", path="VSwitchId"),
        ],
    ),
    "redis": MappingSpec(
        resource_type="redis",
        terraform_type="alicloud_redis_instance",
        rules=[
            MappingRule(hcl_attr="instance_name", path="InstanceName"),
            MappingRule(hcl_attr="instance_class", path="InstanceClass"),
            MappingRule(hcl_attr="engine_version", path="EngineVersion"),
            MappingRule(hcl_attr="connection_domain", path="ConnectionDomain"),
            MappingRule(hcl_attr="port", path="Port", type="int"),
        ],
    ),
    "kms": MappingSpec(
        resource_type="kms",
        terraform_type="alicloud_kms_key",
        rules=[
            MappingRule(hcl_attr="description", path="Description", required=False),
            MappingRule(hcl_attr="key_spec", path="KeySpec"),
            MappingRule(hcl_attr="usage", path="KeyUsage"),
            MappingRule(hcl_attr="origin", path="Origin"),
        ],
    ),
    "actiontrail": MappingSpec(
        resource_type="actiontrail",
        terraform_type="alicloud_actiontrail",
        rules=[
            MappingRule(hcl_attr="name", path="Name"),
            MappingRule(hcl_attr="oss_bucket_name", path="OssBucketName"),
            MappingRule(hcl_attr="oss_key_prefix", path="OssKeyPrefix", required=False),
        ],
    ),
    "nas": MappingSpec(
        resource_type="nas",
        terraform_type="alicloud_nas_file_system",
        rules=[
            MappingRule(hcl_attr="description", path="Description", required=False),
            MappingRule(hcl_attr="storage_type", path="StorageType"),
            MappingRule(hcl_attr="protocol_type", path="ProtocolType"),
        ],
    ),
    "fc": MappingSpec(
        resource_type="fc",
        terraform_type="alicloud_fc_service",
        rules=[
            MappingRule(hcl_attr="name", path="ServiceName"),
            MappingRule(hcl_attr="description", path="Description", required=False),
            MappingRule(hcl_attr="role", path="Role"),
        ],
    ),
    "vpn": MappingSpec(
        resource_type="vpn",
        terraform_type="alicloud_vpn_connection",
        rules=[
            MappingRule(hcl_attr="name", path="Name"),
            MappingRule(hcl_attr="local_subnet", path="LocalSubnet"),
            MappingRule(hcl_attr="remote_subnet", path="RemoteSubnet"),
        ],
    ),
    "ack": MappingSpec(
        resource_type="ack",
        terraform_type="alicloud_cs_kubernetes",
        rules=[
            MappingRule(hcl_attr="name", path="Name"),
            MappingRule(hcl_attr="cluster_type", path="ClusterType"),
            MappingRule(hcl_attr="version", path="Version"),
            MappingRule(hcl_attr="worker_number", path="WorkerNumber", type="int"),
            MappingRule(hcl_attr="vswitch_ids", path="VSwitchIds.VSwitchId", type="list"),
            MappingRule(hcl_attr="vpc_id", path="VpcId"),
        ],
    ),
    "sag": MappingSpec(
        resource_type="sag",
        terraform_type="alicloud_sag",
        rules=[
            MappingRule(hcl_attr="name", path="Name"),
            MappingRule(hcl_attr="cidr_block", path="CidrBlock"),
        ],
    ),
}
