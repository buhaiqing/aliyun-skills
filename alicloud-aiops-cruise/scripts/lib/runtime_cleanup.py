"""runtime_cleanup.py — .runtime/ 清理工具 (Sprint 19)

提供 .runtime/ 中过期数据清理 + 大小限制, 防止 .runtime/ 膨胀.

默认 dry-run 模式 (安全第一), 需显式 --apply 才真正删除.

Usage:
    # 默认 dry-run, 列出将清理的文件
    python3 runtime_cleanup.py

    # 自定义保留天数
    python3 runtime_cleanup.py \\
        --baseline-keep-days 90 \\
        --audit-keep-days 30 \\
        --logs-keep-days 7 \\
        --max-total-size-mb 1024

    # 实际执行清理
    python3 runtime_cleanup.py --apply

    # 报告输出到 JSON
    python3 runtime_cleanup.py --report cleanup-report.json
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 确保 scripts/lib 可导入
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Sprint 19 修复: 显式设置 SKILLS_DIR, 避免 get_runtime_root fallback 到 skill 内部
# __file__ = alicloud-aiops-cruise/scripts/lib/runtime_cleanup.py
# 父 1 = alicloud-aiops-cruise/scripts/lib
# 父 2 = alicloud-aiops-cruise/scripts
# 父 3 = alicloud-aiops-cruise
# 父 4 = aliyun-skills (正确的统一根目录)
SKILLS_DIR = str(Path(__file__).resolve().parent.parent.parent.parent)
os.environ.setdefault("SKILLS_DIR", SKILLS_DIR)

from runtime_root import get_runtime_root


def get_dir_size_mb(path: Path) -> float:
    """递归计算目录大小 (MB)."""
    if not path.exists():
        return 0.0
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def cleanup_baseline(runtime_root: Path, keep_days: int, apply: bool) -> dict:
    """清理 .runtime/baseline/ 中超过 keep_days 的目录.

    策略: 不直接删除, 而是重命名为 .expired (与 baseline-manager 一致).
    实际删除由 retention cleanup job 异步处理.
    """
    baseline_dir = runtime_root / "baseline"
    if not baseline_dir.exists():
        return {"scanned": 0, "marked_expired": 0, "skipped": 0}

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    scanned = 0
    marked = 0

    for entry in sorted(baseline_dir.iterdir()):
        if not entry.is_dir() or entry.name.endswith(".expired"):
            continue
        scanned += 1
        try:
            entry_date = datetime.strptime(entry.name, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if entry_date < cutoff:
            if apply:
                entry.rename(entry.parent / (entry.name + ".expired"))
            marked += 1

    return {"scanned": scanned, "marked_expired": marked, "skipped": scanned - marked}


def cleanup_audit(runtime_root: Path, keep_days: int, apply: bool) -> dict:
    """清理 .runtime/audit/<skill>/ 中超过 keep_days 的旧文件."""
    audit_root = runtime_root / "audit"
    if not audit_root.exists():
        return {"scanned": 0, "deleted": 0}

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    scanned = 0
    deleted = 0

    for f in audit_root.rglob("*"):
        if not f.is_file():
            continue
        scanned += 1
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            if apply:
                try:
                    f.unlink()
                except OSError:
                    pass
            deleted += 1

    return {"scanned": scanned, "deleted": deleted, "kept": scanned - deleted}


def cleanup_logs(runtime_root: Path, keep_days: int, apply: bool) -> dict:
    """清理 .runtime/logs/<skill>/ 中超过 keep_days 的旧日志."""
    logs_root = runtime_root / "logs"
    if not logs_root.exists():
        return {"scanned": 0, "deleted": 0}

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    scanned = 0
    deleted = 0

    for f in logs_root.rglob("*.log"):
        if not f.is_file():
            continue
        scanned += 1
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            if apply:
                try:
                    f.unlink()
                except OSError:
                    pass
            deleted += 1

    return {"scanned": scanned, "deleted": deleted, "kept": scanned - deleted}


def cleanup_cache(runtime_root: Path, apply: bool) -> dict:
    """清理 .runtime/cache/ 所有缓存文件 (cache 是临时的)."""
    cache_dir = runtime_root / "cache"
    if not cache_dir.exists():
        return {"scanned": 0, "deleted": 0}

    scanned = 0
    deleted = 0
    for f in cache_dir.rglob("*"):
        if f.is_file():
            scanned += 1
            if apply:
                try:
                    f.unlink()
                    deleted += 1
                except OSError:
                    pass
            else:
                deleted += 1  # dry-run 也计为 "将删除"

    return {"scanned": scanned, "deleted": deleted}


def enforce_size_limit(runtime_root: Path, max_size_mb: float, apply: bool) -> dict:
    """如果 .runtime/ 总量超过 max_size_mb, 从最旧开始删文件."""
    if not runtime_root.exists():
        return {"total_size_mb": 0.0, "limit_mb": max_size_mb, "enforced": False, "deleted": 0}

    current_size = get_dir_size_mb(runtime_root)
    if current_size <= max_size_mb:
        return {"total_size_mb": round(current_size, 2), "limit_mb": max_size_mb,
                "enforced": False, "deleted": 0}

    # 超过限制, 按 mtime 升序遍历 (最旧的先删)
    all_files = []
    for f in runtime_root.rglob("*"):
        if f.is_file() and not f.name.endswith(".expired"):
            try:
                all_files.append((f.stat().st_mtime, f))
            except OSError:
                pass
    all_files.sort()  # 按 mtime 升序

    deleted = 0
    for _, f in all_files:
        if get_dir_size_mb(runtime_root) <= max_size_mb:
            break
        if apply:
            try:
                size = f.stat().st_size / (1024 * 1024)
                f.unlink()
                deleted += 1
            except OSError:
                pass
        else:
            deleted += 1  # dry-run 计数

    return {"total_size_mb": round(current_size, 2), "limit_mb": max_size_mb,
            "enforced": True, "deleted": deleted}


def main():
    p = argparse.ArgumentParser(description="Sprint 19: .runtime/ 清理工具")
    p.add_argument("--baseline-keep-days", type=int, default=90,
                   help="baseline 保留天数 (默认 90)")
    p.add_argument("--audit-keep-days", type=int, default=30,
                   help="audit 报告保留天数 (默认 30)")
    p.add_argument("--logs-keep-days", type=int, default=7,
                   help="logs 保留天数 (默认 7)")
    p.add_argument("--max-total-size-mb", type=float, default=1024.0,
                   help=".runtime/ 最大总大小 MB (默认 1024 = 1GB)")
    p.add_argument("--apply", action="store_true",
                   help="实际执行删除 (默认 dry-run)")
    p.add_argument("--report", default=None,
                   help="报告输出到 JSON 文件")
    args = p.parse_args()

    runtime_root = get_runtime_root()
    if not runtime_root.exists():
        print(f"[INFO] .runtime/ 不存在: {runtime_root}")
        print(f"[HINT] 调一次 configdrift.sh / baseline-manager.py 自动创建")
        return

    total_before = get_dir_size_mb(runtime_root)
    print(f"==========================================")
    print(f"  Runtime Cleanup (Sprint 19)")
    print(f"  RUNTIME_ROOT: {runtime_root}")
    print(f"  模式: {'APPLY (实际删除)' if args.apply else 'DRY-RUN (只列出, 不删除)'}")
    print(f"  当前总大小: {total_before:.2f} MB")
    print(f"==========================================\n")

    report = {
        "runtime_root": str(runtime_root),
        "apply": args.apply,
        "total_size_mb_before": round(total_before, 2),
        "baseline_keep_days": args.baseline_keep_days,
        "audit_keep_days": args.audit_keep_days,
        "logs_keep_days": args.logs_keep_days,
        "max_total_size_mb": args.max_total_size_mb,
        "actions": {},
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    # 1. baseline (标记过期, 不直接删)
    print(f"[1/4] baseline (keep={args.baseline_keep_days}d) ...")
    result = cleanup_baseline(runtime_root, args.baseline_keep_days, args.apply)
    print(f"  scanned={result['scanned']}  marked_expired={result['marked_expired']}  skipped={result['skipped']}")
    report["actions"]["baseline"] = result

    # 2. audit
    print(f"[2/4] audit (keep={args.audit_keep_days}d) ...")
    result = cleanup_audit(runtime_root, args.audit_keep_days, args.apply)
    kept = result.get("scanned", 0) - result.get("deleted", 0)
    print(f"  scanned={result['scanned']}  deleted={result['deleted']}  kept={kept}")
    result["kept"] = kept
    report["actions"]["audit"] = result

    # 3. logs
    print(f"[3/4] logs (keep={args.logs_keep_days}d) ...")
    result = cleanup_logs(runtime_root, args.logs_keep_days, args.apply)
    kept = result.get("scanned", 0) - result.get("deleted", 0)
    print(f"  scanned={result['scanned']}  deleted={result['deleted']}  kept={kept}")
    result["kept"] = kept
    report["actions"]["logs"] = result

    # 4. cache (全部)
    print(f"[4/4] cache (all) ...")
    result = cleanup_cache(runtime_root, args.apply)
    print(f"  scanned={result['scanned']}  deleted={result['deleted']}")
    report["actions"]["cache"] = result

    # 5. size limit
    print(f"\n[Size Limit] max={args.max_total_size_mb} MB ...")
    result = enforce_size_limit(runtime_root, args.max_total_size_mb, args.apply)
    if result["enforced"]:
        print(f"  [WARN]  超限 ({result['total_size_mb']} > {result['limit_mb']} MB), 清理 {result['deleted']} 个文件")
    else:
        print(f"  PASS 未超限 ({result['total_size_mb']} <= {result['limit_mb']} MB)")
    report["actions"]["size_limit"] = result

    total_after = get_dir_size_mb(runtime_root)
    report["total_size_mb_after"] = round(total_after, 2)
    report["size_freed_mb"] = round(total_before - total_after, 2)

    print(f"\n==========================================")
    print(f"  总大小: {total_before:.2f} MB -> {total_after:.2f} MB")
    print(f"  释放: {total_before - total_after:.2f} MB")
    if not args.apply:
        print(f"  [WARN]  DRY-RUN 模式, 未实际删除.  真正清理加 --apply")
    print(f"==========================================")

    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\n[报告] {args.report}")


if __name__ == "__main__":
    main()
