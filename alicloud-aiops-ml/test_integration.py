"""Integration tests for the full FinOps pipeline."""
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


@pytest.fixture
def sample_resources() -> list[Resource]:
    return [
        Resource(
            resource_id="i-001", resource_type="ecs", instance_name="web-1",
            instance_type="g9i.2xlarge", product="app-x", env="production",
            owner="team-a", cpu_cores=8, memory_gb=32.0, disk_gb=100.0,
            cpu_util_avg=45.0, mem_util_avg=60.0, disk_util_avg=30.0,
            iops_util_avg=20.0, net_in_avg=10.0, net_out_avg=5.0,
            monthly_cost=1200.0, is_prepaid=1, days_until_expire=30,
        ),
        Resource(
            resource_id="i-002", resource_type="ecs", instance_name="web-2",
            instance_type="g9i.xlarge", product="app-x", env="production",
            owner="team-a", cpu_cores=4, memory_gb=16.0, disk_gb=50.0,
            cpu_util_avg=20.0, mem_util_avg=30.0, disk_util_avg=15.0,
            iops_util_avg=10.0, net_in_avg=5.0, net_out_avg=2.0,
            monthly_cost=600.0, is_prepaid=0, days_until_expire=0,
        ),
        Resource(
            resource_id="r-001", resource_type="rds", instance_name="db-main",
            instance_type="rds.mysql.s3.large", product="service-y", env="production",
            owner="team-b", cpu_cores=4, memory_gb=16.0, disk_gb=200.0,
            cpu_util_avg=50.0, mem_util_avg=70.0, disk_util_avg=40.0,
            iops_util_avg=30.0, net_in_avg=5.0, net_out_avg=3.0,
            monthly_cost=800.0, is_prepaid=1, days_until_expire=60,
        ),
    ]


def test_full_pipeline(sample_resources: list[Resource]) -> None:
    """Test the complete pipeline from data to report."""
    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = f"{tmpdir}/resources.json"
        report_path = f"{tmpdir}/report.md"

        aggregate_to_json(sample_resources, json_path)
        loaded = load_resources(json_path)
        assert len(loaded) == 3

        features = extract_features(loaded)
        assert len(features) == 3
        assert "cpu_cores" in features[0]

        anomalies = detect_anomalies(loaded, features)
        assert len(anomalies) == 3

        predictions = predict_cost(loaded, features)
        assert len(predictions) == 3

        clusters = cluster_resources(loaded, features)
        assert len(clusters) == 3

        report = generate_report(loaded, anomalies, predictions, clusters, report_path)
        assert "FinOps 巡检分析报告" in report
        assert Path(report_path).exists()
