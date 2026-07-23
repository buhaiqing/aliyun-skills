#!/usr/bin/env python3
"""
PolarDB MySQL 慢 SQL 聚合分析工具 (Slow SQL Aggregator)

功能：从 DescribeSlowLogRecords API 全量拉取慢 SQL 记录，按 SQLHash 去重汇总，
     生成多维度分析报告（按次数/总耗时 Top N、节点分布、数据库分布、时间分布）。

用法：
  python3 slow-sql-aggregator.py \
    --cluster-id pc-xxx \
    --start-time "2026-06-10T08:28Z" \
    --end-time "2026-06-10T09:28Z" \
    [--page-size 100] [--top-n 15] [--output report.txt]

依赖：
  - aliyun CLI 已安装并配置凭证 (ALIBABA_CLOUD_ACCESS_KEY_ID / ALIBABA_CLOUD_ACCESS_KEY_SECRET)
  - Python 3.7+ (仅使用 stdlib)

安全：凭证通过环境变量传入，脚本不读取/存储/输出任何密钥。
"""

import argparse
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

# ──────────────────────────────────────────────
# 配置常量
# ──────────────────────────────────────────────
ENV_KEY_ID = "ALIBABA_CLOUD_ACCESS_KEY_ID"
ENV_KEY_SECRET = "ALIBABA_CLOUD_ACCESS_KEY_SECRET"
ENV_REGION = "ALIBABA_CLOUD_REGION_ID"

DEFAULT_PAGE_SIZE = 100
DEFAULT_TOP_N = 15
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds, exponential: base^attempt


def _check_prerequisites() -> None:
    """Pre-flight: verify aliyun CLI and credentials."""
    # Check aliyun CLI
    try:
        subprocess.run(["aliyun", "version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[ERROR] TYPE=PREREQUISITE FIX=Install aliyun CLI: https://aliyuncli.alicdn.com/install.sh")
        sys.exit(2)

    # Check credentials (region checked later, allows --region CLI override)
    missing = []
    for var in [ENV_KEY_ID, ENV_KEY_SECRET]:
        if not os.environ.get(var):
            missing.append(var)
    if missing:
        print(f"[ERROR] TYPE=PREREQUISITE FIX=Set env vars: {', '.join(missing)}")
        sys.exit(2)

    # Warn if region also not set (but don't halt — may be passed via --region)
    if not os.environ.get(ENV_REGION):
        print(f"[WARN] {ENV_REGION} not set; must provide --region CLI argument")


class FetchError(Exception):
    """Raised when API call fails after all retries exhausted."""
    def __init__(self, page: int, exit_code: int, stderr: str):
        self.page = page
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"Page {page} API call failed after {MAX_RETRIES} retries (exit={exit_code})")


class EmptyPage(Exception):
    """Raised when API returns success but zero records (normal end-of-data)."""
    pass


def fetch_slow_log_page(cluster_id: str, start_time: str, end_time: str,
                        page: int, page_size: int,
                        region: str | None = None) -> list[dict[str, Any]]:
    """Call aliyun polardb DescribeSlowLogRecords for a single page.

    Args:
        region: 阿里云区域，优先 CLI 参数，其次环境变量 ALIBABA_CLOUD_REGION_ID。
               若都未设置则 HALT。

    Raises:
        FetchError: API 调用失败且重试耗尽。
        EmptyPage: API 成功但无数据（正常分页终止信号）。
    """
    actual_region = region or os.environ.get(ENV_REGION, "")
    if not actual_region:
        print(f"[ERROR] TYPE=PREREQUISITE FIX=Set --region or env var {ENV_REGION}")
        sys.exit(2)

    cmd = [
        "aliyun", "polardb", "DescribeSlowLogRecords",
        "--RegionId", actual_region,
        "--DBClusterId", cluster_id,
        "--StartTime", start_time,
        "--EndTime", end_time,
        "--PageSize", str(page_size),
        "--PageNumber", str(page),
    ]

    last_error: tuple[int, str] | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            print(f"[WARN] Page {page} attempt {attempt}/{MAX_RETRIES} timed out")
            last_error = (-1, "timeout")
            time.sleep(RETRY_BACKOFF_BASE ** attempt)
            continue

        if result.returncode != 0:
            last_error = (result.returncode, result.stderr.strip())
            print(f"[WARN] Page {page} attempt {attempt}/{MAX_RETRIES} failed (exit={result.returncode})")
            time.sleep(RETRY_BACKOFF_BASE ** attempt)
            continue

        # Parse JSON response
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            last_error = (-2, "non-JSON response")
            print(f"[WARN] Page {page} attempt {attempt}/{MAX_RETRIES} returned non-JSON response")
            time.sleep(RETRY_BACKOFF_BASE ** attempt)
            continue

        records = data.get("Items", {}).get("SQLSlowRecord", [])
        if not records:
            raise EmptyPage()
        return records

    # All retries exhausted
    raise FetchError(page, last_error[0] if last_error else -1,
                     last_error[1] if last_error else "unknown")


