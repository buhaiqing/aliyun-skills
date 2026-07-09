#!/usr/bin/env python3
"""
PreFlight 集成测试
验证资源注册表与 Reverse Engineering 的集成
"""

import sys
from pathlib import Path

# 导入测试目标
from resource_registry import (
    ResourceRegistry, 
    CapabilityChecker, 
    SupportLevel,
    ResourceCapability
)
from reverse_engineering import ResourceMapper


class TestColors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"


def test_resource_registry_basic():
    """测试资源注册表基本功能"""
    print(f"\n{TestColors.BLUE}=== Test: Resource Registry Basic ==={TestColors.END}")
    
    registry = ResourceRegistry()
    
    # 测试获取支持的资源
    supported = registry.list_supported()
    assert len(supported) >= 14, f"Expected at least 14 supported resources, got {len(supported)}"
    print(f"  ✅ 支持 {len(supported)} 个资源类型")
    
    # 测试按级别获取
    full_resources = registry.list_by_level(SupportLevel.FULL)
    assert len(full_resources) >= 3, f"Expected at least 3 FULL resources"
    print(f"  ✅ FULL 级别: {len(full_resources)} 个")
    
    partial_resources = registry.list_by_level(SupportLevel.PARTIAL)
    assert len(partial_resources) >= 5, f"Expected at least 5 PARTIAL resources"
    print(f"  ✅ PARTIAL 级别: {len(partial_resources)} 个")
    
    planned_resources = registry.list_by_level(SupportLevel.PLANNED)
    assert len(planned_resources) >= 1, f"Expected at least 1 PLANNED resource"
    print(f"  ✅ PLANNED 级别: {len(planned_resources)} 个")
    
    return True


def test_preflight_full_support():
    """测试 FULL 支持级别的 PreFlight"""
    print(f"\n{TestColors.BLUE}=== Test: PreFlight FULL Support ==={TestColors.END}")
    
    registry = ResourceRegistry()
    result = registry.preflight_check("vpc")
    
    assert result.supported, "VPC should be supported"
    assert result.level == SupportLevel.FULL, f"VPC should be FULL, got {result.level}"
    assert result.can_proceed, "VPC should allow proceed"
    assert not result.fallback_available, "FULL support should not need fallback"
    
    print(f"  ✅ vpc: {result.message}")
    return True


def test_preflight_partial_support():
    """测试 PARTIAL 支持级别的 PreFlight"""
    print(f"\n{TestColors.BLUE}=== Test: PreFlight PARTIAL Support ==={TestColors.END}")
    
    registry = ResourceRegistry()
    result = registry.preflight_check("rds")
    
    assert result.supported, "RDS should be supported"
    assert result.level == SupportLevel.PARTIAL, f"RDS should be PARTIAL, got {result.level}"
    assert result.can_proceed, "RDS should allow proceed with warnings"
    # PARTIAL 级别在具备所有必需能力时，fallback_available 为 False
    assert len(result.warnings) > 0, "RDS should have known issues"
    
    print(f"  ✅ rds: {result.message}")
    print(f"  ⚠️  warnings: {len(result.warnings)}")
    return True


def test_preflight_planned():
    """测试 PLANNED 支持级别的 PreFlight"""
    print(f"\n{TestColors.BLUE}=== Test: PreFlight PLANNED ==={TestColors.END}")
    
    registry = ResourceRegistry()
    result = registry.preflight_check("autoscaling")
    
    assert not result.supported, "AutoScaling should not be supported yet"
    assert result.level == SupportLevel.PLANNED, f"AutoScaling should be PLANNED, got {result.level}"
    assert not result.can_proceed, "PLANNED should not allow proceed"
    assert len(result.suggestions) > 0, "Should provide suggestions"
    
    print(f"  ✅ autoscaling: {result.message}")
    print(f"  ℹ️  suggestions: {len(result.suggestions)}")
    return True


def test_preflight_mongodb_supported():
    """测试 MongoDB 已从 PLANNED 升级为 PARTIAL"""
    print(f"\n{TestColors.BLUE}=== Test: PreFlight MongoDB PARTIAL ==={TestColors.END}")
    
    registry = ResourceRegistry()
    result = registry.preflight_check("mongodb")
    
    assert result.supported, "MongoDB should be supported"
    assert result.level == SupportLevel.PARTIAL, f"MongoDB should be PARTIAL, got {result.level}"
    assert result.can_proceed, "MongoDB should allow proceed"
    
    print(f"  ✅ mongodb: {result.message}")
    return True


