#!/usr/bin/env python3
"""
cost-watch.py v1.0 — 每日成本监控与预警

功能:
  1. 成本异常检测 — 本月 vs 上月环比 >30% 告警，按产品钻取
  2. 资源到期预警 — 资源包/储蓄计划/预留实例 30 天内到期
  3. RI/SCU 覆盖率检查 — 整体 <70% 告警
  4. 预算跟踪 — 当月花费 vs 预算限额
  5. 账户健康摘要 — 余额/代金券/储值卡总览

用法:
  python3 cost-watch.py                          # 全部检查
  python3 cost-watch.py --budget 50000           # 自定义预算 (默认 10000)
  python3 cost-watch.py --anomaly-only           # 仅异常检测
  python3 cost-watch.py --output-dir ./reports   # 指定输出目录

兼容:
  macOS (date -v) / Linux (date -d) 双平台
"""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Sprint 14: 复用 _shared.q_cached 替代本地 q()
# 收益: 12 次 bssopenapi 调用自动获得 1h 文件系统缓存 (跨进程+跨脚本)
#      + 复用 _CMS_SEM 限速 + 退避重试 + 缓存命中统计
from _shared import q_cached

# ── 日期工具 ──

def _current_month() -> str:
    return datetime.now().strftime("%Y-%m")

