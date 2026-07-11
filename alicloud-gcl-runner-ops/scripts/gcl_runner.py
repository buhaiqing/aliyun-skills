#!/usr/bin/env python3
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

The default Critic (Phase 2) is a **mechanical re-classifier** (pure Python regex),
not an LLM call. This makes the runner deterministic, CI-friendly, and
reproducible. The rubric's regex list IS the Critic's score function —
matches the AGENTS.md §12.7 "Critic must hide the raw user request" rule
because the Critic never sees `--user-request`.

Phase 3-A adds optional **LLM-based Critic** via configurable OpenAI-compatible
endpoint: set `GCL_CRITIC_MODE=llm|hybrid` and `GCL_CRITIC_LLM_ENDPOINT` + API key.
Hybrid mode uses mechanical for hard safety gates (safety/credentials/wrapper)
and LLM for nuanced scoring; this is the recommended production config when
LLM is enabled.

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
    6  WRAPPER_BYPASS       — direct aliyun call when skillopt wrapper is required (AGENTS.md §15.8)

REQUIREMENTS
------------
    Python 3.10+ stdlib only. No external dependencies.

SMART ALERT LOOP INTEGRATION
----------------------------
    When --adaptive is enabled, the runner consults the smart alarm engine's
    degradation state to dynamically adjust max_iter for high-risk resources.
    See gcl_smart_alarm_engine.py for pattern detection and auto-degradation.

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
from typing import Any

# gcl_memory import (Layer 1 — non‑fatal)
try:
    from gcl_memory import memory_purge_unknown, memory_store
except ImportError:
    def memory_store(*args: Any, **kwargs: Any) -> int:  # type: ignore[misc]
        return 0

    def memory_purge_unknown(*args: Any, **kwargs: Any) -> dict:  # type: ignore[misc]
        return {"files_removed": 0, "dirs_cleaned": 0, "applied": False}

# gcl_reflexion import (Layer 2 — non‑fatal)
try:
    from gcl_reflexion import (
        compute_command_hash,
        normalize_skill_name,
        reflexion_extract,
        reflexion_report,
        reflexion_store,
        remediation_apply_from_trace,
        success_report,
        success_store,
    )
except ImportError:
    def reflexion_store(*args: Any, **kwargs: Any) -> int:  # type: ignore[misc]
        return 0
    def reflexion_extract(*args: Any, **kwargs: Any) -> dict | None:  # type: ignore[misc]
        return None
    def reflexion_report(*args: Any, **kwargs: Any) -> int:  # type: ignore[misc]
        return 0
    def success_store(*args: Any, **kwargs: Any) -> int:  # type: ignore[misc]
        return 0
    def success_report(*args: Any, **kwargs: Any) -> int:  # type: ignore[misc]
        return 0
    def remediation_apply_from_trace(*args: Any, **kwargs: Any) -> dict:  # type: ignore[misc]
        return {}
    def compute_command_hash(command: str) -> str:  # type: ignore[misc]
        return "sha256:unavailable"
    def normalize_skill_name(skill: str) -> str:  # type: ignore[misc]
        return skill

# R2 memory preflight (Layers 1–3 — non-fatal)
try:
    from memory_preflight import preflight_retrieve
except ImportError:
    def preflight_retrieve(*args: Any, **kwargs: Any) -> dict[str, Any]:  # type: ignore[misc]
        return {
            "empty": True,
            "slots": {},
            "recent_executions": [],
            "known_traps": [],
            "success_patterns": [],
            "strategy_hints": {},
        }

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_git_head() -> str:
    """Return the current git HEAD commit hash, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()[:40]
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_PREFIX = "[GCL-RUNNER]"

def _log(msg: str, *args: Any, **kw: Any) -> None:
    """Emit structured log for AI agent consumption.

    Format: ``[HH:MM:SS] [GCL-RUNNER] key=value [key=value] message``

    All values use ``key=value`` pairs so an AI parsing the log can
    extract structured fields without regex.
    """
    ts = _dt.datetime.now(_dt.timezone.utc).strftime("%H:%M:%S")
    formatted = msg.format(*args, **kw) if args or kw else msg
    print(f"[{ts}] {LOG_PREFIX} {formatted}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default directory for trace persistence (gitignored per AGENTS.md §12.6).
#: Sprint 19: 改用 RUNTIME_ROOT/audit/gcl-runner-ops/
def _resolve_default_audit_dir() -> Path:
    """Sprint 19: 从 RUNTIME_ROOT 解析默认 audit 目录, 不可用则 fallback."""
    env_root = os.environ.get("ALIYUN_SKILLS_RUNTIME_ROOT")
    if env_root:
        return Path(env_root) / "audit" / "gcl-runner-ops"
    # fallback: 推断 aliyun-skills/.runtime/audit/gcl-runner-ops
    _script = Path(__file__).resolve().parent
    _skills = _script.parent.parent
    return _skills / ".runtime" / "audit" / "gcl-runner-ops"

DEFAULT_AUDIT_DIR = _resolve_default_audit_dir()


def resolve_skills_root() -> Path:
    """Repository root containing ``alicloud-*-ops`` skill directories."""
    env_root = os.environ.get("ALIYUN_SKILLS_ROOT")
    if env_root:
        return Path(env_root)
    # .../alicloud-gcl-runner-ops/scripts/gcl_runner.py → repo root is parent³
    candidate = Path(__file__).resolve().parent.parent.parent
    if (candidate / "alicloud-gcl-runner-ops" / "scripts" / "gcl_runner.py").is_file():
        return candidate
    # Legacy fallback: rubric colocated under a single skill tree
    return Path(__file__).resolve().parent.parent

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
    "alicloud-slb-ops": "slb",
    "alicloud-ack-ops": "cs",  # ACK = Container Service
    "alicloud-ask-ops": "cs",
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
    "alicloud-dts-ops": 2,
    "alicloud-waf-ops": 2,
    "alicloud-sls-ops": 2,
    "alicloud-terraform-ops": 2,
    # recommended (max_iter=3)
    "alicloud-slb-ops": 3,
    "alicloud-ack-ops": 3,
    "alicloud-ask-ops": 3,
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
PARAMETER_KNOWLEDGE: dict[tuple[str, str], set] = {
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
WAF_PATTERNS: list[tuple[str, str, str]] = [
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
SECRET_PATTERNS: list[tuple[str, str, str]] = [
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
EXIT_WRAPPER_BYPASS = 6  # AGENTS.md §15.8 — direct aliyun call when wrapper required


# ---------------------------------------------------------------------------
# Smart Alert Loop — Adaptive max_iter (Phase 7)
# ---------------------------------------------------------------------------

#: Resource ID extraction patterns for adaptive degradation.
#: Maps skill name to regex pattern for extracting resource identifier.
RESOURCE_ID_PATTERNS: dict[str, str] = {
    "alicloud-ecs-ops": r"--InstanceId\s+['\"]?(i-[a-z0-9]+)['\"]?",
    "alicloud-rds-ops": r"--DBInstanceId\s+['\"]?(rm-[a-z0-9]+)['\"]?",
    "alicloud-redis-ops": r"--InstanceId\s+['\"]?(r-[a-z0-9]+)['\"]?",
    "alicloud-mongodb-ops": r"--DBInstanceId\s+['\"]?(dds-[a-z0-9]+)['\"]?",
    "alicloud-polar-mysql-ops": r"--DBClusterId\s+['\"]?(pc-[a-z0-9]+)['\"]?",
    "alicloud-polar-postgresql-ops": r"--DBClusterId\s+['\"]?(pc-[a-z0-9]+)['\"]?",
    "alicloud-polar-oracle-ops": r"--DBClusterId\s+['\"]?(pc-[a-z0-9]+)['\"]?",
    "alicloud-elasticsearch-ops": r"--InstanceId\s+['\"]?(es-[a-z0-9]+)['\"]?",
    "alicloud-vpc-ops": r"--VpcId\s+['\"]?(vpc-[a-z0-9]+)['\"]?",
    "alicloud-nat-ops": r"--NatGatewayId\s+['\"]?(ngw-[a-z0-9]+)['\"]?",
    "alicloud-eip-ops": r"--AllocationId\s+['\"]?(eip-[a-z0-9]+)['\"]?",
    "alicloud-slb-ops": r"--LoadBalancerId\s+['\"]?(lb-[a-z0-9]+)['\"]?",
    "alicloud-ack-ops": r"--ClusterId\s+['\"]?(c-[a-z0-9]+)['\"]?",
    "alicloud-fc-ops": r"--serviceName\s+['\"]?([^\s'\"]+)['\"]?",
    "alicloud-kms-ops": r"--KeyId\s+['\"]?(key-[a-z0-9]+)['\"]?",
    "alicloud-ram-ops": r"--UserName\s+['\"]?([^\s'\"]+)['\"]?",
    "alicloud-sls-ops": r"--project\s+['\"]?([^\s'\"]+)['\"]?",
}


def _get_degradation_state_path() -> Path:
    """Resolve path to the smart alarm engine's degradation state file."""
    env_root = os.environ.get("ALIYUN_SKILLS_RUNTIME_ROOT")
    if env_root:
        return Path(env_root) / "gcl-degradation-state.json"
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent / ".runtime" / "gcl-degradation-state.json"


def _load_degradation_state() -> dict[str, Any]:
    """Load degradation state from smart alarm engine."""
    path = _get_degradation_state_path()
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"downgraded_resources": {}}


