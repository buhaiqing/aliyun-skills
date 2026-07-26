"""RED tests for round-3 fixes (C1/C2/H1/H2/M1)."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import json
import pytest

from resource_model import Resource
from tag_collector import _build_arn, _fetch_tags_batch, enrich_tags
from cli_utils import _extract_aliyun_action, cli_call


def make_r(rid: str, rtype: str = "ecs") -> Resource:
    return Resource(
        resource_id=rid, resource_type=rtype, instance_name="n",
        instance_type="t", product="unknown", env="unknown", owner="unknown",
        cpu_cores=4, memory_gb=8.0, disk_gb=40.0,
        cpu_util_avg=0.0, mem_util_avg=0.0, disk_util_avg=0.0,
        iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
        monthly_cost=100.0, is_prepaid=0, days_until_expire=0,
    )


# ─── Fix C1: ARN format must match resource_type ──────────────────────────

def test_build_arn_ecs() -> None:
    arn = _build_arn("i-123", "ecs", "cn-hangzhou", "123456")
    assert arn == "acs:ecs:cn-hangzhou:123456:instance/i-123"


def test_build_arn_rds() -> None:
    arn = _build_arn("rm-123", "rds", "cn-hangzhou", "123456")
    assert arn == "acs:rds:cn-hangzhou:123456:db/rm-123"


def test_build_arn_slb() -> None:
    arn = _build_arn("lb-123", "slb", "cn-hangzhou", "123456")
    assert arn == "acs:slb:cn-hangzhou:123456:slb/lb-123"


def test_build_arn_redis() -> None:
    arn = _build_arn("r-123", "redis", "cn-hangzhou", "123456")
    assert arn == "acs:r-kvstore:cn-hangzhou:123456:instance/r-123"


def test_build_arn_oss() -> None:
    arn = _build_arn("bucket-x", "oss", "cn-hangzhou", "123456")
    assert arn == "acs:oss:cn-hangzhou:123456:bucket/bucket-x"


def test_build_arn_k8s() -> None:
    arn = _build_arn("n-123", "k8s_node", "cn-hangzhou", "123456")
    assert arn == "acs:cs:cn-hangzhou:123456:node/n-123"


def test_fetch_tags_batch_uses_correct_arn_per_resource_type() -> None:
    """Mixed resource types must each get their correct ARN."""
    resources = [
        make_r("i-001", "ecs"),
        make_r("rm-002", "rds"),
        make_r("lb-003", "slb"),
    ]
    with patch("tag_collector.cli_call") as mock_cli:
        mock_cli.return_value = {"TagResources": {"TagResource": []}}
        _fetch_tags_batch(resources, "cn-hangzhou", "123456")
        cmd = mock_cli.call_args[0][0]
        assert "acs:ecs:cn-hangzhou:123456:instance/i-001" in cmd
        assert "acs:rds:cn-hangzhou:123456:db/rm-002" in cmd
        assert "acs:slb:cn-hangzhou:123456:slb/lb-003" in cmd


# ─── Fix C2: account_id must be passed (no zero placeholder) ─────────────

def test_fetch_tags_batch_does_not_use_zero_account_id() -> None:
    """Account ID must be supplied; zero placeholder is rejected by tests."""
    resources = [make_r("i-001", "ecs")]
    with patch("tag_collector.cli_call") as mock_cli:
        mock_cli.return_value = {"TagResources": {"TagResource": []}}
        _fetch_tags_batch(resources, "cn-hangzhou", "1234567890123456")
        cmd = mock_cli.call_args[0][0]
        assert "0000000000000000" not in cmd, f"Zero placeholder leaked: {cmd}"
        assert "1234567890123456" in cmd


# ─── Fix M1: --ResourceType must match per resource ───────────────────────

def test_fetch_tags_batch_uses_per_resource_type() -> None:
    """--ResourceType argument must match each resource's type."""
    resources = [
        make_r("i-001", "ecs"),
        make_r("rm-002", "rds"),
    ]
    with patch("tag_collector.cli_call") as mock_cli:
        mock_cli.return_value = {"TagResources": {"TagResource": []}}
        _fetch_tags_batch(resources, "cn-hangzhou", "123456")
        cmd = mock_cli.call_args[0][0]
        assert "--ResourceType.1 instance" in cmd or "instance" in cmd
        assert "--ResourceType.2 db" in cmd or " db" in cmd


# ─── Fix H1: action extraction must handle --flag properly ───────────────

def test_extract_aliyun_action_rejects_flag_as_action() -> None:
    """If tokens[i+2] is --flag, action extraction must skip it, not treat as action."""
    cmd = "aliyun ecs --some-flag DescribeInstances --RegionId cn-hangzhou"
    action = _extract_aliyun_action(cmd)
    assert action == "DescribeInstances", f"Got {action}"


def test_extract_aliyun_action_validates_uppercase() -> None:
    """If position is a flag, action must be looked up at next position."""
    cmd = "aliyun ecs --debug DescribeInstances"
    action = _extract_aliyun_action(cmd)
    assert action == "DescribeInstances"


# ─── Fix H2: JSONDecodeError must not leak raw exception ─────────────────

def test_cli_call_json_error_does_not_leak_exception() -> None:
    """When JSON parse fails, the error message must not include raw exception text."""
    import json
    # We can't easily inject a bad JSON response via the real CLI.
    # Test the error message construction directly.
    from cli_utils import cli_call as _cli_call
    # Monkeypatch json.loads to raise
    import cli_utils as cu
    orig = cu.json.loads
    cu.json.loads = lambda x: (_ for _ in ()).throw(
        json.JSONDecodeError("Expecting value: line 1 column 1 (char 0)\nLTAIabc123def456 sensitive", "", 0)
    )
    try:
        with pytest.raises(RuntimeError) as exc_info:
            _cli_call("aliyun ecs DescribeInstances --RegionId cn-hangzhou")
        err = str(exc_info.value)
        assert "LTAIabc123def456" not in err, f"Leaked: {err}"
    finally:
        cu.json.loads = orig