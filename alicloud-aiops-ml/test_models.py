"""Tests for ML model modules — feature_engine, iforest_detector, xgboost_predictor, report_generator."""
from __future__ import annotations

import pytest

from resource_model import Resource
from feature_engine import extract_features
from iforest_detector import detect_anomalies
from xgboost_predictor import predict_cost
from report_generator import generate_report


def _make_resource(**kwargs) -> Resource:
    """Helper to create a Resource with sensible defaults."""
    defaults = {
        "resource_id": "test-id",
        "resource_type": "ecs",
        "instance_name": "test",
        "instance_type": "ecs.g9i.large",
        "product": "unknown",
        "env": "unknown",
        "owner": "unknown",
        "cpu_cores": 4,
        "memory_gb": 16.0,
        "disk_gb": 100.0,
        "cpu_util_avg": 50.0,
        "mem_util_avg": 60.0,
        "disk_util_avg": 30.0,
        "iops_util_avg": 20.0,
        "net_in_avg": 10.0,
        "net_out_avg": 15.0,
        "monthly_cost": 500.0,
        "is_prepaid": 0,
        "days_until_expire": 0,
    }
    defaults.update(kwargs)
    return Resource(**defaults)


# ------------------------------------------------------------------
# Feature Engine
# ------------------------------------------------------------------

class TestExtractFeatures:
    """Tests for feature_engine.extract_features."""

    def test_basic(self) -> None:
        r = _make_resource(cpu_cores=4, memory_gb=16, monthly_cost=500)
        features = extract_features([r])
        assert len(features) == 1
        f = features[0]
        assert f["cpu_cores"] == 4.0
        assert f["memory_gb"] == 16.0
        assert f["monthly_cost"] == 500.0

    def test_derived_features(self) -> None:
        r = _make_resource(cpu_util_avg=50, mem_util_avg=25, monthly_cost=1000, cpu_cores=4, memory_gb=8)
        features = extract_features([r])
        f = features[0]
        assert f["cpu_mem_ratio"] == 2.0
        assert f["cost_per_cpu"] == 250.0
        assert f["cost_per_gb"] == 125.0

    def test_zero_memory_ratio_safe(self) -> None:
        r = _make_resource(cpu_util_avg=50, mem_util_avg=0)
        features = extract_features([r])
        assert features[0]["cpu_mem_ratio"] == 0.0

    def test_zero_cpu_cost_safe(self) -> None:
        r = _make_resource(monthly_cost=1000, cpu_cores=0)
        features = extract_features([r])
        assert features[0]["cost_per_cpu"] == 0.0

    def test_zero_memory_cost_safe(self) -> None:
        r = _make_resource(monthly_cost=1000, memory_gb=0)
        features = extract_features([r])
        assert features[0]["cost_per_gb"] == 0.0

    def test_empty_resources(self) -> None:
        assert extract_features([]) == []

    def test_all_features_present(self) -> None:
        r = _make_resource()
        features = extract_features([r])
        expected_keys = {
            "cpu_cores", "memory_gb", "disk_gb",
            "cpu_util_avg", "mem_util_avg", "disk_util_avg",
            "iops_util_avg", "net_in_avg", "net_out_avg",
            "monthly_cost", "is_prepaid", "days_until_expire",
            "cpu_mem_ratio", "cost_per_cpu", "cost_per_gb",
        }
        assert set(features[0].keys()) == expected_keys

    def test_multiple_resources(self) -> None:
        r1 = _make_resource(resource_id="r1")
        r2 = _make_resource(resource_id="r2")
        features = extract_features([r1, r2])
        assert len(features) == 2


# ------------------------------------------------------------------
# Anomaly Detection
# ------------------------------------------------------------------

class TestDetectAnomalies:
    """Tests for iforest_detector.detect_anomalies."""

    def test_empty(self) -> None:
        assert detect_anomalies([], []) == []

    def test_single_resource_not_anomalous(self) -> None:
        r = _make_resource(resource_id="r1", monthly_cost=100)
        features = [{"monthly_cost": 100}]
        results = detect_anomalies([r], features)
        assert len(results) == 1
        assert results[0]["is_anomaly"] is False

    def test_uniform_costs_no_anomaly(self) -> None:
        """All resources have same cost → std=0 → threshold uses min(1)."""
        resources = [_make_resource(resource_id=f"r{i}", monthly_cost=100) for i in range(5)]
        features = [{"monthly_cost": 100} for _ in range(5)]
        results = detect_anomalies(resources, features)
        for r in results:
            assert r["is_anomaly"] == False

    def test_outlier_detected(self) -> None:
        """One resource with cost 10x the mean is flagged."""
        resources = (
            [_make_resource(resource_id=f"r{i}", monthly_cost=100) for i in range(9)]
            + [_make_resource(resource_id="r9", monthly_cost=10000)]
        )
        features = [{"monthly_cost": r.monthly_cost} for r in resources]
        results = detect_anomalies(resources, features)
        anomaly_flags = [r["is_anomaly"] for r in results]
        assert anomaly_flags[9] == True
        assert sum(anomaly_flags) >= 1

    def test_threshold_above_mean(self) -> None:
        resources = [_make_resource(resource_id=f"r{i}", monthly_cost=100) for i in range(10)]
        features = [{"monthly_cost": 100} for _ in range(10)]
        results = detect_anomalies(resources, features)
        # All uniform → threshold = mean + 2*1 = 100 + 2 = 102
        assert results[0]["threshold"] == 102.0

    def test_anomaly_score_proportional(self) -> None:
        resources = (
            [_make_resource(resource_id=f"r{i}", monthly_cost=100) for i in range(9)]
            + [_make_resource(resource_id="r9", monthly_cost=200)]
        )
        features = [{"monthly_cost": r.monthly_cost} for r in resources]
        results = detect_anomalies(resources, features)
        # anomaly_score = cost / threshold
        for r in results:
            assert r["anomaly_score"] >= 0.0


