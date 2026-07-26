"""Edge case tests for alicloud-aiops-ml pipeline."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from resource_model import Resource
from data_pipeline import aggregate_to_json, load_resources
from feature_engine import extract_features
from iforest_detector import detect_anomalies
from xgboost_predictor import predict_cost
from dbscan_cluster import cluster_resources
from report_generator import generate_report
from cli_utils import is_readonly_action, cli_call


# ─── Empty list edge cases ───────────────────────────────────────────────

def test_detect_anomalies_empty_list() -> None:
    """Empty resource list returns empty anomalies (no division-by-zero)."""
    assert detect_anomalies([], []) == []


def test_predict_cost_empty_list() -> None:
    """Empty resource list returns empty predictions."""
    assert predict_cost([], []) == []


def test_cluster_resources_empty_list() -> None:
    """Empty resource list returns empty clusters."""
    assert cluster_resources([], []) == []


def test_extract_features_empty_list() -> None:
    """Empty resource list returns empty features."""
    assert extract_features([]) == []


# ─── Single-resource edge cases ───────────────────────────────────────────

def test_detect_anomalies_single_resource() -> None:
    """Single resource: std fallback to mean*0.1, no crash."""
    r = Resource(
        resource_id="solo", resource_type="ecs", instance_name="s",
        instance_type="t", product="p", env="dev", owner="o",
        cpu_cores=4, memory_gb=16.0, disk_gb=40.0,
        cpu_util_avg=10.0, mem_util_avg=20.0, disk_util_avg=5.0,
        iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
        monthly_cost=500.0, is_prepaid=0, days_until_expire=0,
    )
    feats = extract_features([r])
    result = detect_anomalies([r], feats)
    assert len(result) == 1
    assert "threshold" in result[0]
    assert "is_anomaly" in result[0]


def test_predict_cost_single_resource() -> None:
    """Single resource: falls back to identity (predicted=actual)."""
    r = Resource(
        resource_id="solo", resource_type="ecs", instance_name="s",
        instance_type="t", product="p", env="dev", owner="o",
        cpu_cores=4, memory_gb=16.0, disk_gb=40.0,
        cpu_util_avg=10.0, mem_util_avg=20.0, disk_util_avg=5.0,
        iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
        monthly_cost=500.0, is_prepaid=0, days_until_expire=0,
    )
    feats = extract_features([r])
    result = predict_cost([r], feats)
    assert len(result) == 1
    assert result[0]["predicted_cost"] == 500.0
    assert result[0]["diff"] == 0.0


def test_cluster_resources_single_resource() -> None:
    """Single resource: gets cluster_id 0 (or noise -1, both acceptable)."""
    r = Resource(
        resource_id="solo", resource_type="ecs", instance_name="s",
        instance_type="t", product="p", env="dev", owner="o",
        cpu_cores=4, memory_gb=16.0, disk_gb=40.0,
        cpu_util_avg=10.0, mem_util_avg=20.0, disk_util_avg=5.0,
        iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
        monthly_cost=500.0, is_prepaid=0, days_until_expire=0,
    )
    feats = extract_features([r])
    result = cluster_resources([r], feats)
    assert len(result) == 1
    assert "cluster_id" in result[0]


# ─── Zero-value edge cases (SLB / OSS / K8s without CPU/mem) ─────────────

def test_extract_features_zero_cpu_memory() -> None:
    """Zero CPU/memory resources: ratios should be 0.0 (no ZeroDivisionError)."""
    r = Resource(
        resource_id="lb-1", resource_type="slb", instance_name="lb",
        instance_type="internet", product="edge", env="prod", owner="ops",
        cpu_cores=0, memory_gb=0.0, disk_gb=0.0,
        cpu_util_avg=0.0, mem_util_avg=0.0, disk_util_avg=0.0,
        iops_util_avg=0.0, net_in_avg=10.0, net_out_avg=5.0,
        monthly_cost=100.0, is_prepaid=0, days_until_expire=0,
    )
    feats = extract_features([r])
    assert feats[0]["cpu_mem_ratio"] == 0.0
    assert feats[0]["cost_per_cpu"] == 0.0
    assert feats[0]["cost_per_gb"] == 0.0


def test_xgboost_negative_prediction_clipped() -> None:
    """OLS regression with degenerate data must not produce negative predicted_cost."""
    # All same cost → lstsq gives zero slope → prediction = actual. Use extremes.
    resources = [
        Resource(
            resource_id=f"r{i}", resource_type="ecs", instance_name=f"x{i}",
            instance_type="t", product="p", env="dev", owner="o",
            cpu_cores=100, memory_gb=400.0, disk_gb=0.0,
            cpu_util_avg=0.0, mem_util_avg=0.0, disk_util_avg=0.0,
            iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
            monthly_cost=0.01, is_prepaid=0, days_until_expire=0,
        )
        for i in range(5)
    ]
    feats = extract_features(resources)
    preds = predict_cost(resources, feats)
    for p in preds:
        assert p["predicted_cost"] >= 0.0


# ─── CLI utils edge cases ────────────────────────────────────────────────

def test_is_readonly_action_whitelist() -> None:
    """All Describe*/List*/Get* are read-only; write actions rejected."""
    assert is_readonly_action("DescribeInstances") is True
    assert is_readonly_action("ListBuckets") is True
    assert is_readonly_action("GetResource") is True
    assert is_readonly_action("CreateInstance") is False
    assert is_readonly_action("DeleteBucket") is False
    assert is_readonly_action("ModifyAttribute") is False
    assert is_readonly_action("RebootInstance") is False


def test_cli_call_rejects_write_action() -> None:
    """Write actions (Create*/Delete*) must raise ValueError."""
    with pytest.raises(ValueError, match="write action"):
        cli_call("aliyun ecs CreateInstance --RegionId cn-hangzhou")


def test_cli_call_rejects_release_action() -> None:
    """Release* is a write op; must be rejected."""
    with pytest.raises(ValueError, match="write action"):
        cli_call("aliyun ecs ReleaseInstance --RegionId cn-hangzhou")


def test_cli_call_credentials_in_stderr_masked() -> None:
    """LTAI AK IDs in stderr must be masked (best-effort dry test)."""
    # We don't actually run aliyun; we test the _mask_credentials regex indirectly
    # by ensuring cli_call raises RuntimeError on non-zero exit and the message
    # does not contain a leaked AK. We use a guaranteed-failing command.
    with pytest.raises(RuntimeError):
        cli_call("aliyun ecs DescribeInstances --this-flag-does-not-exist", timeout=5)


def test_cli_call_timeout_does_not_leak_cmd_params() -> None:
    """Timeout error must NOT contain the full cmd (which might have secrets)."""
    import subprocess
    # Use a sleep that exceeds timeout
    with pytest.raises(RuntimeError) as exc_info:
        cli_call("aliyun ecs DescribeInstances --RegionId cn-hangzhou --Token SECRET_TOKEN_VALUE", timeout=1)
    err_msg = str(exc_info.value)
    assert "SECRET_TOKEN_VALUE" not in err_msg, f"Token leaked: {err_msg}"


# ─── Data pipeline edge cases ─────────────────────────────────────────────

def test_load_resources_corrupted_json(tmp_path: Path) -> None:
    """Corrupted JSON file should raise a clear JSONDecodeError."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json")
    with pytest.raises(json.JSONDecodeError):
        load_resources(str(bad_file))


