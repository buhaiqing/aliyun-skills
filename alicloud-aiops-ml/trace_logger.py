"""Structured trace logging for AIOps pipeline — AI self-analysis data source.

Produces machine-parseable JSON trace artifacts that capture the full
execution trace: timing, inputs, outputs, model parameters, data quality
metrics, and error context for every pipeline step.

Design goals:
1. AI can determine WHAT happened (input/output summaries)
2. AI can determine HOW LONG it took (per-step and total timing)
3. AI can determine WHY decisions were made (model params, thresholds)
4. AI can assess data QUALITY (CMS completeness, null counts, edge cases)
5. AI can compare runs (provenance: region, days, parameters, timestamps)
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """ISO 8601 timestamp with microsecond precision."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")


def _now_ms() -> float:
    """Monotonic clock in milliseconds for duration computation."""
    return time.perf_counter() * 1000


@dataclass
class TraceStep:
    """A single pipeline step with full observability.

    Fields:
        step_id: Unique step identifier (e.g. "collect", "detect_anomalies")
        step_index: 1-indexed sequential position in pipeline
        started_at: ISO 8601 timestamp with microseconds
        ended_at: ISO 8601 timestamp with microseconds (set on completion)
        duration_ms: Wall-clock duration in milliseconds
        status: "OK" | "ERROR" | "SKIP"
        input_summary: Lightweight description of inputs (keys=str, values=primitive)
        output_summary: Lightweight description of outputs
        metrics: Step-specific quantitative metrics (see per-step contract)
        model_params: Model/hyperparameter values used in this step (for AI reproducibility)
        data_quality: Data quality indicators (null counts, edge case counts, completeness)
        error: Error message if status=ERROR
        warnings: Non-fatal warnings collected during execution
    """

    step_id: str
    step_index: int
    started_at: str = field(default_factory=_now_iso)
    ended_at: str = ""
    duration_ms: float = 0.0
    status: str = "OK"
    input_summary: dict[str, Any] = field(default_factory=dict)
    output_summary: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    model_params: dict[str, Any] = field(default_factory=dict)
    data_quality: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    def add_warning(self, message: str) -> None:
        """Append a non-fatal warning."""
        self.warnings.append(message)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        d = asdict(self)
        d["error"] = self.error  # preserve None as null in JSON
        return d