def test_preflight_unknown():
    """测试未知资源类型的 PreFlight"""
    print(f"\n{TestColors.BLUE}=== Test: PreFlight Unknown Resource ==={TestColors.END}")
    
    registry = ResourceRegistry()
    result = registry.preflight_check("unknown_resource_xyz")
    
    assert not result.supported, "Unknown resource should not be supported"
    assert result.level == SupportLevel.UNSUPPORTED, "Unknown should be UNSUPPORTED"
    assert not result.can_proceed, "Unknown should not allow proceed"
    assert len(result.suggestions) > 0, "Should provide helpful suggestions"
    
    print(f"  ✅ unknown_resource: {result.message}")
    return True


def test_capability_checker():
    """测试能力检查器"""
    print(f"\n{TestColors.BLUE}=== Test: Capability Checker ==={TestColors.END}")
    
    checker = CapabilityChecker()
    
    # 测试批量检查 - 全部支持
    results = checker.check_import_request(["vpc", "ecs", "rds"], fail_fast=False)
    assert len(results) == 3, "Should have 3 results"
    assert all(r.can_proceed for r in results.values()), "All should be able to proceed"
    
    print(f"  ✅ 批量检查: {len(results)} 个资源")
    
    # 测试批量检查 - 包含不支持
    results = checker.check_import_request(["vpc", "autoscaling"], fail_fast=False)
    assert len(results) == 2, "Should have 2 results"
    assert results["vpc"].can_proceed, "VPC should proceed"
    assert not results["autoscaling"].can_proceed, "AutoScaling should not proceed"
    
    print(f"  ✅ 降级检测: vpc={results['vpc'].can_proceed}, autoscaling={results['autoscaling'].can_proceed}")
    
    # 测试报告生成
    report = checker.generate_report(results)
    assert "vpc" in report, "Report should mention vpc"
    assert "autoscaling" in report, "Report should mention autoscaling"
    
    print(f"  ✅ 报告生成: {len(report)} 字符")
    return True


