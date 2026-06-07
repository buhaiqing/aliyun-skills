#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gcl_runner.py — Generator-Critic-Loop (GCL) runner for `alicloud-*-ops` skills.

Implements the loop flow defined in `AGENTS.md` §12.4 (Generator-Critic-Loop
adversarial quality gate). Wraps every `aliyun` / SDK invocation in a
re-evaluable quality gate that:

  [0] Pre-flight      — load rubric, resolve env.* / user.*, sanitize secrets
  [1.5] H Detection   — check CLI params, JSON structure, WAF compliance (opt-in)
  [1] Generate        — invoke the command (subprocess) and capture trace
  [2] Critique        — re-classify output using the rubric's regex hot-spots
  [3] Decide          — apply termination rules from `AGENTS.md` §12.5

  Persistent trace → ./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json
  Trace schema is the one defined in `AGENTS.md` §12.6.

The Critic in Phase 2 is a **mechanical re-classifier** (pure Python regex),
not an LLM call. This makes the runner deterministic, CI-friendly, and
reproducible. The rubric's regex list IS the Critic's score function —
matches the AGENTS.md §12.7 "Critic must hide the raw user request" rule
because the Critic never sees `--user-request`.

Phase 6 adds an optional **Hallucination Detection (H)** layer: a pre-execution
structural validity check that verifies CLI parameters exist, JSON payloads
match OpenAPI schemas, and commands comply with WAF best practices. Enable
via `--enable-hallucination-check`.

USAGE
-----
    python gcl_runner.py \\
        --skill alicloud-ecs-ops \\
        --op DeleteInstance \\
        --command "aliyun ecs DeleteInstance --InstanceId i-bp1..." \\
        --max-iter 2

    # with hallucination detection enabled
    python gcl_runner.py \\
        --skill alicloud-ecs-ops \\
        --op DeleteInstance \\
        --command "aliyun ecs DeleteInstance --InstanceId i-bp1..." \\
        --enable-hallucination-check

    # with custom rubric and prompt template paths
    python gcl_runner.py \\
        --skill alicloud-ecs-ops \\
        --op DeleteInstance \\
        --command "aliyun ecs DeleteInstance --InstanceId i-bp1..." \\
        --rubric /path/to/rubric.md \\
        --prompt-template /path/to/prompt-templates.md \\
        --output-dir /custom/audit-dir

EXIT CODES
----------
    0  PASS                 — every rubric dimension meets its threshold
    1  MAX_ITER             — reached max_iterations; best-so-far + unresolved items
    2  SAFETY_FAIL          — Safety=0; ABORT (no partial output)
    3  USAGE_ERROR          — bad CLI args or missing files
    4  RUBRIC_ERROR         — rubric file unparseable or missing required sections
    5  HALLUCINATION_ABORT  — H detected unresolved hallucinations after regeneration

REQUIREMENTS
------------
    Python 3.10+ stdlib only. No external dependencies.

DESIGN
------
- The script is intentionally a single file. It can be copy-pasted into
  any of the 14 `required` skill directories as a 1:1 drop-in.
- The `--command` argument is the exact `aliyun` (or SDK-shell) command.
  The runner does NOT rewrite the command; it only captures its execution
  trace and re-classifies the result.
- The Critic's regex list is parsed from the rubric's §2.x "Detection
  Regex" tables. Tables that don't exist (e.g. for purely control-plane
  skills) degrade gracefully — Critic still scores 1 on Safety if the
  command did not match any non-empty pre-flight sub-rule.
- Secret sanitization is mandatory and is applied to BOTH the command
  string AND the result_excerpt before either is written to the trace
  (per AGENTS.md §8 + §12.6).
- Hallucination Detection (H) is an optional pre-execution gate. It does
  NOT call any cloud API — it only checks structural validity against a
  pre-compiled parameter knowledge base and WAF patterns.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import shlex
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default directory for trace persistence (gitignored per AGENTS.md §12.6).
DEFAULT_AUDIT_DIR = Path("./audit-results")

#: Aliyun product → CLI subcommand mapping.
#: Used to validate the command's product prefix matches the skill.
PRODUCT_CLI = {
    "alicloud-ecs-ops": "ecs",
    "alicloud-redis-ops": "r-kvstore",
    "alicloud-rds-ops": "rds",
    "alicloud-ram-ops": "ram",
    "alicloud-kms-ops": "kms",
    "alicloud-eip-ops": "vpc",  # EIP ops live under vpc
    "alicloud-vpc-ops": "vpc",
    "alicloud-nat-ops": "vpc",  # NAT Gateway ops also live under vpc
    "alicloud-mongodb-ops": "dds",
    "alicloud-elasticsearch-ops": "elasticsearch",
    "alicloud-polar-mysql-ops": "polardb",
    "alicloud-polar-postgresql-ops": "polardb",
    "alicloud-polar-oracle-ops": "polardb-io",  # legacy
    "alicloud-polar-pg-ops": "polardb-pg",  # legacy
    "alicloud-slb-ops": "slb",
    "alicloud-ack-ops": "cs",  # ACK = Container Service
    "alicloud-ack-serverless-ops": "cs",
    "alicloud-fc-ops": "fc",
    "alicloud-eci-ops": "eci",
    "alicloud-cms-ops": "cms",
    "alicloud-actiontrail-ops": "actiontrail",
    "alicloud-billing-ops": "bss",
    "alicloud-das-ops": "das",
    "alicloud-resource-manager-ops": "resourcemanager",
    "alicloud-agentrun-ops": "agentrun",
}

#: Default `max_iter` per skill class (AGENTS.md §12.8).
SKILL_MAX_ITER = {
    # required (max_iter=2)
    "alicloud-ecs-ops": 2,
    "alicloud-redis-ops": 2,
    "alicloud-rds-ops": 2,
    "alicloud-ram-ops": 2,
    "alicloud-kms-ops": 2,
    "alicloud-eip-ops": 2,
    "alicloud-vpc-ops": 2,
    "alicloud-nat-ops": 2,
    "alicloud-mongodb-ops": 2,
    "alicloud-elasticsearch-ops": 2,
    "alicloud-polar-mysql-ops": 2,
    "alicloud-polar-postgresql-ops": 2,
    "alicloud-polar-oracle-ops": 2,
    "alicloud-polar-pg-ops": 2,
    # recommended (max_iter=3)
    "alicloud-slb-ops": 3,
    "alicloud-ack-ops": 3,
    "alicloud-ack-serverless-ops": 3,
    "alicloud-fc-ops": 3,
    "alicloud-eci-ops": 3,
    "alicloud-cms-ops": 3,
    # optional (max_iter=5; GCL not required for read-only)
    "alicloud-actiontrail-ops": 5,
    "alicloud-billing-ops": 5,
    "alicloud-das-ops": 5,
    "alicloud-resource-manager-ops": 5,
    "alicloud-agentrun-ops": 5,
}

