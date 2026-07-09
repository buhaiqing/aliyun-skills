#!/usr/bin/env python3
"""
Resource Registry - 渐进式资源支持机制

提供统一的资源类型注册、能力预检和优雅降级处理。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SupportLevel(Enum):
    """资源支持级别"""
    FULL = "full"           # 完整支持：发现 + HCL生成 + 导入
    PARTIAL = "partial"     # 部分支持：发现 + 基础HCL（可能有警告）
    EXPERIMENTAL = "experimental"  # 实验性：功能可用但可能不稳定
    PLANNED = "planned"     # 计划中：已识别需求但未实现
    UNSUPPORTED = "unsupported"    # 不支持：明确不支持的资源


class ResourceCapability(Enum):
    """资源能力标识"""
    DISCOVER = "discover"           # 资源发现
    HCL_GENERATE = "hcl_generate"   # HCL生成
    IMPORT = "import"               # Terraform导入
    ASSOCIATED_DISCOVER = "associated_discover"  # 关联资源发现


@dataclass
class ResourceTypeInfo:
    """资源类型信息"""
    name: str                           # 资源类型名称（如 rds）
    tf_type: str                        # Terraform资源类型（如 alicloud_db_instance）
    api_product: str                    # 阿里云产品代码（如 rds）
    api_action: str                     # 查询API名称
    id_param: str                       # ID参数名
    support_level: SupportLevel         # 支持级别
    capabilities: set[ResourceCapability] = field(default_factory=set)
    missing_capabilities: set[ResourceCapability] = field(default_factory=set)
    known_issues: list[str] = field(default_factory=list)
    added_date: str | None = None    # 添加日期
    last_verified: str | None = None # 最后验证日期

    def is_capable(self, capability: ResourceCapability) -> bool:
        """检查是否支持特定能力"""
        return capability in self.capabilities

    def to_preflight_report(self) -> dict[str, Any]:
        """生成预检报告"""
        return {
            "name": self.name,
            "terraform_type": self.tf_type,
            "support_level": self.support_level.value,
            "capabilities": [c.value for c in self.capabilities],
            "missing": [c.value for c in self.missing_capabilities],
            "known_issues": self.known_issues,
            "verified": self.last_verified or "never"
        }


@dataclass
class PreFlightResult:
    """PreFlight 检查结果"""
    resource_type: str
    supported: bool
    level: SupportLevel
    message: str
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    can_proceed: bool = False
    fallback_available: bool = False


class ResourceRegistry:
    """
    资源注册中心
    
    统一管理所有支持的资源类型，提供能力查询和预检功能。
    """

    # 内置资源注册表
    _REGISTRY: dict[str, ResourceTypeInfo] = {
        # 完整支持
        "vpc": ResourceTypeInfo(
            name="vpc",
            tf_type="alicloud_vpc",
            api_product="vpc",
            api_action="DescribeVpcAttribute",
            id_param="VpcId",
            support_level=SupportLevel.FULL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT,
                ResourceCapability.ASSOCIATED_DISCOVER
            },
            known_issues=[
                "关联发现: VSwitch/RouteTable/NAT Gateway"
            ],
            added_date="2024-06-01",
            last_verified="2026-06-08"
        ),

        "vswitch": ResourceTypeInfo(
            name="vswitch",
            tf_type="alicloud_vswitch",
            api_product="vpc",
            api_action="DescribeVSwitchAttributes",
            id_param="VSwitchId",
            support_level=SupportLevel.FULL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT
            },
            added_date="2024-06-01",
            last_verified="2024-06-08"
        ),

        "ecs": ResourceTypeInfo(
            name="ecs",
            tf_type="alicloud_instance",
            api_product="ecs",
            api_action="DescribeInstances",
            id_param="InstanceIds",
            support_level=SupportLevel.FULL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT,
                ResourceCapability.ASSOCIATED_DISCOVER,
            },
            known_issues=[
                "关联发现: VSwitch/SecurityGroup/数据盘 (不含 disk_attachment)"
            ],
            added_date="2024-06-01",
            last_verified="2026-06-08"
        ),

        # 部分支持 - 已实现但可能不完整
        "rds": ResourceTypeInfo(
            name="rds",
            tf_type="alicloud_db_instance",
            api_product="rds",
            api_action="DescribeDBInstanceAttribute",
            id_param="DBInstanceId",
            support_level=SupportLevel.PARTIAL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT,
                ResourceCapability.ASSOCIATED_DISCOVER,
            },
            missing_capabilities=set(),
            known_issues=[
                "关联发现: VPC/VSwitch",
                "暂不支持自动发现关联的数据库账号",
                "暂不支持只读实例关联"
            ],
            added_date="2024-06-08",
            last_verified="2024-06-08"
        ),

        "redis": ResourceTypeInfo(
            name="redis",
            tf_type="alicloud_kvstore_instance",
            api_product="r-kvstore",
            api_action="DescribeInstanceAttribute",
            id_param="InstanceId",
            support_level=SupportLevel.PARTIAL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT
            },
            missing_capabilities={ResourceCapability.ASSOCIATED_DISCOVER},
            known_issues=[
                "暂不支持 Redis Cluster 模式"
            ],
            added_date="2024-06-08",
            last_verified="2024-06-08"
        ),

        "slb": ResourceTypeInfo(
            name="slb",
            tf_type="alicloud_slb_load_balancer",
            api_product="slb",
            api_action="DescribeLoadBalancerAttribute",
            id_param="LoadBalancerId",
            support_level=SupportLevel.PARTIAL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT,
                ResourceCapability.ASSOCIATED_DISCOVER,
            },
            missing_capabilities=set(),
            known_issues=[
                "关联发现: VPC/VSwitch/后端 ECS",
                "暂不支持监听器自动发现",
                "暂不支持后端服务器组 HCL"
            ],
            added_date="2024-06-08",
            last_verified="2024-06-08"
        ),

        "eip": ResourceTypeInfo(
            name="eip",
            tf_type="alicloud_eip_address",
            api_product="vpc",
            api_action="DescribeEipAddresses",
            id_param="AllocationId",
            support_level=SupportLevel.PARTIAL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT
            },
            known_issues=[
                "暂不支持自动发现绑定的ECS/SLB"
            ],
            added_date="2024-06-08",
            last_verified="2024-06-08"
        ),

        "security_group": ResourceTypeInfo(
            name="security_group",
            tf_type="alicloud_security_group",
            api_product="ecs",
            api_action="DescribeSecurityGroupAttribute",
            id_param="SecurityGroupId",
            support_level=SupportLevel.PARTIAL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT
            },
            missing_capabilities={ResourceCapability.ASSOCIATED_DISCOVER},
            known_issues=[
                "暂不支持安全组规则导入"
            ],
            added_date="2024-06-08",
            last_verified="2024-06-08"
        ),

        "disk": ResourceTypeInfo(
            name="disk",
            tf_type="alicloud_disk",
            api_product="ecs",
            api_action="DescribeDisks",
            id_param="DiskIds",
            support_level=SupportLevel.PARTIAL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT,
            },
            missing_capabilities={ResourceCapability.ASSOCIATED_DISCOVER},
            known_issues=[
                "仅导入数据盘 (跳过系统盘)",
                "已挂载磁盘需单独 import alicloud_disk_attachment",
            ],
            added_date="2026-06-08",
            last_verified="2026-06-08",
        ),

        "route_table": ResourceTypeInfo(
            name="route_table",
            tf_type="alicloud_route_table",
            api_product="vpc",
            api_action="DescribeRouteTableAttribute",
            id_param="RouteTableId",
            support_level=SupportLevel.PARTIAL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT,
            },
            missing_capabilities=set(),
            known_issues=[
                "关联发现: VPC 导入时自动发现",
                "暂不支持 alicloud_route_entry 规则导入",
            ],
            added_date="2026-06-08",
            last_verified="2026-06-08",
        ),

        "nat_gateway": ResourceTypeInfo(
            name="nat_gateway",
            tf_type="alicloud_nat_gateway",
            api_product="vpc",
            api_action="DescribeNatGateways",
            id_param="NatGatewayId",
            support_level=SupportLevel.PARTIAL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT,
            },
            missing_capabilities={ResourceCapability.ASSOCIATED_DISCOVER},
            known_issues=[
                "暂不支持 SNAT/DNAT 规则导入"
            ],
            added_date="2026-06-08",
            last_verified="2026-06-08"
        ),

        "alb": ResourceTypeInfo(
            name="alb",
            tf_type="alicloud_alb_load_balancer",
            api_product="alb",
            api_action="GetLoadBalancerAttribute",
            id_param="LoadBalancerId",
            support_level=SupportLevel.PARTIAL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT,
            },
            missing_capabilities={ResourceCapability.ASSOCIATED_DISCOVER},
            known_issues=[
                "暂不支持监听器规则自动发现"
            ],
            added_date="2026-07-03",
            last_verified="2026-07-03"
        ),

        "waf": ResourceTypeInfo(
            name="waf",
            tf_type="alicloud_wafv3_instance",
            api_product="waf",
            api_action="DescribeInstance",
            id_param="InstanceId",
            support_level=SupportLevel.PARTIAL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT,
            },
            missing_capabilities={ResourceCapability.ASSOCIATED_DISCOVER},
            known_issues=[
                "暂不支持 WAF 防护规则配置导入"
            ],
            added_date="2026-07-03",
            last_verified="2026-07-03"
        ),

        "mongodb": ResourceTypeInfo(
            name="mongodb",
            tf_type="alicloud_mongodb_instance",
            api_product="dds",
            api_action="DescribeDBInstanceAttribute",
            id_param="DBInstanceId",
            support_level=SupportLevel.PARTIAL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT,
            },
            missing_capabilities={ResourceCapability.ASSOCIATED_DISCOVER},
            known_issues=[
                "暂不支持副本集成员自动发现"
            ],
            added_date="2026-06-08",
            last_verified="2026-06-08"
        ),

        "polardb": ResourceTypeInfo(
            name="polardb",
            tf_type="alicloud_polardb_cluster",
            api_product="polardb",
            api_action="DescribeDBClusterAttribute",
            id_param="DBClusterId",
            support_level=SupportLevel.PARTIAL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT,
            },
            missing_capabilities={ResourceCapability.ASSOCIATED_DISCOVER},
            known_issues=[
                "暂不支持 PolarDB 节点自动发现"
            ],
            added_date="2026-06-08",
            last_verified="2026-06-08"
        ),

        "oss": ResourceTypeInfo(
            name="oss",
            tf_type="alicloud_oss_bucket",
            api_product="oss",
            api_action="GetBucketInfo",
            id_param="Bucket",
            support_level=SupportLevel.PARTIAL,
            capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT,
            },
            missing_capabilities={ResourceCapability.ASSOCIATED_DISCOVER},
            known_issues=[
                "暂不支持 Bucket 策略/生命周期规则导入"
            ],
            added_date="2026-06-08",
            last_verified="2026-06-08"
        ),

        # 计划中
        "autoscaling": ResourceTypeInfo(
            name="autoscaling",
            tf_type="alicloud_ess_scaling_group",
            api_product="ess",
            api_action="DescribeScalingGroups",
            id_param="ScalingGroupId",
            support_level=SupportLevel.PLANNED,
            capabilities=set(),
            missing_capabilities={
                ResourceCapability.DISCOVER,
                ResourceCapability.HCL_GENERATE,
                ResourceCapability.IMPORT,
            },
            added_date=None,
            last_verified=None,
        ),
    }

    def __init__(self):
        self._custom_resources: dict[str, ResourceTypeInfo] = {}

    def get(self, resource_type: str) -> ResourceTypeInfo | None:
        """获取资源类型信息"""
        # 先查自定义注册表
        if resource_type in self._custom_resources:
            return self._custom_resources[resource_type]
        # 再查内置注册表
        return self._REGISTRY.get(resource_type)

    def list_all(self) -> list[ResourceTypeInfo]:
        """列出所有支持的资源类型"""
        all_resources = dict(self._REGISTRY)
        all_resources.update(self._custom_resources)
        return list(all_resources.values())

    def list_by_level(self, level: SupportLevel) -> list[ResourceTypeInfo]:
        """按支持级别列出资源类型"""
        return [
            r for r in self.list_all()
            if r.support_level == level
        ]

    def list_supported(self) -> list[ResourceTypeInfo]:
        """列出所有可操作的资源类型（FULL + PARTIAL + EXPERIMENTAL）"""
        supported_levels = {
            SupportLevel.FULL,
            SupportLevel.PARTIAL,
            SupportLevel.EXPERIMENTAL
        }
        return [
            r for r in self.list_all()
            if r.support_level in supported_levels
        ]

    def register(self, info: ResourceTypeInfo) -> None:
        """注册自定义资源类型"""
        self._custom_resources[info.name] = info

    def preflight_check(
        self,
        resource_type: str,
        required_capabilities: set[ResourceCapability] | None = None
    ) -> PreFlightResult:
        """
        PreFlight 预检
        
        Args:
            resource_type: 资源类型名称
            required_capabilities: 必需的能力集合
        
        Returns:
            PreFlightResult 检查结果
        """
        required_capabilities = required_capabilities or {
            ResourceCapability.DISCOVER,
            ResourceCapability.HCL_GENERATE
        }

        info = self.get(resource_type)

        # 未知资源类型
        if info is None:
            return PreFlightResult(
                resource_type=resource_type,
                supported=False,
                level=SupportLevel.UNSUPPORTED,
                message=f"❌ 不支持的资源类型: {resource_type}",
                warnings=["该资源类型尚未在注册表中定义"],
                suggestions=[
                    "请检查资源类型名称是否正确",
                    f"查看支持的类型: {', '.join(self.list_supported_names())}",
                    "如需支持该类型，请在 GitHub 提交 Issue"
                ],
                can_proceed=False,
                fallback_available=False
            )

        # 检查支持级别
        if info.support_level == SupportLevel.UNSUPPORTED:
            return PreFlightResult(
                resource_type=resource_type,
                supported=False,
                level=SupportLevel.UNSUPPORTED,
                message=f"❌ 资源类型 '{resource_type}' 明确不支持",
                warnings=info.known_issues,
                suggestions=[
                    "该资源类型被标记为不支持，可能有技术限制",
                    "请联系管理员了解详情"
                ],
                can_proceed=False,
                fallback_available=False
            )

        if info.support_level == SupportLevel.PLANNED:
            return PreFlightResult(
                resource_type=resource_type,
                supported=False,
                level=SupportLevel.PLANNED,
                message=f"⏳ 资源类型 '{resource_type}' 正在开发中",
                warnings=["该功能尚未实现"],
                suggestions=[
                    "该资源类型计划在未来的版本中支持",
                    "当前版本: 请关注更新日志",
                    "如需提前使用，请联系开发团队"
                ],
                can_proceed=False,
                fallback_available=False
            )

        # 检查必需能力
        missing = required_capabilities - info.capabilities

        if missing:
            # 有缺失能力，但可能仍可继续
            can_proceed = info.support_level in {
                SupportLevel.FULL, SupportLevel.PARTIAL, SupportLevel.EXPERIMENTAL
            }

            return PreFlightResult(
                resource_type=resource_type,
                supported=True,
                level=info.support_level,
                message=f"⚠️ 资源类型 '{resource_type}' 部分支持 ({info.support_level.value})",
                warnings=[
                    f"缺少能力: {', '.join(c.value for c in missing)}"
                ] + info.known_issues,
                suggestions=[
                    "可以继续执行，但功能可能受限",
                    "建议检查生成的HCL配置",
                    "考虑手动补充缺失的部分"
                ],
                can_proceed=can_proceed,
                fallback_available=True
            )

        # 完整支持
        status_icon = {
            SupportLevel.FULL: "✅",
            SupportLevel.PARTIAL: "⚡",
            SupportLevel.EXPERIMENTAL: "🧪"
        }.get(info.support_level, "✓")

        return PreFlightResult(
            resource_type=resource_type,
            supported=True,
            level=info.support_level,
            message=f"{status_icon} 资源类型 '{resource_type}' 支持 ({info.support_level.value})",
            warnings=info.known_issues,
            suggestions=[],
            can_proceed=True,
            fallback_available=False
        )

    def list_supported_names(self) -> list[str]:
        """列出支持的资源类型名称"""
        return [r.name for r in self.list_supported()]

    def generate_support_matrix(self) -> str:
        """生成支持矩阵文档"""
        lines = [
            "# Terraform IaC 资源支持矩阵\n",
            "| 资源类型 | Terraform类型 | 支持级别 | 能力 | 已知问题 |",
            "|---------|--------------|---------|------|---------|"
        ]

        for info in sorted(self.list_all(), key=lambda x: x.name):
            caps = ", ".join(c.value for c in info.capabilities) or "-"
            issues = "; ".join(info.known_issues) or "-"

            level_icon = {
                SupportLevel.FULL: "✅",
                SupportLevel.PARTIAL: "⚡",
                SupportLevel.EXPERIMENTAL: "🧪",
                SupportLevel.PLANNED: "⏳",
                SupportLevel.UNSUPPORTED: "❌"
            }.get(info.support_level, "?")

            lines.append(
                f"| {info.name} | {info.tf_type} | "
                f"{level_icon} {info.support_level.value} | {caps} | {issues} |"
            )

        return "\n".join(lines)


class CapabilityChecker:
    """
    能力检查器 - 在 PreFlight 阶段使用
    """

    def __init__(self, registry: ResourceRegistry | None = None):
        self.registry = registry or ResourceRegistry()

    def check_import_request(
        self,
        resource_types: list[str],
        fail_fast: bool = True
    ) -> dict[str, PreFlightResult]:
        """
        检查导入请求
        
        Args:
            resource_types: 资源类型列表
            fail_fast: 遇到不支持类型时立即失败
        
        Returns:
            各资源类型的检查结果
        """
        results = {}
        has_unsupported = False

        for rtype in resource_types:
            result = self.registry.preflight_check(rtype)
            results[rtype] = result

            if not result.can_proceed:
                has_unsupported = True
                if fail_fast:
                    break

        return results

    def generate_report(self, results: dict[str, PreFlightResult]) -> str:
        """生成检查报告"""
        lines = ["\n" + "=" * 60, "PreFlight 资源能力检查报告", "=" * 60]

        all_supported = all(r.can_proceed for r in results.values())

        for rtype, result in results.items():
            lines.append(f"\n{result.message}")

            if result.warnings:
                lines.append("  警告:")
                for w in result.warnings:
                    lines.append(f"    - {w}")

            if result.suggestions:
                lines.append("  建议:")
                for s in result.suggestions:
                    lines.append(f"    • {s}")

        lines.extend([
            "",
            "=" * 60,
            f"检查结果: {'✅ 通过' if all_supported else '❌ 未通过'}",
            "=" * 60
        ])

        return "\n".join(lines)


# 全局注册表实例
_default_registry: ResourceRegistry | None = None


def get_registry() -> ResourceRegistry:
    """获取全局注册表实例"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ResourceRegistry()
    return _default_registry


if __name__ == "__main__":
    # 测试代码
    registry = ResourceRegistry()

    print("支持的资源类型:")
    for r in registry.list_supported():
        print(f"  - {r.name} ({r.support_level.value})")

    print("\n" + "=" * 60)
    print("PreFlight 检查示例:\n")

    # 测试支持的类型
    result = registry.preflight_check("vpc")
    print(f"vpc: {result.message}")

    # 测试部分支持的类型
    result = registry.preflight_check("rds")
    print(f"rds: {result.message}")
    if result.warnings:
        print(f"  警告: {result.warnings}")

    # 测试计划中的类型
    result = registry.preflight_check("mongodb")
    print(f"mongodb: {result.message}")
    print(f"  建议: {result.suggestions[0] if result.suggestions else 'N/A'}")

    # 测试未知类型
    result = registry.preflight_check("unknown_resource")
    print(f"unknown_resource: {result.message}")

    print("\n" + "=" * 60)
    print("支持矩阵:")
    print(registry.generate_support_matrix())
