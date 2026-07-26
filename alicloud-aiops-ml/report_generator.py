"""Report generator - Markdown output for FinOps analysis."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from resource_model import Resource


def generate_report(
    resources: list[Resource],
    anomalies: list[dict],
    predictions: list[dict],
    clusters: list[dict],
    output_path: str,
) -> str:
    """Generate Markdown report from analysis results."""
    lines = [
        "# FinOps 巡检分析报告",
        f"\n> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"\n> 资源总数: {len(resources)}",
        "",
        "## 1. 资源概览",
        _section_overview(resources),
        "",
        "## 2. 异常检测",
        _section_anomalies(anomalies),
        "",
        "## 3. 成本预测",
        _section_predictions(predictions),
        "",
        "## 4. 资源聚类",
        _section_clusters(clusters),
        "",
    ]
    content = "\n".join(lines)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(content)
    return content


def _section_overview(resources: list[Resource]) -> str:
    by_type: dict[str, int] = {}
    total_cost = 0.0
    for r in resources:
        by_type[r.resource_type] = by_type.get(r.resource_type, 0) + 1
        total_cost += r.monthly_cost
    lines = ["| 类型 | 数量 |", "|------|------|"]
    for t, c in sorted(by_type.items()):
        lines.append(f"| {t} | {c} |")
    lines.append(f"\n**月度总成本**: ¥{total_cost:,.2f}")
    return "\n".join(lines)


def _section_anomalies(anomalies: list[dict]) -> str:
    flagged = [a for a in anomalies if a.get("is_anomaly")]
    if not flagged:
        return "无异常发现。"
    lines = ["| 资源ID | 类型 | 月成本 | 阈值 | 异常分 |", "|--------|------|--------|------|--------|"]
    for a in flagged:
        lines.append(f"| {a['resource_id']} | {a['resource_type']} | ¥{a['monthly_cost']:.2f} | ¥{a['threshold']:.2f} | {a['anomaly_score']:.3f} |")
    return "\n".join(lines)


def _section_predictions(predictions: list[dict]) -> str:
    if not predictions:
        return "无预测数据。"
    lines = ["| 资源ID | 实际成本 | 预测成本 | 偏差 |", "|--------|----------|----------|------|"]
    for p in predictions[:10]:
        lines.append(f"| {p['resource_id']} | ¥{p['actual_cost']:.2f} | ¥{p['predicted_cost']:.2f} | ¥{p['diff']:.2f} |")
    return "\n".join(lines)


def _section_clusters(clusters: list[dict]) -> str:
    if not clusters:
        return "无聚类数据。"
    by_cluster: dict[int, list[str]] = {}
    for c in clusters:
        cid = c["cluster_id"]
        by_cluster.setdefault(cid, []).append(c["resource_id"])
    lines = ["| 聚类ID | 资源数量 | 示例资源 |", "|--------|----------|----------|"]
    for cid, rids in sorted(by_cluster.items()):
        example = rids[0] if rids else "-"
        lines.append(f"| {cid} | {len(rids)} | {example} |")
    return "\n".join(lines)