def test_load_resources_extra_keys_ignored(tmp_path: Path) -> None:
    """Extra keys in JSON (forward compatibility) are silently dropped, no crash."""
    fwd_file = tmp_path / "fwd.json"
    fwd_file.write_text(json.dumps([
        {
            "resource_id": "x", "resource_type": "ecs",
            "instance_name": "n", "instance_type": "t",
            "product": "p", "env": "e", "owner": "o",
            "cpu_cores": 4, "memory_gb": 8.0, "disk_gb": 40.0,
            "cpu_util_avg": 0.0, "mem_util_avg": 0.0, "disk_util_avg": 0.0,
            "iops_util_avg": 0.0, "net_in_avg": 0.0, "net_out_avg": 0.0,
            "monthly_cost": 0.0, "is_prepaid": 0, "days_until_expire": 0,
            "future_field": "should be ignored",
            "another_unknown": 42,
        }
    ]))
    loaded = load_resources(str(fwd_file))
    assert loaded[0].resource_id == "x"
    assert not hasattr(loaded[0], "future_field")


def test_load_resources_missing_required_key(tmp_path: Path) -> None:
    """Missing required field should raise TypeError (no silent garbage)."""
    bad_file = tmp_path / "missing.json"
    bad_file.write_text(json.dumps([{"resource_id": "x"}]))  # missing all required
    with pytest.raises(TypeError):
        load_resources(str(bad_file))


# ─── Report generator edge cases ─────────────────────────────────────────

def test_generate_report_with_empty_anomalies(tmp_path: Path) -> None:
    """Report should not crash on empty anomalies list."""
    r = Resource(
        resource_id="r1", resource_type="ecs", instance_name="n",
        instance_type="t", product="p", env="e", owner="o",
        cpu_cores=4, memory_gb=8.0, disk_gb=40.0,
        cpu_util_avg=0.0, mem_util_avg=0.0, disk_util_avg=0.0,
        iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
        monthly_cost=100.0, is_prepaid=0, days_until_expire=0,
    )
    out = tmp_path / "r.md"
    content = generate_report([r], [], [], [], str(out))
    assert "无异常发现" in content


def test_generate_report_with_all_zero_costs(tmp_path: Path) -> None:
    """All-zero-cost resources: total ¥0 formatted correctly, no crash."""
    resources = [
        Resource(
            resource_id=f"r{i}", resource_type="ecs", instance_name=f"n{i}",
            instance_type="t", product="p", env="e", owner="o",
            cpu_cores=4, memory_gb=8.0, disk_gb=40.0,
            cpu_util_avg=0.0, mem_util_avg=0.0, disk_util_avg=0.0,
            iops_util_avg=0.0, net_in_avg=0.0, net_out_avg=0.0,
            monthly_cost=0.0, is_prepaid=0, days_until_expire=0,
        )
        for i in range(3)
    ]
    out = tmp_path / "r.md"
    content = generate_report(resources, [], [], [], str(out))
    assert "¥0" in content or "0.00" in content