#!/usr/bin/env python3
"""
module_catalog.py — Module-first NL2HCL 模块目录与物化

根目录 main.tf 仅包含 module 块；资源实现位于 alicloud-terraform-ops/modules/。
"""

from __future__ import annotations

import shutil
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MODULES_ROOT = Path(__file__).resolve().parent.parent / "modules"


@dataclass
class ModulePlan:
    """根模块编排计划."""

    use_web_stack: bool = False
    use_vpc_network: bool = False
    use_route_table: bool = False
    use_standalone_disk: bool = False
    use_standalone_eip: bool = False

    enable_ecs: bool = False
    enable_rds: bool = False
    enable_redis: bool = False
    enable_slb: bool = False
    enable_nat: bool = False
    enable_eip_in_stack: bool = False
    enable_mongodb: bool = False
    enable_oss: bool = False
    enable_polardb: bool = False
    enable_alb: bool = False

    ecs_count: int = 1
    az_count: int = 2
    ecs_data_disk_size: int = 0
    standalone_disk_size: int = 100
    instance_type: str = ""
    vpc_cidr: str = ""
    rds_instance_class: str = ""
    mongodb_instance_class: str = ""
    polardb_instance_class: str = ""

    modules_used: set[str] = field(default_factory=set)

    def record(self, *names: str) -> None:
        self.modules_used.update(names)