@dataclass
class TraceRun:
    """Complete pipeline execution trace.

    Fields:
        run_id: UUID4 unique identifier for this run
        started_at: ISO 8601 timestamp when pipeline started
        ended_at: ISO 8601 timestamp when pipeline finished
        region: Alibaba Cloud region
        days: Metrics analysis window in days
        total_duration_ms: Total wall-clock time
        exit_code: Pipeline exit code (0=success, 1=partial, 2=fatal)
        steps: Ordered list of pipeline steps
        summary: Run-level aggregate metrics
        provenance: Environment metadata (CLI version, OS, Python version)
    """

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: str = field(default_factory=_now_iso)
    ended_at: str = ""
    region: str = ""
    days: int = 7
    total_duration_ms: float = 0.0
    exit_code: int = -1
    steps: list[TraceStep] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    user_id: str | None = None
    platform: str | None = None
    chat_type: str | None = None

    @classmethod
    def new(cls, **kwargs: Any) -> "TraceRun":
        """Factory that auto-injects user_id/session_id/platform from chat context.

        Caller-supplied kwargs win over the bound ChatContext defaults.
        """
        from alicloud_shared.chat_context import current

        ctx = current()
        if ctx is not None:
            kwargs.setdefault("user_id", ctx.user_id)
            kwargs.setdefault("session_id", ctx.session_id)
            kwargs.setdefault("platform", ctx.platform)
            kwargs.setdefault("chat_type", ctx.chat_type)
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "region": self.region,
            "days": self.days,
            "total_duration_ms": self.total_duration_ms,
            "exit_code": self.exit_code,
            "steps": [s.to_dict() for s in self.steps],
            "summary": self.summary,
            "provenance": self.provenance,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "platform": self.platform,
            "chat_type": self.chat_type,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class TraceLogger:
    """Thread-safe structured trace logger.

    Usage:
        tracer = TraceLogger(output_dir=".runtime/traces")
        run = tracer.start_run(region="cn-hangzhou", days=7)

        with tracer.step("collect", step_index=1) as step:
            resources = collect_all_flat(region)
            step.output_summary = {"resource_count": len(resources)}
            step.metrics = {"resource_count": len(resources), "by_type": {...}}

        tracer.finish_run(exit_code=0)
        tracer.write_trace()
    """

    def __init__(self, output_dir: str = ".runtime/traces") -> None:
        self._output_dir = Path(output_dir)
        self._lock = threading.Lock()
        self._current_run: TraceRun | None = None
        self._run_start_ms: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_run(self, region: str, days: int) -> TraceRun:
        """Begin a new pipeline run and record provenance."""
        import platform
        import sys

        self._run_start_ms = _now_ms()
        self._current_run = TraceRun(region=region, days=days)
        self._current_run.provenance = {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "started_at_iso": self._current_run.started_at,
        }
        logger.info("Trace run started: %s (region=%s, days=%d)",
                      self._current_run.run_id, region, days)
        return self._current_run

    @contextmanager
    def step(self, step_id: str, step_index: int) -> Generator[TraceStep, None, None]:
        """Context manager that auto-records step timing and status.

        On normal exit: status="OK", records ended_at and duration_ms.
        On exception: status="ERROR", records error message, re-raises.
        If step.status is pre-set to "SKIP": recorded as skipped.
        """
        if self._current_run is None:
            raise RuntimeError("start_run() must be called before step()")

        step = TraceStep(step_id=step_id, step_index=step_index)
        start_ms = _now_ms()
        logger.debug("Step %d/%s started", step_index, step_id)

        try:
            yield step
        except Exception as exc:
            step.status = "ERROR"
            step.error = str(exc)
            step.ended_at = _now_iso()
            step.duration_ms = round(_now_ms() - start_ms, 4)
            logger.error("Step %d/%s FAILED: %s (%.2fms)",
                          step_index, step_id, exc, step.duration_ms)
            self._record_step(step)
            raise
        else:
            step.ended_at = _now_iso()
            step.duration_ms = round(_now_ms() - start_ms, 4)
            # Respect pre-set SKIP status
            if step.status not in ("SKIP", "ERROR"):
                step.status = "OK"
            logger.debug("Step %d/%s %s (%.2fms)",
                          step_index, step_id, step.status, step.duration_ms)
            self._record_step(step)

    def finish_run(self, exit_code: int) -> None:
        """Finalize the run with exit code and summary."""
        if self._current_run is None:
            raise RuntimeError("start_run() must be called before finish_run()")

        total_ms = round(_now_ms() - self._run_start_ms, 2)
        with self._lock:
            self._current_run.ended_at = _now_iso()
            self._current_run.total_duration_ms = total_ms
            self._current_run.exit_code = exit_code
            self._current_run.summary = self._compute_summary()

        logger.info("Trace run finished: %s (exit=%d, %.0fms)",
                      self._current_run.run_id, exit_code, total_ms)

    def write_trace(self) -> Path | None:
        """Write trace JSON to disk. Returns path or None on failure.

        Graceful degradation: never raises on I/O failure.
        """
        if self._current_run is None:
            logger.warning("write_trace() called with no active run")
            return None

        try:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            filename = f"trace_{self._current_run.run_id}.json"
            path = self._output_dir / filename
            path.write_text(self._current_run.to_json(), encoding="utf-8")
            logger.info("Trace written: %s", path)
            return path
        except (OSError, IOError) as exc:
            logger.warning("Failed to write trace: %s", exc)
            return None

    def summary_text(self) -> str:
        """Human-readable trace summary in diagnostic logging format."""
        if self._current_run is None:
            return "[WARN] No active trace run"

        run = self._current_run
        lines = [
            f"[SUMMARY] RUN_ID={run.run_id[:8]} REGION={run.region} "
            f"DAYS={run.days} EXIT={run.exit_code} "
            f"DURATION={run.total_duration_ms / 1000:.1f}s",
        ]
        for step in run.steps:
            status = step.status
            sid = step.step_id
            dur = f" {step.duration_ms / 1000:.1f}s" if step.duration_ms > 0 else ""
            if status == "SKIP":
                lines.append(f"[RESULT] STEP_{step.step_index}=SKIP {sid}")
            elif status == "ERROR":
                lines.append(f"[RESULT] STEP_{step.step_index}=ERROR {sid}: {step.error}{dur}")
            else:
                # Include key metrics in summary
                key_parts = []
                if step.metrics:
                    for k, v in sorted(step.metrics.items()):
                        if isinstance(v, (int, float, str)):
                            key_parts.append(f"{k}={v}")
                detail = f": {', '.join(key_parts[:3])}" if key_parts else ""
                lines.append(f"[RESULT] STEP_{step.step_index}=OK {sid}{detail}{dur}")
            if step.warnings:
                for w in step.warnings:
                    lines.append(f"[WARN] {w}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_step(self, step: TraceStep) -> None:
        with self._lock:
            if self._current_run:
                self._current_run.steps.append(step)

    def _compute_summary(self) -> dict[str, Any]:
        run = self._current_run
        if run is None:
            return {}

        ok = sum(1 for s in run.steps if s.status == "OK")
        err = sum(1 for s in run.steps if s.status == "ERROR")
        skip = sum(1 for s in run.steps if s.status == "SKIP")

        # Extract key metrics from step outputs
        resource_count = 0
        anomaly_count = 0
        cluster_count = 0
        noise_count = 0
        predicted_total = 0.0

        for step in run.steps:
            sid = step.step_id
            if sid == "collect" and "resource_count" in step.metrics:
                resource_count = step.metrics["resource_count"]
            elif sid == "detect_anomalies" and "anomaly_count" in step.metrics:
                anomaly_count = step.metrics["anomaly_count"]
            elif sid == "predict_cost" and "predicted_total_cost" in step.metrics:
                predicted_total = step.metrics["predicted_total_cost"]
            elif sid == "cluster":
                cluster_count = step.metrics.get("cluster_count", 0)
                noise_count = step.metrics.get("noise_count", 0)

        return {
            "resource_count": resource_count,
            "anomaly_count": anomaly_count,
            "predicted_total_cost": predicted_total,
            "cluster_count": cluster_count,
            "noise_count": noise_count,
            "ok_steps": ok,
            "error_steps": err,
            "skip_steps": skip,
            "total_warnings": sum(len(s.warnings) for s in run.steps),
        }
