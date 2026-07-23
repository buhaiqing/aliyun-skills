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
        --traces-keep-days 7 \\
        --max-total-size-mb 1024

    # 实际执行清理
    python3 runtime_cleanup.py --apply

    # 报告输出到 JSON
    python3 runtime_cleanup.py --report cleanup-report.json
"""
import argparse
import json
import os
import subprocess
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


def iter_skill_runtime_roots(skills_dir: Path, runtime_root: Path) -> list[Path]:
    """Unified repo .runtime/ plus per-skill alicloud-*/.runtime/ trees."""
    roots: list[Path] = []
    if runtime_root.exists():
        roots.append(runtime_root)
    for skill in sorted(skills_dir.glob("alicloud-*")):
        if not skill.is_dir():
            continue
        rt = skill / ".runtime"
        if rt.is_dir() and rt not in roots:
            roots.append(rt)
    return roots


def cleanup_traces(skills_dir: Path, runtime_root: Path, keep_days: int, apply: bool) -> dict:
    """清理 SkillOpt 本地 trace JSON 与 session 索引（Local-first canonical store).

    扫描:
      - ${runtime_root}/traces/trace-*.json 以及 traces/<skill>/trace-*.json
      - alicloud-*/.runtime/traces/trace-*.json (legacy)
      - ${runtime_root}/sessions/<skill>/skillopt-session-*.json
      - */.runtime/skillopt-session-*.json (legacy)
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    skills_dir = Path(skills_dir)
    trace_scanned = 0
    trace_deleted = 0
    session_scanned = 0
    session_deleted = 0

    def _maybe_delete(path: Path, scanned_attr: str, deleted_attr: str) -> None:
        nonlocal trace_scanned, trace_deleted, session_scanned, session_deleted
        if scanned_attr == "trace":
            trace_scanned += 1
        else:
            session_scanned += 1
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            return
        if mtime >= cutoff:
            return
        if scanned_attr == "trace":
            trace_deleted += 1
        else:
            session_deleted += 1
        if apply:
            try:
                path.unlink()
            except OSError:
                pass

    for rt_root in iter_skill_runtime_roots(skills_dir, runtime_root):
        traces_dir = rt_root / "traces"
        if traces_dir.is_dir():
            for pattern in ("trace-*.json", "*/trace-*.json"):
                for f in traces_dir.glob(pattern):
                    if f.is_file():
                        _maybe_delete(f, "trace", "trace")

        for pattern in ("skillopt-session-*.json",):
            for f in rt_root.glob(pattern):
                if f.is_file():
                    _maybe_delete(f, "session", "session")

    sessions_root = runtime_root / "sessions"
    if sessions_root.is_dir():
        for f in sessions_root.glob("*/skillopt-session-*.json"):
            if f.is_file():
                _maybe_delete(f, "session", "session")

    return {
        "trace_scanned": trace_scanned,
        "trace_deleted": trace_deleted,
        "trace_kept": trace_scanned - trace_deleted,
        "session_scanned": session_scanned,
        "session_deleted": session_deleted,
        "session_kept": session_scanned - session_deleted,
    }


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


def cleanup_memory(memory_keep_days: int, apply: bool) -> dict:
    """调用 gcl_memory.py --maintain 清理执行记忆过期条目.

    gcl_memory.py 位于 alicloud-gcl-runner-ops/scripts/gcl_memory.py.
    如果找不到 gcl_memory.py, 静默跳过 (非 fatal).
    """
    skills_dir = os.environ.get("SKILLS_DIR", SKILLS_DIR)
    gcl_memory_path = Path(skills_dir) / "alicloud-gcl-runner-ops" / "scripts" / "gcl_memory.py"
    if not gcl_memory_path.is_file():
        return {"status": "skipped", "reason": f"gcl_memory.py not found at {gcl_memory_path}"}

    datetime.now(timezone.utc) - timedelta(days=memory_keep_days)
    memory_root = Path(skills_dir) / ".runtime" / "memory"
    if not memory_root.exists():
        return {"status": "skipped", "reason": f"memory root not found: {memory_root}"}

    cmd = [
        sys.executable, str(gcl_memory_path),
        "--maintain",
        "--keep-days", str(memory_keep_days),
        "--memory-root", str(memory_root),
    ]
    if apply:
        cmd.append("--apply")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return {"status": "error", "rc": proc.returncode, "stderr": proc.stderr.strip()}
        # Parse stdout for result dict (last line is JSON)
        last_line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
        try:
            result = json.loads(last_line)
            result["status"] = "ok"
            return result
        except json.JSONDecodeError:
            return {"status": "ok", "rc": proc.returncode, "raw": proc.stdout.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "error", "reason": str(exc)}