def fetch_all_slow_logs(cluster_id: str, start_time: str, end_time: str,
                        page_size: int = DEFAULT_PAGE_SIZE,
                        region: str | None = None) -> list[dict[str, Any]]:
    """Fetch all slow log records with automatic pagination.

    Pagination stops when EmptyPage is raised (normal end-of-data).
    FetchError propagates to caller — no silent data loss.
    """
    all_records: list[dict[str, Any]] = []
    page = 1

    print(f"[DIAG] Fetching slow logs: cluster={cluster_id} range=[{start_time}, {end_time}] region={region or os.environ.get(ENV_REGION, '?')}")

    # First page
    try:
        first_page = fetch_slow_log_page(cluster_id, start_time, end_time, 1, page_size, region)
    except EmptyPage:
        print("[INFO] No slow log records found in time range.")
        return []
    all_records.extend(first_page)

    # Keep fetching until EmptyPage (natural end) or FetchError (failure)
    while True:
        page += 1
        try:
            records = fetch_slow_log_page(cluster_id, start_time, end_time, page, page_size, region)
        except EmptyPage:
            break  # Normal termination: no more data
        all_records.extend(records)
        if page % 5 == 0:
            print(f"[DIAG] Fetched page {page}, total records so far: {len(all_records)}")

    print(f"[RESULT] Total records fetched: {len(all_records)} (pages: {page})")
    return all_records


def aggregate_by_sqlhash(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate records by SQLHash — count, total/max/avg time, rows scanned."""
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "count": 0,
        "total_time_ms": 0,
        "max_ms": 0,
        "rows_scanned": 0,
        "db": "",
        "sample": "",
    })

    for r in records:
        h = r.get("SQLHash", "?")
        s = stats[h]
        s["count"] += 1
        t = r.get("QueryTimeMS", 0)
        s["total_time_ms"] += t
        s["max_ms"] = max(s["max_ms"], t)
        s["rows_scanned"] += r.get("ParseRowCounts", 0)
        s["db"] = r.get("DBName", "")
        s["sample"] = r.get("SQLText", "")

    for h in stats:
        s = stats[h]
        s["avg_ms"] = s["total_time_ms"] / s["count"]

    return stats


def aggregate_by_node(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate records by DBNodeId."""
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "total_ms": 0})
    for r in records:
        n = r.get("DBNodeId", "?")
        stats[n]["count"] += 1
        stats[n]["total_ms"] += r.get("QueryTimeMS", 0)
    return stats


def aggregate_by_database(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate records by DBName."""
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "total_ms": 0})
    for r in records:
        d = r.get("DBName", "?")
        stats[d]["count"] += 1
        stats[d]["total_ms"] += r.get("QueryTimeMS", 0)
    return stats


def aggregate_by_time(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate records by minute-level time buckets."""
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "total_ms": 0, "max_ms": 0})
    for r in records:
        ts = r.get("ExecutionStartTime", "")[:16]  # YYYY-MM-DDTHH:MM
        stats[ts]["count"] += 1
        t = r.get("QueryTimeMS", 0)
        stats[ts]["total_ms"] += t
        stats[ts]["max_ms"] = max(stats[ts]["max_ms"], t)
    return stats