def plan_modules(intent: dict[str, Any], defaults: dict[str, str]) -> ModulePlan:
    """根据 parse_intent 结果选择 module-first 编排."""
    resources = set(intent.get("resources", []))
    plan = ModulePlan(
        ecs_count=intent.get("count", 1),
        az_count=intent.get("az_count", 2),
        ecs_data_disk_size=intent.get("data_disk_size") or 0,
        standalone_disk_size=intent.get("data_disk_size") or 100,
        instance_type=intent.get("instance_type") or defaults.get("instance_type", "ecs.g7.large"),
        vpc_cidr=defaults.get("vpc_cidr", "10.0.0.0/16"),
        rds_instance_class=defaults.get("rds_class", "rds.mysql.s1.small"),
        mongodb_instance_class=intent.get("mongodb_instance_class")
            or defaults.get("mongodb_class", "dds.mongo.shard.small"),
        polardb_instance_class=intent.get("polardb_instance_class")
            or defaults.get("polardb_class", "polar.mysql.x4.medium"),
    )

    has_ecs = "alicloud_instance" in resources
    has_rds = "alicloud_db_instance" in resources
    has_redis = "alicloud_kvstore_instance" in resources
    has_slb = "alicloud_slb" in resources
    has_nat = "alicloud_nat_gateway" in resources
    has_eip = "alicloud_eip" in resources
    has_route = "alicloud_route_table" in resources
    has_mongodb = "alicloud_mongodb_instance" in resources
    has_oss = "alicloud_oss_bucket" in resources
    has_polardb = "alicloud_polardb_cluster" in resources
    has_alb = "alicloud_alb_load_balancer" in resources
    has_security_group_standalone = "alicloud_security_group" in resources and "alicloud_instance" not in resources
    has_waf = "alicloud_wafv3_instance" in resources
    has_standalone_disk = bool(intent.get("wants_standalone_disk")) or (
        "alicloud_disk" in resources and not has_ecs
    )

    stack_addons = has_ecs or has_rds or has_redis or has_slb or has_nat or has_mongodb or has_polardb or has_alb
    network_explicit = "alicloud_vpc" in resources or "alicloud_vswitch" in resources

    if stack_addons or (has_eip and network_explicit):
        plan.use_web_stack = True
        plan.record("web-stack", "vpc-network")
        plan.enable_ecs = has_ecs
        plan.enable_rds = has_rds
        plan.enable_redis = has_redis
        plan.enable_slb = has_slb
        plan.enable_nat = has_nat
        plan.enable_eip_in_stack = has_eip
        plan.enable_mongodb = has_mongodb
        plan.enable_polardb = has_polardb
        plan.enable_alb = has_alb
        if has_ecs:
            plan.record("compute-ecs")
        if has_rds:
            plan.record("addon-rds")
        if has_redis:
            plan.record("addon-redis")
        if has_slb:
            plan.record("addon-slb")
        if has_nat:
            plan.record("addon-nat")
        if has_eip:
            plan.record("addon-eip")
        if has_mongodb:
            plan.record("addon-mongodb")
        if has_polardb:
            plan.record("addon-polardb")
        if has_alb:
            plan.record("addon-alb")
    elif network_explicit or has_route or has_standalone_disk:
        plan.use_vpc_network = True
        plan.record("vpc-network")

    if has_route and not plan.use_web_stack:
        plan.use_route_table = True
        plan.record("addon-route-table")

    if has_standalone_disk and not plan.use_web_stack:
        plan.use_standalone_disk = True
        plan.record("addon-disk")

    if has_eip and not plan.use_web_stack:
        plan.use_standalone_eip = True
        plan.record("addon-eip")

    # 仅 EIP、无任何网络关键词时仍生成独立 EIP
    if has_eip and not plan.use_web_stack and not plan.use_vpc_network:
        plan.use_standalone_eip = True
        plan.record("addon-eip")

    # 独立 MongoDB（无 ECS 等 addon 时走独立路径）
    if has_mongodb and not plan.use_web_stack:
        if not plan.use_vpc_network:
            plan.use_vpc_network = True
            plan.record("vpc-network")
        plan.record("addon-mongodb")

    # 独立 OSS（不依赖 VPC，可直接独立）
    if has_oss:
        plan.enable_oss = True
        plan.record("addon-oss")

    # 独立 PolarDB
    if has_polardb and not plan.use_web_stack:
        if not plan.use_vpc_network:
            plan.use_vpc_network = True
            plan.record("vpc-network")
        plan.record("addon-polardb")

    # 独立 ALB
    if has_alb and not plan.use_web_stack:
        if not plan.use_vpc_network:
            plan.use_vpc_network = True
            plan.record("vpc-network")
        plan.record("addon-alb")

    # 独立安全组（无 ECS 时走独立路径）
    if has_security_group_standalone and not plan.use_web_stack:
        if not plan.use_vpc_network:
            plan.use_vpc_network = True
            plan.record("vpc-network")
        plan.record("addon-security-group")

    # WAF（不绑定 web-stack，独立渲染）
    if has_waf:
        plan.record("addon-waf")

    return plan


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def render_main_tf(plan: ModulePlan, environment: str, region: str) -> str:
    """生成仅含 module 块的 root main.tf."""
    blocks: list[str] = []

    if plan.use_web_stack:
        data_disk = plan.ecs_data_disk_size if plan.enable_ecs else 0
        blocks.append(textwrap.dedent(f"""\
            module "web_stack" {{
              source = "./modules/web-stack"

              providers = {{
                alicloud = alicloud
              }}

              environment         = var.environment
              region              = var.region
              vpc_cidr            = "{plan.vpc_cidr}"
              az_count            = {plan.az_count}

              enable_ecs          = {_bool_str(plan.enable_ecs)}
              ecs_instance_type   = "{plan.instance_type}"
              ecs_count           = {plan.ecs_count}
              ecs_data_disk_size  = {data_disk}

              enable_rds          = {_bool_str(plan.enable_rds)}
              rds_instance_class  = "{plan.rds_instance_class}"
              enable_redis        = {_bool_str(plan.enable_redis)}
              enable_slb          = {_bool_str(plan.enable_slb)}
              enable_nat          = {_bool_str(plan.enable_nat)}
              enable_eip          = {_bool_str(plan.enable_eip_in_stack)}
              enable_mongodb      = {_bool_str(plan.enable_mongodb)}
              mongodb_instance_class = "{plan.mongodb_instance_class}"
              enable_polardb      = {_bool_str(plan.enable_polardb)}
              polardb_instance_class = "{plan.polardb_instance_class}"
              enable_alb          = {_bool_str(plan.enable_alb)}
            }}
        """))

    if plan.use_vpc_network:
        blocks.append(textwrap.dedent(f"""\
            module "vpc_network" {{
              source = "./modules/vpc-network"

              providers = {{
                alicloud = alicloud
              }}

              environment = var.environment
              region      = var.region
              vpc_cidr    = "{plan.vpc_cidr}"
              az_count    = {plan.az_count}
            }}
        """))

    # 独立 MongoDB（不在 web-stack 内时）
    if plan.enable_mongodb and not plan.use_web_stack:
        blocks.append(textwrap.dedent(f"""\
            module "mongodb" {{
              source = "./modules/addon-mongodb"

              providers = {{
                alicloud = alicloud
              }}

              environment         = var.environment
              vswitch_id          = module.vpc_network.primary_vswitch_id
              mongodb_instance_class = "{plan.mongodb_instance_class}"
              mongodb_engine_version = "4.2"
              mongodb_storage     = 20
            }}
        """))

    # 独立 OSS（不依赖 VPC，独立渲染）
    if plan.enable_oss:
        blocks.append(textwrap.dedent("""\
            module "oss" {
              source = "./modules/addon-oss"

              providers = {
                alicloud = alicloud
              }

              environment = var.environment
              bucket_name = "${var.environment}-oss-${var.region}"
            }
        """))

    # 独立 PolarDB（不在 web-stack 内时）
    if plan.enable_polardb and not plan.use_web_stack:
        blocks.append(textwrap.dedent(f"""\
            module "polardb" {{
              source = "./modules/addon-polardb"

              providers = {{
                alicloud = alicloud
              }}

              environment          = var.environment
              vswitch_id           = module.vpc_network.primary_vswitch_id
              polardb_engine       = "MySQL"
              polardb_engine_version = "8.0"
              polardb_instance_class = "{plan.polardb_instance_class}"
            }}
        """))

    # 独立 ALB（不在 web-stack 内时）
    if plan.enable_alb and not plan.use_web_stack:
        blocks.append(textwrap.dedent("""\
            module "alb" {
              source = "./modules/addon-alb"

              providers = {
                alicloud = alicloud
              }

              environment    = var.environment
              vpc_id         = module.vpc_network.vpc_id
              vswitch_id     = module.vpc_network.primary_vswitch_id
              zone_id        = module.vpc_network.primary_zone_id
            }
        """))

    # 独立安全组（不在 web-stack 内时）
    if "addon-security-group" in plan.modules_used and not plan.use_web_stack:
        blocks.append(textwrap.dedent("""\
            module "security_group" {
              source = "./modules/addon-security-group"

              providers = {
                alicloud = alicloud
              }

              environment = var.environment
              vpc_id      = module.vpc_network.vpc_id
            }
        """))

    # WAF（独立渲染，不依赖 VPC）
    if "addon-waf" in plan.modules_used:
        blocks.append(textwrap.dedent("""\
            module "waf" {
              source = "./modules/addon-waf"

              providers = {
                alicloud = alicloud
              }

              environment = var.environment
              region      = var.region
              domains     = ["${var.environment}.example.com"]
            }
        """))

    if plan.use_route_table:
        blocks.append(textwrap.dedent("""\
            module "route_table" {
              source = "./modules/addon-route-table"

              providers = {
                alicloud = alicloud
              }

              environment = var.environment
              vpc_id      = module.vpc_network.vpc_id
            }
        """))

    if plan.use_standalone_disk:
        blocks.append(textwrap.dedent(f"""\
            module "standalone_disk" {{
              source = "./modules/addon-disk"

              providers = {{
                alicloud = alicloud
              }}

              environment = var.environment
              zone_id     = module.vpc_network.primary_zone_id
              size        = {plan.standalone_disk_size}
            }}
        """))

    if plan.use_standalone_eip:
        blocks.append(textwrap.dedent("""\
            module "standalone_eip" {
              source = "./modules/addon-eip"

              providers = {
                alicloud = alicloud
              }

              environment = var.environment
            }
        """))

    if not blocks:
        blocks.append(textwrap.dedent(f"""\
            module "vpc_network" {{
              source = "./modules/vpc-network"

              providers = {{
                alicloud = alicloud
              }}

              environment = var.environment
              region      = var.region
              vpc_cidr    = "{plan.vpc_cidr}"
              az_count    = {plan.az_count}
            }}
        """))
        plan.use_vpc_network = True
        plan.record("vpc-network")

    return "\n".join(blocks)


