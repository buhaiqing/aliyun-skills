#!/usr/bin/env python3
"""Batch generate well-architected-assessment.md files for missing skills."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# Skill configurations with product-specific details
SKILL_CONFIGS = {
    "alicloud-ecs-ops": {
        "name": "ECS",
        "chinese_name": "云服务器",
        "resource": "Instance",
        "billing_models": ["Pay-As-You-Go", "Subscription", "Spot", "Reserved Instance"],
        "key_metrics": ["CPUUtilization", "MemoryUsage", "DiskUsage", "NetworkIn/Out"],
        "security_features": ["Security Groups", "Cloud Assistant", "Instance RAM Roles"],
        "backup_methods": ["Snapshots", "Images", "Automatic Snapshot Policy"],
    },
    "alicloud-rds-ops": {
        "name": "RDS",
        "chinese_name": "关系型数据库",
        "resource": "DBInstance",
        "billing_models": ["Pay-As-You-Go", "Subscription", "Serverless"],
        "key_metrics": ["CPUUtilization", "MemoryUsage", "Connections", "IOPS"],
        "security_features": ["VPC Isolation", "SSL Encryption", "TDE", "Audit Logs"],
        "backup_methods": ["Automated Backups", "Manual Backups", "Cross-region Backup"],
    },
    "alicloud-redis-ops": {
        "name": "Redis",
        "chinese_name": "云数据库 Redis",
        "resource": "Instance",
        "billing_models": ["Pay-As-You-Go", "Subscription"],
        "key_metrics": ["CPUUtilization", "MemoryUsage", "Connections", "OpsPerSec"],
        "security_features": ["VPC", "Password Auth", "SSL", "IP Whitelist"],
        "backup_methods": ["AOF Persistence", "RDB Backups", "Manual Backup"],
    },
    "alicloud-vpc-ops": {
        "name": "VPC",
        "chinese_name": "专有网络",
        "resource": "VPC/VSwitch/RouteTable",
        "billing_models": ["Free", "Pay-As-You-Go (NAT/SLB/EIP)"],
        "key_metrics": ["NetworkIn/Out", "ConnectionCount", "BandwidthUtilization"],
        "security_features": ["Security Groups", "Network ACLs", "Flow Logs"],
        "backup_methods": ["Route Table Export", "Network Topology Backup"],
    },
    "alicloud-slb-ops": {
        "name": "SLB",
        "chinese_name": "负载均衡",
        "resource": "LoadBalancer",
        "billing_models": ["Pay-As-You-Go (LCU)", "Pay-By-Bandwidth"],
        "key_metrics": ["QPS", "ActiveConnections", "ResponseTime", "DropConnections"],
        "security_features": ["HTTPS/TLS", "Access Control", "WAF Integration"],
        "backup_methods": ["Configuration Export", "Cross-AZ Redundancy"],
    },
    "alicloud-ram-ops": {
        "name": "RAM",
        "chinese_name": "访问控制",
        "resource": "User/Role/Policy",
        "billing_models": ["Free"],
        "key_metrics": ["ActiveSessions", "AccessKeyAge", "PolicyAttachments"],
        "security_features": ["MFA", "STS Tokens", "Policy Conditions", "AccessKey Rotation"],
        "backup_methods": ["Policy Export", "User/Role Metadata Backup"],
    },
    "alicloud-ack-ops": {
        "name": "ACK",
        "chinese_name": "容器服务 Kubernetes",
        "resource": "Cluster/Node/Namespace",
        "billing_models": ["Pay-As-You-Go", "Subscription (Worker Nodes)"],
        "key_metrics": ["CPUUtilization", "MemoryUsage", "PodCount", "APIServerLatency"],
        "security_features": ["RAM Integration", "Network Policies", "Pod Security", "Image Scanning"],
        "backup_methods": ["etcd Backups", "Application YAML Export", "Velero"],
    },
    "alicloud-eip-ops": {
        "name": "EIP",
        "chinese_name": "弹性公网 IP",
        "resource": "EipAddress",
        "billing_models": ["Pay-By-Traffic", "Pay-By-Bandwidth"],
        "key_metrics": ["Bandwidth", "TrafficIn/Out", "ConnectionCount"],
        "security_features": ["Anti-DDoS", "Access Control", "Binding Limits"],
        "backup_methods": ["Configuration Backup", "Cross-region Migration"],
    },
    "alicloud-nat-ops": {
        "name": "NAT Gateway",
        "chinese_name": "NAT 网关",
        "resource": "NatGateway",
        "billing_models": ["Pay-As-You-Go (LCU)", "Pay-By-Bandwidth"],
        "key_metrics": ["SNAT Connections", "DNAT Rules", "Bandwidth"],
        "security_features": ["Source IP Mapping", "Connection Limits", "Logging"],
        "backup_methods": ["Configuration Export", "Cross-AZ HA"],
    },
    "alicloud-mongodb-ops": {
        "name": "MongoDB",
        "chinese_name": "云数据库 MongoDB",
        "resource": "DBInstance",
        "billing_models": ["Pay-As-You-Go", "Subscription"],
        "key_metrics": ["CPUUtilization", "MemoryUsage", "Connections", "QPS"],
        "security_features": ["VPC", "Account Auth", "SSL", "Audit Logs"],
        "backup_methods": ["Automated Backup", "Point-in-Time Recovery"],
    },
    "alicloud-cms-ops": {
        "name": "CloudMonitor",
        "chinese_name": "云监控",
        "resource": "Alarm/Metric/Dashboard",
        "billing_models": ["Free Tier", "Pay-As-You-Go (API Calls)"],
        "key_metrics": ["API Calls", "Custom Metrics", "Alarm Notifications"],
        "security_features": ["RAM Integration", "Webhook Auth", "Access Control"],
        "backup_methods": ["Alarm Rule Export", "Dashboard JSON Backup"],
    },
    "alicloud-das-ops": {
        "name": "DAS",
        "chinese_name": "数据库自治服务",
        "resource": "Instance/Alarm",
        "billing_models": ["Pay-As-You-Go", "Subscription"],
        "key_metrics": ["Active Sessions", "Slow Queries", "Storage"],
        "security_features": ["SQL Audit", "Access Control", "Encryption"],
        "backup_methods": ["Auto Scaling History", "SQL Analysis Export"],
    },
    "alicloud-actiontrail-ops": {
        "name": "ActionTrail",
        "chinese_name": "操作审计",
        "resource": "Trail/Event",
        "billing_models": ["Free", "Pay-As-You-Go (OSS/SLS Storage)"],
        "key_metrics": ["EventCount", "StorageSize", "QueryLatency"],
        "security_features": ["Immutable Logs", "KMS Encryption", "Integrity Validation"],
        "backup_methods": ["OSS Archive", "SLS Storage", "Multi-region Trail"],
    },
    "alicloud-polar-mysql-ops": {
        "name": "PolarDB MySQL",
        "chinese_name": "云原生关系型数据库 MySQL",
        "resource": "DBCluster",
        "billing_models": ["Pay-As-You-Go", "Subscription", "Serverless"],
        "key_metrics": ["CPUUtilization", "MemoryUsage", "Connections", "QPS/TPS"],
        "security_features": ["VPC", "SSL", "TDE", "Database Audit"],
        "backup_methods": ["Automated Backup", "Log Backup", "Cross-region Backup"],
    },
    "alicloud-polar-postgresql-ops": {
        "name": "PolarDB PostgreSQL",
        "chinese_name": "云原生关系型数据库 PostgreSQL",
        "resource": "DBCluster",
        "billing_models": ["Pay-As-You-Go", "Subscription", "Serverless"],
        "key_metrics": ["CPUUtilization", "MemoryUsage", "Connections", "QPS/TPS"],
        "security_features": ["VPC", "SSL", "TDE", "Database Audit"],
        "backup_methods": ["Automated Backup", "Log Backup", "Cross-region Backup"],
    },
    "alicloud-polar-oracle-ops": {
        "name": "PolarDB Oracle",
        "chinese_name": "云原生关系型数据库 Oracle 兼容版",
        "resource": "DBCluster",
        "billing_models": ["Pay-As-You-Go", "Subscription"],
        "key_metrics": ["CPUUtilization", "MemoryUsage", "Connections", "QPS/TPS"],
        "security_features": ["VPC", "SSL", "TDE", "Database Audit"],
        "backup_methods": ["Automated Backup", "Log Backup", "Cross-region Backup"],
    },
    "alicloud-resourcemanager-ops": {
        "name": "Resource Manager",
        "chinese_name": "资源管理",
        "resource": "Folder/Account/ResourceGroup",
        "billing_models": ["Free"],
        "key_metrics": ["ResourceCount", "AccountCount", "PolicyAttachments"],
        "security_features": ["Folder Hierarchy", "Control Policies", "Tag Policies"],
        "backup_methods": ["Resource Hierarchy Export", "Control Policy Backup"],
    },
    "alicloud-gcl-runner-ops": {
        "name": "GCL Runner",
        "chinese_name": "GCL 质量门禁运行器",
        "resource": "Trace/Rubric",
        "billing_models": ["Free (Local Execution)"],
        "key_metrics": ["PassRate", "ExecutionTime", "IterationCount"],
        "security_features": ["Secret Masking", "Trace Sanitization", "No External Calls"],
        "backup_methods": ["Trace Archive", "Rubric Version Control"],
    },
}


def generate_template(skill_name: str, config: dict) -> str:
    """Generate well-architected-assessment.md content for a skill."""

    billing_table = "\n".join(
        [f"| {model} | Use Case | Savings |" for model in config["billing_models"]]
    ) if len(config["billing_models"]) > 1 else f"| {config['billing_models'][0]} | All workloads | N/A |"

    metrics_table = "\n".join(
        [f"| {metric} | acs_{skill_name.replace('-ops', '').replace('-', '_')} | Threshold |" for metric in config["key_metrics"]]
    )

    security_list = "\n".join([f"- {feat}" for feat in config["security_features"]])
    backup_list = "\n".join([f"- {method}" for method in config["backup_methods"]])

    return f'''# Well-Architected Assessment — Alibaba Cloud {config['name']}

This document evaluates the {config['name']} skill's operations against Alibaba Cloud's
[Well-Architected Framework](https://help.aliyun.com/zh/product/2362200.html).

## 安全 (Security)

### Identity & Access Management

| Requirement | Guidance |
|-------------|----------|
| **RAM Policy** | Use scoped permissions: `acs:{config['name'].lower()}:*:*:{config['resource'].lower()}/*`. Avoid wildcard `*` actions. |
| **Least Privilege** | Create dedicated RAM users/roles with minimum required permissions. Never use `AdministratorAccess`. |
| **STS Tokens** | Use `AssumeRole` for temporary access with 1-hour expiry for automation. |
| **AccessKey Rotation** | Rotate AccessKeys every 90 days. Use `DisableAccessKey` to revoke compromised keys. |

### Network Security

{security_list}

### Data Protection

- Enable encryption at rest for sensitive data
- Use HTTPS endpoints for all API calls
- Enable audit logging for compliance

## 稳定 (Stability)

### Failure-Oriented Design

- All operations follow Pre-flight → Execute → Validate → Recover pattern
- Document idempotent behavior for retry scenarios
- Identify failure domains and blast radius

### Backup & Recovery

{backup_list}

### Recovery Objectives

| Metric | Target | Measurement |
|--------|--------|-------------|
| RTO | < 4 hours | Time to restore service |
| RPO | < 1 hour | Data loss window |

## 成本 (Cost)

### Billing Model Selection

| Billing Type | Best Use Case | Savings |
|-------------|---------------|---------|
{billing_table}

### Cost Optimization

- Monitor resource utilization and right-size
- Use Reserved Instances for predictable workloads
- Enable auto-decommission for temporary resources

## 效率 (Efficiency)

### Automation

- Use batch APIs for operations on ≥ 3 resources
- Document concurrency limits
- Integrate with CI/CD pipelines

### Operational Integration

- Map skill errors to CMS alarm rules
- Document escalation paths
- Maintain change history via ActionTrail

## 性能 (Performance)

### Key Metrics

| Metric | Namespace | Optimization Action |
|--------|-----------|---------------------|
{metrics_table}

### Scaling Patterns

- Horizontal scaling: add/remove instances
- Vertical scaling: modify instance specifications
- Auto-scaling: configure thresholds based on metrics

---

*This assessment follows the Well-Architected Framework five pillars: Security, Stability, Cost, Efficiency, Performance.*
'''


def main():
    """Generate well-architected-assessment.md for all configured skills."""
    generated = []
    skipped = []

    for skill_name, config in SKILL_CONFIGS.items():
        skill_dir = REPO_ROOT / skill_name
        ref_dir = skill_dir / "references"
        target_file = ref_dir / "well-architected-assessment.md"

        if not skill_dir.exists():
            skipped.append(f"{skill_name}: directory not found")
            continue

        if target_file.exists():
            skipped.append(f"{skill_name}: already exists")
            continue

        # Create references directory if needed
        ref_dir.mkdir(exist_ok=True)

        # Generate and write content
        content = generate_template(skill_name, config)
        target_file.write_text(content, encoding="utf-8")
        generated.append(skill_name)

    # Print report
    print("=" * 60)
    print("Well-Architected Assessment Generation Report")
    print("=" * 60)
    print(f"\nGenerated: {len(generated)} files")
    for skill in generated:
        print(f"  ✓ {skill}")

    if skipped:
        print(f"\nSkipped: {len(skipped)}")
        for reason in skipped:
            print(f"  - {reason}")

    print("\n" + "=" * 60)
    return 0 if generated else 1


if __name__ == "__main__":
    sys.exit(main())