def format_report(records: list[dict[str, Any]], cluster_id: str,
                  start_time: str, end_time: str, top_n: int) -> str:
    """Generate formatted multi-section analysis report."""
    lines = []
    sep = "=" * 90

    # Header
    lines.append(sep)
    lines.append("PolarDB 慢 SQL 聚合分析报告")
    lines.append(f"集群: {cluster_id} | 时间范围: {start_time} ~ {end_time}")
    lines.append(f"报告生成时间: {datetime.now().isoformat()}")
    lines.append(sep)
    lines.append(f"总记录数: {len(records)}")
    lines.append("")

    # Section 1: Top N by count
    hash_stats = aggregate_by_sqlhash(records)
    by_count = sorted(hash_stats.items(), key=lambda x: -x[1]["count"])
    by_time = sorted(hash_stats.items(), key=lambda x: -x[1]["total_time_ms"])

    lines.append(sep)
    lines.append(f"Top {top_n} 慢 SQL（按出现次数）")
    lines.append(sep)
    for i, (h, s) in enumerate(by_count[:top_n], 1):
        lines.append(f"\n#{i} SQLHash: {h}")
        lines.append(f"   数据库: {s['db']} | 次数: {s['count']} | 总耗时: {s['total_time_ms']/1000:.1f}s | 最大: {s['max_ms']/1000:.1f}s | 平均: {s['avg_ms']/1000:.1f}s")
        lines.append(f"   总扫描行数: {s['rows_scanned']:,}")
        lines.append(f"   示例SQL: {s['sample'][:300]}")

    # Section 2: Top N by total time
    lines.append("")
    lines.append(sep)
    lines.append(f"Top {top_n} 慢 SQL（按总耗时）")
    lines.append(sep)
    for i, (h, s) in enumerate(by_time[:top_n], 1):
        lines.append(f"\n#{i} SQLHash: {h}")
        lines.append(f"   数据库: {s['db']} | 次数: {s['count']} | 总耗时: {s['total_time_ms']/1000:.1f}s | 最大: {s['max_ms']/1000:.1f}s | 平均: {s['avg_ms']/1000:.1f}s")
        lines.append(f"   总扫描行数: {s['rows_scanned']:,}")
        lines.append(f"   示例SQL: {s['sample'][:300]}")

    # Section 3: Node distribution
    node_stats = aggregate_by_node(records)
    lines.append("")
    lines.append(sep)
    lines.append("按节点分布")
    lines.append(sep)
    for n, s in sorted(node_stats.items(), key=lambda x: -x[1]["count"]):
        lines.append(f"  {n}: {s['count']} 条 | 总耗时 {s['total_ms']/1000:.1f}s")

    # Section 4: Database distribution
    db_stats = aggregate_by_database(records)
    lines.append("")
    lines.append(sep)
    lines.append("按数据库分布")
    lines.append(sep)
    for d, s in sorted(db_stats.items(), key=lambda x: -x[1]["count"]):
        lines.append(f"  {d}: {s['count']} 条 | 总耗时 {s['total_ms']/1000:.1f}s")

    # Section 5: Time distribution
    time_stats = aggregate_by_time(records)
    lines.append("")
    lines.append(sep)
    lines.append("慢查询时间分布（按分钟）")
    lines.append(sep)
    for ts in sorted(time_stats.keys()):
        s = time_stats[ts]
        lines.append(f"  {ts}: {s['count']:>4} 条 | 总耗时 {s['total_ms']/1000:>6.1f}s | 最大 {s['max_ms']/1000:>5.1f}s")

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="PolarDB MySQL 慢 SQL 聚合分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 slow-sql-aggregator.py \\
    --cluster-id pc-m5euynyck962mwbqg \\
    --start-time "2026-06-10T08:28Z" \\
    --end-time "2026-06-10T09:28Z" \\
    --output report.txt

环境变量:
  ALIBABA_CLOUD_ACCESS_KEY_ID      阿里云 AccessKey ID
  ALIBABA_CLOUD_ACCESS_KEY_SECRET  阿里云 AccessKey Secret
  ALIBABA_CLOUD_REGION_ID          阿里云区域 (e.g. cn-qingdao)
        """,
    )
    parser.add_argument("--cluster-id", required=True, help="PolarDB 集群 ID (e.g. pc-xxx)")
    parser.add_argument("--start-time", required=True, help="起始时间 (ISO 8601, e.g. 2026-06-10T08:28Z)")
    parser.add_argument("--end-time", required=True, help="结束时间 (ISO 8601)")
    parser.add_argument("--region", help=f"阿里云区域 (默认: 环境变量 {ENV_REGION})")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help=f"每页记录数 (默认: {DEFAULT_PAGE_SIZE})")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N, help=f"Top N 数量 (默认: {DEFAULT_TOP_N})")
    parser.add_argument("--output", "-o", help="输出文件路径 (默认: stdout)")

    args = parser.parse_args()

    # Pre-flight
    _check_prerequisites()

    # Fetch
    try:
        records = fetch_all_slow_logs(args.cluster_id, args.start_time, args.end_time, args.page_size, args.region)
    except FetchError as e:
        print(f"[ERROR] TYPE=API_FAILURE FIX=Check network/credentials, or retry later. {e}")
        sys.exit(1)
    if not records:
        print("[INFO] No slow log records found.")
        sys.exit(0)

    # Analyze & format
    report = format_report(records, args.cluster_id, args.start_time, args.end_time, args.top_n)

    # Output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[RESULT] Report saved to: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
