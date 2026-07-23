#!/usr/bin/env python3
"""
Test script for HCL generation functions.
验证新添加的 RDS/Redis/SLB/EIP/SG HCL 生成函数
"""

from reverse_engineering import ResourceMapper


def test_rds_hcl():
    """Test RDS HCL generation."""
    print("=" * 60)
    print("Test: RDS HCL Generation")
    print("=" * 60)

    mapper = ResourceMapper()

    # Mock RDS API response
    mock_data = {
        "Items": {
            "DBInstanceAttribute": [{
                "DBInstanceId": "rm-bp1xxxxxxxxxxxxx",
                "DBInstanceDescription": "prod-mysql",
                "Engine": "MySQL",
                "EngineVersion": "8.0",
                "DBInstanceClass": "rds.mysql.c1.large",
                "VSwitchId": "vsw-bp1xxxxxxxxx",
                "VpcId": "vpc-bp1xxxxxxxxx",
                "ZoneId": "cn-hangzhou-b",
                "DBInstanceStorage": 100
            }]
        }
    }

    hcl = mapper.to_hcl("rds", mock_data)
    print(hcl)

    # Validation checks
    assert 'resource "alicloud_db_instance"' in hcl
    assert "prod-mysql" in hcl
    assert "MySQL" in hcl
    assert "prevent_destroy = true" in hcl
    print("✅ RDS HCL validation passed\n")


def test_redis_hcl():
    """Test Redis HCL generation."""
    print("=" * 60)
    print("Test: Redis HCL Generation")
    print("=" * 60)

    mapper = ResourceMapper()

    # Mock Redis API response
    mock_data = {
        "Instances": {
            "KVStoreInstance": [{
                "InstanceId": "r-bp1xxxxxxxxxxxxx",
                "InstanceName": "cache-cluster",
                "InstanceClass": "redis.master.large.default",
                "EngineVersion": "6.0",
                "VpcId": "vpc-bp1xxxxxxxxx",
                "VSwitchId": "vsw-bp1xxxxxxxxx",
                "ZoneId": "cn-hangzhou-b"
            }]
        }
    }

    hcl = mapper.to_hcl("redis", mock_data)
    print(hcl)

    # Validation checks
    assert 'resource "alicloud_kvstore_instance"' in hcl
    assert "cache-cluster" in hcl
    assert "prevent_destroy = true" in hcl
    print("✅ Redis HCL validation passed\n")


def test_slb_hcl():
    """Test SLB HCL generation."""
    print("=" * 60)
    print("Test: SLB HCL Generation")
    print("=" * 60)

    mapper = ResourceMapper()

    # Mock SLB API response
    mock_data = {
        "LoadBalancer": {
            "LoadBalancerId": "lb-bp1xxxxxxxxxxxxx",
            "LoadBalancerName": "web-lb",
            "LoadBalancerSpec": "slb.s1.small",
            "AddressType": "internet",
            "VpcId": "vpc-bp1xxxxxxxxx",
            "VSwitchId": "vsw-bp1xxxxxxxxx"
        }
    }

    hcl = mapper.to_hcl("slb", mock_data)
    print(hcl)

    # Validation checks
    assert 'resource "alicloud_slb_load_balancer"' in hcl
    assert "web-lb" in hcl
    assert "slb.s1.small" in hcl
    assert "prevent_destroy = true" in hcl
    print("✅ SLB HCL validation passed\n")


def test_eip_hcl():
    """Test EIP HCL generation."""
    print("=" * 60)
    print("Test: EIP HCL Generation")
    print("=" * 60)

    mapper = ResourceMapper()

    # Mock EIP API response
    mock_data = {
        "EipAddresses": {
            "EipAddress": [{
                "AllocationId": "eip-bp1xxxxxxxxxxxxx",
                "IpAddress": "47.97.XXX.XXX",
                "Bandwidth": "10",
                "ISP": "BGP",
                "InternetChargeType": "PayByTraffic"
            }]
        }
    }

    hcl = mapper.to_hcl("eip", mock_data)
    print(hcl)

    # Validation checks
    assert 'resource "alicloud_eip_address"' in hcl
    assert "BGP" in hcl
    assert "PayByTraffic" in hcl
    assert "prevent_destroy = true" in hcl
    print("✅ EIP HCL validation passed\n")


def test_sg_hcl():
    """Test Security Group HCL generation."""
    print("=" * 60)
    print("Test: Security Group HCL Generation")
    print("=" * 60)

    mapper = ResourceMapper()

    # Mock Security Group API response
    mock_data = {
        "SecurityGroup": {
            "SecurityGroupId": "sg-bp1xxxxxxxxxxxxx",
            "SecurityGroupName": "web-sg",
            "Description": "Security group for web servers",
            "VpcId": "vpc-bp1xxxxxxxxx"
        }
    }

    hcl = mapper.to_hcl("security_group", mock_data)
    print(hcl)

    # Validation checks
    assert 'resource "alicloud_security_group"' in hcl
    assert "web-sg" in hcl
    assert "prevent_destroy = true" in hcl
    print("✅ Security Group HCL validation passed\n")


def test_all_resource_types():
    """Test all supported resource types are mapped."""
    print("=" * 60)
    print("Test: Resource Type Mapping Coverage")
    print("=" * 60)

    mapper = ResourceMapper()

    expected_types = [
        "vpc", "vswitch", "ecs", "rds", "redis",
        "slb", "eip", "security_group"
    ]

    supported_types = list(mapper.RESOURCE_APIS.keys())

    print(f"Expected types: {expected_types}")
    print(f"Supported types: {supported_types}")

    for rtype in expected_types:
        assert rtype in supported_types, f"Missing resource type: {rtype}"
        print(f"  ✅ {rtype}")

    print("\n✅ All resource types are mapped\n")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("HCL Generation Function Tests")
    print("=" * 60 + "\n")

    try:
        test_all_resource_types()
        test_rds_hcl()
        test_redis_hcl()
        test_slb_hcl()
        test_eip_hcl()
        test_sg_hcl()

        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