def _last_month() -> str:
    now = datetime.now()
    # Cross-platform: try date -v (macOS), fallback to date -d (Linux)
    try:
        result = subprocess.run(
            ["date", "-v-1m", "+%Y-%m"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["date", "-d", "1 month ago", "+%Y-%m"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    # Fallback: subtract 30 days
    from datetime import timedelta
    return (now - timedelta(days=30)).strftime("%Y-%m")


# ── 检查项 1: 成本异常检测 ──

def _days_in_month(year: int, month: int) -> int:
    """Return number of days in a given month."""
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    return (next_month - datetime(year, month, 1)).days


def check_cost_anomaly(current_month: str, last_month: str) -> dict:
    """本月 vs 上月总花费环比（按日均归一化）。返回异常详情或 None."""
    result = {"total_current": 0, "total_last": 0, "daily_current": 0, "daily_last": 0,
              "change_pct": 0, "anomaly": False, "products": []}

    current = q_cached(["bssopenapi", "QueryBillOverview", "--BillingCycle", current_month])
    last = q_cached(["bssopenapi", "QueryBillOverview", "--BillingCycle", last_month])

    if not current or not last:
        return result

    current_items = current.get("Data", {}).get("Items", {}).get("Item", [])
    last_items = last.get("Data", {}).get("Items", {}).get("Item", [])

    def total(items):
        return sum(float(i.get("PretaxAmount", 0) or 0) for i in items)

    # Partial month normalization: compare daily averages
    now = datetime.now()
    cur_year, cur_month = int(current_month[:4]), int(current_month[5:7])
    las_year, las_month = int(last_month[:4]), int(last_month[5:7])
    cur_days = min(now.day, _days_in_month(cur_year, cur_month))
    las_days = _days_in_month(las_year, las_month)

    total_cur = total(current_items)
    total_las = total(last_items)
    result["total_current"] = round(total_cur, 2)
    result["total_last"] = round(total_las, 2)
    result["daily_current"] = round(total_cur / cur_days, 2) if cur_days > 0 else 0
    result["daily_last"] = round(total_las / las_days, 2) if las_days > 0 else 0

    if result["daily_last"] > 0:
        result["change_pct"] = round((result["daily_current"] / result["daily_last"] - 1) * 100, 1)

    # Product breakdown with daily normalization
    from collections import defaultdict
    product_map = defaultdict(lambda: {"name": "", "current": 0.0, "last": 0.0})
    for i in current_items:
        code = i.get("ProductCode", "unknown")
        product_map[code]["name"] = i.get("ProductName", code)
        product_map[code]["current"] += float(i.get("PretaxAmount", 0) or 0)
    for i in last_items:
        code = i.get("ProductCode", "unknown")
        if code not in product_map:
            product_map[code]["name"] = i.get("ProductName", code)
        product_map[code]["last"] += float(i.get("PretaxAmount", 0) or 0)

    for code, info in sorted(product_map.items(), key=lambda x: x[1]["current"], reverse=True):
        cur_daily = round(info["current"] / cur_days, 2) if cur_days > 0 else 0
        las_daily = round(info["last"] / las_days, 2) if las_days > 0 else 0
        result["products"].append({
            "code": code,
            "name": info["name"],
            "current_month": round(info["current"], 2),
            "last_month": round(info["last"], 2),
            "daily_current": cur_daily,
            "daily_last": las_daily,
            "change": round((cur_daily / las_daily - 1) * 100, 1) if las_daily > 0 else 0,
        })

    # Alert level (now based on daily average, not raw totals)
    abs_change = abs(result["change_pct"])
    if abs_change > 50:
        result["level"] = "P0_CRITICAL"
        result["anomaly"] = True
    elif abs_change > 30:
        result["level"] = "P1_WARNING"
        result["anomaly"] = True
    else:
        result["level"] = "OK"

    return result


# ── 检查项 2: 资源到期预警 ──

def check_expiry(threshold_days: int = 30) -> dict:
    """检查资源包/储蓄计划/预留实例到期。"""
    result = {"resource_packages": [], "savings_plans": [], "total_expiring": 0}

    # Resource packages
    rp = q_cached(["bssopenapi", "QueryResourcePackageInstances", "--PageNum", "1", "--PageSize", "100"])
    if rp:
        instances = rp.get("Data", {}).get("Instances", {}).get("Instance", [])
        for inst in instances:
            if inst.get("Status") != "Valid":
                continue
            expiry = inst.get("ExpiryTime", "")
            if not expiry:
                continue
            try:
                exp_dt = datetime.strptime(expiry, "%Y-%m-%dT%H:%M:%SZ")
                days_left = (exp_dt - datetime.now()).days
                if 0 <= days_left <= threshold_days:
                    result["resource_packages"].append({
                        "id": inst.get("InstanceId", ""),
                        "type": inst.get("PackageType", ""),
                        "remaining": inst.get("RemainingAmount", ""),
                        "total": inst.get("TotalAmount", ""),
                        "expiry": expiry,
                        "days_left": days_left,
                    })
            except (ValueError, TypeError):
                continue

    # Savings plans
    sp = q_cached(["bssopenapi", "QuerySavingsPlansInstance", "--PageNum", "1", "--PageSize", "100"])
    if sp:
        items = sp.get("Data", {}).get("Items", [])
        for item in items:
            if item.get("Status") != "NORMAL":
                continue
            end = item.get("EndTime", "")
            if not end:
                continue
            try:
                end_dt = datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ")
                days_left = (end_dt - datetime.now()).days
                value_str = item.get("CurrentPoolValue", "0")
                pool_value = float(value_str) if value_str else 0
                if 0 <= days_left <= threshold_days or pool_value < 100:
                    result["savings_plans"].append({
                        "id": item.get("InstanceId", ""),
                        "type": item.get("SavingsType", ""),
                        "pool_value": pool_value,
                        "end": end,
                        "days_left": days_left,
                    })
            except (ValueError, TypeError):
                continue

    result["total_expiring"] = len(result["resource_packages"]) + len(result["savings_plans"])
    return result


# ── 检查项 3: RI/SCU 覆盖率 ──

def check_coverage() -> dict:
    """RI/SCU 覆盖率检查。"""
    result = {"coverage_pct": 0, "product_coverage": [], "low_coverage": []}

    total = q_cached(["bssopenapi", "DescribeResourceCoverageTotal"])
    if total:
        tc = total.get("Data", {}).get("TotalCoverage", {})
        result["coverage_pct"] = float(tc.get("CoveragePercentage", 0) or 0)

    detail = q_cached(["bssopenapi", "DescribeResourceCoverageDetail", "--PageNum", "1", "--PageSize", "20"])
    if detail:
        items = detail.get("Data", {}).get("Items", [])
        for item in items:
            cov = float(item.get("CoveragePercentage", 0) or 0)
            entry = {
                "code": item.get("CommodityCode", ""),
                "coverage": cov,
                "quantity": item.get("TotalQuantity", 0),
                "unit": item.get("CapacityUnit", ""),
            }
            result["product_coverage"].append(entry)
            if cov < 80:
                result["low_coverage"].append(entry)

    return result


# ── 检查项 4: 预算跟踪 ──

def check_budget(budget_limit: float) -> dict:
    """当月花费 vs 预算。"""
    result = {"budget": budget_limit, "spend": 0, "pct": 0, "balance": "0", "alert": False}

    overview = q_cached(["bssopenapi", "QueryBillOverview", "--BillingCycle", _current_month()])
    bal = q_cached(["bssopenapi", "QueryAccountBalance"])

    if overview:
        items = overview.get("Data", {}).get("Items", {}).get("Item", [])
        result["spend"] = round(sum(float(i.get("PretaxAmount", 0) or 0) for i in items), 2)
        result["pct"] = round(result["spend"] / budget_limit * 100, 1) if budget_limit > 0 else 0

    if bal:
        result["balance"] = bal.get("Data", {}).get("AvailableAmount", "0")

    if result["pct"] >= 90:
        result["level"] = "P0_CRITICAL"
        result["alert"] = True
    elif result["pct"] >= 80:
        result["level"] = "P1_WARNING"
        result["alert"] = True
    else:
        result["level"] = "OK"

    return result


# ── 检查项 5: 账户健康摘要 ──

def check_account_health() -> dict:
    """账户金融健康摘要。"""
    result = {
        "balance": "0", "credit": "0",
        "coupons": [], "prepaid_cards": [],
        "active_orders": [],
    }

    bal = q_cached(["bssopenapi", "QueryAccountBalance"])
    if bal:
        result["balance"] = bal.get("Data", {}).get("AvailableAmount", "0")
        result["credit"] = bal.get("Data", {}).get("CreditAmount", "0")

    coupons = q_cached(["bssopenapi", "QueryCashCoupons"])
    if coupons:
        for c in coupons.get("Data", {}).get("CashCoupon", []):
            if c.get("Status") == "Available":
                result["coupons"].append({
                    "id": c.get("CashCouponId", ""),
                    "value": c.get("NominalValue", ""),
                    "balance": c.get("Balance", ""),
                    "expiry": c.get("ExpiryTime", ""),
                })

    cards = q_cached(["bssopenapi", "QueryPrepaidCards"])
    if cards:
        for c in cards.get("Data", {}).get("PrepaidCard", []):
            result["prepaid_cards"].append({
                "id": c.get("PrepaidCardId", ""),
                "value": c.get("NominalValue", ""),
                "balance": c.get("Balance", ""),
                "expiry": c.get("ExpiryTime", ""),
            })

    orders = q_cached(["bssopenapi", "QueryOrders", "--PageNum", "1", "--PageSize", "5"])
    if orders:
        for o in orders.get("Data", {}).get("OrderList", {}).get("Order", []):
            result["active_orders"].append({
                "id": o.get("OrderId", ""),
                "product": o.get("ProductCode", ""),
                "status": o.get("PaymentStatus", ""),
                "time": o.get("CreateTime", ""),
            })

    return result


# ── 报告生成 ──

def generate_report(anomaly, expiry, coverage, budget, health, output_dir: Path):
    """生成 Markdown 报告 + JSON 持久化。"""
    now = datetime.now(timezone.utc)
    rid = f"costwatch-{now.strftime('%Y%m%dT%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    md_path = output_dir / f"{rid}.md"
    js_path = output_dir / f"{rid}.json"

    # ── JSON ──
    report_json = {
        "report_id": rid,
        "timestamp": now.isoformat(),
        "checks": {
            "anomaly": anomaly,
            "expiry": expiry,
            "coverage": coverage,
            "budget": budget,
            "health": health,
        },
    }
    js_path.write_text(json.dumps(report_json, indent=2, ensure_ascii=False, default=str))

    # ── Markdown ──
    lines = []
    lines.append("# CostWatch 每日成本监控报告")
    lines.append("")
    lines.append(f"**时间**: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    lines.append(f"**报告ID**: {rid}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1) Cost anomaly
    lines.append("## 1️⃣ 成本异常检测")
    lines.append("")
    level_icon = {"P0_CRITICAL": "CRITICAL", "P1_WARNING": "WARNING", "OK": "PASS"}
    emoji = level_icon.get(anomaly.get("level", "OK"), "PASS")
    lines.append(f"{emoji} **等级**: {anomaly.get('level', 'OK')}")
    lines.append("")
    lines.append("| 指标 | 金额 (CNY) |")
    lines.append("|------|:---------:|:")
    lines.append(f"| 本月 ({_current_month()}) | {anomaly['total_current']:>10.2f} |")
    lines.append(f"| 上月 ({_last_month()}) | {anomaly['total_last']:>10.2f} |")
    lines.append(f"| 日均本月 | {anomaly['daily_current']:>10.2f} CNY/天 |")
    lines.append(f"| 日均上月 | {anomaly['daily_last']:>10.2f} CNY/天 |")
    lines.append(f"| 日均环比变化 | {anomaly['change_pct']:>+9.1f}% |")
    lines.append("")

    anomaly_items = anomaly.get("products", [])
    if anomaly_items:
        lines.append("### 产品级钻取（按日均环比排序）")
        lines.append("")
        lines.append("| 产品 | 日均本月 (CNY) | 日均上月 (CNY) | 变化 | 月度预估 |")
        lines.append("|------|:-------------:|:-------------:|:----:|:--------:|")
        # Sort by absolute daily change descending
        sorted_items = sorted(anomaly_items, key=lambda x: abs(x.get('change', 0)), reverse=True)
        for p in sorted_items[:10]:
            chg = p.get('change', 0)
            sign = "CRITICAL" if chg > 30 else ("WARNING" if chg > 10 else ("SAFE" if chg < -30 else ""))
            daily_cur = p.get('daily_current', 0)
            daily_las = p.get('daily_last', 0)
            monthly_est = daily_cur * 30  # projected full-month cost
            lines.append(f"| {p['name']} | {daily_cur:>10.2f} | {daily_las:>10.2f} | {sign} {chg:>+6.1f}% | {monthly_est:>8.0f} CNY |")

    # 2) Expiry
    lines.append("## 2️⃣ 资源到期预警")
    lines.append("")
    if expiry["total_expiring"] > 0:
        lines.append(f"[WARN] **{expiry['total_expiring']}** 个资源即将到期")
        lines.append("")
        for rp in expiry["resource_packages"]:
            lines.append(f"- CRITICAL 资源包 `{rp['id']}` ({rp['type']}): 剩余 {rp['remaining']}/{rp['total']}, {rp['days_left']} 天后到期")
        for sp in expiry["savings_plans"]:
            warn = "CRITICAL" if sp["pool_value"] < 100 else "WARNING"
            lines.append(f"- {warn} 储蓄计划 `{sp['id']}` ({sp['type']}): 池值 {sp['pool_value']:.0f} CNY, {sp['days_left']} 天后到期")
        lines.append("")
    else:
        lines.append("PASS 无 30 天内到期的资源。")
        lines.append("")

    lines.append("---")
    lines.append("")

    # 3) Coverage
    lines.append("## 3️⃣ RI/SCU 覆盖率")
    lines.append("")
    cov = coverage["coverage_pct"]
    cov_icon = "CRITICAL" if cov < 70 else ("WARNING" if cov < 80 else "PASS")
    lines.append(f"{cov_icon} **整体覆盖率**: {cov:.1f}%")
    lines.append("")
    if coverage["low_coverage"]:
        lines.append("### 低覆盖率产品")
        lines.append("")
        lines.append("| 产品 | 覆盖率 | 按量付费量 |")
        lines.append("|------|:------:|:---------:|")
        for p in coverage["low_coverage"]:
            lines.append(f"| {p['code']} | {p['coverage']:.1f}% | {p['quantity']} {p['unit']} |")
        lines.append("")
    lines.append("")

    lines.append("---")
    lines.append("")

    # 4) Budget
    lines.append("## 4️⃣ 预算跟踪")
    lines.append("")
    budget_icon = {"P0_CRITICAL": "CRITICAL", "P1_WARNING": "WARNING", "OK": "PASS"}
    b_emoji = budget_icon.get(budget.get("level", "OK"), "PASS")
    lines.append(f"{b_emoji} **预算**: {budget['budget']:.0f} CNY | **已花费**: {budget['spend']:.2f} CNY | **使用率**: {budget['pct']:.1f}%")
    lines.append("")
    lines.append(f"| 账户余额 | {budget['balance']} CNY |")
    lines.append("")

    lines.append("---")
    lines.append("")

    # 5) Health
    lines.append("## 5️⃣ 账户金融健康摘要")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|------|:---:|")
    lines.append(f"| 可用余额 | {health['balance']} CNY |")
    lines.append(f"| 信用额度 | {health['credit']} CNY |")
    lines.append(f"| 可用代金券 | {len(health['coupons'])} 张 |")
    if health["coupons"]:
        total_coupon = sum(float(c.get("balance", 0) or 0) for c in health["coupons"])
        lines.append(f"| 代金券总余额 | {total_coupon:.2f} CNY |")
    lines.append(f"| 储值卡 | {len(health['prepaid_cards'])} 张 |")
    lines.append("")
    if health["active_orders"]:
        lines.append("### 近期订单")
        lines.append("")
        lines.append("| 订单ID | 产品 | 状态 |")
        lines.append("|--------|------|:----:|")
        for o in health["active_orders"]:
            lines.append(f"| {o['id']} | {o['product']} | {o['status']} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*由 alicloud-billing-ops cost-watch.py 自动生成*")

    md_path.write_text("\n".join(lines))
    print(f"PASS Report: {md_path} ({md_path.stat().st_size} bytes)")
    print(f"PASS JSON:   {js_path} ({js_path.stat().st_size} bytes)")

    return rid


# ── 主入口 ──

def main():
    parser = argparse.ArgumentParser(description="CostWatch 每日成本监控")
    parser.add_argument("--budget", type=float, default=10000, help="月预算限额 (默认 10000 CNY)")
    parser.add_argument("--anomaly-only", action="store_true", help="仅执行成本异常检测")
    parser.add_argument("--expiry-only", action="store_true", help="仅执行到期检查")
    parser.add_argument("--output-dir", default="./reports", help="报告输出目录 (默认 ./reports)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)

    print("=" * 50)
    print("  CostWatch v1.0 — 每日成本监控")
    print("=" * 50)
    print()

    current = _current_month()
    last = _last_month()
    print(f"[INFO] 本月: {current} | 上月: {last}")
    print()

    results = {}

    # 1) Anomaly
    if not args.expiry_only:
        print("[1/5] 成本异常检测...", end=" ")
        results["anomaly"] = check_cost_anomaly(current, last)
        anomaly = results["anomaly"]
        print(f"{anomaly['level']} (当月: {anomaly['total_current']:.2f}, 上月: {anomaly['total_last']:.2f}, 环比: {anomaly['change_pct']:+.1f}%)")

    # 2) Expiry
    if not args.anomaly_only:
        print("[2/5] 资源到期预警...", end=" ")
        results["expiry"] = check_expiry()
        print(f"{results['expiry']['total_expiring']} 个即将到期")

        # 3) Coverage
        print("[3/5] RI/SCU 覆盖率...", end=" ")
        results["coverage"] = check_coverage()
        print(f"{results['coverage']['coverage_pct']:.1f}%")

        # 4) Budget
        print("[4/5] 预算跟踪...", end=" ")
        results["budget"] = check_budget(args.budget)
        b = results["budget"]
        print(f"{b['pct']:.1f}% ({b['spend']:.2f} / {b['budget']:.0f})")

        # 5) Health
        print("[5/5] 账户健康摘要...", end=" ")
        results["health"] = check_account_health()
        h = results["health"]
        print(f"余额: {h['balance']} CNY, 代金券: {len(h['coupons'])}张, 储值卡: {len(h['prepaid_cards'])}张")

    print()

    # Report
    rid = generate_report(
        results.get("anomaly", {}),
        results.get("expiry", {}),
        results.get("coverage", {}),
        results.get("budget", {}),
        results.get("health", {}),
        output_dir,
    )

    print()
    print(f"[SUMMARY] Report: {rid}")
    print(f"[SUMMARY] Output: {output_dir.resolve()}")

    # Sprint 14: 输出缓存统计, 便于观测缓存命中收益
    from _shared import cache_stats
    cs = cache_stats()
    print(f"[CACHE] {cs['total']} calls, hit_rate={cs['hit_rate']*100:.0f}% (hit={cs['hit']} miss={cs['miss']} bypass={cs['bypass']})")


if __name__ == "__main__":
    main()