def render_outputs_tf(plan: ModulePlan) -> str:
    """根据 module 编排生成 outputs.tf."""
    outputs: list[str] = []

    if plan.use_web_stack:
        outputs.append(textwrap.dedent("""\
            output "vpc_id" {
              description = "The ID of the VPC"
              value       = module.web_stack.vpc_id
            }

            output "vswitch_ids" {
              description = "vSwitch IDs by AZ suffix"
              value       = module.web_stack.vswitch_ids
            }
        """))
        if plan.enable_ecs:
            outputs.append(textwrap.dedent("""\
                output "ecs_instance_ids" {
                  description = "ECS instance IDs"
                  value       = module.web_stack.ecs_instance_ids
                }

                output "security_group_id" {
                  description = "Security group ID"
                  value       = module.web_stack.security_group_id
                }
            """))
        if plan.enable_rds:
            outputs.append(textwrap.dedent("""\
                output "rds_instance_id" {
                  value = module.web_stack.rds_instance_id
                }
            """))
        if plan.enable_redis:
            outputs.append(textwrap.dedent("""\
                output "redis_instance_id" {
                  value = module.web_stack.redis_instance_id
                }
            """))
        if plan.enable_slb:
            outputs.append(textwrap.dedent("""\
                output "slb_id" {
                  value = module.web_stack.slb_id
                }
            """))
        if plan.enable_nat:
            outputs.append(textwrap.dedent("""\
                output "nat_gateway_id" {
                  value = module.web_stack.nat_gateway_id
                }
            """))
        if plan.enable_eip_in_stack:
            outputs.append(textwrap.dedent("""\
                output "eip_address" {
                  value = module.web_stack.eip_address
                }
            """))
        if plan.enable_mongodb:
            outputs.append(textwrap.dedent("""\
                output "mongodb_instance_id" {
                  value = module.web_stack.mongodb_instance_id
                }
            """))
        if plan.enable_polardb:
            outputs.append(textwrap.dedent("""\
                output "polardb_cluster_id" {
                  value = module.web_stack.polardb_cluster_id
                }
            """))
        if plan.enable_alb:
            outputs.append(textwrap.dedent("""\
                output "alb_id" {
                  value = module.web_stack.alb_id
                }
            """))

    if plan.use_vpc_network and not plan.use_web_stack:
        outputs.append(textwrap.dedent("""\
            output "vpc_id" {
              value = module.vpc_network.vpc_id
            }

            output "vswitch_ids" {
              value = module.vpc_network.vswitch_ids
            }
        """))

    if plan.use_route_table:
        outputs.append(textwrap.dedent("""\
            output "route_table_id" {
              value = module.route_table.route_table_id
            }
        """))

    if plan.use_standalone_disk:
        outputs.append(textwrap.dedent("""\
            output "disk_id" {
              value = module.standalone_disk.disk_id
            }
        """))

    if plan.use_standalone_eip:
        outputs.append(textwrap.dedent("""\
            output "eip_address" {
              value = module.standalone_eip.eip_address
            }
        """))

    if plan.enable_mongodb and not plan.use_web_stack:
        outputs.append(textwrap.dedent("""\
            output "mongodb_instance_id" {
              value = module.mongodb.mongodb_instance_id
            }
            output "mongodb_connection_string" {
              value = module.mongodb.mongodb_connection_string
            }
        """))

    if plan.enable_oss:
        outputs.append(textwrap.dedent("""\
            output "oss_bucket_name" {
              value = module.oss.bucket_name
            }
        """))

    if plan.enable_polardb and not plan.use_web_stack:
        outputs.append(textwrap.dedent("""\
            output "polardb_cluster_id" {
              value = module.polardb.polardb_cluster_id
            }
            output "polardb_connection_string" {
              value = module.polardb.polardb_connection_string
            }
        """))

    if plan.enable_alb and not plan.use_web_stack:
        outputs.append(textwrap.dedent("""\
            output "alb_id" {
              value = module.alb.alb_id
            }
            output "alb_dns_name" {
              value = module.alb.alb_dns_name
            }
        """))

    if "addon-security-group" in plan.modules_used and not plan.use_web_stack:
        outputs.append(textwrap.dedent("""\
            output "security_group_id" {
              value = module.security_group.security_group_id
            }
        """))

    if "addon-waf" in plan.modules_used:
        outputs.append(textwrap.dedent("""\
            output "waf_instance_id" {
              value = module.waf.waf_instance_id
            }
        """))

    if not outputs:
        outputs.append(textwrap.dedent("""\
            output "environment" {
              value = var.environment
            }
        """))

    return "\n\n".join(outputs)


def copy_modules(output_dir: Path) -> Path:
    """将完整 modules/ 目录复制到输出目录，保证嵌套 module source 可用."""
    dest = output_dir / "modules"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(MODULES_ROOT, dest)
    return dest


def modules_for_trace(plan: ModulePlan) -> list[dict[str, Any]]:
    """供执行轨迹 / 日志使用的模块清单."""
    return [{"module": name, "strategy": "module-first"} for name in sorted(plan.modules_used)]