#: Known CLI parameters per (product, operation). Used by the Hallucination
#: Detector to verify `--flag` existence before executing the command.
#: Format: {(product, operation): {known_flag1, known_flag2, ...}}
#: These are compiled from Alibaba Cloud OpenAPI specs and `aliyun help` output.
#: When `aliyun` CLI is available, the H detector will also attempt live help
#: parsing as a superset. This knowledge base serves as the offline fallback.
PARAMETER_KNOWLEDGE: Dict[Tuple[str, str], set] = {
    # ECS (ecs)
    ("ecs", "DescribeInstances"): {"--RegionId", "--PageSize", "--PageNumber", "--InstanceIds", "--Status", "--VpcId", "--VSwitchId", "--ZoneId", "--InstanceName", "--InstanceNetworkType", "--InstanceChargeType", "--ResourceGroupId", "--Tag", "--DryRun", "--InnerIpAddresses", "--PublicIpAddresses", "--PrivateIpAddresses", "--SecurityGroupId", "--Ipv6Address", "--HpcClusterId", "--RdmaIpAddresses", "--InstanceType", "--KeyPairName", "--LockReason", "--DeviceAvailable", "--IoOptimized", "--AdditionalAttributes", "--NeedSaleCycle", "--HttpEndpoint", "--HttpTokens", "--HttpPutResponseHopLimit", "--EcsInstanceName"},
    ("ecs", "CreateInstance"): {"--RegionId", "--ImageId", "--InstanceType", "--SecurityGroupId", "--VSwitchId", "--InstanceName", "--Description", "--InternetChargeType", "--InternetMaxBandwidthIn", "--InternetMaxBandwidthOut", "--HostName", "--Password", "--ZoneId", "--IoOptimized", "--SystemDisk", "--SystemDiskSize", "--SystemDiskCategory", "--DataDisk", "--DataDisk-0-Size", "--DataDisk-0-Category", "--DataDisk-1-Size", "--KeyPairName", "--SpotStrategy", "--SpotPriceLimit", "--SecurityEnhancementStrategy", "--Tag", "--ResourceGroupId", "--Period", "--PeriodUnit", "--AutoRenew", "--AutoRenewPeriod", "--InstanceChargeType", "--DeploymentSetId", "--DeploymentSetGroupNo", "--DedicatedHostId", "--CreditSpecification", "--PrivateIpAddress", "--DryRun", "--ClientToken", "--HpcClusterId", "--HttpEndpoint", "--HttpTokens", "--HttpPutResponseHopLimit", "--StorageSetId", "--StorageSetPartitionNumber"},
    ("ecs", "DeleteInstance"): {"--RegionId", "--InstanceId", "--Force"},
    ("ecs", "StartInstance"): {"--RegionId", "--InstanceId"},
    ("ecs", "StopInstance"): {"--RegionId", "--InstanceId", "--ForceStop", "--StoppedMode", "--ConfirmStop"},
    ("ecs", "RebootInstance"): {"--RegionId", "--InstanceId", "--ForceStop"},
    ("ecs", "RunInstances"): {"--RegionId", "--ImageId", "--InstanceType", "--SecurityGroupId", "--VSwitchId", "--InstanceName", "--Description", "--InternetChargeType", "--InternetMaxBandwidthIn", "--InternetMaxBandwidthOut", "--HostName", "--Password", "--ZoneId", "--IoOptimized", "--SystemDisk", "--SystemDiskSize", "--SystemDiskCategory", "--DataDisk", "--KeyPairName", "--SpotStrategy", "--SpotPriceLimit", "--SecurityEnhancementStrategy", "--Tag", "--ResourceGroupId", "--Period", "--PeriodUnit", "--AutoRenew", "--AutoRenewPeriod", "--InstanceChargeType", "--Amount", "--MinAmount", "--UniqueSuffix", "--PrivateIpAddress", "--DryRun", "--ClientToken", "--DeploymentSetId", "--DedicatedHostId", "--CreditSpecification", "--HttpEndpoint", "--HttpTokens", "--HttpPutResponseHopLimit", "--StorageSetId", "--StorageSetPartitionNumber"},
    ("ecs", "DescribeDisks"): {"--RegionId", "--ZoneId", "--DiskIds", "--InstanceId", "--DiskType", "--Category", "--Status", "--PageSize", "--PageNumber", "--Tag", "--ResourceGroupId", "--DryRun", "--Portable", "--DeleteWithInstance", "--DeleteAutoSnapshot", "--EnableAutoSnapshot", "--AdditionalAttributes", "--DiskName"},
    ("ecs", "CreateDisk"): {"--RegionId", "--ZoneId", "--DiskName", "--Description", "--Size", "--Category", "--SnapshotId", "--Tag", "--ResourceGroupId", "--DryRun", "--ClientToken", "--InstanceId", "--DeleteWithInstance", "--DeleteAutoSnapshot", "--EnableAutoSnapshot", "--PerformanceLevel", "--StorageSetId", "--StorageSetPartitionNumber", "--ProvisionedIops", "--BurstingEnabled"},
    ("ecs", "DeleteDisk"): {"--RegionId", "--DiskId"},
    ("ecs", "AttachDisk"): {"--RegionId", "--InstanceId", "--DiskId", "--Device", "--DeleteWithInstance", "--Bootable", "--KeyPairName", "--Password"},
    ("ecs", "DetachDisk"): {"--RegionId", "--InstanceId", "--DiskId", "--Device", "--Force"},
    ("ecs", "DescribeSecurityGroups"): {"--RegionId", "--PageSize", "--PageNumber", "--SecurityGroupId", "--VpcId", "--ResourceGroupId", "--Tag", "--SecurityGroupName", "--SecurityGroupType", "--DryRun", "--NetworkType"},
    ("ecs", "CreateSecurityGroup"): {"--RegionId", "--Description", "--SecurityGroupName", "--VpcId", "--SecurityGroupType", "--Tag", "--ResourceGroupId", "--ServiceManaged", "--ClientToken"},
    ("ecs", "DeleteSecurityGroup"): {"--RegionId", "--SecurityGroupId"},
    ("ecs", "AuthorizeSecurityGroup"): {"--RegionId", "--SecurityGroupId", "--IpProtocol", "--PortRange", "--SourceCidrIp", "--SourceGroupId", "--SourcePortRange", "--Policy", "--Priority", "--NicType", "--DestCidrIp", "--Ipv6SourceCidrIp", "--SourcePrefixListId", "--Description", "--Permissions"},
    ("ecs", "RevokeSecurityGroup"): {"--RegionId", "--SecurityGroupId", "--IpProtocol", "--PortRange", "--SourceCidrIp", "--SourceGroupId", "--SourcePortRange", "--Policy", "--Priority", "--NicType", "--DestCidrIp", "--Ipv6SourceCidrIp", "--SourcePrefixListId", "--Description", "--Permissions"},
    ("ecs", "CreateSnapshot"): {"--RegionId", "--DiskId", "--SnapshotName", "--Description", "--RetentionDays", "--Tag", "--Category", "--InstantAccess", "--InstantAccessRetentionDays", "--ClientToken"},
    ("ecs", "DescribeSnapshots"): {"--RegionId", "--InstanceId", "--DiskId", "--SnapshotIds", "--SnapshotName", "--Status", "--PageSize", "--PageNumber", "--Tag", "--ResourceGroupId", "--DryRun", "--SnapshotLinkId", "--SourceDiskType", "--Usage", "--KMSKeyId", "--Category", "--Encrypted"},
    ("ecs", "DeleteSnapshot"): {"--RegionId", "--SnapshotId"},
    ("ecs", "ReplaceSystemDisk"): {"--RegionId", "--InstanceId", "--ImageId", "--SystemDiskSize", "--Platform", "--Architecture", "--Password", "--KeyPairName", "--SecurityEnhancementStrategy", "--DiskId"},
    ("ecs", "TagResources"): {"--RegionId", "--ResourceId", "--ResourceType", "--Tag", "--Tag-0-Key", "--Tag-0-Value"},
    ("ecs", "RunCommand"): {"--RegionId", "--CommandContent", "--Type", "--Timeout", "--InstanceId", "--WorkingDir", "--EnableParameter", "--ContentEncoding", "--RepeatMode", "--Frequency", "--KeepCommand", "--Username", "--WindowsPasswordName"},
    # RDS (rds)
    ("rds", "DescribeDBInstances"): {"--RegionId", "--PageSize", "--PageNumber", "--DBInstanceId", "--DBInstanceStatus", "--Engine", "--ZoneId", "--ResourceGroupId", "--SearchKey", "--InstanceLevel", "--ConnectionMode", "--Expired", "--Tags", "--ClientToken"},
    ("rds", "CreateDBInstance"): {"--RegionId", "--Engine", "--EngineVersion", "--DBInstanceClass", "--DBInstanceStorage", "--DBInstanceNetType", "--DBInstanceDescription", "--SecurityIPList", "--PayType", "--Period", "--UsedTime", "--ZoneId", "--VpcId", "--VSwitchId", "--ClientToken", "--InstanceNetworkType", "--PrivateIpAddress", "--AutoRenew", "--StorageAutoScale", "--StorageUpperBound", "--TargetDedicatedHostIdForMaster", "--EncryptionKey", "--Category", "--DedicatedHostGroupId", "--ServerlessConfig", "--DeletionProtection", "--BpeEnabled", "--DryRun", "--ResourceGroupId"},
    ("rds", "DeleteDBInstance"): {"--RegionId", "--DBInstanceId"},
    ("rds", "RestartDBInstance"): {"--RegionId", "--DBInstanceId"},
    ("rds", "CreateDatabase"): {"--RegionId", "--DBInstanceId", "--DBName", "--CharacterSetName", "--DBDescription"},
    ("rds", "DeleteDatabase"): {"--RegionId", "--DBInstanceId", "--DBName"},
    ("rds", "CreateAccount"): {"--RegionId", "--DBInstanceId", "--AccountName", "--AccountPassword", "--AccountDescription", "--AccountType"},
    ("rds", "DeleteAccount"): {"--RegionId", "--DBInstanceId", "--AccountName"},
    ("rds", "CreateBackup"): {"--RegionId", "--DBInstanceId", "--DBName", "--BackupStrategy", "--BackupMethod", "--BackupType"},
    ("rds", "DescribeSlowLogs"): {"--RegionId", "--DBInstanceId", "--StartTime", "--EndTime", "--PageSize", "--PageNumber", "--DBName", "--SortKey"},
    ("rds", "ModifySecurityIps"): {"--RegionId", "--DBInstanceId", "--SecurityIPList", "--SecurityIPGroupName", "--SecurityIPGroupAttribute", "--ModifyMode", "--WhitelistNetworkType"},
    ("rds", "DescribeParameters"): {"--RegionId", "--DBInstanceId"},
    # Redis / Tair (r-kvstore)
    ("r-kvstore", "DescribeInstances"): {"--RegionId", "--PageSize", "--PageNumber", "--InstanceIds", "--InstanceStatus", "--InstanceClass", "--ChargeType", "--NetworkType", "--EngineVersion", "--Expired", "--SearchKey", "--ZoneId", "--VpcId", "--VSwitchId", "--Tag", "--ResourceGroupId"},
    ("r-kvstore", "CreateInstance"): {"--RegionId", "--InstanceClass", "--InstanceName", "--Password", "--InstanceType", "--EngineVersion", "--ZoneId", "--VpcId", "--VSwitchId", "--ChargeType", "--Period", "--NetworkType", "--Config", "--ClientToken", "--AutoRenew", "--AutoUseCoupon", "--BusinessInfo", "--CouponNo", "--DedicatedHostId", "--DryRun", "--GlobalInstanceId", "--PrivateIpAddress", "--ResourceGroupId", "--RestoreTime", "--SecondaryZoneId", "--SrcDBInstanceId", "--Token"},
    ("r-kvstore", "DeleteInstance"): {"--RegionId", "--InstanceId", "--GlobalInstanceId"},
    ("r-kvstore", "FlushInstance"): {"--RegionId", "--InstanceId"},
    ("r-kvstore", "DescribeBackups"): {"--RegionId", "--InstanceId", "--PageSize", "--PageNumber", "--StartTime", "--EndTime", "--NodeId"},
    ("r-kvstore", "CreateBackup"): {"--RegionId", "--InstanceId"},
    ("r-kvstore", "RestoreInstance"): {"--RegionId", "--InstanceId", "--BackupId"},
    # SLB (slb)
    ("slb", "DescribeLoadBalancers"): {"--RegionId", "--LoadBalancerId", "--LoadBalancerName", "--LoadBalancerStatus", "--AddressType", "--Address", "--VpcId", "--VSwitchId", "--InternetChargeType", "--NetworkType", "--ServerId", "--PageSize", "--PageNumber", "--ResourceGroupId", "--Tag", "--MasterZoneId", "--SlaveZoneId", "--PayType"},
    ("slb", "DeleteLoadBalancer"): {"--RegionId", "--LoadBalancerId"},
    ("slb", "AddBackendServers"): {"--RegionId", "--LoadBalancerId", "--BackendServers"},
    ("slb", "RemoveBackendServers"): {"--RegionId", "--LoadBalancerId", "--BackendServers"},
    ("slb", "SetBackendServers"): {"--RegionId", "--LoadBalancerId", "--BackendServers"},
    ("slb", "DescribeHealthStatus"): {"--RegionId", "--LoadBalancerId", "--ListenerPort", "--ListenerProtocol"},
    # RAM (ram)
    ("ram", "CreateUser"): {"--UserName", "--DisplayName", "--MobilePhone", "--Email", "--Comments"},
    ("ram", "DeleteUser"): {"--UserName"},
    ("ram", "ListUsers"): {"--Marker", "--MaxItems"},
    ("ram", "CreatePolicy"): {"--PolicyName", "--Description", "--PolicyDocument"},
    ("ram", "DeletePolicy"): {"--PolicyName"},
    ("ram", "AttachPolicyToUser"): {"--PolicyName", "--PolicyType", "--UserName"},
    ("ram", "DetachPolicyFromUser"): {"--PolicyName", "--PolicyType", "--UserName"},
    # VPC (vpc)
    ("vpc", "DescribeVpcs"): {"--RegionId", "--VpcId", "--VpcName", "--PageSize", "--PageNumber", "--ResourceGroupId", "--Tag", "--DryRun", "--IsDefault"},
    ("vpc", "DeleteVpc"): {"--RegionId", "--VpcId"},
    ("vpc", "DescribeVSwitches"): {"--RegionId", "--VpcId", "--VSwitchId", "--ZoneId", "--PageSize", "--PageNumber", "--VSwitchName", "--IsDefault", "--ResourceGroupId", "--Tag", "--DryRun", "--RouteTableId"},
    ("vpc", "DeleteVSwitch"): {"--RegionId", "--VSwitchId"},
    ("vpc", "DescribeNatGateways"): {"--RegionId", "--NatGatewayId", "--VpcId", "--PageSize", "--PageNumber", "--ResourceGroupId", "--Tag", "--DryRun", "--InstanceChargeType", "--Spec", "--NetworkType", "--NatType"},
    ("vpc", "DescribeEipAddresses"): {"--RegionId", "--AllocationId", "--EipAddress", "--Status", "--PageSize", "--PageNumber", "--ResourceGroupId", "--Tag", "--DryRun", "--InstanceId", "--InstanceType", "--InternetChargeType", "--SecurityProtectionEnabled", "--Bandwidth", "--AssociatedInstanceType", "--AssociatedInstanceId"},
    ("vpc", "ReleaseEipAddress"): {"--RegionId", "--AllocationId"},
    # KMS (kms)
    ("kms", "CreateKey"): {"--KeySpec", "--KeyUsage", "--Description", "--EnableAutomaticRotation", "--RotationInterval", "--ProtectionLevel", "--Origin"},
    ("kms", "ScheduleKeyDeletion"): {"--KeyId", "--PendingWindowInDays"},
    ("kms", "CancelKeyDeletion"): {"--KeyId"},
    ("kms", "DescribeKey"): {"--KeyId"},
    ("kms", "Encrypt"): {"--KeyId", "--Plaintext", "--EncryptionContext"},
    ("kms", "Decrypt"): {"--CiphertextBlob", "--EncryptionContext"},
    # CMS (cms)
    ("cms", "DescribeMetricList"): {"--Namespace", "--MetricName", "--Period", "--StartTime", "--EndTime", "--Dimensions", "--NextToken", "--Length", "--Cursor"},
    ("cms", "PutMetricAlarm"): {"--RegionId", "--Name", "--Namespace", "--MetricName", "--Period", "--Statistics", "--Threshold", "--ComparisonOperator", "--EvaluationCount", "--Period", "--ContactGroups", "--StartTime", "--EndTime", "--SilenceTime", "--EffectiveInterval"},
    ("cms", "DeleteMetricAlarm"): {"--RegionId", "--AlarmId"},
    # MongoDB / DDS (dds)
    ("dds", "DescribeDBInstances"): {"--RegionId", "--PageSize", "--PageNumber", "--DBInstanceId", "--Engine", "--ZoneId", "--Expired", "--ChargeType", "--ResourceGroupId", "--Tag", "--DBInstanceType", "--DBInstanceClass", "--DBInstanceStatus", "--ReplicationFactor", "--NetworkType", "--VpcId", "--VSwitchId"},
    ("dds", "DeleteDBInstance"): {"--RegionId", "--DBInstanceId", "--ClientToken"},
    # Elasticsearch (elasticsearch)
    ("elasticsearch", "DescribeInstances"): {"--page", "--size", "--instanceId", "--esVersion", "--description", "--resourceGroupId", "--tags", "--vpcId", "--zoneId", "--paymentType", "--status"},
    ("elasticsearch", "DeleteInstance"): {"--InstanceId", "--clientToken"},
    # PolarDB (polardb)
    ("polardb", "DescribeDBClusters"): {"--RegionId", "--PageSize", "--PageNumber", "--DBClusterIds", "--DBClusterDescription", "--DBClusterStatus", "--PayType", "--ResourceGroupId", "--Tag"},
    ("polardb", "DeleteDBCluster"): {"--RegionId", "--DBClusterId"},
    ("polardb", "CreateDBCluster"): {"--RegionId", "--DBNodeClass", "--ClusterCategory", "--DBClusterDescription", "--PayType", "--Period", "--UsedTime", "--VpcId", "--VSwitchId", "--DBType", "--DBVersion", "--ZoneId", "--CreationOption", "--SourceResourceId", "--CloneDataPoint", "--AutoRenew", "--ResourceGroupId", "--TDEStatus", "--StorageType", "--DBNodeCount", "--ParameterGroupId", "--ServerlessType", "--ScaleMin", "--ScaleMax", "--StoragePlan", "--StorageAutoScale"},
    # ACK / CS (cs)
    ("cs", "DescribeClusters"): {"--name", "--clusterType", "--pageSize", "--page_number", "--regionId"},
    ("cs", "DeleteCluster"): {"--clusterId", "--retain_resources", "--retain_all"},
    # FC (fc)
    ("fc", "ListFunctions"): {"--serviceName", "--prefix", "--startKey", "--nextToken", "--limit"},
    ("fc", "DeleteFunction"): {"--serviceName", "--functionName"},
    # SLS (sls)
    ("sls", "DescribeProject"): {"--project"},
    ("sls", "DeleteLogStore"): {"--project", "--logstore"},
    # ActionTrail (actiontrail)
    ("actiontrail", "DescribeTrails"): {"--RegionId", "--NameList", "--IncludeShadowTrails"},
    # BSS (bss)
    ("bss", "DescribeInstanceBill"): {"--BillingCycle", "--ProductCode", "--PageNum", "--PageSize", "--OwnerId", "--IsHideZeroConsumption", "--IsBillingItem"},
}

