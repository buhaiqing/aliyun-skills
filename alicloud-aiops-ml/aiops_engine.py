"""AIOps ML Engine — unified entry point for FinOps analysis pipeline.

Orchestrates the full pipeline: collect → enrich → feature extract →
anomaly detection → cost prediction → clustering → report generation.

Produces structured trace artifacts in .runtime/traces/ for downstream
AI self-analysis of pipeline performance, data quality, and model behavior.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from pipeline import collect_all_flat
from tag_collector import enrich_tags
from feature_engine import extract_features
from iforest_detector import detect_anomalies
from xgboost_predictor import predict_cost
from dbscan_cluster import cluster_resources
from report_generator import generate_report
from trace_logger import TraceLogger


logger = logging.getLogger("aiops_engine")


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AIOps FinOps Analysis Engine — collect, analyze, and report on Alibaba Cloud resources.",
    )
    parser.add_argument(
        "--region", required=True,
        help="Alibaba Cloud region (e.g. cn-hangzhou)",
    )
    parser.add_argument(
        "--output", default=".runtime/reports",
        help="Output directory for reports (default: .runtime/reports)",
    )
    parser.add_argument(
        "--days", type=int, default=7,
        help="Days of metrics to collect (default: 7)",
    )
    parser.add_argument(
        "--format", default="markdown", choices=["markdown", "json"],
        help="Report output format (default: markdown)",
    )
    parser.add_argument(
        "--account-id", default=os.environ.get("ALIBABA_CLOUD_ACCOUNT_ID", ""),
        help="Alibaba Cloud account ID for tag enrichment (default: $ALIBABA_CLOUD_ACCOUNT_ID)",
    )
    parser.add_argument(
        "--trace-dir", default=".runtime/traces",
        help="Directory for trace JSON output (default: .runtime/traces)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def _check_prerequisites(account_id: str) -> None:
    """Verify required environment and credentials are available."""
    if not account_id:
        logger.warning(
            "No --account-id provided and ALIBABA_CLOUD_ACCOUNT_ID not set; "
            "tag enrichment will be skipped"
        )
    if not os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"):
        logger.warning(
            "ALIBABA_CLOUD_ACCESS_KEY_ID not set; API calls may fail"
        )


def _count_by_type(resources: list) -> dict[str, int]:
    """Compute resource count breakdown by resource_type."""
    by_type: dict[str, int] = {}
    for r in resources:
        by_type[r.resource_type] = by_type.get(r.resource_type, 0) + 1
    return by_type


def _compute_data_quality(resources: list, features: list[dict]) -> dict[str, Any]:
    """Compute data quality metrics for AI self-analysis.

    Returns indicators that help AI distinguish "genuinely zero" from
    "data unavailable" (CMS API failure, missing fields, etc.).
    """
    if not resources or not features:
        return {"total": 0}

    total = len(resources)
    zero_cost = sum(1 for r in resources if r.monthly_cost == 0)
    zero_cpu = sum(1 for f in features if f.get("cpu_util_avg", 0) == 0)
    zero_mem = sum(1 for f in features if f.get("mem_util_avg", 0) == 0)
    unknown_product = sum(1 for r in resources if r.product == "unknown")
    unknown_env = sum(1 for r in resources if r.env == "unknown")
    missing_cms = zero_cpu  # proxy: CPU util=0 likely means CMS unavailable

    return {
        "total": total,
        "zero_monthly_cost": zero_cost,
        "zero_cpu_util": zero_cpu,
        "zero_mem_util": zero_mem,
        "unknown_product": unknown_product,
        "unknown_env": unknown_env,
        "cms_data_available_pct": round((total - missing_cms) / max(total, 1) * 100, 1),
    }


def main(argv: list[str] | None = None) -> int:
    """Orchestrate the full FinOps analysis pipeline with structured tracing.

    Returns 0 on success, 1 on partial failure, 2 on fatal failure.
    Produces trace JSON at .runtime/traces/trace_{run_id}.json for AI analysis.
    """
    args = _parse_args(argv)
    _setup_logging(verbose=args.verbose)
    _check_prerequisites(args.account_id)

    tracer = TraceLogger(output_dir=args.trace_dir)
    tracer.start_run(region=args.region, days=args.days)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{'='*60}")
    print(f"  AIOps FinOps Analysis Engine")
    print(f"  Region: {args.region}")
    print(f"  Metrics window: {args.days} days")
    print(f"  Output: {args.output}")
    print(f"  Format: {args.format}")
    print(f"{'='*60}\n")

    # ------------------------------------------------------------------
    # Step 1: Collect resources
    # ------------------------------------------------------------------
    try:
        with tracer.step("collect", step_index=1) as step:
            step.input_summary = {"region": args.region, "days": args.days}
            resources = collect_all_flat(args.region)
            by_type = _count_by_type(resources)
            step.output_summary = {"resource_count": len(resources)}
            step.metrics = {
                "resource_count": len(resources),
                "by_type": by_type,
            }
            step.model_params = {"max_workers": 6}
        print(f"  [OK] Collected {len(resources)} resources")
    except Exception:
        tracer.finish_run(exit_code=2)
        tracer.write_trace()
        print("FATAL: Resource collection failed. Aborting.")
        return 2

    # ------------------------------------------------------------------
    # Step 2: Enrich with tags
    # ------------------------------------------------------------------
    if args.account_id:
        with tracer.step("enrich_tags", step_index=2) as step:
            step.input_summary = {
                "region": args.region,
                "resource_count": len(resources),
            }
            try:
                enriched = enrich_tags(resources, args.region, args.account_id)
                resources = enriched
                tagged = sum(1 for r in resources if r.product != "unknown")
                untagged = len(resources) - tagged
                step.output_summary = {"tagged": tagged, "untagged": untagged}
                step.metrics = {"tagged_count": tagged, "untagged_count": untagged}
                if untagged > 0:
                    step.add_warning(f"{untagged} resources have no product tag")
                print(f"  [OK] Tags enriched ({tagged} tagged, {untagged} unknown)")
            except Exception as e:
                step.add_warning(f"Tag enrichment failed: {e}")
                print(f"  [WARN] Tag enrichment failed — continuing without tags")
    else:
        with tracer.step("enrich_tags", step_index=2) as step:
            step.status = "SKIP"
        print(f"  [SKIP] Tag enrichment — no account ID available")

    # ------------------------------------------------------------------
    # Step 3: Extract features
    # ------------------------------------------------------------------
    try:
        with tracer.step("extract_features", step_index=3) as step:
            step.input_summary = {"resource_count": len(resources)}
            features = extract_features(resources)
            feature_names = list(features[0].keys()) if features else []
            dq = _compute_data_quality(resources, features)
            step.output_summary = {"feature_count": len(features)}
            step.metrics = {
                "feature_count": len(features),
                "feature_names": feature_names,
            }
            step.data_quality = dq
            step.model_params = {
                "derived_features": ["cpu_mem_ratio", "cost_per_cpu", "cost_per_gb"],
            }
            if dq.get("cms_data_available_pct", 100) < 50:
                step.add_warning(
                    f"CMS data available for only {dq['cms_data_available_pct']}% "
                    f"of resources; utilization metrics may be unreliable"
                )
        print(f"  [OK] Extracted features for {len(features)} resources")
    except Exception:
        tracer.finish_run(exit_code=2)
        tracer.write_trace()
        print("FATAL: Feature extraction failed. Aborting.")
        return 2

    # ------------------------------------------------------------------
    # Step 4: Detect anomalies
    # ------------------------------------------------------------------
    with tracer.step("detect_anomalies", step_index=4) as step:
        step.input_summary = {"resource_count": len(resources)}
        try:
            anomalies = detect_anomalies(resources, features)
            anomaly_list = [a for a in anomalies if a.get("is_anomaly")]
            anomaly_count = len(anomaly_list)
            # Extract model parameters from anomaly results
            if anomalies:
                threshold = anomalies[0].get("threshold", 0)
            else:
                threshold = 0
            costs = [f["monthly_cost"] for f in features]
            import numpy as np
            mean_cost = float(np.mean(costs)) if costs else 0.0
            std_cost = float(np.std(costs)) if len(costs) > 1 else 0.0
            step.output_summary = {"anomaly_count": anomaly_count}
            step.metrics = {
                "anomaly_count": anomaly_count,
                "total_resources": len(resources),
                "anomaly_ratio": round(anomaly_count / max(len(resources), 1), 3),
                "threshold_value": threshold,
                "mean_cost": round(mean_cost, 2),
                "std_cost": round(std_cost, 2),
            }
            step.model_params = {
                "method": "z_score_threshold",
                "contamination": 0.1,
                "formula": "mean_cost + 2 * max(std_cost, 1)",
            }
            print(f"  [OK] Detected {anomaly_count} anomalies")
        except Exception as e:
            step.add_warning(f"Anomaly detection failed: {e}")
            anomalies = []
            print(f"  [WARN] Anomaly detection failed")

    # ------------------------------------------------------------------
    # Step 5: Predict costs
    # ------------------------------------------------------------------
    with tracer.step("predict_cost", step_index=5) as step:
        step.input_summary = {"resource_count": len(resources)}
        try:
            predictions = predict_cost(resources, features)
            if predictions:
                predicted_total = sum(p.get("predicted_cost", 0) for p in predictions)
                diffs = [abs(p.get("diff", 0)) for p in predictions]
                mae = sum(diffs) / len(diffs) if diffs else 0
            else:
                predicted_total = 0
                mae = 0
            step.output_summary = {"prediction_count": len(predictions)}
            step.metrics = {
                "predicted_total_cost": round(predicted_total, 2),
                "mae": round(mae, 2),
                "prediction_count": len(predictions),
            }
            step.model_params = {
                "method": "ols_linear_regression",
                "features": ["cpu_cores", "memory_gb"],
            }
            print(f"  [OK] Cost predictions for {len(predictions)} resources")
        except Exception as e:
            step.add_warning(f"Cost prediction failed: {e}")
            predictions = []
            print(f"  [WARN] Cost prediction failed")

    # ------------------------------------------------------------------
    # Step 6: Cluster resources
    # ------------------------------------------------------------------
    with tracer.step("cluster", step_index=6) as step:
        step.input_summary = {"resource_count": len(resources)}
        try:
            clusters = cluster_resources(resources, features)
            cluster_ids = {c["cluster_id"] for c in clusters}
            unique_clusters = len(cluster_ids - {-1})
            noise_count = sum(1 for c in clusters if c["cluster_id"] == -1)
            step.output_summary = {
                "cluster_count": unique_clusters,
                "noise_count": noise_count,
            }
            step.metrics = {
                "cluster_count": unique_clusters,
                "noise_count": noise_count,
                "total_clustered": len(clusters),
            }
            step.model_params = {
                "method": "vectorized_dbscan",
                "eps": 0.5,
                "min_samples": 1,
                "features": ["cpu_cores", "memory_gb", "monthly_cost"],
            }
            print(f"  [OK] {unique_clusters} clusters identified")
        except Exception as e:
            step.add_warning(f"Clustering failed: {e}")
            clusters = []
            print(f"  [WARN] Clustering failed")

    # ------------------------------------------------------------------
    # Step 7: Generate report
    # ------------------------------------------------------------------
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.format == "json":
        import json as json_mod
        output_path = output_dir / f"finops_report_{args.region}_{timestamp}.json"
        report_data = {
            "metadata": {
                "region": args.region,
                "generated_at": datetime.now().isoformat(),
                "resource_count": len(resources),
                "anomaly_count": len([a for a in (anomalies or []) if a.get("is_anomaly")]),
            },
            "anomalies": anomalies,
            "predictions": predictions,
            "clusters": clusters,
        }
        output_path.write_text(json_mod.dumps(report_data, indent=2, default=str))
        with tracer.step("generate_report", step_index=7) as step:
            step.input_summary = {"resource_count": len(resources), "format": "json"}
            step.output_summary = {"report_path": str(output_path)}
            step.metrics = {
                "report_path": str(output_path),
                "report_size_bytes": output_path.stat().st_size,
                "format": "json",
            }
        print(f"  [OK] JSON report saved to {output_path}")
    else:
        with tracer.step("generate_report", step_index=7) as step:
            step.input_summary = {"resource_count": len(resources), "format": "markdown"}
            output_path = output_dir / f"finops_report_{args.region}_{timestamp}.md"
            generate_report(resources, anomalies, predictions, clusters, str(output_path))
            step.output_summary = {"report_path": str(output_path)}
            step.metrics = {
                "report_path": str(output_path),
                "report_size_bytes": output_path.stat().st_size,
                "format": "markdown",
            }
        print(f"  [OK] Markdown report saved to {output_path}")

    # ------------------------------------------------------------------
    # Finalize and write trace
    # ------------------------------------------------------------------
    # Determine exit code
    total_warnings = sum(len(s.warnings) for s in tracer._current_run.steps) if tracer._current_run else 0
    error_steps = sum(1 for s in (tracer._current_run.steps if tracer._current_run else []) if s.status == "ERROR")
    exit_code = 1 if error_steps > 0 else 0

    tracer.finish_run(exit_code=exit_code)
    trace_path = tracer.write_trace()

    print(f"\n{'='*60}")
    print(f"  Pipeline complete")
    print(f"  Resources: {len(resources)}")
    print(f"  Anomalies: {len([a for a in (anomalies or []) if a.get('is_anomaly')])}")
    if trace_path:
        print(f"  Trace: {trace_path}")
    print(f"  Report: {output_path}")
    print(f"{'='*60}\n")
    print(tracer.summary_text())

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