# ------------------------------------------------------------------
# Cost Prediction
# ------------------------------------------------------------------

class TestPredictCost:
    """Tests for xgboost_predictor.predict_cost."""

    def test_empty(self) -> None:
        assert predict_cost([], []) == []

    def test_single_resource(self) -> None:
        r = _make_resource(cpu_cores=4, memory_gb=16, monthly_cost=500)
        results = predict_cost([r], [{"cpu_cores": 4, "memory_gb": 16, "monthly_cost": 500}])
        assert len(results) == 1
        assert "predicted_cost" in results[0]

    def test_negative_predicted_clipped(self) -> None:
        """OLS may predict negative for unusual features; should be clipped to 0."""
        # Construct data where OLS would predict negative: low cpu/mem with high cost
        r1 = _make_resource(resource_id="r1", cpu_cores=4, memory_gb=16, monthly_cost=500)
        r2 = _make_resource(resource_id="r2", cpu_cores=2, memory_gb=4, monthly_cost=200)
        features = [
            {"cpu_cores": 4, "memory_gb": 16, "monthly_cost": 500},
            {"cpu_cores": 2, "memory_gb": 4, "monthly_cost": 200},
        ]
        results = predict_cost([r1, r2], features)
        for r in results:
            assert r["predicted_cost"] >= 0.0

    def test_multiple_resources(self) -> None:
        resources = [_make_resource(resource_id=f"r{i}") for i in range(10)]
        features = [
            {"cpu_cores": r.cpu_cores, "memory_gb": r.memory_gb, "monthly_cost": r.monthly_cost}
            for r in resources
        ]
        results = predict_cost(resources, features)
        assert len(results) == 10
        for r in results:
            assert "predicted_cost" in r
            assert "actual_cost" in r
            assert "diff" in r

    def test_result_contains_resource_id(self) -> None:
        r = _make_resource(resource_id="my-instance")
        features = [{"cpu_cores": r.cpu_cores, "memory_gb": r.memory_gb, "monthly_cost": r.monthly_cost}]
        results = predict_cost([r], features)
        assert results[0]["resource_id"] == "my-instance"


# ------------------------------------------------------------------
# Report Generator
# ------------------------------------------------------------------

class TestGenerateReport:
    """Tests for report_generator.generate_report."""

    def test_markdown_report_basic(self, tmp_path) -> None:
        resources = [_make_resource()]
        anomalies = [{"resource_id": "r1", "resource_type": "ecs", "monthly_cost": 1000, "threshold": 800, "anomaly_score": 1.25, "is_anomaly": True}]
        predictions = [{"resource_id": "r1", "predicted_cost": 500, "actual_cost": 480, "diff": 20}]
        clusters = [{"resource_id": "r1", "resource_type": "ecs", "cluster_id": 0}]

        output_path = tmp_path / "report.md"
        content = generate_report(resources, anomalies, predictions, clusters, str(output_path))
        assert output_path.exists()
        assert "FinOps" in content
        assert "资源总数" in content

    def test_empty_anomalies(self, tmp_path) -> None:
        output_path = tmp_path / "report.md"
        content = generate_report([], [], [], [], str(output_path))
        assert "无异常发现" in content or "无" in content

    def test_anomaly_section_flagged(self, tmp_path) -> None:
        resources = [_make_resource()]
        anomalies = [
            {"resource_id": "r1", "resource_type": "ecs", "monthly_cost": 9999, "threshold": 500, "anomaly_score": 19.9, "is_anomaly": True},
        ]
        output_path = tmp_path / "report.md"
        content = generate_report(resources, anomalies, [], [], str(output_path))
        assert "r1" in content
        assert "9999" in content

    def test_creates_missing_parent_dirs(self, tmp_path) -> None:
        nested = tmp_path / "deep" / "nested" / "report.md"
        generate_report([], [], [], [], str(nested))
        assert nested.exists()

    def test_empty_predictions_section(self, tmp_path) -> None:
        output_path = tmp_path / "report.md"
        content = generate_report([], [], [], [], str(output_path))
        assert "无预测数据" in content or "无" in content

    def test_clusters_section(self, tmp_path) -> None:
        clusters = [
            {"resource_id": "r1", "resource_type": "ecs", "cluster_id": 0},
            {"resource_id": "r2", "resource_type": "ecs", "cluster_id": 0},
            {"resource_id": "r3", "resource_type": "rds", "cluster_id": 1},
            {"resource_id": "r4", "resource_type": "rds", "cluster_id": -1},
        ]
        output_path = tmp_path / "report.md"
        content = generate_report([], [], [], clusters, str(output_path))
        # cluster_id=-1 should appear as "离群点" or "-1"
        assert "-1" in content