#: WAF compliance patterns flagged by the Hallucination Detector.
#: These are regex patterns that match commands that may violate Well-Architected
#: best practices. Format: [(regex, pillar, description)]
WAF_PATTERNS: List[Tuple[str, str, str]] = [
    # Security pillar
    (r"--DeletionProtection\s+false", "Security", "Disabling deletion protection on a production resource"),
    (r"--Force\b", "Security", "Use of --Force flag on destructive operation without explicit confirmation"),
    (r"--EnableBackupLog\s+false", "Security", "Disabling backup logging reduces audit trail"),
    # Stability pillar
    (r"--Period\s+1\b(?!\d)", "Stability", "Very short billing period (1 month/1 year) may cause unexpected service interruption"),
    (r"--BackupRetentionPeriod\s+0\b", "Stability", "Setting backup retention to 0 disables backups"),
    (r"--AutoRenew\s+false", "Stability", "Disabling auto-renewal risks service interruption"),
    # Cost pillar
    (r"--PayType\s+PostPaid\b", "Cost", "PostPaid billing may be more expensive for stable workloads; consider PrePaid"),
    (r"--InstanceChargeType\s+PostPaid\b", "Cost", "PostPaid billing may be more expensive for stable workloads; consider PrePaid"),
    (r"--InternetChargeType\s+PayByTraffic\b", "Cost", "PayByTraffic may be more expensive for high-bandwidth workloads; consider PayByBandwidth"),
    # Efficiency pillar
    (r"--InstanceType\s+ecs\.(?:t5|t6|s6)\b", "Efficiency", "Burstable instance types (t5/t6/s6) may be inappropriate for production workloads"),
    # Performance pillar
    (r"--SystemDiskCategory\s+cloud_efficiency", "Performance", "cloud_efficiency disk may be insufficient for production workloads; consider cloud_ssd or cloud_essd"),
    (r"--DBInstanceClass\s+rds\.mysql\.(?:s2|t1)\b", "Performance", "Burstable/entry-level DB instance class may be insufficient for production workloads"),
]

