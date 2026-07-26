"""Tests for trace_logger.py — structured trace logging for AI self-analysis."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from trace_logger import TraceLogger, TraceRun, TraceStep, _now_iso


class TestTraceStep:
    """TraceStep unit tests."""

    def test_basic_creation(self) -> None:
        step = TraceStep(step_id="collect", step_index=1)
        assert step.step_id == "collect"
        assert step.step_index == 1
        assert step.status == "OK"
        assert step.error is None
        assert step.warnings == []

    def test_to_dict(self) -> None:
        step = TraceStep(step_id="collect", step_index=1)
        step.output_summary = {"resource_count": 42}
        step.metrics = {"resource_count": 42}
        d = step.to_dict()
        assert d["step_id"] == "collect"
        assert d["step_index"] == 1
        assert d["status"] == "OK"
        assert d["error"] is None
        assert d["output_summary"]["resource_count"] == 42

    def test_add_warning(self) -> None:
        step = TraceStep(step_id="test", step_index=1)
        step.add_warning("test warning")
        assert len(step.warnings) == 1
        assert step.warnings[0] == "test warning"

    def test_timestamp_format(self) -> None:
        step = TraceStep(step_id="test", step_index=1)
        # started_at should be ISO 8601 with microseconds
        assert "T" in step.started_at
        assert "." in step.started_at  # microseconds separator


class TestTraceRun:
    """TraceRun unit tests."""

    def test_basic_creation(self) -> None:
        run = TraceRun(region="cn-hangzhou", days=7)
        assert run.region == "cn-hangzhou"
        assert run.days == 7
        assert len(run.run_id) == 36  # UUID4
        assert run.steps == []

    def test_to_dict(self) -> None:
        run = TraceRun(region="cn-hangzhou", days=7)
        step = TraceStep(step_id="collect", step_index=1)
        run.steps.append(step)
        d = run.to_dict()
        assert d["region"] == "cn-hangzhou"
        assert d["days"] == 7
        assert len(d["steps"]) == 1
        assert d["steps"][0]["step_id"] == "collect"

    def test_to_json(self) -> None:
        run = TraceRun(region="cn-hangzhou", days=7)
        step = TraceStep(step_id="collect", step_index=1)
        run.steps.append(step)
        j = run.to_json()
        data = json.loads(j)
        assert data["region"] == "cn-hangzhou"
        assert len(data["steps"]) == 1

    def test_provenance(self) -> None:
        run = TraceRun(region="cn-hangzhou", days=7)
        run.provenance = {"python_version": "3.12", "platform": "darwin"}
        d = run.to_dict()
        assert d["provenance"]["python_version"] == "3.12"


class TestTraceLogger:
    """TraceLogger integration tests."""

    @pytest.fixture
    def tracer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield TraceLogger(output_dir=tmpdir)

    def test_start_run(self, tracer) -> None:
        run = tracer.start_run(region="cn-hangzhou", days=7)
        assert run.region == "cn-hangzhou"
        assert run.days == 7
        assert len(run.run_id) == 36

    def test_step_context_manager_ok(self, tracer) -> None:
        tracer.start_run(region="cn-hangzhou", days=7)
        with tracer.step("collect", step_index=1) as step:
            step.output_summary = {"resource_count": 10}
            step.metrics = {"resource_count": 10}
        assert step.status == "OK"
        assert step.duration_ms > 0
        assert step.ended_at != ""

    def test_step_context_manager_error(self, tracer) -> None:
        tracer.start_run(region="cn-hangzhou", days=7)
        with pytest.raises(ValueError, match="test error"):
            with tracer.step("test", step_index=1) as step:
                raise ValueError("test error")
        # Step should be recorded with ERROR status
        run = tracer._current_run
        assert run is not None
        assert len(run.steps) == 1
        assert run.steps[0].status == "ERROR"
        assert "test error" in run.steps[0].error

    def test_step_context_manager_skip(self, tracer) -> None:
        tracer.start_run(region="cn-hangzhou", days=7)
        with tracer.step("enrich_tags", step_index=2) as step:
            step.status = "SKIP"
        assert step.status == "SKIP"
        assert step.duration_ms >= 0

    def test_full_run(self, tracer) -> None:
        """End-to-end: 7-step pipeline with trace output."""
        tracer.start_run(region="cn-hangzhou", days=7)

        with tracer.step("collect", step_index=1) as step:
            step.output_summary = {"resource_count": 42}
            step.metrics = {
                "resource_count": 42,
                "by_type": {"ecs": 10, "rds": 8, "redis": 6, "slb": 5, "oss": 8, "k8s_node": 5},
            }

        with tracer.step("enrich_tags", step_index=2) as step:
            step.status = "SKIP"

        with tracer.step("extract_features", step_index=3) as step:
            step.metrics = {
                "feature_count": 15,
                "feature_names": ["cpu_cores", "memory_gb", "disk_gb", "monthly_cost"],
            }
            step.data_quality = {"total": 42, "zero_monthly_cost": 5, "cms_data_available_pct": 85.7}

        with tracer.step("detect_anomalies", step_index=4) as step:
            step.metrics = {
                "anomaly_count": 3,
                "anomaly_ratio": 0.071,
                "threshold_value": 2345.67,
                "mean_cost": 1234.50,
                "std_cost": 555.58,
            }
            step.model_params = {
                "method": "z_score_threshold",
                "contamination": 0.1,
                "formula": "mean_cost + 2 * max(std_cost, 1)",
            }

        with tracer.step("predict_cost", step_index=5) as step:
            step.metrics = {
                "predicted_total_cost": 45678.90,
                "mae": 123.45,
            }
            step.model_params = {"method": "ols_linear_regression", "features": ["cpu_cores", "memory_gb"]}

        with tracer.step("cluster", step_index=6) as step:
            step.metrics = {"cluster_count": 5, "noise_count": 2}
            step.model_params = {"method": "vectorized_dbscan", "eps": 0.5, "min_samples": 1}

        with tracer.step("generate_report", step_index=7) as step:
            step.metrics = {"report_size_bytes": 8521, "format": "markdown"}

        tracer.finish_run(exit_code=0)
        trace_path = tracer.write_trace()

        # Verify file was written
        assert trace_path is not None
        assert trace_path.exists()

        # Verify JSON is valid and complete
        data = json.loads(trace_path.read_text())
        assert data["region"] == "cn-hangzhou"
        assert data["days"] == 7
        assert data["exit_code"] == 0
        assert len(data["steps"]) == 7
        assert data["total_duration_ms"] > 0

        # Verify step ordering
        step_ids = [s["step_id"] for s in data["steps"]]
        assert step_ids == [
            "collect", "enrich_tags", "extract_features",
            "detect_anomalies", "predict_cost", "cluster", "generate_report",
        ]

        # Verify model params are captured
        anomaly_step = data["steps"][3]
        assert anomaly_step["model_params"]["method"] == "z_score_threshold"
        assert anomaly_step["model_params"]["contamination"] == 0.1

        cluster_step = data["steps"][5]
        assert cluster_step["model_params"]["eps"] == 0.5

        # Verify data quality is captured
        feature_step = data["steps"][2]
        assert "data_quality" in feature_step
        assert feature_step["data_quality"]["cms_data_available_pct"] == 85.7

        # Verify summary is computed
        assert data["summary"]["resource_count"] == 42
        assert data["summary"]["anomaly_count"] == 3
        assert data["summary"]["cluster_count"] == 5
        assert data["summary"]["noise_count"] == 2

    def test_summary_text_format(self, tracer) -> None:
        tracer.start_run(region="cn-hangzhou", days=7)
        with tracer.step("collect", step_index=1) as step:
            step.metrics = {"resource_count": 42, "by_type": {"ecs": 10}}
        with tracer.step("enrich_tags", step_index=2) as step:
            step.status = "SKIP"
        tracer.finish_run(exit_code=0)
        text = tracer.summary_text()
        assert "[SUMMARY]" in text
        assert "RUN_ID=" in text
        assert "REGION=cn-hangzhou" in text
        assert "STEP_1=OK collect" in text
        assert "STEP_2=SKIP enrich_tags" in text
        assert "EXIT=0" in text

    def test_write_trace_graceful_degradation(self) -> None:
        """write_trace() to non-writable directory should not raise."""
        tracer = TraceLogger(output_dir="/nonexistent/path/that/cannot/be/created")
        tracer.start_run(region="cn-hangzhou", days=7)
        tracer.finish_run(exit_code=0)
        # Should not raise
        path = tracer.write_trace()
        assert path is None  # graceful failure

    def test_empty_run(self, tracer) -> None:
        tracer.start_run(region="cn-hangzhou", days=7)
        tracer.finish_run(exit_code=0)
        trace_path = tracer.write_trace()
        assert trace_path is not None
        data = json.loads(trace_path.read_text())
        assert data["steps"] == []
        assert data["exit_code"] == 0

    def test_step_without_start_run(self, tracer) -> None:
        with pytest.raises(RuntimeError, match="start_run"):
            with tracer.step("test", step_index=1):
                pass

    def test_timestamps_are_sequential(self, tracer) -> None:
        tracer.start_run(region="cn-hangzhou", days=7)
        with tracer.step("step1", step_index=1):
            pass
        with tracer.step("step2", step_index=2):
            pass
        tracer.finish_run(exit_code=0)
        run = tracer._current_run
        assert run is not None
        assert run.steps[0].started_at <= run.steps[1].started_at
        assert run.steps[0].ended_at <= run.steps[1].started_at

    def test_duration_is_positive(self, tracer) -> None:
        tracer.start_run(region="cn-hangzhou", days=7)
        with tracer.step("test", step_index=1):
            pass
        assert tracer._current_run is not None
        step = tracer._current_run.steps[0]
        assert step.duration_ms >= 0
        assert step.duration_ms < 5000  # should be very fast

    def test_provenance_is_recorded(self, tracer) -> None:
        tracer.start_run(region="cn-hangzhou", days=7)
        tracer.finish_run(exit_code=0)
        run = tracer._current_run
        assert run is not None
        assert "python_version" in run.provenance
        assert "platform" in run.provenance
        assert "started_at_iso" in run.provenance