def _extract_resource_id(skill: str, command: str) -> str | None:
    """Extract resource identifier from command for adaptive lookup."""
    pattern = RESOURCE_ID_PATTERNS.get(skill)
    if not pattern:
        return None
    m = re.search(pattern, command)
    return m.group(1) if m else None


def get_adaptive_max_iter(skill: str, command: str, base_max_iter: int) -> tuple[int, str | None]:
    """
    Determine max_iter using smart alarm engine's degradation state.

    Returns (effective_max_iter, degradation_reason).
    If the resource is downgraded, returns the reduced max_iter and reason.
    Otherwise returns base_max_iter and None.
    """
    resource_id = _extract_resource_id(skill, command)
    if not resource_id:
        return base_max_iter, None

    state = _load_degradation_state()
    downgraded = state.get("downgraded_resources", {})

    if resource_id in downgraded:
        info = downgraded[resource_id]
        current = info.get("current_max_iter", base_max_iter)
        reason = (
            f"Resource {resource_id} downgraded due to {info.get('reason', 'unknown')} "
            f"(restore at {info.get('auto_restore_at', 'unknown')})"
        )
        return current, reason

    return base_max_iter, None


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


def parse_rubric(rubric_path: Path) -> dict[str, Any]:
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
    frontmatter: dict[str, str] = {}
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
    ops: dict[str, str] = {}
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
    regexes: list[tuple[str, str]] = []
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
    rubric: dict[str, Any],
    user_request: str | None,
) -> tuple[bool, list[str]]:
    """Pre-flight checks per AGENTS.md §12.4 [0].

    Returns (ok, [list of error messages]). If `ok` is False, the runner
    should HALT before invoking the command.
    """
    errors: list[str] = []

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
    + a known equivalent for legacy products). Also accepts commands routed
    through a `*skillopt-wrapper.sh` that ultimately call `aliyun <expected>`.
    """
    cmd = command.strip()
    parts = shlex.split(cmd)
    # Strip wrapper prefix tokens so the aliyun/product/operation indices align.
    while parts and "skillopt-wrapper.sh" in parts[0]:
        parts = parts[1:]
    if not parts or parts[0] != "aliyun":
        return False
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


def _extract_cli_params(command: str) -> tuple[str | None, str | None, list[str]]:
    """Extract (product, operation, [flags]) from a `aliyun` CLI command.

    Returns (product, operation, flags). If the command is not an `aliyun`
    CLI command, returns (None, None, []).
    """
    cmd = command.strip()
    parts = shlex.split(cmd)
    # If the command is routed through a skillopt wrapper, skip the wrapper
    # path token(s) so the aliyun/product/operation indices line up.
    while parts and "skillopt-wrapper.sh" in parts[0]:
        parts = parts[1:]
    if not parts or not parts[0] == "aliyun":
        return None, None, []
    if len(parts) < 3:
        return None, None, []

    product = parts[1]
    operation = parts[2]
    flags: list[str] = []
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
    product: str | None,
    operation: str | None,
    flags: list[str],
) -> tuple[bool, list[str]]:
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

    unrecognized: list[str] = []
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


def _detect_json_hallucinations(command: str) -> tuple[bool, list[str]]:
    """Check JSON payloads in the command for structural validity.

    Parses any JSON-like argument value and checks field-level patterns.
    Returns (pass, [issues]).
    """
    cmd = command.strip()
    issues: list[str] = []

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


def _detect_waf_violations(command: str) -> tuple[bool, list[str]]:
    """Check command against WAF_PATTERNS.

    Returns (pass, [violations]).
    """
    command_lower = command.lower()
    violations: list[str] = []

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


# ---------------------------------------------------------------------------
# Wrapper Compliance (AGENTS.md §15.8 + GCL §3, §9, §14.2.4)
# ---------------------------------------------------------------------------

# Skills that have a SkillOpt wrapper script (per AGENTS.md §15.5 list).
# When a command targets one of these skills' products AND its wrapper exists,
# the command MUST be routed through the wrapper — not bare `aliyun <product>`.
SKILLS_WITH_WRAPPERS: set = {
    "alicloud-ecs-ops", "alicloud-redis-ops", "alicloud-rds-ops",
    "alicloud-ram-ops", "alicloud-kms-ops", "alicloud-eip-ops",
    "alicloud-vpc-ops", "alicloud-nat-ops", "alicloud-mongodb-ops",
    "alicloud-elasticsearch-ops", "alicloud-polar-mysql-ops",
    "alicloud-polar-postgresql-ops", "alicloud-polar-oracle-ops",
    "alicloud-slb-ops", "alicloud-ack-ops", "alicloud-ask-ops",
    "alicloud-fc-ops", "alicloud-eci-ops", "alicloud-cms-ops",
    "alicloud-waf-ops", "alicloud-sls-ops", "alicloud-dts-ops",
    "alicloud-terraform-ops", "alicloud-resourcemanager-ops",
    "alicloud-agentrun-ops", "alicloud-oss-ops",
}


def classify_execution_path(command: str) -> dict[str, Any]:
    """Classify how a command was routed to `aliyun`.

    Per AGENTS.md §15.8 (Wrapper-First Execution Rule), every aliyun CLI
    invocation against a skill with a SkillOpt wrapper MUST go through
    that wrapper. Direct `aliyun <product>` calls are a silent bypass
    and lose self-repair / Langfuse tracing / circuit-breaker protection.

    Returns:
        {
          "path": "wrapper" | "direct_aliyun" | "sdk_jit" | "data_plane" | "other",
          "wrapper_detected": Optional[str],   # path to wrapper if wrapper path
          "skill": Optional[str],               # skill name inferred from product
          "wrapper_should_be_used": bool,       # True if skill has a wrapper
          "violation": bool                     # True if bypass detected
        }
    """
    cmd = command.strip()
    if not cmd:
        return {"path": "other", "wrapper_detected": None, "skill": None,
                "wrapper_should_be_used": False, "violation": False}

    # 1. Wrapper path — command starts with (sources/).../scripts/*-skillopt-wrapper.sh
    #    OR explicitly invokes skillopt_wrap. The wrapper always passes its
    #    product prefix as $1, so we detect by looking for a *-skillopt-wrapper.sh
    #    prefix in the command string.
    if re.search(r"skillopt-wrapper\.sh", cmd):
        return {"path": "wrapper", "wrapper_detected": "inferred_from_command",
                "skill": None, "wrapper_should_be_used": True, "violation": False}

    # 2. Direct `aliyun <product>` call
    if cmd.startswith("aliyun "):
        parts = shlex.split(cmd)
        if len(parts) >= 2:
            product = parts[1]
            # Reverse-lookup skill from product prefix
            skill = _skill_from_command(cmd)
            should_use_wrapper = skill in SKILLS_WITH_WRAPPERS
            return {
                "path": "direct_aliyun",
                "wrapper_detected": None,
                "skill": skill or product,
                "wrapper_should_be_used": should_use_wrapper,
                "violation": should_use_wrapper,  # bypass = violation
            }

    # 3. SDK / JIT Go script
    if cmd.startswith(("go run", "go-script", "./")) or re.search(r"\.go\b", cmd):
        return {"path": "sdk_jit", "wrapper_detected": None, "skill": None,
                "wrapper_should_be_used": False, "violation": False}

    # 4. Data-plane tools (redis-cli, mongosh, etc.) — wrapper doesn't apply
    if _is_data_plane_tool(cmd):
        return {"path": "data_plane", "wrapper_detected": None, "skill": None,
                "wrapper_should_be_used": False, "violation": False}

    # 5. Anything else (curl, custom scripts, etc.)
    return {"path": "other", "wrapper_detected": None, "skill": None,
            "wrapper_should_be_used": False, "violation": False}


def _detect_wrapper_bypass(command: str) -> tuple[bool, list[str]]:
    """Check whether a command bypassed its skill's SkillOpt wrapper.

    Per AGENTS.md §15.8, calling `aliyun <product>` directly when a
    `scripts/*-skillopt-wrapper.sh` exists is a silent bypass. This
    strips self-repair, Langfuse tracing, and circuit-breaker
    protection — and is FORBIDDEN by the spec.

    Returns (pass, [violations]).
    """
    path_info = classify_execution_path(command)
    if not path_info["violation"]:
        return (True, [])

    skill = path_info["skill"] or "unknown"
    return (False, [
        f"WRAPPER_BYPASS: command targets skill '{skill}' which has a "
        f"scripts/*-skillopt-wrapper.sh, but the command was executed as "
        f"a direct `aliyun` call. Re-run via the wrapper, e.g. "
        f"`./{skill}/scripts/<product>-skillopt-wrapper.sh <subcommand> ...`. "
        f"See AGENTS.md §15.8 (Wrapper-First Execution Rule)."
    ])


def hallucination_detect(command: str) -> dict[str, Any]:
    """Run Hallucination Detection (H) on a generated command.

    This is a pre-execution structural validity check per §14. It does NOT
    call any cloud API.

    Returns:
    {
        "status": "PASS"|"FAIL",
        "checks": {
            "cli_parameters": { "status": "PASS"|"FAIL", "total": N, "recognized": N, "unrecognized": [...] },
            "json_structure": { "status": "PASS"|"FAIL", "issues": [...] },
            "waf_compliance": { "status": "PASS"|"FAIL", "violations": [...] },
            "wrapper_compliance": { "status": "PASS"|"FAIL", "violations": [...], "execution_path": "..." }
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

    # Wrapper compliance check (AGENTS.md §15.8 + GCL §14.2.4)
    wrapper_pass, wrapper_violations = _detect_wrapper_bypass(command)
    path_info = classify_execution_path(command)
    wrapper_check = {
        "status": "PASS" if wrapper_pass else "FAIL",
        "violations": wrapper_violations,
        "execution_path": path_info["path"],
        "wrapper_should_be_used": path_info["wrapper_should_be_used"],
        "skill": path_info["skill"],
        "note": "no wrapper required for this skill/path" if not path_info["wrapper_should_be_used"] else "",
    }

    # Overall
    all_pass = cli_pass and json_pass and waf_pass and wrapper_pass
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
    if not wrapper_pass:
        report_parts.append(
            f"WRAPPER_BYPASS: {wrapper_violations[0] if wrapper_violations else 'command bypassed skillopt wrapper'}"
        )

    return {
        "status": "PASS" if all_pass else "FAIL",
        "checks": {
            "cli_parameters": cli_check,
            "json_structure": json_check,
            "waf_compliance": waf_check,
            "wrapper_compliance": wrapper_check,
        },
        "report": " | ".join(report_parts) if report_parts else "",
    }


# ---------------------------------------------------------------------------
# Generator (Phase 2: subprocess)
# ---------------------------------------------------------------------------


def run_command(command: str, timeout: int = 300) -> dict[str, Any]:
    """Execute `command` and capture its trace.

    Returns a dict with:
        - command: str
        - exit_code: int
        - stdout: str
        - stderr: str
        - result_excerpt: str  (first 500 chars of stdout)
        - request_id: str      (random UUID; placeholder for cloud RequestId)
        - duration_ms: int
        - execution_path: str  (wrapper | direct_aliyun | sdk_jit | data_plane | other)
        - execution_path_skill: Optional[str]  (skill inferred from product, if any)
    """
    start = _dt.datetime.now(tz=_dt.timezone.utc)
    request_id = str(uuid.uuid4())
    path_info = classify_execution_path(command)
    base_meta = {
        "execution_path": path_info["path"],
        "execution_path_skill": path_info["skill"],
    }

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
            **base_meta,
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
            **base_meta,
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
        **base_meta,
    }


# ---------------------------------------------------------------------------
# Critic — test accuracy / regression assessment (AGENTS.md §12, gcl-spec §2.1)
# ---------------------------------------------------------------------------


def evaluate_test_assessment(
    assessment: dict[str, Any] | None,
) -> dict[str, Any]:
    """Evaluate optional test_assessment payload (accuracy over coverage).

    Mechanical Critic uses this when the Generator trace (or CLI) supplies
    ``test_assessment``. Returns a normalized dict with ``passed`` and
    ``blocking_reason`` for decide() / trace persistence.
    """
    if not assessment:
        return {
            "evaluated": False,
            "tests_accurate": True,
            "accuracy_issues": [],
            "regression_required": False,
            "regression_suites": [],
            "regression_rationale": "",
            "regression_evidence_ok": True,
            "passed": True,
            "blocking_reason": None,
        }

    tests_accurate = bool(assessment.get("tests_accurate", True))
    accuracy_issues = list(assessment.get("accuracy_issues") or [])
    regression_required = bool(assessment.get("regression_required", False))
    regression_suites = list(assessment.get("regression_suites") or [])
    regression_rationale = str(assessment.get("regression_rationale") or "")

    # Evidence: explicit flag, or all entries in regression_evidence passed
    evidence_ok = True
    if regression_required:
        if assessment.get("regression_runs_passed") is True:
            evidence_ok = True
        elif assessment.get("regression_runs_passed") is False:
            evidence_ok = False
        else:
            evidence = assessment.get("regression_evidence")
            if isinstance(evidence, list) and evidence:
                evidence_ok = all(
                    isinstance(item, dict) and item.get("passed") is True
                    for item in evidence
                )
            else:
                evidence_ok = False

    blocking_reason: str | None = None
    if not tests_accurate:
        blocking_reason = "inaccurate_tests"
    elif regression_required and not evidence_ok:
        blocking_reason = "missing_regression_evidence"

    passed = blocking_reason is None

    return {
        "evaluated": True,
        "tests_accurate": tests_accurate,
        "accuracy_issues": accuracy_issues,
        "regression_required": regression_required,
        "regression_suites": regression_suites,
        "regression_rationale": regression_rationale,
        "regression_evidence_ok": evidence_ok,
        "passed": passed,
        "blocking_reason": blocking_reason,
    }


def _apply_test_assessment_suggestions(
    suggestions: list[str],
    test_result: dict[str, Any],
) -> list[str]:
    """Append ≤3 total suggestions from test assessment failures."""
    if test_result.get("passed", True):
        return suggestions
    if test_result.get("blocking_reason") == "inaccurate_tests":
        issues = test_result.get("accuracy_issues") or []
        if issues:
            suggestions.append(
                "TEST_ACCURACY: fix or add tests — " + issues[0]
            )
        else:
            suggestions.append(
                "TEST_ACCURACY: existing tests do not accurately assert "
                "the changed behavior; add assertions that would fail on regression."
            )
    elif test_result.get("blocking_reason") == "missing_regression_evidence":
        suites = test_result.get("regression_suites") or []
        if suites:
            suggestions.append(
                "REGRESSION: run and pass required suite(s) — " + suites[0]
            )
        else:
            suggestions.append(
                "REGRESSION: regression_required=true but no green-run "
                "evidence (set regression_runs_passed=true or regression_evidence)."
            )
    return suggestions[:3]


# ---------------------------------------------------------------------------
# LLM-based Critic (Phase 3-A): prompt loading & HTTP call
# ---------------------------------------------------------------------------

def load_generator_template(skills_root: Path, skill: str) -> str:
    """Load the Generator prompt body from ``references/prompt-templates.md``.

    Extracts only the inner `` ```text `` fenced block from §1 Generator.
    Falls back to the full section if no fence is present.
    """
    path = skills_root / skill / "references" / "prompt-templates.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    in_generator = False
    section_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## 1.") and "Generator" in line:
            in_generator = True
            continue
        if line.startswith("## 2."):
            break
        if in_generator:
            section_lines.append(line)
    fenced = _extract_text_fence_block(section_lines)
    if fenced:
        return fenced
    return "\n".join(section_lines).strip()


def _extract_text_fence_block(lines: list[str]) -> str:
    """Return inner content of the first ```text fence in *lines*."""
    in_fence = False
    collected: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```text"):
            in_fence = True
            continue
        if in_fence and stripped.startswith("```"):
            break
        if in_fence:
            collected.append(line)
    return "\n".join(collected).strip()


def apply_memory_preflight_slots(text: str, slots: dict[str, str]) -> str:
    """Replace R2 memory placeholders in a Generator prompt template."""
    result = text
    for key in ("recent_executions", "known_traps", "success_patterns", "strategy_hints"):
        result = result.replace("{{" + key + "}}", slots.get(key, ""))
    return result


def attach_memory_preflight_to_trace(
    trace: dict[str, Any],
    memory_preflight: dict[str, Any] | None,
    skills_root: Path | None,
    skill: str,
) -> None:
    """Attach R2 pre-flight data and optional filled Generator template to trace."""
    if not memory_preflight:
        return
    trace["memory_preflight"] = memory_preflight
    slots = memory_preflight.get("slots") or {}
    strategy = memory_preflight.get("strategy_hints") or {}
    _log(
        "event=memory_preflight_inject recent={} traps={} success={} strategy_empty={} empty={}",
        len(memory_preflight.get("recent_executions", [])),
        len(memory_preflight.get("known_traps", [])),
        len(memory_preflight.get("success_patterns", [])),
        strategy.get("empty", True),
        memory_preflight.get("empty", True),
    )
    if skills_root is not None:
        template = load_generator_template(skills_root, skill)
        if template:
            trace["generator_prompt_with_memory"] = apply_memory_preflight_slots(
                template, slots
            )


def load_critic_template(skills_root: Path, skill: str) -> str:
    """Load the Critic prompt template from the skill's references/prompt-templates.md.

    Looks for the section starting with `## 2. Critic` and extracts the template
    with {{placeholders}} to be filled at runtime.
    """
    path = skills_root / skill / "references" / "prompt-templates.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    in_critic = False
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## 2.") and "Critic" in line:
            in_critic = True
            continue
        if line.startswith("## 3."):
            break
        if in_critic:
            lines.append(line)
    template = "\n".join(lines).strip()
    return template


HARNESS_CLI_CODING_AGENT = "harness_cli"


def resolve_gcl_coding_agent() -> str:
    """Resolve coding_agent for GCL critic token records (Phase 1 TEL)."""
    for key in ("HARNESS_CODING_AGENT", "SKILLOPT_CODING_AGENT"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return HARNESS_CLI_CODING_AGENT


def parse_openai_llm_usage(
    resp_json: dict[str, Any],
    fallback_model: str,
) -> dict[str, Any] | None:
    """Extract OpenAI-compatible usage block; None when absent or empty."""
    usage = resp_json.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    if prompt is None and completion is None and total is None:
        return None
    if total is None and prompt is not None and completion is not None:
        total = int(prompt) + int(completion)
    model = resp_json.get("model") or fallback_model or "unknown"
    return {
        "model": str(model),
        "prompt_tokens": int(prompt or 0),
        "completion_tokens": int(completion or 0),
        "total_tokens": int(total or 0),
    }


def build_critic_meta(
    *,
    mode: str,
    llm_model: str | None,
    fallback: str | None = None,
    latency_ms: int | None = None,
    llm_usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build critic_meta persisted on each GCL iteration (includes token usage when LLM ran)."""
    model = (llm_model or os.environ.get("GCL_CRITIC_LLM_MODEL") or "unknown").strip() or "unknown"
    meta: dict[str, Any] = {
        "mode": mode,
        "llm_model": llm_model,
        "model": model,
        "coding_agent": resolve_gcl_coding_agent(),
        "fallback": fallback,
        "llm_usage": llm_usage,
    }
    if latency_ms is not None:
        meta["latency_ms"] = latency_ms
    return meta


def _pop_critic_llm_meta(result: dict[str, Any]) -> dict[str, Any]:
    """Remove internal _critic_llm_meta from critique_llm() result."""
    meta = result.pop("_critic_llm_meta", None)
    if meta is None:
        model = os.environ.get("GCL_CRITIC_LLM_MODEL") or "unknown"
        return {"latency_ms": None, "llm_usage": None, "model": model}
    return meta


def critique_llm(
    op: str,
    trace: dict[str, Any],
    rubric: dict[str, Any],
    template: str,
) -> dict[str, Any]:
    """Call LLM endpoint to critique the generator output.

    Uses OpenAI-compatible /v1/chat/completions endpoint, configured via:
      - GCL_CRITIC_LLM_ENDPOINT: base URL (must be full /v1/chat/completions path)
      - GCL_CRITIC_LLM_API_KEY: Bearer token (optional if endpoint has it)
      - GCL_CRITIC_LLM_MODEL: model name (default: gpt-4o-mini)
      - GCL_CRITIC_LLM_TIMEOUT: request timeout in seconds (default: 30)

    Returns exactly the same dict shape as mechanical critique:
      {
        "scores": { "correctness": 0|0.5|1, ... },
        "suggestions": ["..."],
        "matched_regexes": [],
        "blocking": True|False,
        "test_assessment": { ... } (optional)
      }
    """
    import urllib.error
    import urllib.request

    endpoint: str = os.environ["GCL_CRITIC_LLM_ENDPOINT"]
    api_key: str = os.environ.get("GCL_CRITIC_LLM_API_KEY", "")
    model: str | None = os.environ.get("GCL_CRITIC_LLM_MODEL")
    fallback_model: str = model or "gpt-4o-mini"
    timeout: int = int(os.environ.get("GCL_CRITIC_LLM_TIMEOUT", "30"))

    # Fill template placeholders
    rubric_text = json.dumps(rubric, indent=2, ensure_ascii=False)
    generator_output = json.dumps(trace, indent=2, ensure_ascii=False)
    prompt = template
    prompt = prompt.replace("{{output.rubric}}", rubric_text)
    prompt = prompt.replace("{{output.generator_output}}", generator_output)
    prompt = prompt.replace("{{output.trace}}", generator_output)

    # Build OpenAI-compatible request
    messages = [
        {"role": "user", "content": prompt},
    ]
    payload: dict[str, Any] = {
        "model": model or "gpt-4o-mini",
        "messages": messages,
        "temperature": 0.0,  # deterministic scoring
        "response_format": {"type": "json_object"},
    }
    data_bytes = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(endpoint, method="POST", data=data_bytes)
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    def _fail_open_scores(
        suggestion: str,
        *,
        latency_ms: int | None = None,
    ) -> dict[str, Any]:
        return {
            "scores": {
                "correctness": 0.5,
                "safety": 0.5,
                "idempotency": 0.5,
                "traceability": 0.5,
                "spec_compliance": 0.5,
                "region_compliance": 0.5,
                "credential_hygiene": 0.5,
                "well_architected": 0.5,
                "wrapper_compliance": 0.5,
            },
            "suggestions": [suggestion],
            "matched_regexes": [],
            "blocking": False,
            "test_assessment": None,
            "_critic_llm_meta": {
                "latency_ms": latency_ms,
                "llm_usage": None,
                "model": fallback_model,
            },
        }

    start_ts = _dt.datetime.now(_dt.timezone.utc).timestamp()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as f:
            resp_bytes = f.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        print(f"[WARN] GCL LLM Critic call failed: {e}", file=sys.stderr)
        end_ts = _dt.datetime.now(_dt.timezone.utc).timestamp()
        latency_ms = max(0, int((end_ts - start_ts) * 1000))
        return _fail_open_scores(f"LLM call failed: {e}", latency_ms=latency_ms)

    end_ts = _dt.datetime.now(_dt.timezone.utc).timestamp()
    latency_ms = max(0, int((end_ts - start_ts) * 1000))

    # Parse response JSON
    content = ""
    try:
        resp_json = json.loads(resp_bytes.decode("utf-8"))
        content = resp_json["choices"][0]["message"]["content"]
        result = json.loads(content)
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"[WARN] GCL LLM response parse failed: {e}; got: {content[:200]!r}", file=sys.stderr)
        return _fail_open_scores(f"LLM response parse failed: {e}", latency_ms=latency_ms)

    # Ensure all required score dimensions exist; clip to 0/0.5/1 per spec
    default_scores = {
        "correctness": 0.5,
        "safety": 0.5,
        "idempotency": 0.5,
        "traceability": 0.5,
        "spec_compliance": 0.5,
        "region_compliance": 0.5,
        "credential_hygiene": 0.5,
        "well_architected": 0.5,
        "wrapper_compliance": 0.5,
    }
    scores = result.get("scores", {})
    for k in default_scores:
        if k not in scores:
            scores[k] = default_scores[k]
    # Clip to 0/0.5/1 per AGENTS.md §12 requirement
    for k, v in scores.items():
        if v <= 0.25:
            scores[k] = 0.0
        elif v <= 0.75:
            scores[k] = 0.5
        else:
            scores[k] = 1.0

    llm_usage = parse_openai_llm_usage(resp_json, fallback_model)

    return {
        "scores": scores,
        "suggestions": result.get("suggestions", [])[:3],
        "matched_regexes": [],
        "blocking": result.get("blocking", False),
        "test_assessment": result.get("test_assessment"),
        "_critic_llm_meta": {
            "latency_ms": latency_ms,
            "llm_usage": llm_usage,
            "model": (llm_usage or {}).get("model") or fallback_model,
        },
    }


def _critic_trace_payload(critic_result: dict[str, Any]) -> dict[str, Any]:
    """Build the critic sub-object persisted in each iteration trace."""
    payload: dict[str, Any] = {
        "scores": critic_result["scores"],
        "suggestions": critic_result["suggestions"],
        "matched_regexes": critic_result["matched_regexes"],
        "blocking": critic_result["blocking"],
    }
    ta = critic_result.get("test_assessment")
    if ta is not None:
        payload["test_assessment"] = ta
    cm = critic_result.get("critic_meta")
    if cm is not None:
        payload["critic_meta"] = cm
    return payload


# ---------------------------------------------------------------------------
# Critic (Phase 2: mechanical regex re-classifier)
# ---------------------------------------------------------------------------


def critique(
    op: str,
    trace: dict[str, Any],
    rubric: dict[str, Any],
    gcl_critic_mode: str = "mechanical",
    *,
    skills_root: Path | None = None,
    skill: str | None = None,
    llm_model: str | None = None,
) -> dict[str, Any]:
    """Critique the Generator's output against the rubric.

    - mechanical: pure-Python regex re-classifier (default), does not see user request
    - llm: LLM-based Critic, uses prompt from skill's prompt-templates.md
    - hybrid: mechanical for hard safety gates, LLM for nuanced scoring (recommended when LLM enabled)

    In all modes, the Critic never sees the original user request (per AGENTS.md §12.7
    rubber-stamping prevention rule).

    Returns a dict with:
        - scores: dict[str, float]    (5 core + 3 Aliyun extensions)
        - suggestions: list[str]       (≤ 3 actionable items)
        - matched_regexes: list[str]   (regex patterns that matched; [] for llm)
        - blocking: bool
        - test_assessment: dict        (when trace includes test_assessment input)
        - critic_meta: dict           (mode, model, latency_ms, fallback if any)
    """
    # The Critic's input is the trace; the user_request is NOT passed in.
    command = trace["command"]
    exit_code = trace["exit_code"]
    stdout = trace["stdout"]
    stderr = trace["stderr"]
    full_text = f"{command}\n{stdout}\n{stderr}"

    matched: list[str] = []
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
    scores: dict[str, float] = {}

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

    # 2.4 Wrapper Compliance (AGENTS.md §15.8) — must use skillopt wrapper
    #     when the targeted skill has one. A direct `aliyun <product>` call
    #     is a silent bypass that strips self-repair / tracing / circuit breaker.
    path_info = classify_execution_path(command)
    if path_info["wrapper_should_be_used"] and path_info["path"] == "direct_aliyun":
        # Bypass detected. Same severity as a destructive op: blocking.
        scores["wrapper_compliance"] = 0.0
    elif path_info["path"] == "wrapper":
        # Explicitly routed through the wrapper. Full marks.
        scores["wrapper_compliance"] = 1.0
    else:
        # Either no wrapper applies (sdk_jit, data_plane, other) or
        # skill has no wrapper at all. Pass with a caveat.
        scores["wrapper_compliance"] = 1.0

    # ---- Suggestions ----
    suggestions: list[str] = []
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

    if scores.get("wrapper_compliance", 1.0) == 0.0:
        blocking = True
        suggestions.append(
            f"WRAPPER_BYPASS: command targets skill '{path_info['skill']}' "
            f"which has a scripts/*-skillopt-wrapper.sh, but the command was "
            f"executed as a direct `aliyun` call (execution_path="
            f"{path_info['path']}). Re-run via the wrapper: "
            f"./{path_info['skill']}/scripts/<product>-skillopt-wrapper.sh "
            f"<subcommand> ... See AGENTS.md §15.8."
        )

    if scores["correctness"] == 0.0:
        suggestions.append(
            f"Generator exit_code={exit_code}; stderr={stderr[:200]!r}. "
            "Inspect error and re-run with corrected args."
        )

    if not blocking and scores["correctness"] == 1.0:
        # All good; limit suggestions to 0 if nothing to say
        suggestions = []

    test_result = evaluate_test_assessment(trace.get("test_assessment"))
    if test_result["evaluated"] and not test_result["passed"]:
        blocking = True
        suggestions = _apply_test_assessment_suggestions(suggestions, test_result)

    # Dispatch to LLM/hybrid if needed
    if gcl_critic_mode == "mechanical":
        # pure mechanical regex
        critic_meta = build_critic_meta(
            mode="mechanical",
            llm_model=llm_model,
            fallback=None,
            llm_usage=None,
        )
        return {
            "scores": scores,
            "suggestions": suggestions[:3],
            "matched_regexes": matched,
            "blocking": blocking,
            "test_assessment": test_result,
            "critic_meta": critic_meta,
        }

    # For LLM/hybrid: load skill's prompt template from references/prompt-templates.md
    if skills_root is None or not skill:
        gcl_critic_mode = "mechanical"
        critic_meta = build_critic_meta(
            mode="mechanical",
            llm_model=llm_model,
            fallback="missing_skills_root_or_skill",
            llm_usage=None,
        )
        return {
            "scores": scores,
            "suggestions": suggestions[:3],
            "matched_regexes": matched,
            "blocking": blocking,
            "test_assessment": test_result,
            "critic_meta": critic_meta,
        }
    template = load_critic_template(skills_root, skill)
    if gcl_critic_mode == "hybrid":
        # Keep mechanical scores for hard dimensions; LLM will score others
        mechanical_scores = scores.copy()
        mechanical_blocking = blocking
        mechanical_suggestions = suggestions[:]
        mechanical_matched = matched.copy()

    llm_result = critique_llm(
        op=op,
        trace=trace,
        rubric=rubric,
        template=template,
    )

    llm_meta = _pop_critic_llm_meta(llm_result)

    if gcl_critic_mode == "llm":
        # Pure LLM
        critic_meta = build_critic_meta(
            mode="llm",
            llm_model=llm_model,
            fallback=None,
            latency_ms=llm_meta.get("latency_ms"),
            llm_usage=llm_meta.get("llm_usage"),
        )
        return {
            "scores": llm_result["scores"],
            "suggestions": llm_result.get("suggestions", [])[:3],
            "matched_regexes": [],
            "blocking": llm_result.get("blocking", False),
            "test_assessment": llm_result.get("test_assessment", test_result),
            "critic_meta": critic_meta,
        }
    elif gcl_critic_mode == "hybrid":
        # Hybrid: mechanical for hard gates (safety/credential/wrapper), LLM for everything else
        merged_scores = mechanical_scores.copy()
        for dim, score in llm_result.get("scores", {}).items():
            # If mechanical is already 0, keep 0; otherwise take LLM's score
            if merged_scores.get(dim, 0.5) != 0:
                merged_scores[dim] = score
        merged_blocking = mechanical_blocking or llm_result.get("blocking", False)
        merged_suggestions = mechanical_suggestions[:]
        merged_suggestions += llm_result.get("suggestions", [])
        critic_meta = build_critic_meta(
            mode="hybrid",
            llm_model=llm_model,
            fallback=None,
            latency_ms=llm_meta.get("latency_ms"),
            llm_usage=llm_meta.get("llm_usage"),
        )
        return {
            "scores": merged_scores,
            "suggestions": merged_suggestions[:3],
            "matched_regexes": mechanical_matched,
            "blocking": merged_blocking,
            "test_assessment": llm_result.get("test_assessment", test_result),
            "critic_meta": critic_meta,
        }
    else:
        # unknown mode → fall back to mechanical
        critic_meta = build_critic_meta(
            mode=gcl_critic_mode,
            llm_model=llm_model,
            fallback="mechanical",
            llm_usage=None,
        )
        return {
            "scores": scores,
            "suggestions": suggestions[:3],
            "matched_regexes": matched,
            "blocking": blocking,
            "test_assessment": test_result,
            "critic_meta": critic_meta,
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


def decide(critic: dict[str, Any], iter_no: int, max_iter: int) -> str:
    """Return one of: PASS / RETRY / MAX_ITER / SAFETY_FAIL / WRAPPER_BYPASS.

    First match wins (AGENTS.md §12.5):
      - Safety=0 → ABORT (SAFETY_FAIL)
      - wrapper_compliance=0 → ABORT (WRAPPER_BYPASS) — same severity as
        Safety=0 per AGENTS.md §15.8 (Wrapper-First Execution Rule)
      - all scores >= threshold (0.5) AND iter>=1 → PASS
      - iter < max_iter → RETRY
      - else → MAX_ITER
    """
    scores = critic["scores"]
    if critic["blocking"]:
        if scores.get("wrapper_compliance", 1.0) == 0.0:
            return "WRAPPER_BYPASS"
        if scores.get("safety", 1) == 0.0:
            return "SAFETY_FAIL"
        ta = critic.get("test_assessment") or {}
        if ta.get("evaluated") and not ta.get("passed", True):
            if iter_no < max_iter:
                return "RETRY"
            return "MAX_ITER"
        return "SAFETY_FAIL"
    if scores.get("safety", 1) == 0.0:
        return "SAFETY_FAIL"
    if scores.get("wrapper_compliance", 1.0) == 0.0:
        return "WRAPPER_BYPASS"

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
    user_request: str | None,
    rubric: dict[str, Any],
    max_iter: int,
    gcl_critic_mode: str = "mechanical",
    llm_model: str | None = None,
    enable_hallucination_check: bool = False,
    test_assessment: dict[str, Any] | None = None,
    memory_preflight: dict[str, Any] | None = None,
    skills_root: Path | None = None,
) -> dict[str, Any]:
    """Run the Generator-Critic loop per AGENTS.md §12.4 + §14.

    When enable_hallucination_check is True, runs the Hallucination Detection
    (H) gate before executing the command. If H fails, the command is
    regenerated once; if it still fails, the loop aborts with HALLUCINATION_ABORT.

    Returns the trace dict (will be persisted to disk by the caller).
    """
    trace: dict[str, Any] = {
        "skill": skill,
        "request": _sanitize_user_request(user_request),
        "rubric_version": rubric["version"],
        "iterations": [],
        "failure_pattern": None,  # populated by extract_failure_pattern() if SAFETY_FAIL
    }
    attach_memory_preflight_to_trace(trace, memory_preflight, skills_root, skill)

    decision = "MAX_ITER"
    best_iter: dict[str, Any] | None = None
    best_score_sum = -1.0

    for iter_no in range(1, max_iter + 1):
        # [1.5] Hallucination Detection (H) — pre-execution check
        h_result: dict[str, Any] | None = None
        if enable_hallucination_check:
            h_result = hallucination_detect(command)
            if h_result["status"] == "FAIL":
                # HALLUCINATION_ABORT — structural hallucinations detected.
                # In mechanical mode, the command is fixed, so no regeneration is attempted.
                # In a future LLM-based H, the Orchestrator would re-prompt Generator (G)
                # with the hallucination report and re-check after regeneration.
                iter_record: dict[str, Any] = {
                    "iter": iter_no,
                    "hallucination_detector": h_result,
                    "regenerated": False,
                    "generator": {
                        "command": command,
                        "exit_code": -1,
                        "result_excerpt": "",
                        "request_id": str(uuid.uuid4()),
                        "duration_ms": 0,
                        "execution_path": classify_execution_path(command)["path"],
                        "execution_path_skill": classify_execution_path(command)["skill"],
                    },
                    "critic": {
                        "scores": {k: 0.0 for k in ("correctness", "safety", "idempotency", "traceability", "spec_compliance", "region_compliance", "credential_hygiene", "well_architected", "wrapper_compliance")},
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
        if test_assessment is not None:
            gen_trace["test_assessment"] = test_assessment

        # [2] Critique
        critic_result = critique(
            op,
            gen_trace,
            rubric,
            gcl_critic_mode=gcl_critic_mode,
            skills_root=skills_root,
            skill=skill,
            llm_model=llm_model,
        )

        # [3] Decide
        decision = decide(critic_result, iter_no, max_iter)

        # Persist this iteration (sanitized)
        iter_record: dict[str, Any] = {
            "iter": iter_no,
            "generator": _sanitize_trace(gen_trace),
            "critic": _critic_trace_payload(critic_result),
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

        if decision in ("PASS", "SAFETY_FAIL", "WRAPPER_BYPASS"):
            break

    trace["final"] = {
        "status": decision,
        "iter": len(trace["iterations"]),
        "output": _summarize_output(trace["iterations"][-1]),
    }
    if decision == "MAX_ITER" and best_iter is not None:
        trace["final"]["best_iter"] = best_iter["iter"]
        trace["final"]["best_output"] = _summarize_output(best_iter)

    # Extract failure pattern for Reflexion (Layer 2)
    last_critic = trace["iterations"][-1]["critic"]
    fp: dict | None = None
    if decision == "SAFETY_FAIL":
        fp = extract_failure_pattern(
            last_critic, skill, op, command, status="SAFETY_FAIL"
        )
    elif decision == "MAX_ITER":
        fp = extract_failure_pattern(
            last_critic, skill, op, command, status="MAX_ITER",
            scores=last_critic.get("scores"),
        )
    elif decision == "PASS":
        fp = extract_failure_pattern(
            last_critic, skill, op, command, status="PASS_NEAR_MISS",
            scores=last_critic.get("scores"),
        )
    trace["failure_pattern"] = fp
    _log("event=reflexion_extract decision={} skill={} op={} pattern={}",
         decision, skill, op, "found" if fp else "skipped")
    if fp is not None:
        _log("event=reflexion_pattern category={} failing_dimensions={}",
             fp.get("category", "?"), fp.get("failing_dimensions", fp.get("low_dimensions", "")))

    if decision == "PASS":
        sp_row, sp_meta = extract_success_pattern(trace, skill, op, command)
        trace["success_pattern"] = sp_meta
        if sp_row is not None:
            trace["_success_pattern_payload"] = sp_row
            _log(
                "event=success_extract result=captured reason={} skill={} op={}",
                sp_meta.get("capture_reason", "?"),
                skill,
                op,
            )
        else:
            _log(
                "event=success_extract result=skipped reason={} skill={} op={}",
                sp_meta.get("reason", "?"),
                skill,
                op,
            )

    return trace


def _sanitize_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Sanitize the generator trace's command/stdout/stderr/result_excerpt."""
    out = dict(trace)
    out["command"] = sanitize(trace["command"])
    out["stdout"] = sanitize(trace["stdout"])
    out["stderr"] = sanitize(trace["stderr"])
    out["result_excerpt"] = sanitize(trace["result_excerpt"])
    return out


def extract_failure_pattern(
    critic_result: dict[str, Any],
    skill: str,
    op: str,
    command: str,
    status: str = "SAFETY_FAIL",
    scores: dict[str, float] | None = None,
) -> dict[str, Any] | None:
    """Extract a failure pattern from a critic result.

    Handles three capture modes depending on ``status``:

    - ``SAFETY_FAIL``: safety=0 → ``cli_parameter`` or ``runtime`` category.
    - ``MAX_ITER``: iterations exhausted → ``max_iter`` category with failing dimensions.
    - ``PASS_NEAR_MISS``: passed but one or more dimensions < 0.8 → ``near_miss`` category.

    Returns a structured failure pattern dict, or None if no pattern can be extracted.
    """
    if status == "SAFETY_FAIL":
        if critic_result["scores"].get("safety", 1.0) > 0.0:
            return None
        category = "cli_parameter"
        for regex_info in critic_result.get("matched_regexes", []):
            risk = regex_info.get("risk", "")
            if "DESTRUCTIVE" in risk or "FATAL" in risk:
                category = "runtime"
                break
        fix = ""
        suggestions = critic_result.get("suggestions", [])
        if suggestions:
            fix = suggestions[0][:200]
        result: dict[str, Any] = {
            "category": category,
            "skill": skill,
            "command": command[:200],
            "error": next(iter(critic_result.get("suggestions", [])), "")[:120],
            "root_cause": f"safety=0 during {op}",
            "fix": fix,
        }
        # Add runtime-specific fields for reflexion memory (Layer 2)
        if category == "runtime":
            result["operation"] = op
            result["failure_pattern"] = result["error"]
            result["prevention"] = fix
        return result

    if status == "MAX_ITER":
        all_scores = scores or critic_result.get("scores", {})
        failing = [k for k, v in all_scores.items() if v < 0.5]

        if not failing:
            # Check if any dimension is below 0.8 (near-miss threshold)
            low_dims = [f"{k}={v}" for k, v in all_scores.items() if v < 0.8]
            if low_dims:
                # Record as near-miss even though technically passing thresholds
                return {
                    "category": "max_iter",
                    "skill": skill,
                    "operation": op,
                    "command": command[:200],
                    "failing_dimensions": "none_below_0.5",
                    "best_score": f"{sum(all_scores.values()):.1f}",
                    "low_dimensions": ", ".join(low_dims),
                    "scores": f"count={len(all_scores)} sum={sum(all_scores.values()):.1f}",
                    "fix": "All dimensions pass minimum threshold but some are below optimal; consider parameter refinement",
                }
            return None  # Truly no issue to record

        low = [f"{k}={v}" for k, v in all_scores.items() if v < 0.8]
        best_score = f"{sum(all_scores.values()):.1f}"
        return {
            "category": "max_iter",
            "skill": skill,
            "operation": op,
            "command": command[:200],
            "failing_dimensions": ", ".join(failing),
            "best_score": best_score,
            "low_dimensions": ", ".join(low),
            "scores": f"count={len(all_scores)} sum={best_score}",
            "fix": "Review failing dimensions; increase --max-iter or refine operation parameters",
        }

    if status == "PASS_NEAR_MISS":
        all_scores = scores or critic_result.get("scores", {})
        low = [f"{k}={v}" for k, v in sorted(all_scores.items()) if v < 0.8]
        if not low:
            return None
        scores_summary = ", ".join(low)
        return {
            "category": "near_miss",
            "skill": skill,
            "operation": op,
            "command": command[:200],
            "low_dimensions": ", ".join(k.split("=")[0] for k in low),
            "scores": scores_summary,
            "fix": "Monitor low-scoring dimensions; consider pre-flight validation improvements",
        }

    return None


_CAPTURE_REASON_PRIORITY: tuple[str, ...] = (
    "hallucination_recovery",
    "multi_iter",
    "near_miss_resolved",
    "score_recovery",
    "traps_informed",
)


def _iter_score_sum(iter_record: dict[str, Any]) -> float:
    scores = iter_record.get("critic", {}).get("scores") or {}
    return float(sum(scores.values()))


def _scores_summary_low_first(scores: dict[str, float]) -> str:
    ordered = sorted(scores.items(), key=lambda item: item[1])
    return ", ".join(f"{k}={v}" for k, v in ordered)


def _detect_hard_won_signals(trace: dict[str, Any]) -> dict[str, bool]:
    """Return HW-* booleans per success-patterns.md §4.1."""
    iters: list[dict[str, Any]] = trace.get("iterations") or []
    signals: dict[str, bool] = {
        "multi_iter": len(iters) >= 2,
        "traps_informed": False,
        "score_recovery": False,
        "near_miss_resolved": False,
        "hallucination_recovery": False,
    }

    preflight = trace.get("memory_preflight") or {}
    traps = preflight.get("known_traps") or []
    signals["traps_informed"] = len(traps) >= 1

    if len(iters) >= 2:
        final_sum = _iter_score_sum(iters[-1])
        for earlier in iters[:-1]:
            scores = earlier.get("critic", {}).get("scores") or {}
            if scores and final_sum - sum(scores.values()) >= 0.5:
                signals["score_recovery"] = True
            if any(float(v) < 0.8 for v in scores.values()):
                signals["near_miss_resolved"] = True

    saw_h_fail = False
    for it in iters:
        h = it.get("hallucination_detector")
        if h and h.get("status") == "FAIL":
            saw_h_fail = True
        if saw_h_fail and it.get("regenerated"):
            signals["hallucination_recovery"] = True

    return signals


def _is_ordinary_pass(
    trace: dict[str, Any],
    signals: dict[str, bool],
    final_scores: dict[str, float],
) -> bool:
    """Ordinary PASS skip — all OR-* must hold (success-patterns.md §4.1)."""
    iters: list[dict[str, Any]] = trace.get("iterations") or []
    preflight = trace.get("memory_preflight") or {}
    traps = preflight.get("known_traps") or []
    or1 = len(iters) == 1
    or2 = not preflight or len(traps) == 0
    or3 = bool(final_scores) and min(final_scores.values()) >= 0.95
    or4 = not signals["score_recovery"] and not signals["near_miss_resolved"]
    return or1 and or2 and or3 and or4


def _pick_capture_reason(signals: dict[str, bool]) -> str:
    for reason in _CAPTURE_REASON_PRIORITY:
        if signals.get(reason):
            return reason
    return "multi_iter"


def _earlier_low_dimensions(trace: dict[str, Any]) -> str:
    dims: list[str] = []
    iters: list[dict[str, Any]] = trace.get("iterations") or []
    for earlier in iters[:-1]:
        for dim, val in (earlier.get("critic", {}).get("scores") or {}).items():
            if float(val) < 0.8 and dim not in dims:
                dims.append(dim)
    return ", ".join(dims)


def _build_success_hint(
    *,
    iterations: int,
    capture_reason: str,
    command_excerpt: str,
    preflight_had_traps: bool,
    trap_count: int,
    low_dims: str,
    scores_summary: str,
) -> str:
    parts = [
        f"PASS after {iterations} iteration(s) ({capture_reason}).",
        f"Command: {command_excerpt}",
    ]
    if preflight_had_traps:
        parts.append(f"Preflight listed {trap_count} known trap(s).")
    if low_dims:
        parts.append(f"Earlier low dimensions: {low_dims}.")
    parts.append(f"Final scores: {scores_summary}")
    return " ".join(parts)[:300]


def _trace_has_test_assessment_only(trace: dict[str, Any]) -> bool:
    iters: list[dict[str, Any]] = trace.get("iterations") or []
    if not iters:
        return False
    return all(it.get("generator", {}).get("test_assessment") for it in iters)


def _trace_final_command(trace: dict[str, Any], fallback: str) -> str:
    iters: list[dict[str, Any]] = trace.get("iterations") or []
    if iters:
        cmd = iters[-1].get("generator", {}).get("command")
        if cmd:
            return str(cmd)
    return fallback


def extract_success_pattern(
    trace: dict[str, Any],
    skill: str,
    op: str,
    command: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Extract a hard-won PASS success pattern from a GCL trace (R4 §4.4).

    Returns ``(store_row, trace_meta)``. ``store_row`` is passed to
    ``success_store()``; ``trace_meta`` is persisted as ``trace["success_pattern"]``.
    """
    final = trace.get("final") or {}
    status = final.get("status", "")
    if status != "PASS":
        return None, {"captured": False, "reason": str(status).lower() or "not_pass"}

    if trace.get("dry_run"):
        return None, {"captured": False, "reason": "dry_run"}

    if _trace_has_test_assessment_only(trace):
        return None, {"captured": False, "reason": "test_assessment_only"}

    iters: list[dict[str, Any]] = trace.get("iterations") or []
    if not iters:
        return None, {"captured": False, "reason": "no_iterations"}

    last_critic = iters[-1].get("critic") or {}
    if last_critic.get("blocking"):
        return None, {"captured": False, "reason": "critic_blocked"}
    final_scores: dict[str, float] = last_critic.get("scores") or {}
    if final_scores.get("safety", 1.0) <= 0:
        return None, {"captured": False, "reason": "safety_zero"}

    signals = _detect_hard_won_signals(trace)

    if _is_ordinary_pass(trace, signals, final_scores):
        return None, {"captured": False, "reason": "ordinary_pass"}

    if not any(signals.values()):
        return None, {"captured": False, "reason": "no_hard_won_signal"}

    raw_cmd = _trace_final_command(trace, command)
    sanitized_cmd = sanitize(raw_cmd)
    if "<masked>" in sanitized_cmd:
        return None, {"captured": False, "reason": "sanitized_secret"}

    capture_reason = _pick_capture_reason(signals)
    preflight = trace.get("memory_preflight") or {}
    traps: list[dict[str, Any]] = preflight.get("known_traps") or []
    trap_count = len(traps)
    preflight_had_traps = trap_count >= 1
    scores_min = float(min(final_scores.values())) if final_scores else 0.0
    scores_summary = _scores_summary_low_first(final_scores)
    low_dims = _earlier_low_dimensions(trace)
    command_excerpt = sanitized_cmd[:200]
    command_hash = compute_command_hash(sanitized_cmd)

    hint = _build_success_hint(
        iterations=len(iters),
        capture_reason=capture_reason,
        command_excerpt=command_excerpt,
        preflight_had_traps=preflight_had_traps,
        trap_count=trap_count,
        low_dims=low_dims,
        scores_summary=scores_summary,
    )

    path_info = classify_execution_path(sanitized_cmd)
    row: dict[str, Any] = {
        "skill": normalize_skill_name(skill),
        "operation": op,
        "command_excerpt": command_excerpt,
        "command_hash": command_hash,
        "capture_reason": capture_reason,
        "iterations": len(iters),
        "scores_summary": scores_summary[:200],
        "scores_min": scores_min,
        "preflight_had_traps": preflight_had_traps,
        "trap_count": trap_count,
        "hint": hint,
        "source": "gcl-runner",
        "git_commit": _get_git_head(),
        "execution_path": path_info.get("path"),
    }
    categories = sorted(
        {str(t.get("category")) for t in traps if t.get("category")}
    )
    if categories:
        row["matched_trap_categories"] = categories

    store_key = f"{row['skill']}:{op}:{command_hash}"
    meta = {
        "captured": True,
        "capture_reason": capture_reason,
        "store_key": store_key,
    }
    return row, meta


def _synthesize_dry_run(
    skill: str,
    op: str,
    command: str,
    user_request: str | None,
    rubric: dict[str, Any],
    gcl_critic_mode: str = "mechanical",
    llm_model: str | None = None,
    enable_hallucination_check: bool = False,
    test_assessment: dict[str, Any] | None = None,
    memory_preflight: dict[str, Any] | None = None,
    skills_root: Path | None = None,
) -> dict[str, Any]:
    """Build a single-iteration trace WITHOUT executing the command.

    Used by `--dry-run` for Critic-only regression tests. The command
    string is preserved in the trace so the Critic can still classify it.
    The generator trace is synthesized with exit_code=0 and empty stdout.
    """
    h_result: dict[str, Any] | None = None
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
    if test_assessment is not None:
        synthetic_gen["test_assessment"] = test_assessment
    critic_result = critique(
        op,
        synthetic_gen,
        rubric,
        gcl_critic_mode=gcl_critic_mode,
        skills_root=skills_root,
        skill=skill,
        llm_model=llm_model,
    )
    decision = decide(critic_result, 1, 1)

    iter_record: dict[str, Any] = {
        "iter": 1,
        "generator": _sanitize_trace(synthetic_gen),
        "critic": _critic_trace_payload(critic_result),
        "decision": decision,
    }
    if h_result is not None:
        iter_record["hallucination_detector"] = h_result

    trace: dict[str, Any] = {
        "skill": skill,
        "request": _sanitize_user_request(user_request),
        "rubric_version": rubric["version"],
        "iterations": [iter_record],
        "dry_run": True,
        "final": {
            "status": decision,
            "iter": 1,
            "output": "dry-run; no subprocess executed",
        },
    }
    attach_memory_preflight_to_trace(trace, memory_preflight, skills_root, skill)
    return trace


def _sanitize_user_request(text: str | None) -> str:
    """Sanitize the user-request field. Truncate to 200 chars to limit PII."""
    if text is None:
        return ""
    sanitized = sanitize(text)
    return sanitized[:200]


def _summarize_output(iter_record: dict[str, Any]) -> str:
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


def persist_trace(trace: dict[str, Any], output_dir: Path) -> Path:
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
    p.add_argument("--dry-run-preflight", action="store_true",
                    help="Run pre-flight + H detection + memory injection preview, print injected content, then exit without executing (A2.3)")
    p.add_argument("--enable-hallucination-check", action="store_true", help="Enable the pre-execution Hallucination Detection (H) gate (§14)")
    p.add_argument(
        "--test-assessment",
        default=None,
        metavar="PATH",
        help="JSON file with test_assessment payload (tests_accurate, regression_required, regression_runs_passed, etc.) per gcl-spec §2.1",
    )
    p.add_argument("--adaptive", action="store_true", help="Enable adaptive max_iter based on smart alarm engine degradation state (Phase 7)")
    p.add_argument("--critic-mode", choices=("mechanical", "llm", "hybrid"), default=None,
                 help="Critic mode (default: from GCL_CRITIC_MODE env or 'mechanical')")
    p.add_argument(
        "--disable-memory-preflight",
        action="store_true",
        help="Skip R2 Layer 1–3 pre-flight memory retrieval (default: enabled unless GCL_MEMORY_PREFLIGHT_ENABLED=false)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    # Resolve rubric path
    skills_root = resolve_skills_root()
    rubric_path = Path(args.rubric) if args.rubric else skills_root / args.skill / "references" / "rubric.md"

    # Parse rubric
    try:
        rubric = parse_rubric(rubric_path)
    except RubricError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return EXIT_RUBRIC_ERROR

    # Override max_iter
    base_max_iter = args.max_iter or rubric["max_iter"] or SKILL_MAX_ITER.get(args.skill, 2)
    max_iter = base_max_iter
    adaptive_reason = None

    # Resolve Critic mode from CLI/env (defaults to mechanical)
    gcl_critic_mode: str = args.critic_mode or os.environ.get("GCL_CRITIC_MODE", "mechanical")
    gcl_critic_llm_endpoint: str | None = os.environ.get("GCL_CRITIC_LLM_ENDPOINT")
    gcl_critic_llm_api_key: str | None = os.environ.get("GCL_CRITIC_LLM_API_KEY")
    gcl_critic_llm_model: str | None = os.environ.get("GCL_CRITIC_LLM_MODEL")
    gcl_critic_llm_timeout: int = int(os.environ.get("GCL_CRITIC_LLM_TIMEOUT", "30"))
    gcl_critic_llm_fail_open: bool = os.environ.get("GCL_CRITIC_LLM_FAIL_OPEN", "true").lower() == "true"

    # Pre-flight check for LLM/hybrid mode
    if gcl_critic_mode in ("llm", "hybrid"):
        if not gcl_critic_llm_endpoint:
            if gcl_critic_llm_fail_open:
                print(f"[WARN] GCL_CRITIC_MODE={gcl_critic_mode} but GCL_CRITIC_LLM_ENDPOINT is empty; falling back to mechanical", file=sys.stderr)
                gcl_critic_mode = "mechanical"
            else:
                print(f"[ERROR] GCL_CRITIC_MODE={gcl_critic_mode} requires GCL_CRITIC_LLM_ENDPOINT in .env", file=sys.stderr)
                return EXIT_USAGE_ERROR
        if gcl_critic_mode in ("llm", "hybrid") and not gcl_critic_llm_api_key:
            if gcl_critic_llm_fail_open:
                _log("event=preflight key=GCL_CRITIC_LLM_API_KEY status=empty detail=endpoint_may_reject")

    # Adaptive mode: consult smart alarm engine degradation state
    if args.adaptive:
        adaptive_max_iter, adaptive_reason = get_adaptive_max_iter(args.skill, args.command, base_max_iter)
        if adaptive_max_iter != base_max_iter:
            max_iter = adaptive_max_iter
            _log("event=adaptive_max_iter from={} to={} reason={}",
                 base_max_iter, max_iter, adaptive_reason)

    # Pre-flight
    ok, errors = preflight(args.skill, args.op, args.command, rubric, args.user_request)
    if not ok:
        _log("event=preflight result=failed errors={}", errors)
        return EXIT_USAGE_ERROR

    # R2: Layer 1–3 memory pre-flight retrieval (non-fatal)
    memory_preflight_enabled = (
        not args.disable_memory_preflight
        and os.environ.get("GCL_MEMORY_PREFLIGHT_ENABLED", "true").lower() != "false"
    )
    memory_preflight_data: dict[str, Any] = {"empty": True, "slots": {}}
    if memory_preflight_enabled:
        try:
            memory_preflight_data = preflight_retrieve(
                skill=args.skill,
                operation=args.op,
                skills_root=skills_root,
            )
            _log(
                "event=memory_preflight result=success recent={} traps={} success={} empty={}",
                len(memory_preflight_data.get("recent_executions", [])),
                len(memory_preflight_data.get("known_traps", [])),
                len(memory_preflight_data.get("success_patterns", [])),
                memory_preflight_data.get("empty", True),
            )
        except Exception as exc:
            _log("event=memory_preflight result=error exception={}", exc)

    # A2.3: dry-run preflight — show injection preview then exit
    if args.dry_run_preflight:
        slots = memory_preflight_data.get("slots") or {}
        print("=== DRY-RUN PREFLIGHT ===")
        print(f"skill={args.skill} op={args.op}")
        print(f"command={args.command}")
        if args.enable_hallucination_check:
            h = hallucination_detect(args.command)
            print(f"H detection: status={h['status']} report={h['report']}")
        print(f"memory_preflight: empty={memory_preflight_data.get('empty', True)}")
        print(f"  recent_executions: {len(memory_preflight_data.get('recent_executions', []))}")
        print(f"  known_traps ({len(memory_preflight_data.get('known_traps', []))}):")
        for t in memory_preflight_data.get("known_traps", []):
            print(f"    - [{t.get('category', '?')}] count={t.get('count', 1)} error={str(t.get('error', ''))[:80]}")
        print(f"  success_patterns: {len(memory_preflight_data.get('success_patterns', []))}")
        print("--- injection slots ---")
        for key in ("recent_executions", "known_traps", "success_patterns", "strategy_hints"):
            val = slots.get(key, "")
            print(f"  {key}: ({len(val)} chars) {val[:200]}")
        print("=== END DRY-RUN PREFLIGHT ===")
        return EXIT_PASS

    # Optional test accuracy / regression assessment (skill-change workflows)
    test_assessment: dict[str, Any] | None = None
    if args.test_assessment:
        try:
            test_assessment = json.loads(Path(args.test_assessment).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            _log("event=test_assessment_load result=error exception={}", e)
            return EXIT_USAGE_ERROR

    preflight_for_loop = memory_preflight_data if memory_preflight_enabled else None

    # Run the loop
    if args.dry_run:
        trace = _synthesize_dry_run(
            skill=args.skill,
            op=args.op,
            command=args.command,
            user_request=args.user_request,
            rubric=rubric,
            gcl_critic_mode=gcl_critic_mode,
            llm_model=gcl_critic_llm_model,
            enable_hallucination_check=args.enable_hallucination_check,
            test_assessment=test_assessment,
            memory_preflight=preflight_for_loop,
            skills_root=skills_root,
        )
    else:
        trace = run_loop(
            skill=args.skill,
            op=args.op,
            command=args.command,
            user_request=args.user_request,
            rubric=rubric,
            max_iter=max_iter,
            gcl_critic_mode=gcl_critic_mode,
            llm_model=gcl_critic_llm_model,
            enable_hallucination_check=args.enable_hallucination_check,
            test_assessment=test_assessment,
            memory_preflight=preflight_for_loop,
            skills_root=skills_root,
        )

    # Persist trace (strip ephemeral success-store payload before write)
    success_payload = trace.pop("_success_pattern_payload", None)
    try:
        path = persist_trace(trace, args.output_dir)
    except OSError as e:
        print(f"[ERROR] failed to persist trace: {e}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    # Index trace into execution memory (Layer 1 — non‑fatal)
    try:
        mem_rc = memory_store(trace, trace_path=path)
        if mem_rc != 0:
            _log("event=memory_store result=failed rc={} trace={}", mem_rc, path.name)
        else:
            _log("event=memory_store result=success trace={}", path.name)
    except Exception as exc:
        _log("event=memory_store result=error exception={}", exc)

    # Purge unknown.jsonl test artifacts after each GCL run (non‑fatal)
    try:
        purge_result = memory_purge_unknown(apply=True)
        if purge_result["files_removed"] > 0:
            _log("event=memory_purge_unknown removed={} dirs_cleaned={}",
                 purge_result["files_removed"], purge_result["dirs_cleaned"])
    except Exception as exc:
        _log("event=memory_purge_unknown result=error exception={}", exc)

    # Extract and store failure pattern for Reflexion Memory (Layer 2 — non‑fatal)
    try:
        pattern = reflexion_extract(trace)
        if pattern is not None:
            refl_rc = reflexion_store(pattern)
            if refl_rc != 0:
                _log("event=reflexion_store result=failed rc={} trace={}", refl_rc, path.name)
            else:
                _log("event=reflexion_store result=success category={} trace={}",
                     pattern.get("category", "?"), path.name)
        else:
            _log("event=reflexion_store result=skipped trace={} reason=no_pattern", path.name)
    except Exception as exc:
        _log("event=reflexion_store result=error exception={}", exc)

    # Store hard-won PASS success pattern (R4 — non-fatal)
    try:
        if success_payload is not None:
            sp_rc = success_store(success_payload)
            if sp_rc != 0:
                _log("event=success_store result=failed rc={} trace={}", sp_rc, path.name)
            else:
                _log(
                    "event=success_store result=success reason={} trace={}",
                    success_payload.get("capture_reason", "?"),
                    path.name,
                )
        elif trace.get("success_pattern", {}).get("captured") is False:
            _log(
                "event=success_store result=skipped trace={} reason={}",
                path.name,
                trace.get("success_pattern", {}).get("reason", "?"),
            )
    except Exception as exc:
        _log("event=success_store result=error exception={}", exc)

    # R6 remediation tracking — opportunities + PASS streak (non-fatal)
    try:
        rem_result = remediation_apply_from_trace(trace)
        if rem_result.get("traps", 0) > 0:
            streak = rem_result.get("success_streak") or {}
            _log(
                "event=remediation_apply status={} traps={} confirmed={}",
                rem_result.get("status", "?"),
                rem_result.get("traps", 0),
                streak.get("confirmed", 0),
            )
    except Exception as exc:
        _log("event=remediation_apply result=error exception={}", exc)

    # Optional: regenerate failure-patterns.md (debounced via env; weekly GHA also runs report)
    if os.environ.get("GCL_REFLEXION_AUTO_REPORT", "false").lower() == "true":
        try:
            reflexion_report()
        except Exception as exc:
            _log("event=reflexion_report result=error exception={}", exc)
        try:
            success_report()
        except Exception as exc:
            _log("event=success_report result=error exception={}", exc)

    # Print summary
    final = trace["final"]
    adaptive_marker = " [ADAPTIVE]" if args.adaptive and adaptive_reason else ""
    print(f"[GCL] skill={args.skill} op={args.op} status={final['status']} iter={final['iter']}{adaptive_marker}")
    print(f"[GCL] trace: {path}")
    if args.adaptive and adaptive_reason:
        print(f"[GCL] adaptive note: {adaptive_reason}")
    if final["status"] == "PASS":
        return EXIT_PASS
    if final["status"] == "SAFETY_FAIL":
        return EXIT_SAFETY_FAIL
    if final["status"] == "WRAPPER_BYPASS":
        print(f"[GCL] WRAPPER_BYPASS: {final.get('output', '')}", file=sys.stderr)
        return EXIT_WRAPPER_BYPASS
    if final["status"] == "HALLUCINATION_ABORT":
        print(f"[GCL] hallucination report: {final.get('output', '')}", file=sys.stderr)
        return EXIT_HALLUCINATION_ABORT
    if final["status"] == "MAX_ITER":
        return EXIT_MAX_ITER
    return EXIT_MAX_ITER  # RETRY exhausted


if __name__ == "__main__":
    sys.exit(main())