def test_hcl_generation_coverage():
    """测试 HCL 生成功能覆盖"""
    print(f"\n{TestColors.BLUE}=== Test: HCL Generation Coverage ==={TestColors.END}")
    
    mapper = ResourceMapper()
    registry = ResourceRegistry()
    
    # 所有支持 HCL 生成的资源类型
    hcl_supported = [
        ("vpc", {"Vpc": {"VpcId": "vpc-test", "VpcName": "test-vpc", "CidrBlock": "10.0.0.0/16"}}),
        ("vswitch", {"VSwitch": {"VSwitchId": "vsw-test", "VSwitchName": "test-vsw", "CidrBlock": "10.0.1.0/24", "VpcId": "vpc-test", "ZoneId": "cn-hangzhou-a"}}),
        ("ecs", {"Instances": {"Instance": [{"InstanceId": "i-test", "InstanceName": "test-ecs", "InstanceType": "ecs.c6.large", "ImageId": "centos_7", "VpcAttributes": {"VSwitchId": ["vsw-test"]}}]}}),
        ("rds", {"Items": {"DBInstanceAttribute": [{"DBInstanceId": "rm-test", "DBInstanceDescription": "test-rds", "Engine": "MySQL", "EngineVersion": "8.0", "DBInstanceClass": "rds.mysql.c1.large", "VSwitchId": "vsw-test", "ZoneId": "cn-hangzhou-a", "DBInstanceStorage": 100}]}}),
        ("redis", {"Instances": {"KVStoreInstance": [{"InstanceId": "r-test", "InstanceName": "test-redis", "InstanceClass": "redis.master.large.default", "EngineVersion": "6.0", "VpcId": "vpc-test", "VSwitchId": "vsw-test", "ZoneId": "cn-hangzhou-a"}]}}),
        ("slb", {"LoadBalancer": {"LoadBalancerId": "lb-test", "LoadBalancerName": "test-slb", "LoadBalancerSpec": "slb.s1.small", "AddressType": "internet", "VpcId": "vpc-test", "VSwitchId": "vsw-test"}}),
        ("eip", {"EipAddresses": {"EipAddress": [{"AllocationId": "eip-test", "IpAddress": "47.0.0.1", "Bandwidth": "10", "ISP": "BGP", "InternetChargeType": "PayByTraffic"}]}}),
        ("security_group", {"SecurityGroup": {"SecurityGroupId": "sg-test", "SecurityGroupName": "test-sg", "Description": "Test SG", "VpcId": "vpc-test"}}),
        ("nat_gateway", {"NatGateway": {"NatGatewayId": "nat-test", "Name": "test-nat", "VpcId": "vpc-test", "VSwitchId": "vsw-test", "Spec": "Small", "NatType": "Enhanced"}}),
        ("mongodb", {"DBInstances": {"DBInstance": [{"DBInstanceId": "dds-test", "DBInstanceDescription": "test-mongo", "EngineVersion": "4.2", "DBInstanceClass": "dds.mongo.mid", "VpcId": "vpc-test", "VSwitchId": "vsw-test", "ZoneId": "cn-hangzhou-a"}]}}),
        ("polardb", {"Items": {"DBCluster": [{"DBClusterId": "pc-test", "DBClusterDescription": "test-polardb", "DBType": "MySQL", "DBVersion": "8.0", "VpcId": "vpc-test", "VSwitchId": "vsw-test", "ZoneId": "cn-hangzhou-a"}]}}),
        ("oss", {"BucketName": "my-test-bucket", "Bucket": {"Name": "my-test-bucket", "AccessControlList": {"Grant": "private"}, "StorageClass": "Standard"}}),
        ("disk", {"Disk": {"DiskId": "d-test", "DiskName": "test-disk", "Size": 100, "Category": "cloud_essd", "ZoneId": "cn-hangzhou-a", "Type": "data"}}),
        ("route_table", {"RouteTable": {"RouteTableId": "vtb-test", "RouteTableName": "test-rt", "VpcId": "vpc-test", "Description": "Test RT"}}),
    ]
    
    success_count = 0
    for rtype, mock_data in hcl_supported:
        try:
            hcl = mapper.to_hcl(rtype, mock_data)
            
            # 基本验证
            assert hcl, f"{rtype}: HCL should not be empty"
            assert "resource \"alicloud_" in hcl, f"{rtype}: Should contain resource declaration"
            assert "prevent_destroy = true" in hcl, f"{rtype}: Should have prevent_destroy"
            assert "terraform-reverse-engineering" in hcl, f"{rtype}: Should have import tag"
            
            # 检查不是 TODO（排除所有注释行和行内注释）
            import re
            # 移除所有注释
            hcl_no_comments = re.sub(r'#.*$', '', hcl, flags=re.MULTILINE)
            assert "TODO" not in hcl_no_comments, f"{rtype}: Should not contain TODO outside of comments"
            
            print(f"  ✅ {rtype}: HCL generated ({len(hcl)} chars)")
            success_count += 1
            
        except Exception as e:
            print(f"  ❌ {rtype}: {e}")
    
    assert success_count == len(hcl_supported), f"Expected {len(hcl_supported)} successes, got {success_count}"
    return True


def test_associated_discovery():
    """测试关联资源发现 (无需 API)"""
    print(f"\n{TestColors.BLUE}=== Test: Associated Resource Discovery ==={TestColors.END}")

    mapper = ResourceMapper()

    ecs_data = {
        "Instances": {
            "Instance": [{
                "InstanceId": "i-test",
                "VpcAttributes": {"VSwitchId": ["vsw-abc"]},
                "SecurityGroupIds": {"SecurityGroupId": ["sg-xyz"]},
                "Disks": {"Disk": [
                    {"DiskId": "d-sys", "Type": "system", "Device": "/dev/xvda"},
                    {"DiskId": "d-disk1", "Type": "data", "Device": "/dev/xvdb"},
                ]},
            }]
        }
    }
    found = mapper._discover_from_ecs(ecs_data)
    types = {f["type"] for f in found}
    assert "vswitch" in types, "Should discover vswitch"
    assert "security_group" in types, "Should discover security group"
    assert "disk" in types, "Should discover data disk"
    print(f"  ✅ ECS 关联发现: {len(found)} 个资源 (含 data disk)")

    # 系统盘不应出现在发现列表
    ecs_sys_only = {
        "Instances": {
            "Instance": [{
                "InstanceId": "i-test",
                "Disks": {"Disk": [{"DiskId": "d-sys", "Type": "system", "Device": "/dev/xvda"}]},
            }]
        }
    }
    sys_found = mapper._discover_from_ecs(ecs_sys_only)
    assert not any(f["type"] == "disk" for f in sys_found), "System disk should be skipped"
    print(f"  ✅ 系统盘已正确跳过")

    slb_data = {
        "LoadBalancer": {"VpcId": "vpc-1", "VSwitchId": "vsw-1"},
        "BackendServers": {"BackendServer": [{"ServerId": "i-backend", "ServerIp": "10.0.0.1"}]},
    }
    slb_found = mapper._discover_from_slb(slb_data)
    slb_types = {f["type"] for f in slb_found}
    assert "ecs" in slb_types, "Should discover backend ECS"
    print(f"  ✅ SLB 关联发现: {len(slb_found)} 个资源")
    return True