def cleanup_reflexion(reflexion_decay_days: int, apply: bool) -> dict:
    """调用 gcl_reflexion.py maintain 裁剪低频率/过期失败模式."""
    skills_dir = os.environ.get("SKILLS_DIR", SKILLS_DIR)
    gcl_reflexion_path = Path(skills_dir) / "alicloud-gcl-runner-ops" / "scripts" / "gcl_reflexion.py"
    if not gcl_reflexion_path.is_file():
        return {"status": "skipped", "reason": f"gcl_reflexion.py not found at {gcl_reflexion_path}"}

    reflexion_root = Path(skills_dir) / ".runtime" / "reflexion"
    if not reflexion_root.exists():
        return {"status": "skipped", "reason": f"reflexion root not found: {reflexion_root}"}

    cmd = [
        sys.executable, str(gcl_reflexion_path),
        "maintain",
        "--decay-days", str(reflexion_decay_days),
        "--reflexion-root", str(reflexion_root),
    ]
    if apply:
        cmd.append("--apply")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return {"status": "error", "rc": proc.returncode, "stderr": proc.stderr.strip()}
        return {
            "status": "ok",
            "rc": proc.returncode,
            "stdout_tail": proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "",
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "error", "reason": str(exc)}


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
                f.stat().st_size / (1024 * 1024)
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
    p.add_argument("--traces-keep-days", type=int, default=None,
                   help="SkillOpt 本地 trace 保留天数 (默认: TRACE_KEEP_DAYS 或 7)")
    p.add_argument("--max-total-size-mb", type=float, default=1024.0,
                   help=".runtime/ 最大总大小 MB (默认 1024 = 1GB)")
    p.add_argument("--memory-keep-days", type=int, default=None,
                   help="执行记忆保留天数 (默认: MEMORY_KEEP_DAYS 环境变量或 30)")
    p.add_argument("--reflexion-decay-days", type=int, default=None,
                   help="Reflexion 模式衰减天数 (默认: REFLEXION_DECAY_DAYS 或 90)")
    p.add_argument("--apply", action="store_true",
                   help="实际执行删除 (默认 dry-run)")
    p.add_argument("--traces-only", action="store_true",
                   help="仅清理 SkillOpt 本地 trace/session（跳过 baseline/audit/logs 等）")
    p.add_argument("--report", default=None,
                   help="报告输出到 JSON 文件")
    args = p.parse_args()

    # Resolve memory_keep_days: CLI arg → env var → default 30
    memory_keep_days = args.memory_keep_days or int(os.environ.get("MEMORY_KEEP_DAYS", "30"))
    reflexion_decay_days = args.reflexion_decay_days or int(os.environ.get("REFLEXION_DECAY_DAYS", "90"))
    traces_keep_days = args.traces_keep_days or int(os.environ.get("TRACE_KEEP_DAYS", "7"))
    skills_dir_path = Path(os.environ.get("SKILLS_DIR", SKILLS_DIR))

    runtime_root = get_runtime_root()
    if args.traces_only:
        print("==========================================")
        print("  SkillOpt Trace Cleanup")
        print(f"  SKILLS_DIR: {skills_dir_path}")
        print(f"  RUNTIME_ROOT: {runtime_root}")
        print(f"  模式: {'APPLY (实际删除)' if args.apply else 'DRY-RUN (只列出, 不删除)'}")
        print(f"  traces_keep_days: {traces_keep_days}")
        print("==========================================\n")
        result = cleanup_traces(skills_dir_path, runtime_root, traces_keep_days, args.apply)
        print(
            f"  trace: scanned={result['trace_scanned']} deleted={result['trace_deleted']} "
            f"kept={result['trace_kept']}"
        )
        print(
            f"  session: scanned={result['session_scanned']} deleted={result['session_deleted']} "
            f"kept={result['session_kept']}"
        )
        if not args.apply:
            print("\n  [WARN]  DRY-RUN 模式, 未实际删除.  真正清理加 --apply")
        if args.report:
            report = {
                "runtime_root": str(runtime_root),
                "skills_dir": str(skills_dir_path),
                "apply": args.apply,
                "traces_keep_days": traces_keep_days,
                "actions": {"traces": result},
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False))
            print(f"\n[报告] {args.report}")
        return

    if not runtime_root.exists():
        print(f"[INFO] .runtime/ 不存在: {runtime_root}")
        print("[HINT] 调一次 configdrift.sh / baseline-manager.py 自动创建")
        return

    total_before = get_dir_size_mb(runtime_root)
    print("==========================================")
    print("  Runtime Cleanup (Sprint 19)")
    print(f"  RUNTIME_ROOT: {runtime_root}")
    print(f"  模式: {'APPLY (实际删除)' if args.apply else 'DRY-RUN (只列出, 不删除)'}")
    print(f"  当前总大小: {total_before:.2f} MB")
    print("==========================================\n")

    report = {
        "runtime_root": str(runtime_root),
        "apply": args.apply,
        "total_size_mb_before": round(total_before, 2),
        "baseline_keep_days": args.baseline_keep_days,
        "audit_keep_days": args.audit_keep_days,
        "logs_keep_days": args.logs_keep_days,
        "traces_keep_days": traces_keep_days,
        "max_total_size_mb": args.max_total_size_mb,
        "memory_keep_days": memory_keep_days,
        "reflexion_decay_days": reflexion_decay_days,
        "actions": {},
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    # 1. baseline (标记过期, 不直接删)
    print(f"[1/8] baseline (keep={args.baseline_keep_days}d) ...")
    result = cleanup_baseline(runtime_root, args.baseline_keep_days, args.apply)
    print(f"  scanned={result['scanned']}  marked_expired={result['marked_expired']}  skipped={result['skipped']}")
    report["actions"]["baseline"] = result

    # 2. audit
    print(f"[2/8] audit (keep={args.audit_keep_days}d) ...")
    result = cleanup_audit(runtime_root, args.audit_keep_days, args.apply)
    kept = result.get("scanned", 0) - result.get("deleted", 0)
    print(f"  scanned={result['scanned']}  deleted={result['deleted']}  kept={kept}")
    result["kept"] = kept
    report["actions"]["audit"] = result

    # 3. logs
    print(f"[3/8] logs (keep={args.logs_keep_days}d) ...")
    result = cleanup_logs(runtime_root, args.logs_keep_days, args.apply)
    kept = result.get("scanned", 0) - result.get("deleted", 0)
    print(f"  scanned={result['scanned']}  deleted={result['deleted']}  kept={kept}")
    result["kept"] = kept
    report["actions"]["logs"] = result

    # 4. SkillOpt local traces (canonical; Langfuse is optional mirror)
    print(f"[4/8] traces (keep={traces_keep_days}d) ...")
    result = cleanup_traces(skills_dir_path, runtime_root, traces_keep_days, args.apply)
    print(
        f"  trace scanned={result['trace_scanned']} deleted={result['trace_deleted']} "
        f"kept={result['trace_kept']}"
    )
    print(
        f"  session scanned={result['session_scanned']} deleted={result['session_deleted']} "
        f"kept={result['session_kept']}"
    )
    report["actions"]["traces"] = result

    # 5. cache (全部)
    print("[5/8] cache (all) ...")
    result = cleanup_cache(runtime_root, args.apply)
    print(f"  scanned={result['scanned']}  deleted={result['deleted']}")
    report["actions"]["cache"] = result

    # 6. memory (执行记忆)
    print(f"[6/8] memory (keep={memory_keep_days}d) ...")
    result = cleanup_memory(memory_keep_days, args.apply)
    print(f"  status={result.get('status')}  scanned_files={result.get('scanned_files', '?')}  "
          f"pruned={result.get('entries_pruned', '?')}")
    report["actions"]["memory"] = result

    # 7. reflexion (模式记忆)
    print(f"[7/8] reflexion (decay={reflexion_decay_days}d) ...")
    result = cleanup_reflexion(reflexion_decay_days, args.apply)
    print(f"  status={result.get('status')}  detail={result.get('stdout_tail', result.get('reason', ''))}")
    report["actions"]["reflexion"] = result

    # 8. size limit
    print(f"[8/8] size limit (max={args.max_total_size_mb} MB) ...")
    result = enforce_size_limit(runtime_root, args.max_total_size_mb, args.apply)
    if result["enforced"]:
        print(f"  [WARN]  超限 ({result['total_size_mb']} > {result['limit_mb']} MB), 清理 {result['deleted']} 个文件")
    else:
        print(f"  PASS 未超限 ({result['total_size_mb']} <= {result['limit_mb']} MB)")
    report["actions"]["size_limit"] = result

    total_after = get_dir_size_mb(runtime_root)
    report["total_size_mb_after"] = round(total_after, 2)
    report["size_freed_mb"] = round(total_before - total_after, 2)

    print("\n==========================================")
    print(f"  总大小: {total_before:.2f} MB -> {total_after:.2f} MB")
    print(f"  释放: {total_before - total_after:.2f} MB")
    if not args.apply:
        print("  [WARN]  DRY-RUN 模式, 未实际删除.  真正清理加 --apply")
    print("==========================================")

    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\n[报告] {args.report}")


if __name__ == "__main__":
    main()