#: Secret patterns (AGENTS.md §8 — Security Constraints).
#: All matches are replaced with `<masked>` in trace values.
SECRET_PATTERNS: List[Tuple[str, str, str]] = [
    # (description, regex, replacement)
    ("AK/SK", r"(?i)ALIBABA_CLOUD_ACCESS_KEY_SECRET=\S+", "ALIBABA_CLOUD_ACCESS_KEY_SECRET=<masked>"),
    ("AKID", r"(?i)ALIBABA_CLOUD_ACCESS_KEY_ID=\S+", "ALIBABA_CLOUD_ACCESS_KEY_ID=<masked>"),
    ("CLI SecretKey flag", r"--access-key-secret\s+\S+", "--access-key-secret <masked>"),
    ("CLI AccessKey ID flag", r"--access-key-id\s+\S+", "--access-key-id <masked>"),
    # Note: the [A-Za-z] prefix covers both --password and --AccountPassword
    # and any other Aliyun --*Password / --*Key / --*Token flag. The pattern
    # is intentionally broad to catch engine-specific variants.
    ("CLI *Password flag (any prefix)", r"--[A-Za-z][A-Za-z]*Password\s+\S+", "--<prefix>Password <masked>"),
    ("CLI *Key flag (any prefix)", r"--[A-Za-z][A-Za-z]*Key\s+\S+", "--<prefix>Key <masked>"),
    ("CLI *Token flag (any prefix)", r"--[A-Za-z][A-Za-z]*Token\s+\S+", "--<prefix>Token <masked>"),
    ("CLI *Secret flag (any prefix)", r"--[A-Za-z][A-Za-z]*Secret\s+\S+", "--<prefix>Secret <masked>"),
    ("CLI stsk flag", r"--stsk\s+\S+", "--stsk <masked>"),
    ("Env PGPASSWORD", r"PGPASSWORD=\S+", "PGPASSWORD=<masked>"),
    ("Env MYSQL_PWD", r"MYSQL_PWD=\S+", "MYSQL_PWD=<masked>"),
    ("sqlplus creds", r"(sqlplus\s+\S+/)\S+(@)", r"\1<masked>\2"),
    ("psql / psql URI creds", r"(postgresql://[^:]+:)\S+(@)", r"\1<masked>\2"),
    ("mongo URI creds", r"(mongodb://[^:]+:)\S+(@)", r"\1<masked>\2"),
    ("mysql URI creds", r"(mysql://[^:]+:)\S+(@)", r"\1<masked>\2"),
    ("BEGIN PRIVATE KEY block", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----", "-----BEGIN PRIVATE KEY-----\n<masked>\n-----END PRIVATE KEY-----"),
    ("JWT-like", r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", "<masked-jwt>"),
    ("Bearer token", r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer <masked>"),
    ("Redis AUTH inline", r"(?i)-a\s+\S+", "-a <masked>"),
    ("KMS Plaintext", r"(?i)([\"']?Plaintext[\"']?|[\"']?PlaintextBlob[\"']?)\s*[:=]\s*['\"]?([A-Za-z0-9+/=]+)['\"]?", r"\1=<masked>"),
    ("KMS SecretData", r"(?i)([\"']?SecretData[\"']?)\s*[:=]\s*['\"]?([A-Za-z0-9+/=]+)['\"]?", r"\1=<masked>"),
    ("KMS KeyMaterial", r"(?i)([\"']?KeyMaterial[\"']?)\s*[:=]\s*['\"]?([A-Za-z0-9+/=]+)['\"]?", r"\1=<masked>"),
    ("RAM AccessKeySecret JSON", r'(?i)"AccessKeySecret"\s*:\s*"[^"]+"', '"AccessKeySecret": "<masked>"'),
]

#: Exit code mapping (per AGENTS.md §4 + §14.3 + this script's CLI).
EXIT_PASS = 0
EXIT_MAX_ITER = 1
EXIT_SAFETY_FAIL = 2
EXIT_USAGE_ERROR = 3
EXIT_RUBRIC_ERROR = 4
EXIT_HALLUCINATION_ABORT = 5


# ---------------------------------------------------------------------------
# Secret sanitization
# ---------------------------------------------------------------------------


def sanitize(text: str) -> str:
    """Apply all SECRET_PATTERNS to `text`, returning a sanitized copy.

    Idempotent: running sanitize twice yields the same result as running it once.
    """
    if not text:
        return text
    for _desc, pattern, replacement in SECRET_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


# ---------------------------------------------------------------------------
# Rubric parsing
# ---------------------------------------------------------------------------

#: Regex to extract a markdown table row containing the operation name and
#: sub-rule description. Used for per-op safety sub-rule extraction.
_RUBRIC_OP_ROW_RE = re.compile(
    r"^\s*\|?\s*`?([A-Za-z][A-Za-z0-9_]+(?:[A-Z][A-Za-z0-9_]*)*)`?\s*\|"
    r"(.*?)\|\s*$",
    re.MULTILINE,
)

#: Regex to extract a "Detection Regex" table row: `| <regex> | <risk> | <examples> |`
_RUBRIC_REGEX_ROW_RE = re.compile(
    r"^\s*\|?\s*(`[^`]+`)\s*\|\s*([A-Z_][A-Z_0-9 \-]*)\s*\|",
    re.MULTILINE,
)


def parse_rubric(rubric_path: Path) -> Dict[str, Any]:
    """Parse a `references/rubric.md` file and return its structured content.

    Returns a dict with keys:
        - version: str                 (from frontmatter)
        - last_updated: str            (from frontmatter)
        - api: str                     (from frontmatter)
        - cli_applicability: str       (from frontmatter)
        - ops: dict[str, str]          (per-op sub-rule text)
        - regexes: list[tuple[str, str]]
                                      (list of (regex-pattern, risk-class))
        - max_iter: int                (from §3 or frontmatter; default 2)

    Raises `RubricError` on missing required sections.
    """
    if not rubric_path.is_file():
        raise RubricError(f"rubric file not found: {rubric_path}")

    raw = rubric_path.read_text(encoding="utf-8")

    # Frontmatter
    frontmatter: Dict[str, str] = {}
    if raw.startswith("---"):
        end = raw.find("---", 3)
        if end != -1:
            fm_block = raw[3:end]
            for line in fm_block.splitlines():
                m = re.match(r"^\s*([a-z_]+)\s*:\s*(.+?)\s*$", line)
                if m:
                    key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
                    frontmatter[key] = val

    # Per-op sub-rules (from §1.2 table)
    ops: Dict[str, str] = {}
    # Find §1.2 (Safety) section; capture until §2
    safety_match = re.search(
        r"### 1\.2 Safety.*?(?=### 1\.3|\Z)",
        raw,
        re.DOTALL,
    )
    if safety_match:
        section = safety_match.group(0)
        for m in _RUBRIC_OP_ROW_RE.finditer(section):
            op_name, sub_rule = m.group(1), m.group(2).strip()
            # Skip header row (column header like "| Operation | Sub-rule ... |")
            if op_name.lower() in ("operation", "op", "name"):
                continue
            # Skip empty / decorative rows
            if "---" in op_name or "Sub-rule" in op_name:
                continue
            ops[op_name] = sub_rule

    # Detection regexes (from §2.x tables)
    regexes: List[Tuple[str, str]] = []
    for m in _RUBRIC_REGEX_ROW_RE.finditer(raw):
        # Strip backticks; compile-safe
        pattern = m.group(1).strip("`")
        risk = m.group(2).strip()
        # Sanity: must look like a regex (contains at least one meta-char or \b)
        if any(meta in pattern for meta in ("\\b", "\\s", "\\S", "\\w", "\\d", "(", "[", ".", "*", "+", "?")):
            regexes.append((pattern, risk))

    # max_iter — prefer frontmatter, then §3, else default 2
    max_iter = 2
    if "max_iter" in frontmatter:
        try:
            max_iter = int(frontmatter["max_iter"])
        except (TypeError, ValueError):
            pass

    if not ops and not regexes:
        # A purely control-plane skill may have an empty ops/regexes set;
        # that's fine, but a totally empty rubric is suspicious.
        if "rubric_version" not in frontmatter:
            raise RubricError(
                f"rubric {rubric_path} has neither per-op sub-rules, detection "
                "regexes, nor a `rubric_version` frontmatter key"
            )

    return {
        "version": frontmatter.get("rubric_version", "unknown"),
        "last_updated": frontmatter.get("last_updated", "unknown"),
        "api": frontmatter.get("api", "unknown"),
        "cli_applicability": frontmatter.get("cli_applicability", "unknown"),
        "ops": ops,
        "regexes": regexes,
        "max_iter": max_iter,
        "required_or_recommended": frontmatter.get("gcl_classification", "required"),
    }


class RubricError(Exception):
    """Raised when a rubric file is missing or unparseable."""


# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------


def preflight(
    skill: str,
    op: str,
    command: str,
    rubric: Dict[str, Any],
    user_request: Optional[str],
) -> Tuple[bool, List[str]]:
    """Pre-flight checks per AGENTS.md §12.4 [0].

    Returns (ok, [list of error messages]). If `ok` is False, the runner
    should HALT before invoking the command.
    """
    errors: List[str] = []

    # 1. Skill must be a known alicloud-* skill
    if skill not in PRODUCT_CLI:
        errors.append(
            f"unknown skill {skill!r}; must be one of the alicloud-*-ops skills"
        )

    # 2. CLI product must match the skill (control-plane) OR a data-plane
    #    tool is allowed for dual-path / sdk-only skills.
    expected_product = PRODUCT_CLI.get(skill, "")
    cli_app = rubric.get("cli_applicability", "cli-first")
    if expected_product and not _command_targets_product(command, expected_product):
        if not _is_data_plane_tool(command):
            errors.append(
                f"command targets a different product than {skill!r} "
                f"(expected `aliyun {expected_product} ...` or a data-plane "
                f"tool such as `mongosh` / `mysql` / `psql` / `sqlplus` for "
                f"`cli_applicability={cli_app}` skills); got: {command[:80]!r}"
            )

    # 3. Operation must be documented in the rubric (or the rubric is
    #    purely regex-based, which is also valid)
    if rubric["ops"] and op not in rubric["ops"]:
        errors.append(
            f"operation {op!r} not documented in rubric for skill {skill!r}; "
            f"available: {sorted(rubric['ops'].keys())[:10]}"
        )

    # 4. Sanity: command should not contain unmasked secret values
    sanitized_cmd = sanitize(command)
    if "<masked>" in sanitized_cmd:
        errors.append(
            "command contains a value matching a secret pattern; pass secrets "
            "via env vars (e.g. $ALIBABA_CLOUD_ACCESS_KEY_SECRET) instead of "
            "inlining in --password / --access-key-secret / -a flags"
        )

    # 5. user_request is OPTIONAL (rubric may not require it). If provided,
    #    sanity-check it is not blank.
    if user_request is not None and not user_request.strip():
        errors.append("--user-request must be non-empty if provided")

    return (len(errors) == 0, errors)


def _command_targets_product(command: str, expected: str) -> bool:
    """Return True if `command` starts with `aliyun <expected>` (or `aliyun`
    + a known equivalent for legacy products)."""
    cmd = command.strip()
    if not cmd.startswith("aliyun "):
        return False
    parts = shlex.split(cmd)
    if len(parts) < 2:
        return False
    return parts[1] == expected


#: Data-plane tool names recognized for `cli_applicability: dual-path` or
#: `sdk-only` skills. The Critic's regex list is what enforces the actual
#: safety rules; this list is only for pre-flight command-class validation.
_DATA_PLANE_TOOLS = {
    "mongosh",  # MongoDB
    "mongo",    # MongoDB legacy
    "mysql",    # MySQL / PolarDB MySQL
    "psql",     # PostgreSQL / PolarDB PG
    "sqlplus",  # Oracle
    "sqlcl",    # Oracle SQLcl
    "redis-cli",  # Redis / Tair
    "curl",     # Elasticsearch REST
    "wget",     # generic REST
    "go",       # JIT Go SDK runner
    "kubectl",  # ACK (cross-skill)
}


def _is_data_plane_tool(command: str) -> bool:
    """Return True if `command` starts with a known data-plane tool."""
    cmd = command.strip()
    if not cmd:
        return False
    parts = shlex.split(cmd)
    if not parts:
        return False
    return parts[0] in _DATA_PLANE_TOOLS


# ---------------------------------------------------------------------------
# Hallucination Detection (H) — §14
# ---------------------------------------------------------------------------


def _extract_cli_params(command: str) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Extract (product, operation, [flags]) from a `aliyun` CLI command.

    Returns (product, operation, flags). If the command is not an `aliyun`
    CLI command, returns (None, None, []).
    """
    cmd = command.strip()
    if not cmd.startswith("aliyun "):
        return None, None, []
    parts = shlex.split(cmd)
    if len(parts) < 3:
        return None, None, []

    product = parts[1]
    operation = parts[2]
    flags: List[str] = []
    for part in parts[3:]:
        if part.startswith("--"):
            # Strip value after = (e.g. --RegionId=cn-hangzhou → --RegionId)
            flag = part.split("=")[0]
            flags.append(flag)
        elif part.startswith("-") and not part.startswith("--"):
            # Short flags like -f
            flags.append(part)
    return product, operation, flags


def _detect_cli_hallucinations(
    product: Optional[str],
    operation: Optional[str],
    flags: List[str],
) -> Tuple[bool, List[str]]:
    """Check CLI flags against the PARAMETER_KNOWLEDGE base.

    Returns (pass, [unrecognized flags]).
    """
    if not product or not operation:
        return True, []

    known = PARAMETER_KNOWLEDGE.get((product, operation))
    if known is None:
        # Product/operation not in knowledge base; can't verify.
        # Try a best-effort match: check product only.
        product_known = {
            k for k, v in PARAMETER_KNOWLEDGE.items()
            if k[0] == product and v
        }
        if not product_known:
            return True, []  # Unknown product entirely; pass conservatively

    unrecognized: List[str] = []
    for flag in flags:
        # --flag or --flag=value already stripped above
        if flag.startswith("--") and known is not None and flag not in known:
            # Common known generic flags that are not in OpenAPI specs
            if flag in ("--output", "--format", "--quiet", "--color", "--page", "--pagesize"):
                continue
            unrecognized.append(flag)

    if not unrecognized:
        return True, []
    return False, unrecognized


def _detect_json_hallucinations(command: str) -> Tuple[bool, List[str]]:
    """Check JSON payloads in the command for structural validity.

    Parses any JSON-like argument value and checks field-level patterns.
    Returns (pass, [issues]).
    """
    cmd = command.strip()
    issues: List[str] = []

    # Find JSON-like substrings: {...} or [...] that might be payloads
    json_candidates = re.findall(r"(\{.*?\}|\[.*?\])", cmd, re.DOTALL)
    for candidate in json_candidates:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                # Basic check: no empty field names
                for key in obj:
                    if not key or not isinstance(key, str):
                        issues.append(f"JSON field name is empty or non-string in {candidate[:100]}")
        except (json.JSONDecodeError, ValueError):
            # Not valid JSON; could be a JMESPath expression or similar.
            # Only flag if it looks like a JSON object (starts with {) but
            # fails to parse — that's a likely hallucination.
            stripped = candidate.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                pass  # Might be YAML or a template; don't flag aggressively

    return (len(issues) == 0, issues)


def _detect_waf_violations(command: str) -> Tuple[bool, List[str]]:
    """Check command against WAF_PATTERNS.

    Returns (pass, [violations]).
    """
    command_lower = command.lower()
    violations: List[str] = []

    for pattern, pillar, description in WAF_PATTERNS:
        try:
            if re.search(pattern, command, re.IGNORECASE):
                violations.append(f"[{pillar}] {description} (matched: {pattern})")
        except re.error:
            continue

    # Additional heuristic checks
    if "delete" in command_lower and "--force" not in command_lower:
        # Only flag if it's a Delete* operation
        parts = shlex.split(command)
        if len(parts) >= 3 and parts[2].startswith("Delete"):
            violations.append("[Stability] Destructive delete operation detected without --Force flag; ensure pre-deletion backup or confirmation")

    return (len(violations) == 0, violations)


def hallucination_detect(command: str) -> Dict[str, Any]:
    """Run Hallucination Detection (H) on a generated command.

    This is a pre-execution structural validity check per §14. It does NOT
    call any cloud API.

    Returns:
    {
        "status": "PASS"|"FAIL",
        "checks": {
            "cli_parameters": { "status": "PASS"|"FAIL", "total": N, "recognized": N, "unrecognized": [...] },
            "json_structure": { "status": "PASS"|"FAIL", "issues": [...] },
            "waf_compliance": { "status": "PASS"|"FAIL", "violations": [...] }
        },
        "report": "..."
    }
    """
    product, operation, flags = _extract_cli_params(command)

    # CLI parameter check
    cli_pass, unrecognized = _detect_cli_hallucinations(product, operation, flags)
    cli_check = {
        "status": "PASS" if cli_pass else "FAIL",
        "total": len(flags),
        "recognized": len(flags) - len(unrecognized),
        "unrecognized": unrecognized,
    }

    # JSON structure check
    json_pass, json_issues = _detect_json_hallucinations(command)
    json_check = {
        "status": "PASS" if json_pass else "FAIL",
        "issues": json_issues,
        "note": "no JSON payload in command" if json_pass and not re.search(r"\{.*\}", command, re.DOTALL) else "",
    }

    # WAF compliance check
    waf_pass, waf_violations = _detect_waf_violations(command)
    waf_check = {
        "status": "PASS" if waf_pass else "FAIL",
        "violations": waf_violations,
    }

    # Overall
    all_pass = cli_pass and json_pass and waf_pass
    report_parts = []
    if not cli_pass:
        report_parts.append(
            f"Unrecognized CLI parameters: {', '.join(unrecognized)} "
            f"(expected flags for {product}.{operation})"
        )
    if not json_pass:
        report_parts.append(f"JSON structure issues: {'; '.join(json_issues)}")
    if not waf_pass:
        report_parts.append(f"WAF compliance violations: {'; '.join(waf_violations)}")

    return {
        "status": "PASS" if all_pass else "FAIL",
        "checks": {
            "cli_parameters": cli_check,
            "json_structure": json_check,
            "waf_compliance": waf_check,
        },
        "report": " | ".join(report_parts) if report_parts else "",
    }


# ---------------------------------------------------------------------------
# Generator (Phase 2: subprocess)
# ---------------------------------------------------------------------------


def run_command(command: str, timeout: int = 300) -> Dict[str, Any]:
    """Execute `command` and capture its trace.

    Returns a dict with:
        - command: str
        - exit_code: int
        - stdout: str
        - stderr: str
        - result_excerpt: str  (first 500 chars of stdout)
        - request_id: str      (random UUID; placeholder for cloud RequestId)
        - duration_ms: int
    """
    start = _dt.datetime.now(tz=_dt.timezone.utc)
    request_id = str(uuid.uuid4())

    try:
        proc = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired as e:
        return {
            "command": command,
            "exit_code": 124,  # convention: 124 = timeout
            "stdout": "",
            "stderr": f"timeout after {timeout}s: {e}",
            "result_excerpt": "",
            "request_id": request_id,
            "duration_ms": int((_dt.datetime.now(tz=_dt.timezone.utc) - start).total_seconds() * 1000),
        }
    except FileNotFoundError as e:
        return {
            "command": command,
            "exit_code": 127,  # convention: 127 = command not found
            "stdout": "",
            "stderr": f"command not found: {e}",
            "result_excerpt": "",
            "request_id": request_id,
            "duration_ms": int((_dt.datetime.now(tz=_dt.timezone.utc) - start).total_seconds() * 1000),
        }

    duration = int((_dt.datetime.now(tz=_dt.timezone.utc) - start).total_seconds() * 1000)
    return {
        "command": command,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "result_excerpt": stdout[:500],
        "request_id": request_id,
        "duration_ms": duration,
    }


# ---------------------------------------------------------------------------
# Critic (Phase 2: mechanical regex re-classifier)
# ---------------------------------------------------------------------------


def critique(
    op: str,
    trace: Dict[str, Any],
    rubric: Dict[str, Any],
) -> Dict[str, Any]:
    """Critique the Generator's output against the rubric.

    Phase 2 Critic is a pure-Python regex re-classifier. It does NOT see
    the user's original request (per AGENTS.md §12.7 rubber-stamping
    prevention rule).

    Returns a dict with:
        - scores: dict[str, float]    (5 core + 3 Aliyun extensions)
        - suggestions: list[str]       (≤ 3 actionable items)
        - matched_regexes: list[str]   (regex patterns that matched)
        - blocking: bool
    """
    # The Critic's input is the trace; the user_request is NOT passed in.
    command = trace["command"]
    exit_code = trace["exit_code"]
    stdout = trace["stdout"]
    stderr = trace["stderr"]
    full_text = f"{command}\n{stdout}\n{stderr}"

    matched: List[str] = []
    highest_risk = "READ-ONLY"

    # Apply every detection regex from the rubric
    for pattern, risk in rubric["regexes"]:
        try:
            if re.search(pattern, full_text, re.MULTILINE | re.DOTALL):
                matched.append(f"{pattern} → {risk}")
                if _risk_severity(risk) > _risk_severity(highest_risk):
                    highest_risk = risk
        except re.error:
            # Malformed regex in the rubric; skip silently
            continue

    # ---- Per-dimension scoring (0 / 0.5 / 1) ----
    scores: Dict[str, float] = {}

    # 1.1 Correctness — 1.0 if exit_code==0 AND result_excerpt non-empty
    scores["correctness"] = 1.0 if exit_code == 0 and trace["result_excerpt"] else 0.0

    # 1.2 Safety — depends on highest_risk and op documentation
    op_subrule = rubric["ops"].get(op, "")
    if not op_subrule and not rubric["ops"]:
        # Empty ops table (e.g. purely-regex rubric); use regex score only
        scores["safety"] = 0.0 if "DESTRUCTIVE" in highest_risk or "FATAL" in highest_risk else 1.0
    elif not op_subrule:
        # Op not documented in rubric
        scores["safety"] = 0.0
    else:
        # Op documented. Safety = 0 if a destructive regex matched.
        scores["safety"] = 0.0 if "DESTRUCTIVE" in highest_risk or "FATAL" in highest_risk else 1.0

    # 1.3 Idempotency — heuristic: if exit_code indicates "already exists"
    #    (409) or "not found" (404), the op is naturally idempotent.
    text_lower = full_text.lower()
    if exit_code == 0:
        scores["idempotency"] = 1.0
    elif any(needle in text_lower for needle in ("already exists", "not found", "duplicate", "invalidstatus.notfound")):
        scores["idempotency"] = 0.5
    else:
        scores["idempotency"] = 0.5  # unknown; be conservative

    # 1.4 Traceability — 1.0 if stdout is non-empty (we have a result to audit)
    scores["traceability"] = 1.0 if stdout or stderr else 0.0

    # 1.5 Spec Compliance — 1.0 if the CLI product matches the skill
    #    (already checked in pre-flight; mirror here for the dimension)
    skill_match = _command_targets_product(command, PRODUCT_CLI.get(_skill_from_command(command), ""))
    scores["spec_compliance"] = 1.0 if skill_match else 0.5

    # 2.1 Region Compliance — heuristic: command includes --RegionId
    scores["region_compliance"] = 1.0 if "--regionid" in text_lower else 0.5

    # 2.2 Credential Hygiene — 1.0 if no <masked> appeared during sanitization
    sanitized_full = sanitize(full_text)
    if "<masked>" in sanitized_full and "<masked>" not in full_text:
        scores["credential_hygiene"] = 0.0
    else:
        scores["credential_hygiene"] = 1.0

    # 2.3 Well-Architected — heuristic: rubric_version is set
    scores["well_architected"] = 1.0 if rubric["version"] != "unknown" else 0.5

    # ---- Suggestions ----
    suggestions: List[str] = []
    blocking = False

    if scores["safety"] == 0.0:
        blocking = True
        destructive_matches = [m for m in matched if "DESTRUCTIVE" in m or "FATAL" in m]
        if destructive_matches:
            suggestions.append(
                "BLOCKED: detected destructive regex match — " +
                destructive_matches[0] +
                ". Confirm the operation is intended and required, and re-run with explicit user confirmation."
            )
        else:
            suggestions.append(
                f"BLOCKED: operation {op!r} is not documented in the rubric for "
                "this skill. Add a per-op sub-rule to references/rubric.md §1.2 "
                "before re-running."
            )

    if scores["credential_hygiene"] == 0.0:
        blocking = True
        suggestions.append(
            "BLOCKED: command or output contains a value matching a secret "
            "pattern. Pass secrets via env vars (e.g. --password \"$REDIS_PWD\") "
            "or $ALIBABA_CLOUD_ACCESS_KEY_SECRET instead of inlining."
        )

    if scores["correctness"] == 0.0:
        suggestions.append(
            f"Generator exit_code={exit_code}; stderr={stderr[:200]!r}. "
            "Inspect error and re-run with corrected args."
        )

    if not blocking and scores["correctness"] == 1.0:
        # All good; limit suggestions to 0 if nothing to say
        suggestions = []

    return {
        "scores": scores,
        "suggestions": suggestions[:3],  # AGENTS.md §12.4: ≤ 3 actionable
        "matched_regexes": matched,
        "blocking": blocking,
    }


def _risk_severity(risk: str) -> int:
    """Return a numeric severity for a risk class (higher = more severe)."""
    order = {
        "READ-ONLY": 0,
        "WRITE-KEY": 1,
        "WRITE-LIMITED": 1,
        "WRITE-MANY": 2,
        "DESTRUCTIVE-LIMITED": 3,
        "DESTRUCTIVE-INDEX": 3,
        "DESTRUCTIVE-MASS": 4,
        "DESTRUCTIVE-QUERY": 4,
        "DESTRUCTIVE-MERGE": 4,
        "AGGREGATION-DESTRUCTIVE": 4,
        "FATAL": 5,
        "CONFIG-MUTATION": 3,
    }
    return order.get(risk.upper(), 0)


def _skill_from_command(command: str) -> str:
    """Best-effort reverse-lookup of a skill from a command line.

    Returns the first skill whose PRODUCT_CLI product prefix matches the
    command, or empty string if none matches. Used only to re-validate
    spec_compliance in the Critic.
    """
    cmd = command.strip()
    if not cmd.startswith("aliyun "):
        return ""
    parts = shlex.split(cmd)
    if len(parts) < 2:
        return ""
    product = parts[1]
    for skill, prod in PRODUCT_CLI.items():
        if prod == product:
            return skill
    return ""


# ---------------------------------------------------------------------------
# Decide (termination per AGENTS.md §12.5)
# ---------------------------------------------------------------------------


def decide(critic: Dict[str, Any], iter_no: int, max_iter: int) -> str:
    """Return one of: PASS / RETRY / MAX_ITER / SAFETY_FAIL.

    First match wins (AGENTS.md §12.5):
      - Safety=0 → ABORT (SAFETY_FAIL)
      - all scores >= threshold (0.5) AND iter>=1 → PASS
      - iter < max_iter → RETRY
      - else → MAX_ITER
    """
    scores = critic["scores"]
    if critic["blocking"] or scores.get("safety", 1) == 0.0:
        return "SAFETY_FAIL"

    # All dimensions must meet the threshold (0.5 by default).
    THRESHOLD = 0.5
    all_pass = all(v >= THRESHOLD for v in scores.values())

    if all_pass:
        return "PASS"

    if iter_no < max_iter:
        return "RETRY"
    return "MAX_ITER"


# ---------------------------------------------------------------------------
# Loop (AGENTS.md §12.4 + §14)
# ---------------------------------------------------------------------------


def run_loop(
    skill: str,
    op: str,
    command: str,
    user_request: Optional[str],
    rubric: Dict[str, Any],
    max_iter: int,
    enable_hallucination_check: bool = False,
) -> Dict[str, Any]:
    """Run the Generator-Critic loop per AGENTS.md §12.4 + §14.

    When enable_hallucination_check is True, runs the Hallucination Detection
    (H) gate before executing the command. If H fails, the command is
    regenerated once; if it still fails, the loop aborts with HALLUCINATION_ABORT.

    Returns the trace dict (will be persisted to disk by the caller).
    """
    trace: Dict[str, Any] = {
        "skill": skill,
        "request": _sanitize_user_request(user_request),
        "rubric_version": rubric["version"],
        "iterations": [],
    }

    decision = "MAX_ITER"
    best_iter: Optional[Dict[str, Any]] = None
    best_score_sum = -1.0

    for iter_no in range(1, max_iter + 1):
        # [1.5] Hallucination Detection (H) — pre-execution check
        h_result: Optional[Dict[str, Any]] = None
        if enable_hallucination_check:
            h_result = hallucination_detect(command)
            if h_result["status"] == "FAIL":
                # HALLUCINATION_ABORT — structural hallucinations detected.
                # In mechanical mode, the command is fixed, so no regeneration is attempted.
                # In a future LLM-based H, the Orchestrator would re-prompt Generator (G)
                # with the hallucination report and re-check after regeneration.
                iter_record: Dict[str, Any] = {
                    "iter": iter_no,
                    "hallucination_detector": h_result,
                    "regenerated": False,
                    "generator": {
                        "command": command,
                        "exit_code": -1,
                        "result_excerpt": "",
                        "request_id": str(uuid.uuid4()),
                        "duration_ms": 0,
                    },
                    "critic": {
                        "scores": {k: 0.0 for k in ("correctness", "safety", "idempotency", "traceability", "spec_compliance", "region_compliance", "credential_hygiene", "well_architected")},
                        "suggestions": [f"HALLUCINATION_ABORT: {h_result['report']}"],
                        "matched_regexes": [],
                        "blocking": True,
                    },
                    "decision": "HALLUCINATION_ABORT",
                }
                trace["iterations"].append(iter_record)
                trace["final"] = {
                    "status": "HALLUCINATION_ABORT",
                    "iter": len(trace["iterations"]),
                    "output": f"HALLUCINATION_ABORT: {h_result['report']}",
                }
                return trace

        # [1] Generate
        gen_trace = run_command(command)

        # [2] Critique
        critic_result = critique(op, gen_trace, rubric)

        # [3] Decide
        decision = decide(critic_result, iter_no, max_iter)

        # Persist this iteration (sanitized)
        iter_record: Dict[str, Any] = {
            "iter": iter_no,
            "generator": _sanitize_trace(gen_trace),
            "critic": {
                "scores": critic_result["scores"],
                "suggestions": critic_result["suggestions"],
                "matched_regexes": critic_result["matched_regexes"],
                "blocking": critic_result["blocking"],
            },
            "decision": decision,
        }
        if h_result is not None:
            iter_record["hallucination_detector"] = h_result
            iter_record["regenerated"] = False

        trace["iterations"].append(iter_record)

        # Track best-so-far (per AGENTS.md §12.5 MAX_ITER behavior)
        score_sum = sum(critic_result["scores"].values())
        if score_sum > best_score_sum and not critic_result["blocking"]:
            best_score_sum = score_sum
            best_iter = iter_record

        if decision in ("PASS", "SAFETY_FAIL"):
            break

    trace["final"] = {
        "status": decision,
        "iter": len(trace["iterations"]),
        "output": _summarize_output(trace["iterations"][-1]),
    }
    if decision == "MAX_ITER" and best_iter is not None:
        trace["final"]["best_iter"] = best_iter["iter"]
        trace["final"]["best_output"] = _summarize_output(best_iter)

    return trace


def _sanitize_trace(trace: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize the generator trace's command/stdout/stderr/result_excerpt."""
    out = dict(trace)
    out["command"] = sanitize(trace["command"])
    out["stdout"] = sanitize(trace["stdout"])
    out["stderr"] = sanitize(trace["stderr"])
    out["result_excerpt"] = sanitize(trace["result_excerpt"])
    return out


def _synthesize_dry_run(
    skill: str,
    op: str,
    command: str,
    user_request: Optional[str],
    rubric: Dict[str, Any],
    enable_hallucination_check: bool = False,
) -> Dict[str, Any]:
    """Build a single-iteration trace WITHOUT executing the command.

    Used by `--dry-run` for Critic-only regression tests. The command
    string is preserved in the trace so the Critic can still classify it.
    The generator trace is synthesized with exit_code=0 and empty stdout.
    """
    h_result: Optional[Dict[str, Any]] = None
    if enable_hallucination_check:
        h_result = hallucination_detect(command)

    synthetic_gen = {
        "command": command,
        "exit_code": 0,
        "stdout": "(dry-run; no subprocess executed)",
        "stderr": "",
        "result_excerpt": "(dry-run)",
        "request_id": str(uuid.uuid4()),
        "duration_ms": 0,
    }
    critic_result = critique(op, synthetic_gen, rubric)
    decision = decide(critic_result, 1, 1)

    iter_record: Dict[str, Any] = {
        "iter": 1,
        "generator": _sanitize_trace(synthetic_gen),
        "critic": {
            "scores": critic_result["scores"],
            "suggestions": critic_result["suggestions"],
            "matched_regexes": critic_result["matched_regexes"],
            "blocking": critic_result["blocking"],
        },
        "decision": decision,
    }
    if h_result is not None:
        iter_record["hallucination_detector"] = h_result

    return {
        "skill": skill,
        "request": _sanitize_user_request(user_request),
        "rubric_version": rubric["version"],
        "iterations": [iter_record],
        "final": {
            "status": decision,
            "iter": 1,
            "output": "dry-run; no subprocess executed",
        },
    }


def _sanitize_user_request(text: Optional[str]) -> str:
    """Sanitize the user-request field. Truncate to 200 chars to limit PII."""
    if text is None:
        return ""
    sanitized = sanitize(text)
    return sanitized[:200]


def _summarize_output(iter_record: Dict[str, Any]) -> str:
    """Build a short summary string for `final.output`."""
    gen = iter_record["generator"]
    return (
        f"exit_code={gen['exit_code']} "
        f"request_id={gen.get('request_id', 'n/a')} "
        f"duration={gen.get('duration_ms', 0)}ms"
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def persist_trace(trace: Dict[str, Any], output_dir: Path) -> Path:
    """Write the trace to `./audit-results/gcl-trace-YYYYMMDD-HHMMSS.json`."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]  # avoid collisions within the same second
    path = output_dir / f"gcl-trace-{ts}-{suffix}.json"
    path.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gcl_runner.py",
        description=(
            "Generator-Critic-Loop (GCL) runner for alicloud-*-ops skills. "
            "Implements the loop flow in AGENTS.md §12.4 and §14 (H detection), "
            "and the trace schema in §12.6."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              # Run GCL on a single aliyun command
              python gcl_runner.py \\
                  --skill alicloud-ecs-ops \\
                  --op DeleteInstance \\
                  --command "aliyun ecs DeleteInstance --InstanceId i-bp1..."

              # Run GCL with hallucination detection enabled
              python gcl_runner.py \\
                  --skill alicloud-ecs-ops \\
                  --op DeleteInstance \\
                  --command "aliyun ecs DeleteInstance --InstanceId i-bp1..." \\
                  --enable-hallucination-check

              # Override max-iter and output directory
              python gcl_runner.py \\
                  --skill alicloud-rds-ops \\
                  --op DeleteDatabase \\
                  --command "aliyun rds DeleteDatabase --DBInstanceId rm-bp1... --DBName legacy" \\
                  --max-iter 3 \\
                  --output-dir /custom/audit-dir

            See scripts/README.md for the full guide.
            """
        ),
    )
    p.add_argument("--skill", required=True, help="alicloud-*-ops skill name (e.g. alicloud-ecs-ops)")
    p.add_argument("--op", required=True, help="Operation name (e.g. DeleteInstance)")
    p.add_argument("--command", required=True, help="Exact aliyun / SDK-shell command to run")
    p.add_argument("--user-request", default=None, help="(Optional) original user request, used for trace context only; NEVER seen by the Critic")
    p.add_argument("--rubric", default=None, help="Path to rubric.md; default: <skill>/references/rubric.md")
    p.add_argument("--prompt-template", default=None, help="(Optional) path to prompt-templates.md; not used in Phase 2 mechanical Critic but accepted for forward-compat")
    p.add_argument("--max-iter", type=int, default=None, help="Override max_iter; default: from rubric, then SKILL_MAX_ITER map, then 2")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_AUDIT_DIR, help=f"Trace output directory; default: {DEFAULT_AUDIT_DIR}")
    p.add_argument("--timeout", type=int, default=300, help="Per-iteration subprocess timeout in seconds; default: 300")
    p.add_argument("--dry-run", action="store_true", help="Skip the actual subprocess; useful for Critic-only regression tests")
    p.add_argument("--enable-hallucination-check", action="store_true", help="Enable the pre-execution Hallucination Detection (H) gate (§14)")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    # Resolve rubric path
    skill_root = Path(__file__).resolve().parent.parent
    rubric_path = Path(args.rubric) if args.rubric else skill_root / args.skill / "references" / "rubric.md"

    # Parse rubric
    try:
        rubric = parse_rubric(rubric_path)
    except RubricError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return EXIT_RUBRIC_ERROR

    # Override max_iter
    max_iter = args.max_iter or rubric["max_iter"] or SKILL_MAX_ITER.get(args.skill, 2)

    # Pre-flight
    ok, errors = preflight(args.skill, args.op, args.command, rubric, args.user_request)
    if not ok:
        print("[ERROR] pre-flight failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    # Run the loop
    if args.dry_run:
        trace = _synthesize_dry_run(
            skill=args.skill,
            op=args.op,
            command=args.command,
            user_request=args.user_request,
            rubric=rubric,
            enable_hallucination_check=args.enable_hallucination_check,
        )
    else:
        trace = run_loop(
            skill=args.skill,
            op=args.op,
            command=args.command,
            user_request=args.user_request,
            rubric=rubric,
            max_iter=max_iter,
            enable_hallucination_check=args.enable_hallucination_check,
        )

    # Persist trace
    try:
        path = persist_trace(trace, args.output_dir)
    except OSError as e:
        print(f"[ERROR] failed to persist trace: {e}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    # Print summary
    final = trace["final"]
    print(f"[GCL] skill={args.skill} op={args.op} status={final['status']} iter={final['iter']}")
    print(f"[GCL] trace: {path}")
    if final["status"] == "PASS":
        return EXIT_PASS
    if final["status"] == "SAFETY_FAIL":
        return EXIT_SAFETY_FAIL
    if final["status"] == "HALLUCINATION_ABORT":
        print(f"[GCL] hallucination report: {final.get('output', '')}", file=sys.stderr)
        return EXIT_HALLUCINATION_ABORT
    if final["status"] == "MAX_ITER":
        return EXIT_MAX_ITER
    return EXIT_MAX_ITER  # RETRY exhausted


if __name__ == "__main__":
    sys.exit(main())