def test_nl2hcl_disk_and_route_table():
    """测试正向 NL2HCL 生成 Disk / RouteTable"""
    print(f"\n{TestColors.BLUE}=== Test: NL2HCL Disk & RouteTable ==={TestColors.END}")

    from nl2hcl_generator import NL2HCLGenerator

    gen = NL2HCLGenerator(environment="dev")

    intent_ecs = gen.parse_intent("创建2台ECS，每台100G数据盘")
    assert intent_ecs.get("data_disk_size") == 100
    assert "alicloud_instance" in intent_ecs["resources"]
    files_ecs = gen.generate("创建2台ECS，每台100G数据盘")
    assert 'module "web_stack"' in files_ecs["main.tf"]
    assert "ecs_data_disk_size  = 100" in files_ecs["main.tf"]
    print("  ✅ ECS → web-stack module + data_disk_size")

    gen2 = NL2HCLGenerator(environment="dev")
    files_rt = gen2.generate("创建 VPC 和自定义路由表")
    assert 'module "vpc_network"' in files_rt["main.tf"]
    assert 'module "route_table"' in files_rt["main.tf"]
    assert "route_table_id" in files_rt["outputs.tf"]
    print("  ✅ VPC + route_table modules")

    gen3 = NL2HCLGenerator(environment="dev")
    files_disk = gen3.generate("创建 VPC 和一块独立云盘 200G")
    assert 'module "standalone_disk"' in files_disk["main.tf"]
    assert "size        = 200" in files_disk["main.tf"]
    print("  ✅ standalone_disk module")

    return True


def test_support_matrix_generation():
    """测试支持矩阵生成"""
    print(f"\n{TestColors.BLUE}=== Test: Support Matrix Generation ==={TestColors.END}")
    
    registry = ResourceRegistry()
    matrix = registry.generate_support_matrix()
    
    assert "资源支持矩阵" in matrix, "Should have title"
    assert "vpc" in matrix, "Should mention vpc"
    assert "rds" in matrix, "Should mention rds"
    assert "mongodb" in matrix, "Should mention mongodb"
    assert "✅" in matrix or "⚡" in matrix, "Should have status icons"
    
    print(f"  ✅ 支持矩阵: {len(matrix)} 字符")
    print(f"\n{matrix[:500]}...")
    return True


def run_all_tests():
    """运行所有测试"""
    tests = [
        ("Resource Registry Basic", test_resource_registry_basic),
        ("PreFlight FULL Support", test_preflight_full_support),
        ("PreFlight PARTIAL Support", test_preflight_partial_support),
        ("PreFlight PLANNED", test_preflight_planned),
        ("PreFlight MongoDB PARTIAL", test_preflight_mongodb_supported),
        ("PreFlight Unknown Resource", test_preflight_unknown),
        ("Capability Checker", test_capability_checker),
        ("HCL Generation Coverage", test_hcl_generation_coverage),
        ("Associated Discovery", test_associated_discovery),
        ("NL2HCL Disk & RouteTable", test_nl2hcl_disk_and_route_table),
        ("Support Matrix Generation", test_support_matrix_generation),
    ]
    
    passed = 0
    failed = 0
    
    print(f"\n{'='*60}")
    print(f"PreFlight Integration Test Suite")
    print(f"{'='*60}")
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"{TestColors.RED}  FAILED: {name}{TestColors.END}")
        except Exception as e:
            failed += 1
            print(f"{TestColors.RED}  ERROR in {name}: {e}{TestColors.END}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"Results: {TestColors.GREEN}{passed} passed{TestColors.END}, {TestColors.RED if failed > 0 else TestColors.GREEN}{failed} failed{TestColors.END}")
    print(f"{'='*60}")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
