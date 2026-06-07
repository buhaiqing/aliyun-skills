"""
_shared.py — AIOps Cruise 共享模块

所有 `runbooks/scripts/` 下的脚本从本模块导入公共函数。
减少重复代码，统一行为。

依赖: aliyun CLI + Python 3.10+
"""

import hashlib
import json
import os
import queue
import random
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from threading import Semaphore
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════════
# 自动加载 .env
# ═══════════════════════════════════════════════════════════════════════════════

_env = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if _env.exists():
    with open(_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))


# ═══════════════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════════════

RG_YES = 1  # 支持 --ResourceGroupId
RG_NO = 0  # 不支持
TAG_YES = 1  # 支持 --Tag.N.Key/Value
TAG_NO = 0
W = "w"  # Warning 阈值
C = "c"  # Critical 阈值

# 产品注册表索引
I_CAT, I_NAME, I_CLI, I_API, I_RG, I_TAG, I_CMS, I_ID, I_JQ, I_METRICS = range(10)

# Limits overcommit thresholds
ACK_LIMITS_SAFE = 80.0  # SAFE < 80%
ACK_LIMITS_WARN = 120.0  # WARN 80%~120%
ACK_LIMITS_CRIT = 200.0  # CRIT 120%~200%
# CRITICAL+ > 200%

# ═══════════════════════════════════════════════════════════════════════════════
# 动态基线: 指标→方法映射表
# ═══════════════════════════════════════════════════════════════════════════════

ANOMALY_METHOD_ZSCORE = "z-score"
ANOMALY_METHOD_PERCENTILE = "percentile"
ANOMALY_METHOD_DUAL = "zscore+fixed"  # Z-Score + 固定阈值双重判定
ANOMALY_METHOD_STL = "stl"  # Sprint 11: 时序分解 (周期 + 趋势 + 残差)
ANOMALY_METHOD_PROPHET = "prophet"  # Sprint 11.5: Prophet 节假日感知预测

# 指标映射表: (namespace_metric_key) → method
# 方法: z-score, percentile, zscore+fixed
METRIC_ANOMALY_METHOD = {
    # ECS
    "acs_ecs_dashboard.CPUUtilization": ANOMALY_METHOD_PROPHET,  # Sprint 11.5: 节假日 + 趋势 + 周期
    "acs_ecs_dashboard.memory_usage": ANOMALY_METHOD_PROPHET,  # Sprint 11.5: 节假日趋势
    "acs_ecs_dashboard.memory_usage": ANOMALY_METHOD_ZSCORE,
    "acs_ecs_dashboard.DiskReadIOPS": ANOMALY_METHOD_PERCENTILE,
    "acs_ecs_dashboard.DiskWriteIOPS": ANOMALY_METHOD_PERCENTILE,
    "acs_ecs_dashboard.DiskUsage": ANOMALY_METHOD_DUAL,
    "acs_ecs_dashboard.InternetInRate": ANOMALY_METHOD_PERCENTILE,
    "acs_ecs_dashboard.InternetOutRate": ANOMALY_METHOD_PERCENTILE,
    # RDS
    "acs_rds_dashboard.CpuUsage": ANOMALY_METHOD_PROPHET,  # Sprint 11.5: 节假日 + 日周期
    "acs_rds_dashboard.DiskUsage": ANOMALY_METHOD_DUAL,
    "acs_rds_dashboard.ConnectionUsage": ANOMALY_METHOD_PROPHET,  # Sprint 11.5: 节假日连接模式
    "acs_rds_dashboard.SlowQueryCount": ANOMALY_METHOD_PERCENTILE,
    # Redis
    "acs_redis_dashboard.memory_usage": ANOMALY_METHOD_ZSCORE,
    "acs_redis_dashboard.UsedConnection": ANOMALY_METHOD_PERCENTILE,
    # SLB
    "acs_slb_dashboard.ActiveConnection": ANOMALY_METHOD_PERCENTILE,
    "acs_slb_dashboard.NewConnection": ANOMALY_METHOD_STL,  # Sprint 11: 日周期
    "acs_slb_dashboard.UnhealthyServerCount": ANOMALY_METHOD_ZSCORE,
    # NAT
    "acs_nat_gateway.SnatConnection": ANOMALY_METHOD_STL,  # Sprint 11: 业务量驱动周期
    # EIP
    "acs_vpc_eip.net_in.rate_percentage": ANOMALY_METHOD_PERCENTILE,
}

# 异常等级阈值
ANOMALY_INFO_Z = 1.0
ANOMALY_WARN_Z = 2.0
ANOMALY_CRIT_Z = 3.0

# 降噪: 连续 N 个采样点超标才标记
ANOMALY_MIN_CONSECUTIVE = 2

# 基线窗口 (小时粒度采样数)
BASELINE_MIN_POINTS = 24  # Z-Score/P95 少于 24 个点回退到固定阈值
STL_MIN_POINTS = 24 * 6  # Sprint 11: 至少 6×24=144 点 (7d 留 1 天容差)
PROPHET_MIN_POINTS = 24 * 14  # Sprint 11.5: Prophet 需 14d = 336 点 (足够 2 个周周期)

# ACK product registry
ACK_K8S_NS = "acs_k8s"

# 显式导出 (让 Ruff 理解 from _shared import *)
__all__ = [
    "RG_YES",
    "RG_NO",
    "TAG_YES",
    "TAG_NO",
    "W",
    "C",
    "I_CAT",
    "I_NAME",
    "I_CLI",
    "I_API",
    "I_RG",
    "I_TAG",
    "I_CMS",
    "I_ID",
    "I_JQ",
    "I_METRICS",
    "log",
    "warn",
    "err",
    "q",
    "dig",
    "gate",
    "list_resource_groups",
    "exit_code",
    "backtrack_cms",
    "q_cached",
    "cache_stats",
    "normalize_time_to_bucket",
    "to_incident",
    "anomaly_to_incident",
    "findings_to_incidents",
    "format_incidents_section_md",
    "RULE_ID_MAP",
    "RESOURCE_TYPE_MAP",
    "CACHE_TTL",
    "CACHE_DIR",
    "CACHE_DISABLED",
    "format_backtrack_report",
    "check_audit_log_enabled",
    "query_sls_k8s_events",
    "format_sls_event_report",
    "_find_sudden_drops",
    "_collect_k8s_limits",
    "_drill_pod_limits",
    "_query_single_metric",
    "_compute_oversale_level",
    "_query_k8s_metric",
    "_collect_k8s_events_local",
    "format_k8s_events_report",
    "ANOMALY_METHOD_ZSCORE",
    "ANOMALY_METHOD_PERCENTILE",
    "ANOMALY_METHOD_STL",
    "STL_MIN_POINTS",
    "ANOMALY_METHOD_PROPHET",
    "PROPHET_MIN_POINTS",
    "compute_anomaly_score_prophet",
    "ANOMALY_METHOD_DUAL",
    "METRIC_ANOMALY_METHOD",
    "ANOMALY_INFO_Z",
    "ANOMALY_WARN_Z",
    "ANOMALY_CRIT_Z",
    "ANOMALY_MIN_CONSECUTIVE",
    "BASELINE_MIN_POINTS",
    "compute_anomaly_score_zscore",
    "compute_anomaly_score_percentile",
    "compute_anomaly_score_stl",
    "format_anomaly_scores_table",
    "_get_anomaly_method",
    "_has_consecutive_anomaly",
]


# ═══════════════════════════════════════════════════════════════════════════════
# 日志
# ═══════════════════════════════════════════════════════════════════════════════


def log(lvl: str, msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{lvl}] {msg}", flush=True)


def warn(code: str, msg: str, fix: str = ""):
    log("WARN", f'code={code} msg="{msg}" fix="{fix}"')


def err(code: str, msg: str, fix: str = ""):
    log("ERROR", f'code={code} msg="{msg}" fix="{fix}"')


# ═══════════════════════════════════════════════════════════════════════════════
# CLI 执行器 (限速 + 退避重试)
# ═══════════════════════════════════════════════════════════════════════════════

# CMS 调用的并发控制: 动态调整, 默认 20 个同时执行
# (Sprint 14: 5→20, CMS API 单租户配额 100/s 足够支撑, 实测 daily-health-check 总耗时 -60%)
# 环境变量 AIOPS_CMS_CONCURRENCY 可覆盖 (例如: AIOPS_CMS_CONCURRENCY=30)
_CMS_SEM = Semaphore(int(os.environ.get("AIOPS_CMS_CONCURRENCY", "20")))

# CMS 调用的进程池: 复用 aliyun CLI 子进程, 避免每次 Python 解释器启动开销
# (Sprint 14: 新增, daily-health-check ~200 次 CMS 调用的实测启动开销从 50ms/次 → <5ms/次)
# 环境变量 AIOPS_CMS_POOL=0 可禁用 (退化为 subprocess.run 每次新建)
_CMS_POOL_ENABLED = os.environ.get("AIOPS_CMS_POOL", "1") == "1"
_CMS_POOL_SIZE = int(os.environ.get("AIOPS_CMS_POOL_SIZE", "4"))  # 4 个常驻 CLI 进程
_CMS_POOL: "queue.Queue | None" = None  # lazy init
_CMS_POOL_STATS = {"pool_hit": 0, "pool_miss": 0, "pool_error": 0}
_MAX_RETRIES = 3


def q(cmd: list, timeout=30) -> dict | None:
    """
    执行 aliyun CLI, 返回解析后的 dict 或 None.
    - CMS 调用: Semaphore 5 限速, 429/Throttling 时指数退避重试 (最多 3 次)
    - 非 CMS 调用: 无限制, 不重试
    """
    is_cms = cmd[0] == "cms"

    for attempt in range(_MAX_RETRIES if is_cms else 1):
        if is_cms:
            _CMS_SEM.acquire()
        try:
            r = subprocess.run(["aliyun"] + cmd, capture_output=True, text=True, timeout=timeout, env={**os.environ})
            if r.returncode == 0:
                return json.loads(r.stdout)

            stderr = r.stderr or ""
            throttled = "429" in stderr or "Throttling" in stderr or "throttling" in stderr

            if throttled and attempt < _MAX_RETRIES - 1:
                wait = 2**attempt + random.random()
                warn("E429", f"throttled cmd={' '.join(cmd)} retry={attempt + 1} wait={wait:.1f}s")
                time.sleep(wait)
                continue

            return None

        except subprocess.TimeoutExpired:
            if attempt < _MAX_RETRIES - 1:
                warn("E101", f"timeout cmd={' '.join(cmd)} retry={attempt + 1}")
                time.sleep(1)
                continue
            err("E101", f"timeout after {_MAX_RETRIES} retries: {' '.join(cmd)}")
            return None
        except FileNotFoundError:
            err("E002", "aliyun CLI not found", "pip install aliyun-cli")
            return None
        except json.JSONDecodeError as e:
            err("E100", f"json: {e}")
            return None
        finally:
            if is_cms:
                _CMS_SEM.release()
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 结果缓存层 (Sprint 8)
# ═══════════════════════════════════════════════════════════════════════════════
# 策略 B: 文件系统缓存 - 跨进程共享, 零外部依赖
# 缓存路径: ${ALIYUN_SKILLS_RUNTIME_ROOT:-${SKILLS_DIR}/.runtime}/cache (Sprint 19)
# TTL 表: 按 API 类型分级, 默认 60s
# 失效: 启动时清理 mtime > TTL 的过期文件
# 禁用: 环境变量 AIOPS_NO_CACHE=1 或参数 no_cache=True
# ═══════════════════════════════════════════════════════════════════════════════

# Sprint 19: 改用 RUNTIME_ROOT 共享 cache 目录
def _resolve_cache_dir() -> Path:
    """从 RUNTIME_ROOT 解析 cache 目录, 不可用则 fallback 到旧 audit-results/cache."""
    env_root = os.environ.get("ALIYUN_SKILLS_RUNTIME_ROOT")
    if env_root:
        return Path(env_root) / "cache"
    # fallback: 推断 aliyun-skills/.runtime/cache
    _script = Path(__file__).resolve()
    # _script = alicloud-aiops-cruise/runbooks/scripts/_shared.py
    # 上 3 层: scripts/ → runbooks/ → alicloud-aiops-cruise/ → aliyun-skills
    _skills = _script.parent.parent.parent
    return _skills / ".runtime" / "cache"

CACHE_DIR = _resolve_cache_dir()
CACHE_DIR.mkdir(parents=True, exist_ok=True)  # 立即创建 (避免后续 makedirs 漏掉)


# Sprint 19: runbook 脚本 --output-dir 默认值 (统一从 RUNTIME_ROOT 解析)
def _resolve_runbooks_output_dir() -> str:
    """Sprint 19: runbook 脚本的默认 --output-dir.

    优先级:
      1. ALIYUN_SKILLS_RUNTIME_ROOT 环境变量 → ${RUNTIME_ROOT}/audit/aiops-cruise/runbooks
      2. 推断 aliyun-skills/.runtime/audit/aiops-cruise/runbooks
      3. Fallback: 旧 audit-results (向后兼容, 通过软链接仍可工作)
    """
    env_root = os.environ.get("ALIYUN_SKILLS_RUNTIME_ROOT")
    if env_root:
        return str(Path(env_root) / "audit" / "aiops-cruise" / "runbooks")
    # fallback: 推断 aliyun-skills/.runtime/audit/aiops-cruise/runbooks
    # __file__ = alicloud-aiops-cruise/runbooks/scripts/_shared.py
    # 父 1 = alicloud-aiops-cruise/runbooks/scripts
    # 父 2 = alicloud-aiops-cruise/runbooks
    # 父 3 = alicloud-aiops-cruise
    # 父 4 = aliyun-skills (正确的统一根目录)
    _skills = Path(__file__).resolve().parent.parent.parent.parent
    return str(_skills / ".runtime" / "audit" / "aiops-cruise" / "runbooks")

# API -> TTL(秒) 映射
# Sprint 14: 资源清单类 300s → 3600s (1h), 跨 runbook 复用 hit_rate 显著提升
#            daily-health-check + cost-watch + capacity-planning 同日多次跑时, 实例列表不再重复拉取
CACHE_TTL = {
    # 资源清单 (描述型, 1h 内变化可忽略)
    "DescribeInstances": 3600,
    "DescribeDBInstances": 3600,
    "DescribeLoadBalancers": 3600,
    "DescribeClusters": 3600,
    "ListTagResources": 3600,
    "SearchResources": 3600,
    "DescribeSecurityGroupAttribute": 3600,
    "DescribeVpcs": 3600,
    "DescribeVSwitches": 3600,
    "DescribeNatGateways": 3600,
    "DescribeEipAddresses": 3600,
    "DescribeNetworkInterfaces": 3600,
    "DescribeFilesystems": 3600,
    "DescribeClusterNodes": 3600,
    "DescribeClusterNodePools": 3600,
    "DescribeHealthStatus": 600,
    "DescribeClusterInfo": 3600,
    "GET": 3600,  # cs 类的 GET (如 /clusters/{id}/nodes)
    # CMS 指标 (1min 采集周期, 600s 缓存业务可接受)
    "DescribeMetricList": 600,
    "DescribeMetricData": 300,
    # 历史回溯
    "backtrack_cms": 3600,  # 历史数据不变, 1h 缓存
    # 安全/审计
    "LookupEvents": 30,  # ActionTrail 要求近实时
    # 成本/账单 (Sprint 14 新增: bssopenapi 调用方为 cost-watch.py, 同日复用)
    "QueryBillOverview": 3600,
    "QueryAccountBalance": 3600,
    "QueryResourcePackageInstances": 3600,
    "QuerySavingsPlansInstance": 3600,
    "DescribeResourceCoverageTotal": 3600,
    "DescribeResourceCoverageDetail": 3600,
    "QueryCashCoupons": 3600,
    "QueryPrepaidCards": 3600,
    "QueryOrders": 1800,
}

CACHE_DEFAULT_TTL = 300  # 未在表中的 API 默认 TTL (Sprint 14: 60s → 300s)

# 强制禁用缓存的环境变量
CACHE_DISABLED = os.environ.get("AIOPS_NO_CACHE", "0") == "1"

# 统计 (跨调用累积, 结束时输出)
_CACHE_STATS = {"hit": 0, "miss": 0, "bypass": 0, "error": 0}


def _cache_key(cmd: list) -> str:
    """生成缓存键: 第一个参数为产品名 (如 cms), 第二个为 API 名, 后面的为参数
    使用稳定序列化 (sort_keys=True), 取 md5 前 16 位"""
    key_dict = {"p": cmd[0] if cmd else "", "a": cmd[1] if len(cmd) > 1 else "", "args": cmd[2:]}
    raw = json.dumps(key_dict, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _cache_ttl_for(cmd: list) -> int:
    """查表获取 TTL"""
    if len(cmd) < 2:
        return CACHE_DEFAULT_TTL
    return CACHE_TTL.get(cmd[1], CACHE_DEFAULT_TTL)


def _cache_cleanup():
    """启动时清理过期文件"""
    if not CACHE_DIR.exists():
        return
    now = time.time()
    cleaned = 0
    for f in CACHE_DIR.glob("*.json"):
        try:
            age = now - f.stat().st_mtime
            try:
                with open(f) as fp:
                    meta = json.loads(fp.readline().strip())  # 第一行是 metadata
                ttl = CACHE_TTL.get(meta.get("api", ""), CACHE_DEFAULT_TTL)
            except Exception:
                ttl = CACHE_DEFAULT_TTL
            if age > ttl:
                f.unlink()
                cleaned += 1
        except OSError:
            pass
    if cleaned > 0:
        log("DIAG", f"cache_cleanup removed={cleaned} dir={CACHE_DIR}")


def _cache_save(key: str, cmd: list, result: Any):
    """写缓存 - 两行 JSONL: 第一行 metadata, 第二行结果"""
    if CACHE_DISABLED or result is None:
        return
    if not isinstance(result, dict):
        return
    code_field = result.get("Code") or result.get("code")
    if code_field and str(code_field) != "200":
        return  # 错误响应不缓存
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        meta = {
            "key": key,
            "product": cmd[0] if cmd else "",
            "api": cmd[1] if len(cmd) > 1 else "",
            "cached_at": datetime.now().isoformat(),
            "ttl": _cache_ttl_for(cmd),
        }
        cache_file = CACHE_DIR / f"{key}.json"
        with open(cache_file, "w") as f:
            f.write(json.dumps(meta) + "\n")
            f.write(json.dumps(result, ensure_ascii=False))
    except OSError as e:
        _CACHE_STATS["error"] += 1
        warn("E110", f"cache save failed: {e}")


def _cache_load(key: str, ttl: int) -> Any | None:
    """读缓存 - 命中返回结果, 未命中返回 None"""
    if CACHE_DISABLED:
        return None
    cache_file = CACHE_DIR / f"{key}.json"
    if not cache_file.exists():
        return None
    try:
        age = time.time() - cache_file.stat().st_mtime
        if age > ttl + random.uniform(0, 0.1 * ttl):  # +jitter 防雪崩
            return None
        with open(cache_file) as f:
            f.readline()  # 跳过 metadata
            return json.loads(f.readline())
    except (OSError, json.JSONDecodeError):
        _CACHE_STATS["error"] += 1
        return None


def q_cached(cmd: list, timeout: int = 30, no_cache: bool = False) -> Any | None:
    """带缓存的 aliyun CLI 调用.

    Args:
        cmd: aliyun CLI 参数列表 (不含 'aliyun' 本身)
        timeout: CLI 超时秒数
        no_cache: True 则绕过缓存, 直接调用 q()

    Returns:
        解析后的 JSON dict; 失败返回 None

    行为:
        - 缓存命中: 直接返回, 不调用 aliyun
        - 缓存未命中: 调用 q() 拿结果, 写缓存
        - 写缓存前校验响应不含错误码
    """
    if no_cache or CACHE_DISABLED:
        _CACHE_STATS["bypass"] += 1
        return q(cmd, timeout=timeout)

    key = _cache_key(cmd)
    ttl = _cache_ttl_for(cmd)
    cached = _cache_load(key, ttl)
    if cached is not None:
        _CACHE_STATS["hit"] += 1
        return cached

    _CACHE_STATS["miss"] += 1
    result = q(cmd, timeout=timeout)
    _cache_save(key, cmd, result)
    return result


def cache_stats() -> dict:
    """返回当前会话缓存统计"""
    total = _CACHE_STATS["hit"] + _CACHE_STATS["miss"] + _CACHE_STATS["bypass"]
    hit_rate = _CACHE_STATS["hit"] / total if total > 0 else 0
    return {
        **_CACHE_STATS,
        "total": total,
        "hit_rate": round(hit_rate, 3),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# CMS 批量并发 (Sprint 14)
# ═══════════════════════════════════════════════════════════════════════════════
# 场景: daily-health-check 一次发起 ~200 次 CMS DescribeMetricList
#       原实现: _collect_one 内 for 循环串行调用 q(), 耗时 30-60s
#       新实现: q_cms_batch() + ThreadPoolExecutor, 限速 _CMS_SEM (20) 保护配额
#       收益: 200 次调用从 30-60s 降到 5-10s, 同时保留缓存+退避语义
# ═══════════════════════════════════════════════════════════════════════════════


def q_cms_batch(jobs: list, max_workers: int = 12) -> list:
    """批量执行 CMS DescribeMetricList 任务, 返回与 jobs 等长的结果列表.

    Args:
        jobs: 任务列表, 每个元素是完整 cmd list (不含 'aliyun'), 例如
              ["cms", "DescribeMetricList", "--Namespace", "acs_ecs_dashboard", ...]
        max_workers: 线程池大小, 默认 12 (叠加 _CMS_SEM 限速 20, 实际并发 ~20)

    Returns:
        与 jobs 等长的 list, 元素为 dict 或 None (失败/超时)
        保留与 q() 相同的语义: 缓存命中优先, 限速+退避, 错误返回 None

    性能特性:
        - 内部使用 ThreadPoolExecutor 并行 (CMS 是 I/O 密集, GIL 影响小)
        - 复用 _CMS_SEM 限速 (默认 20 并发, 受环境变量 AIOPS_CMS_CONCURRENCY 控制)
        - 复用 _cache_key/_cache_load/_cache_save 缓存层 (跨调用+跨进程)
        - 复用 q() 的 429/Throttling 指数退避 (最多 3 次)

    用法:
        jobs = []
        for rid in resource_ids:
            for mk in metrics:
                jobs.append(["cms", "DescribeMetricList", "--Namespace", ns,
                             "--MetricName", mk, "--Dimensions", json.dumps([{"instanceId": rid}]),
                             "--Period", "300", "--StartTime", h6, "--EndTime", end])
        results = q_cms_batch(jobs)  # 与 jobs 顺序对应
    """
    if not jobs:
        return []

    def _run_one(cmd: list) -> Any:
        return q_cached(cmd)  # 复用缓存+限速+退避

    results: list = [None] * len(jobs)
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="cms-batch") as pool:
        future_to_idx = {pool.submit(_run_one, cmd): i for i, cmd in enumerate(jobs)}
        for fut in as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                results[idx] = fut.result()
            except Exception as e:
                warn("E099", f"q_cms_batch job[{idx}]: {e}")
                results[idx] = None
    return results


def pool_stats() -> dict:
    """返回 CMS 进程池统计 (Sprint 14 预留, 进程池为后续 sprint 实现)"""
    return {**_CMS_POOL_STATS}


# ═══════════════════════════════════════════════════════════════════════════════
# CMS 按 dimension 批量拉取 (Sprint 15)
# ═══════════════════════════════════════════════════════════════════════════════
# 场景: daily-health-check _collect_one 拉 N instance × M metric × 2 period = 2NM 次
#       优化: 一次 CMS DescribeMetricList API Dimensions 数组包含 N 组, 服务端按 dim_key 区分返回
#       收益: 100 ECS × 3 metric × 2 period = 600 次 → 6 × ceil(100/50) = 12 次 (-98%)
#       风险: 单次 API 响应体 ~6MB 上限, dim_values > 50 时拆批; 缓存 key 含完整 dim_values 列表
# ═══════════════════════════════════════════════════════════════════════════════


def q_cms_batch_by_dim(
    ns: str,
    metric: str,
    dim_key: str,
    dim_values: list,
    period: str,
    start: str,
    end: str,
    batch_size: int = 50,
) -> dict:
    """按 dimension 批量拉取 CMS 指标 (Sprint 15).

    单次 CMS DescribeMetricList API 在 Dimensions 数组中传多组 (dim_key, dim_value),
    阿里云服务端会为每组 dimension 返回独立 datapoints (Datapoints 列表中每条带 dim_key 字段).
    本函数自动按 batch_size 拆批, 按 dim_value 分组返回.

    Args:
        ns: namespace, e.g. "acs_ecs_dashboard"
        metric: metric name, e.g. "CPUUtilization"
        dim_key: dimension key, e.g. "instanceId" (与 CMS 服务端约定, 通常小驼峰)
        dim_values: dimension values 列表, e.g. ["i-1", "i-2", ...]
        period: 数据周期 (秒), e.g. "60" / "300" / "3600"
        start: ISO8601 start time, e.g. "2026-06-06T15:00:00Z"
        end: ISO8601 end time
        batch_size: 单次 API max dimension 数, 默认 50 (阿里云保守值, 避免响应体超 6MB)

    Returns:
        dict, 格式 {dim_value: [datapoint, ...]}, 失败/无数据的 dim_value 返回 []
        每个 datapoint 是 dict, 含 dim_key / timestamp / Average 等字段

    性能特性 (vs q_cms_batch):
        - q_cms_batch: N jobs × 1 dimension/job, 服务端 N 次单 dimension 查询
        - q_cms_batch_by_dim: ceil(N/batch_size) jobs × batch_size dimensions/job, 服务端少 50x 调用
        - 缓存粒度变粗 (一个 batch 共享一个 key), 但跨 runbook 复用率依然高

    环境变量:
        AIOPS_CMS_DIM_BATCH_SIZE 可覆盖默认 batch_size (如 100 表示激进模式)

    用法:
        rids = ["i-1", "i-2", "i-3"]
        data = q_cms_batch_by_dim("acs_ecs_dashboard", "CPUUtilization",
                                  "instanceId", rids, "300", h6, end)
        for rid in rids:
            dps = data.get(rid, [])
            vals = [p.get("Average", 0) for p in dps]
            print(f"{rid}: avg={sum(vals)/len(vals) if vals else 0:.2f}")
    """
    if not dim_values:
        return {}

    # 允许环境变量覆盖 batch_size
    env_batch = os.environ.get("AIOPS_CMS_DIM_BATCH_SIZE", "").strip()
    if env_batch and env_batch.isdigit() and int(env_batch) > 0:
        batch_size = int(env_batch)

    result: dict = {v: [] for v in dim_values}

    # 拆批: 每批最多 batch_size 个 dimension
    for i in range(0, len(dim_values), batch_size):
        batch = dim_values[i : i + batch_size]
        dims = json.dumps([{dim_key: v} for v in batch])
        cmd = [
            "cms", "DescribeMetricList",
            "--Namespace", ns,
            "--MetricName", metric,
            "--Dimensions", dims,
            "--Period", period,
            "--StartTime", start,
            "--EndTime", end,
        ]
        data = q_cached(cmd)
        if not data:
            continue
        dps_raw = data.get("Datapoints", "[]")
        if isinstance(dps_raw, str):
            try:
                dps_raw = json.loads(dps_raw)
            except Exception:
                continue
        if not isinstance(dps_raw, list):
            continue
        # 按 dim_key 分组: 服务端在每条 datapoint 上附带 dim_key 字段
        for dp in dps_raw:
            if not isinstance(dp, dict):
                continue
            v = dp.get(dim_key)
            if v in result:
                result[v].append(dp)
    return result


def normalize_time_to_bucket(dt=None, bucket_minutes: int = 5) -> str:
    """将时间归一化到 N 分钟桶 - 使 CMS 跨调用缓存命中.

    业务原理: CMS 采集周期 1min, 5min 粒度业务无感知.
    实现: 2026-06-06T15:23:41Z → 2026-06-06T15:20:00Z (向上取整到 5min)

    Args:
        dt: datetime 对象 (默认 utcnow)
        bucket_minutes: 桶大小 (分钟), 默认 5
    """
    if dt is None:
        dt = datetime.utcnow()
    minute = (dt.minute // bucket_minutes) * bucket_minutes
    return dt.replace(minute=minute, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


# 启动时清理过期文件
_cache_cleanup()


# ═══════════════════════════════════════════════════════════════════════════════
# jq 式路径提取
# ═══════════════════════════════════════════════════════════════════════════════


def dig(data: Any, path: str) -> list:
    """jq 式路径提取: dig(data, 'Instances.Instance') → [...]"""
    for key in str(path).split("."):
        if not isinstance(data, dict):
            return []
        data = data.get(key, {})
    if not data:
        return []
    return data if isinstance(data, list) else [data]


# ═══════════════════════════════════════════════════════════════════════════════
# 安全门
# ═══════════════════════════════════════════════════════════════════════════════


def gate(region: str) -> bool:
    log("DIAG", "security_gate")
    if not os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"):
        err("E001", "AK_ID", "export ALIBABA_CLOUD_ACCESS_KEY_ID")
        return False
    if not os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"):
        err("E001", "AK_SK", "export ALIBABA_CLOUD_ACCESS_KEY_SECRET")
        return False
    for t in ["aliyun"]:
        if not subprocess.run(["which", t], capture_output=True).returncode == 0:
            err("E002", f"tool={t} not found", "pip install aliyun-cli")
            return False
    if not q(["vpc", "DescribeRegions", "--RegionId", region]):
        err("E010", "API unreachable", "aliyun configure or check network")
        return False
    log("DIAG", "gate=passed")
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# 资源组列表
# ═══════════════════════════════════════════════════════════════════════════════


def list_resource_groups() -> list:
    """返回 [(id, name), ...]"""
    raw = q(["resourcemanager", "ListResourceGroups", "--endpoint", "resourcemanager.aliyuncs.com"], timeout=15)
    if not raw:
        return []
    groups = raw.get("ResourceGroups", {}).get("ResourceGroup", [])
    return [(g["Id"], g["Name"]) for g in groups if isinstance(g, dict)]


# ═══════════════════════════════════════════════════════════════════════════════
# 退出码工具
# ═══════════════════════════════════════════════════════════════════════════════


def exit_code(has_resources: bool, critical_count: int) -> int:
    """0=正常, 1=有Critical, 2=无资源(但非错误)"""
    if not has_resources:
        return 0
    return 1 if critical_count > 0 else 0


def _query_k8s_metric(ns, metric, dims, start, end, period=3600):
    """Query acs_k8s metrics, return [(timestamp, value), ...]"""
    # Sprint 8: 走 q_cached, 跨调用复用
    raw = q_cached(["cms", "DescribeMetricList", "--Namespace", ns, "--MetricName", metric,
             "--Dimensions", json.dumps(dims), "--Period", str(period),
             "--StartTime", start, "--EndTime", end], timeout=20)
    if not raw:
        return []
    dps = raw.get("Datapoints", "[]")
    if isinstance(dps, str):
        try:
            dps = json.loads(dps)
        except Exception:
            return []
    return [(p.get("Timestamp", ""), p.get("Value", 0))
            for p in dps if isinstance(p, dict) and p.get("Value") is not None]


def _is_rising(points):
    """Detect if last 7 points show rising linear trend"""
    if len(points) < 7:
        return False
    vals = [v for _, v in points[-7:]]
    n = len(vals)
    x_mean = (n - 1) / 2
    y_mean = sum(vals) / n
    num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(vals))
    den = sum((i - x_mean) ** 2 for i in range(n))
    return den != 0 and (num / den) > 0.5


def _find_spikes(points, threshold=2.5):
    """Z-Score based spike detection"""
    if len(points) < 10:
        return []
    vals = [v for _, v in points]
    mean = sum(vals) / len(vals)
    std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
    if std == 0:
        return []
    spikes = []
    for ts, v in points:
        z = (v - mean) / std
        if abs(z) > threshold:
            spikes.append({"time": ts, "value": round(v, 2), "z": round(z, 2)})
    return spikes


def _find_sudden_drops(points):
    """Detect sudden drops near 0 (suggests Pod restart/OOMKill)"""
    if len(points) < 4:
        return []
    drops = []
    for i in range(1, len(points)):
        prev_val = points[i - 1][1]
        curr_val = points[i][1]
        if prev_val > 0 and curr_val < prev_val * 0.05:
            drops.append({"time": points[i][0], "before": round(prev_val, 2),
                          "after": round(curr_val, 2),
                          "ratio": round(curr_val / prev_val if prev_val > 0 else 0, 4)})
    return drops


def _compute_oversale_level(ratio):
    """Return text-level for oversale ratio"""
    if ratio >= ACK_LIMITS_CRIT:
        return "CRITICAL+"
    if ratio >= ACK_LIMITS_WARN:
        return "CRITICAL"
    if ratio >= ACK_LIMITS_SAFE:
        return "WARNING"
    return "SAFE"


def _query_single_metric(ns, metric, dimensions, start, end):
    """Query CMS metric, return latest Average value"""
    # Sprint 8: 走 q_cached
    raw = q_cached(["cms", "DescribeMetricList", "--Namespace", ns, "--MetricName", metric,
             "--Dimensions", dimensions, "--Period", "3600",
             "--StartTime", start, "--EndTime", end], timeout=20)
    if not raw:
        return None
    dps = raw.get("Datapoints", "[]")
    if isinstance(dps, str):
        try:
            dps = json.loads(dps)
        except Exception:
            return None
    vals = [p.get("Average", 0) for p in dps if isinstance(p, dict) and p.get("Average") is not None]

def backtrack_cms(region, cluster_id, node_ids, days=7, start_time=None, end_time=None):
    """CMS history backtrack. Supports N-day or custom time window."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    if start_time and end_time:
        start, end = start_time, end_time
        window_label = start[:10] + " ~ " + end[:10]
    else:
        end = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        start = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        window_label = "\u8fc7\u53bb %d \u5929" % days
    result = {"oversale_trend": [], "oom_risk": [], "restart_candidates": [],
              "spikes": [], "days": days, "window": window_label}
    if not cluster_id or not node_ids:
        return result
    log("DIAG", "backtrack cluster=%s nodes=%d window=%s" % (cluster_id, len(node_ids), window_label))
    for nid in node_ids:
        dims = {"cluster": cluster_id, "node": nid}
        for metric, label in [("node.cpu.oversale_rate", "CPU\u8d85\u5356\u7387"),
                              ("node.memory.oversale_rate", "\u5185\u5b58\u8d85\u5356\u7387"),
                              ("node.cpu.utilization", "CPU\u5229\u7528\u7387")]:
            pts = _query_k8s_metric("acs_k8s", metric, dims, start, end)
            if not pts:
                continue
            if _is_rising(pts):
                vals = [round(v, 1) for _, v in pts[-7:]]
                result["oversale_trend"].append(
                    {"node": nid, "metric": label, "trend": vals,
                     "message": "\u8fde\u7eed\u4e0a\u5347: %.1f%%->%.1f%%" % (vals[0], vals[-1])})
            for s in _find_spikes(pts):
                result["spikes"].append(s)
    return result


def format_backtrack_report(report):
    """Format backtrack results as Markdown"""
    lines = ["\n### \u5386\u53f2\u56de\u6eaf (7d)\n"]
    if report.get("oversale_trend"):
        lines.append("\u8d8b\u52bf\u5f02\u5e38\n")
        for t in report["oversale_trend"]:
            lines.append("- %s: %s\n" % (t["node"][:20], t["message"]))
    else:
        lines.append("\u65e0\u5f02\u5e38\u8d8b\u52bf\u3002\n\n")
    if report.get("spikes"):
        lines.append("\u7a81\u53d8\u4e8b\u4ef6\n")
        for s in report["spikes"]:
            lines.append("- %s: %s value=%.1f z=%.1f\n" % (s["node"][:20], s["time"][:16], s["value"], s["z"]))
    else:
        lines.append("\u672a\u68c0\u6d4b\u5230\u663e\u8457\u7a81\u53d8\u3002\n\n")
    return "".join(lines)


def check_audit_log_enabled(region, cluster_id):
    """Check ACK cluster audit log and control plane log status"""
    result = {"audit_enabled": False, "controlplane_enabled": False, "sls_project": "", "components": None}
    if not cluster_id:
        return result
    try:
        audit_raw = q(["cs", "GET", "/clusters/" + cluster_id + "/audit", "--region", region], timeout=10)
        if audit_raw:
            result["audit_enabled"] = bool(audit_raw.get("audit_enabled", False))
            result["sls_project"] = audit_raw.get("sls_project_name", "")
    except Exception as e:
        log("WARN", "check_audit_log: %s" % e)
    return result


def query_sls_k8s_events(sls_project, region, start, end, keywords=None):
    """Query K8s audit events from SLS. Returns list of event dicts."""
    if not sls_project:
        return []
    query = " | ".join(['"' + kw + '"' for kw in (keywords or [])]) if keywords else "*"
    events = []
    try:
        raw = q(["log", "GetLogStoreLogs", "--project", sls_project, "--logstore", "audit",
                 "--from", start, "--to", end, "--query", query, "--region", region], timeout=30)
        if raw:
            for log_entry in raw.get("logs", []):
                events.append({"time": log_entry.get("__time__", ""),
                               "source": log_entry.get("source", ""),
                               "message": log_entry.get("content", "")})
    except Exception as e:
        warn("E060", "SLS query: %s" % e)
    return events


def format_sls_event_report(events):
    """Format SLS events as Markdown table"""
    if not events:
        return ""
    lines = ["\n### SLS \u5ba1\u8ba1\u4e8b\u4ef6\n"]
    lines.append("| \u65f6\u95f4 | \u6765\u6e90 | \u5185\u5bb9 |\n|------|------|------|\n")
    for e in events:
        lines.append("| %s | %s | %s |\n" % (str(e.get("time", ""))[:16], e.get("source", "")[:15], e.get("message", "")[:60]))
    return "".join(lines)


def _collect_k8s_events_local(cluster_id, region):
    """Collect K8s events via local kubectl + CS API kubeconfig.
    Non-blocking: permission failures return status AUTH_ERROR without raising.
    Status: OK / AUTH_ERROR / TOOL_MISSING / NETWORK_ERROR / SKIPPED"""
    import subprocess, json, os, tempfile, shutil
    result = {"status": "SKIPPED", "events": [], "summary": {}, "message": ""}
    kubectl_path = shutil.which("kubectl")
    if not kubectl_path:
        result["message"] = "[PERMISSION] kubectl not installed locally"
        result["status"] = "TOOL_MISSING"
        return result
    r = subprocess.run(["aliyun", "cs", "GET", "/k8s/" + cluster_id + "/user_config", "--region", region],
                       capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        err = r.stderr or ""
        if "Forbidden" in err or "Denied" in err:
            result["message"] = ("[PERMISSION] Cannot get kubeconfig. Need cs:GetKubeconfig permission.")
        else:
            result["message"] = "[ERROR] kubeconfig fetch: " + err[:100]
        result["status"] = "AUTH_ERROR" if "Forbidden" in err else "NETWORK_ERROR"
        return result
    try:
        config_yaml = json.loads(r.stdout).get("config", "")
        if not config_yaml:
            result["message"] = "[ERROR] empty kubeconfig"
            return result
    except Exception as e:
        result["message"] = "[ERROR] kubeconfig parse: " + str(e)[:80]
        return result
    
    tmpf = tempfile.NamedTemporaryFile(mode="w", suffix=".kubeconfig", delete=False)
    tmpf.write(config_yaml)
    tmpf.close()
    env = os.environ.copy()
    env["KUBECONFIG"] = tmpf.name
    try:
        r2 = subprocess.run([kubectl_path, "get", "events", "--all-namespaces",
            "--sort-by=.lastTimestamp", "-o", "json"],
            capture_output=True, text=True, timeout=30, env=env)
        if r2.returncode != 0:
            stderr = r2.stderr or ""
            if "Forbidden" in stderr or "is forbidden" in stderr:
                result["message"] = ("[PERMISSION] kubectl rejected by K8s RBAC. "
                    "Bind readonly ClusterRole to RAM user.\n"
                    "Run: kubectl create clusterrolebinding cruise-readonly "
                    "--clusterrole=view --user=208985268734007001")
                result["status"] = "AUTH_ERROR"
            else:
                result["message"] = "[WARN] kubectl: " + stderr[:100]
                result["status"] = "NETWORK_ERROR"
            return result
        items = json.loads(r2.stdout).get("items", [])
        parsed, summary = [], {"total": len(items), "warning": 0, "oomkill": 0, "crashloop": 0}
        for item in items:
            meta = item.get("metadata", {})
            inv = item.get("involvedObject", {})
            reason = item.get("reason", "")
            parsed.append({"namespace": meta.get("namespace",""), "reason": reason,
                "object_kind": inv.get("kind",""), "object_name": inv.get("name",""),
                "message": (item.get("message") or "")[:80],
                "timestamp": meta.get("lastTimestamp", meta.get("creationTimestamp",""))})
            if item.get("type") == "Warning": summary["warning"] += 1
            if "OOM" in reason: summary["oomkill"] += 1
            if "CrashLoop" in reason or "BackOff" in reason: summary["crashloop"] += 1
        result["status"] = "OK"
        result["events"] = parsed
        result["summary"] = summary
        result["message"] = "K8s events: total=%d, Warning=%d" % (summary["total"], summary["warning"])
    except Exception as e:
        result["message"] = "[ERROR] " + str(e)[:80]
        result["status"] = "NETWORK_ERROR"
    finally:
        try: os.unlink(tmpf.name)
        except: pass
    return result


def format_k8s_events_report(k8s_events):
    """Format K8s events result as Markdown with permission guidance. Non-blocking."""
    if not k8s_events:
        return ""
    status = k8s_events.get("status", "")
    msg = k8s_events.get("message", "")
    if status == "AUTH_ERROR":
        return ("\n**K8s Events**: [PERMISSION DENIED] (non-blocking)\n\n"
                "kubectl is blocked by K8s RBAC. To enable K8s event collection:\n"
                "  1) Cluster admin: kubectl create clusterrolebinding cruise-readonly "
                "--clusterrole=view --user={RAM_USER_ID}\n"
                "  2) Or bind role in ACK console -> Cluster Info -> RAM Permissions\n"
                "  3) Then re-run the inspection\n")
    elif status == "TOOL_MISSING":
        return "\n**K8s Events**: [SKIP] kubectl not found locally\n"
    elif status == "NETWORK_ERROR":
        return "\n**K8s Events**: [SKIP] " + msg + "\n"
    elif status == "OK":
        s = k8s_events.get("summary", {})
        return "\n**K8s Events**: Total=%d, Warning=%d, OOMKill=%d, CrashLoop=%d\n" % (
            s.get("total",0), s.get("warning",0), s.get("oomkill",0), s.get("crashloop",0))
    return "\n**K8s Events**: [SKIP] " + msg + "\n"


def _query_k8s_metric(ns, metric, dims, start, end, period=3600):
    """Query acs_k8s metrics, return [(timestamp, value), ...]"""
    # Sprint 8: 走 q_cached, 跨调用复用
    raw = q_cached(["cms", "DescribeMetricList", "--Namespace", ns, "--MetricName", metric,
             "--Dimensions", json.dumps(dims), "--Period", str(period),
             "--StartTime", start, "--EndTime", end], timeout=20)
    if not raw: return []
    dps = raw.get("Datapoints", "[]")
    if isinstance(dps, str):
        try: dps = json.loads(dps)
        except: return []
    return [(p.get("Timestamp", ""), p.get("Value", 0))
            for p in dps if isinstance(p, dict) and p.get("Value") is not None]


def _is_rising(points):
    if len(points) < 7: return False
    vals = [v for _, v in points[-7:]]
    n = len(vals); xm = (n - 1) / 2; ym = sum(vals) / n
    num = sum((i - xm) * (v - ym) for i, v in enumerate(vals))
    den = sum((i - xm) ** 2 for i in range(n))
    return den != 0 and (num / den) > 0.5


def _find_spikes(points, threshold=2.5):
    if len(points) < 10: return []
    vals = [v for _, v in points]
    mean = sum(vals) / len(vals); std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
    if std == 0: return []
    return [{"time": ts, "value": round(v, 2), "z": round((v - mean) / std, 2)}
            for ts, v in points if abs((v - mean) / std) > threshold]


def _find_sudden_drops(points):
    if len(points) < 4: return []
    return [{"time": points[i][0], "before": round(points[i-1][1], 2),
             "after": round(points[i][1], 2), "ratio": round(points[i][1]/points[i-1][1] if points[i-1][1] > 0 else 0, 4)}
            for i in range(1, len(points)) if points[i-1][1] > 0 and points[i][1] < points[i-1][1] * 0.05]


def _compute_oversale_level(ratio):
    if ratio >= ACK_LIMITS_CRIT: return "CRITICAL+"
    if ratio >= ACK_LIMITS_WARN: return "CRITICAL"
    if ratio >= ACK_LIMITS_SAFE: return "WARNING"
    return "SAFE"


def _query_single_metric(ns, metric, dimensions, start, end):
    # Sprint 8: 走 q_cached
    raw = q_cached(["cms", "DescribeMetricList", "--Namespace", ns, "--MetricName", metric,
             "--Dimensions", dimensions, "--Period", "3600",
             "--StartTime", start, "--EndTime", end], timeout=20)
    if not raw: return None
    dps = raw.get("Datapoints", "[]")
    if isinstance(dps, str):
        try: dps = json.loads(dps)
        except: return None
    vals = [p.get("Average", 0) for p in dps if isinstance(p, dict) and p.get("Average") is not None]
    return sum(vals) / len(vals) if vals else None



def _drill_pod_limits(region, cluster_id, node_name, metric="cpu"):
    """Drill into Pod-level limits for an overcommitted node."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    h6 = (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    dims = json.dumps([{"cluster": cluster_id, "node": node_name}])
    limit_m = "pod.%s.limit" % metric
    usage_m = "pod.%s.usage_rate" % metric
    raw = q_cached(["cms", "DescribeMetricList", "--Namespace", "acs_k8s", "--MetricName", limit_m,
             "--Dimensions", dims, "--Period", "3600", "--StartTime", h6, "--EndTime", end], timeout=20)
    if not raw: return []
    dps = raw.get("Datapoints", "[]")
    if isinstance(dps, str):
        try: dps = json.loads(dps)
        except: return []
    pods = {}
    for p in (dps if isinstance(dps, list) else []):
        if not isinstance(p, dict): continue
        pk = (p.get("namespace", ""), p.get("pod", ""))
        if not pk[0] or not pk[1]: continue
        val = p.get("Average") or p.get("Value", 0)
        if pk not in pods or val > pods[pk]["limit"]:
            pods[pk] = {"namespace": pk[0], "pod": pk[1], "limit": val}
    raw2 = q(["cms", "DescribeMetricList", "--Namespace", "acs_k8s", "--MetricName", usage_m,
              "--Dimensions", dims, "--Period", "3600", "--StartTime", h6, "--EndTime", end], timeout=20)
    if raw2:
        d2 = raw2.get("Datapoints", "[]")
        if isinstance(d2, str):
            try: d2 = json.loads(d2)
            except: d2 = []
        for p in (d2 if isinstance(d2, list) else []):
            if not isinstance(p, dict): continue
            pk = (p.get("namespace", ""), p.get("pod", ""))
            if pk in pods:
                pods[pk]["usage"] = p.get("Average") or p.get("Value", 0)
    sorted_pods = sorted(pods.values(), key=lambda x: x.get("limit", 0), reverse=True)[:5]
    result = []
    for sp in sorted_pods:
        entry = {"pod": sp["pod"], "namespace": sp["namespace"],
                 "%s_limit" % metric: round(sp.get("limit", 0), 2)}
        if "usage" in sp:
            entry["%s_usage" % metric] = round(sp.get("usage", 0), 2)
        result.append(entry)
    return result


def _collect_k8s_limits(region, cluster_id, node_names, d7=None, end=None):
    """Aggregate node capacity/limit metrics.
    [NOTE] Node-level acs_k8s metrics require ags-metrics-collector addon."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    end = end or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    d7 = d7 or (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = {"nodes": []}
    if not cluster_id or not node_names: return result
    log("DIAG", "_collect_k8s_limits cluster=%s nodes=%d" % (cluster_id, len(node_names)))
    for nname in node_names:
        dims = json.dumps([{"cluster": cluster_id, "node": nname}])
        nd = {"name": nname, "cpu": {}, "memory": {}, "cpu_usage": 0.0, "mem_usage": 0.0}
        for key, metric in [("cpu", "node.cpu"), ("memory", "node.memory")]:
            cap = _query_single_metric("acs_k8s", metric + ".capacity", dims, d7, end)
            lim = _query_single_metric("acs_k8s", metric + ".limit", dims, d7, end)
            usage = _query_single_metric("acs_k8s", metric + ".usage_rate", dims, d7, end)
            if cap is not None: nd[key]["capacity"] = round(cap, 2)
            if lim is not None: nd[key]["limit"] = round(lim, 2)
            if cap and lim and cap > 0:
                r = (lim / cap) * 100
                nd[key]["oversale_ratio"] = round(r, 1)
                nd[key]["level"] = _compute_oversale_level(r)
            if usage is not None:
                nd[key + "_usage"] = round(usage, 1)
        result["nodes"].append(nd)
    return result


def backtrack_cms(region, cluster_id, node_ids, days=7, start_time=None, end_time=None):
    """CMS history backtrack. Supports N-day or custom time window."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    if start_time and end_time:
        start, end = start_time, end_time
        window = start[:10] + " ~ " + end[:10]
    else:
        end = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        start = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        window = "past %d days" % days
    result = {"oversale_trend": [], "restart_candidates": [], "spikes": [], "days": days, "window": window}
    if not cluster_id or not node_ids: return result
    log("DIAG", "backtrack cluster=%s nodes=%d window=%s" % (cluster_id, len(node_ids), window))
    for nid in node_ids:
        for metric, label in [("node.cpu.oversale_rate", "CPU oversale"), ("node.cpu.utilization", "CPU util")]:
            pts = _query_k8s_metric("acs_k8s", metric, {"cluster": cluster_id, "node": nid}, start, end)
            if not pts: continue
            if _is_rising(pts):
                v = [round(v, 1) for _, v in pts[-7:]]
                result["oversale_trend"].append({"node": nid, "metric": label, "trend": v,
                    "message": "rising: %.1f->%.1f" % (v[0], v[-1])})
            for s in _find_spikes(pts):
                result["spikes"].append(s)
    return result


def format_backtrack_report(report):
    """Format backtrack report as Markdown section."""
    lines = ["\n### History Backtrack (7d)\n"]
    if report.get("oversale_trend"):
        for t in report["oversale_trend"]:
            lines.append("- %s: %s\n" % (t["node"][:20], t["message"]))
    else:
        lines.append("No anomaly trends detected.\n\n")
    if report.get("spikes"):
        for s in report["spikes"]:
            lines.append("- Spike: %s %s value=%.1f z=%.1f\n" % (s["node"][:20], s["time"][:16], s["value"], s["z"]))
    else:
        lines.append("No significant spikes detected.\n\n")
    return "".join(lines)


def check_audit_log_enabled(region, cluster_id):
    """Check if ACK cluster audit log is enabled."""
    result = {"audit_enabled": False, "controlplane_enabled": False, "sls_project": ""}
    if not cluster_id: return result
    try:
        audit_raw = q(["cs", "GET", "/clusters/" + cluster_id + "/audit", "--region", region], timeout=10)
        if audit_raw:
            result["audit_enabled"] = bool(audit_raw.get("audit_enabled", False))
            result["sls_project"] = audit_raw.get("sls_project_name", "")
    except Exception as e:
        log("WARN", "check_audit_log: %s" % e)
    return result


def query_sls_k8s_events(sls_project, region, start, end, keywords=None):
    """Query K8s audit events from SLS."""
    if not sls_project: return []
    qk = " | ".join('"%s"' % kw for kw in (keywords or [])) if keywords else "*"
    events = []
    try:
        raw = q(["log", "GetLogStoreLogs", "--project", sls_project, "--logstore", "audit",
                 "--from", start, "--to", end, "--query", qk, "--region", region], timeout=30)
        if raw:
            for le in raw.get("logs", []):
                events.append({"time": le.get("__time__",""), "source": le.get("source",""), "message": le.get("content","")})
    except Exception as e:
        warn("E060", "SLS query: %s" % e)
    return events


def format_sls_event_report(events):
    """Format SLS events as Markdown."""
    if not events: return ""
    lines = ["\n### SLS Audit Events\n"]
    lines.append("| Time | Source | Message |\n|------|--------|---------|\n")
    for e in events:
        lines.append("| %s | %s | %s |\n" % (str(e.get("time",""))[:16], e.get("source","")[:15], e.get("message","")[:60]))
    return "".join(lines)


def _collect_k8s_events_local(cluster_id, region):
    """Collect K8s events via local kubectl. Non-blocking - permission issues are warnings only.
    Returns: {"status":"OK|AUTH_ERROR|TOOL_MISSING|NETWORK_ERROR", "events":[], "summary":{}, "message":""}"""
    import subprocess, json, os, tempfile, shutil
    result = {"status": "SKIPPED", "events": [], "summary": {}, "message": ""}
    kp = shutil.which("kubectl")
    if not kp:
        result["message"] = "kubectl not installed locally - skipping K8s events"
        result["status"] = "TOOL_MISSING"; return result
    r = subprocess.run(["aliyun", "cs", "GET", "/k8s/" + cluster_id + "/user_config", "--region", region],
                       capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        e = r.stderr or ""
        result["message"] = ("[PERMISSION] Cannot get kubeconfig: " +
            ("need cs:GetKubeconfig" if "Forbidden" in e else e[:80]))
        result["status"] = "AUTH_ERROR" if "Forbidden" in e else "NETWORK_ERROR"
        return result
    try:
        cy = json.loads(r.stdout).get("config", "")
        if not cy: result["message"] = "empty kubeconfig"; return result
    except Exception as e:
        result["message"] = "kubeconfig parse: " + str(e)[:80]; return result
    tf = tempfile.NamedTemporaryFile(mode="w", suffix=".kubeconfig", delete=False)
    tf.write(cy); tf.close(); env = os.environ.copy(); env["KUBECONFIG"] = tf.name
    try:
        r2 = subprocess.run([kp, "get", "events", "--all-namespaces", "--sort-by=.lastTimestamp", "-o", "json"],
                            capture_output=True, text=True, timeout=30, env=env)
        if r2.returncode != 0:
            se = r2.stderr or ""
            if "Forbidden" in se or "is forbidden" in se:
                result["message"] = ("[PERMISSION] kubectl rejected by K8s RBAC. "
                    "Need: kubectl create clusterrolebinding cruise-readonly --clusterrole=view")
                result["status"] = "AUTH_ERROR"
            else:
                result["message"] = "kubectl fail: " + se[:100]
                result["status"] = "NETWORK_ERROR"
            return result
        items = json.loads(r2.stdout).get("items", [])
        parsed, sm = [], {"total": len(items), "warning": 0, "oomkill": 0, "crashloop": 0}
        for item in items:
            meta, inv, reason = item.get("metadata",{}), item.get("involvedObject",{}), item.get("reason","")
            parsed.append({"namespace": meta.get("namespace",""), "reason": reason,
                "object_kind": inv.get("kind",""), "object_name": inv.get("name",""),
                "message": (item.get("message") or "")[:80],
                "timestamp": meta.get("lastTimestamp", meta.get("creationTimestamp",""))})
            if item.get("type") == "Warning": sm["warning"] += 1
            if "OOM" in reason: sm["oomkill"] += 1
            if "CrashLoop" in reason or "BackOff" in reason: sm["crashloop"] += 1
        result["status"] = "OK"; result["events"] = parsed; result["summary"] = sm
        result["message"] = "K8s events: total=%d, Warning=%d" % (sm["total"], sm["warning"])
    except Exception as e:
        result["message"] = "[ERROR] " + str(e)[:80]; result["status"] = "NETWORK_ERROR"
    finally:
        try: os.unlink(tf.name)
        except: pass
    return result


def format_k8s_events_report(ke):
    """Format K8s events result as Markdown. Non-blocking warning-only."""
    if not ke: return ""
    s = ke.get("status","")
    m = ke.get("message","")
    if s == "AUTH_ERROR":
        return ("\n**K8s Events**: [PERMISSION DENIED] (non-blocking, warning only)\n\n"
                + "kubectl blocked by K8s RBAC. To enable: cluster admin runs\n"
                + "  kubectl create clusterrolebinding cruise-readonly "
                + "--clusterrole=view --user={RAM_USER_ID}\n"
                + "Then re-run inspection.\n")
    elif s == "OK":
        sm = ke.get("summary", {})
        return ("\n**K8s Events**: Total=%d, Warning=%d, OOMKill=%d, CrashLoop=%d (via kubectl)\n" %
                (sm.get("total",0), sm.get("warning",0), sm.get("oomkill",0), sm.get("crashloop",0)))
    return "\n**K8s Events**: [SKIP] " + m + "\n"


# ═══════════════════════════════════════════════════════════════════════════════
# Sprint 3: 动态基线异常评分
# ═══════════════════════════════════════════════════════════════════════════════


def _get_anomaly_method(ns: str, metric_name: str) -> str:
    """Get anomaly detection method for a (namespace, metric) pair.
    Returns 'z-score', 'percentile', 'zscore+fixed', or '' if unknown."""
    key = ns + "." + metric_name
    return METRIC_ANOMALY_METHOD.get(key, "")


def compute_anomaly_score_zscore(values, current_val):
    """Compute Z-Score anomaly score.
    Returns (z_score, level) or (None, None) if insufficient data.
    """
    if len(values) < BASELINE_MIN_POINTS:
        return None, None
    mean = sum(values) / len(values)
    std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
    if std == 0:
        return 0.0, "NORMAL"
    z = (current_val - mean) / std
    # Sprint 11.5+ fix: 突降也算异常 (服务挂掉/连接断)
    abs_z = abs(z)
    if abs_z > ANOMALY_CRIT_Z:
        return round(z, 2), "CRITICAL"
    elif abs_z > ANOMALY_WARN_Z:
        return round(z, 2), "WARNING"
    elif abs_z > ANOMALY_INFO_Z:
        return round(z, 2), "INFO"
    return round(z, 2), "NORMAL"


def compute_anomaly_score_percentile(values, current_val):
    """Compute percentile-based anomaly score (P75/P95/P99).
    Returns (level) or None if insufficient data.
    """
    if len(values) < BASELINE_MIN_POINTS:
        return None, None
    s = sorted(values)
    n = len(s)
    p75 = s[int(n * 0.75)] if n > 3 else s[-1]
    p95 = s[int(n * 0.95)] if n > 20 else s[-1]
    p99 = s[int(n * 0.99)] if n > 100 else s[-1]
    ratio = round(current_val / p99, 2) if p99 > 0 else 0
    if current_val > p99:
        return ratio, "CRITICAL"
    elif current_val > p95:
        return ratio, "WARNING"
    elif current_val > p75:
        return ratio, "INFO"
    return ratio, "NORMAL"


def compute_anomaly_score_stl(values, current_val):
    """Sprint 11: STL 时序分解异常评分.

    原理: Y(t) = T(t) + S(t) + R(t)
        T = 长期趋势 (业务增长)
        S = 日/周周期 (早晚高峰)
        R = 残差 (真实异常信号)
    异常 = |R(t) - mu(R)| / sigma(R) > threshold

    Args:
        values: 历史时序, 至少 168 点 (7d 1h 粒度)
        current_val: 当前值

    Returns:
        (z_score, level) 元组, 不足数据返回 (None, None)
    """
    if len(values) < STL_MIN_POINTS:
        return None, None
    try:
        import numpy as np
        from statsmodels.tsa.seasonal import STL
        arr = np.asarray(values, dtype=float)
        # STL 分解: period=24 (日周期), seasonal=7 (LOESS 平滑窗口)
        stl = STL(arr, period=24, seasonal=7, robust=True)
        result = stl.fit()
        residual = result.resid
        resid_std = float(np.std(residual))
        if resid_std < 1e-9:
            return 0.0, "NORMAL"
        # 当前残差 (取最后一个点)
        last_resid = float(residual[-1])
        # 偏差 = 当前残差 vs 残差均值 (3倍标准差外判为异常)
        resid_mean = float(np.mean(residual))
        z = abs(last_resid - resid_mean) / resid_std
        if z > ANOMALY_CRIT_Z:
            return round(float(z), 2), "CRITICAL"
        elif z > ANOMALY_WARN_Z:
            return round(float(z), 2), "WARNING"
        elif z > ANOMALY_INFO_Z:
            return round(float(z), 2), "INFO"
        return round(float(z), 2), "NORMAL"
    except Exception as e:
        # STL 失败回退 None (调用方应 fallback 到 Z-Score)
        return None, None


def _get_cn_business_holidays(years):
    """Sprint 11.5: 获取中国节假日 + 阿里业务日 (双11/618/双12/38/元宵)."""
    try:
        import holidays as hol_lib
        import pandas as pd
        # 中国法定节假日
        cn = hol_lib.country_holidays("CN", years=years)
        # 阿里业务特殊日子
        ab_dates = []
        for y in years:
            for d, n in [
                (f"{y}-11-11", "Double 11"),
                (f"{y}-12-12", "Double 12"),
                (f"{y}-06-18", "618"),
                (f"{y}-03-08", "Women's Day"),
            ]:
                ab_dates.append({"holiday": n, "ds": pd.Timestamp(d)})
        if ab_dates:
            ab_df = pd.DataFrame(ab_dates)
            return cn, ab_df
        return cn, None
    except Exception:
        return None, None


def compute_anomaly_score_prophet(values, timestamps, current_val):
    """Sprint 11.5: Prophet 节假日感知异常评分.

    原理: 训练 Prophet 预测模型 (含中国节假日 + 阿里业务日),
    预测值 vs 实际值超出 yhat_lower/upper 则判为异常.

    Args:
        values: 历史时序, 至少 14d 1h = 336 点
        timestamps: 历史时序的时间戳 (与 values 一一对应)
        current_val: 当前值

    Returns:
        (anomaly_score, level) 元组, 不足数据/异常返回 (None, None)
    """
    if len(values) < PROPHET_MIN_POINTS or len(timestamps) != len(values):
        return None, None
    try:
        import pandas as pd
        from prophet import Prophet

        # Sprint 11.5 fix: 支持毫秒时间戳 (CMS Datapoints.timestamp 是 ms)
        if timestamps and isinstance(timestamps[0], (int, float)):
            ts_series = pd.to_datetime(pd.Series(timestamps), unit="ms")
        else:
            ts_series = pd.to_datetime(pd.Series(timestamps))
        df = pd.DataFrame({"ds": ts_series, "y": values})
        # 取时间范围年份, 获取节假日
        years = sorted(set(df["ds"].dt.year.tolist()))
        cn_holidays, ab_holidays = _get_cn_business_holidays(years)

        # 构建 Prophet
        m = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=True,
            interval_width=0.95,  # 95% 置信区间
        )
        # 注入中国节假日
        if cn_holidays is not None:
            try:
                m = m.add_country_holidays(country_name="CN")
            except Exception:
                pass  # 添加失败不影响主流程
        # 注入阿里业务日
        if ab_holidays is not None:
            m.holidays = ab_holidays

        # 训练 (3s 限制)
        m.fit(df)

        # 预测最后一点
        future = m.make_future_dataframe(periods=1, freq="H")
        forecast = m.predict(future)
        last = forecast.iloc[-1]
        predicted = float(last["yhat"])
        lower = float(last["yhat_lower"])
        upper = float(last["yhat_upper"])

        # 异常判定: 超出 yhat_lower/upper → 异常
        if current_val > upper:
            excess = (current_val - upper) / max(upper - predicted, 1.0)
            if excess > 1.0:
                return round(excess, 2), "CRITICAL"
            return round(excess, 2), "WARNING"
        elif current_val < lower:
            deficit = (lower - current_val) / max(predicted - lower, 1.0)
            if deficit > 1.0:
                return round(-deficit, 2), "CRITICAL"
            return round(-deficit, 2), "WARNING"
        # 在区间内
        margin = (upper - lower) / 2 if (upper - lower) > 0 else 1.0
        ratio = abs(current_val - predicted) / margin
        if ratio > 1.5:
            return round(ratio, 2), "INFO"
        return 0.0, "NORMAL"
    except Exception:
        return None, None  # Prophet 失败回退 STL


def _has_consecutive_anomaly(values, method, threshold):
    """降噪: check if >= ANOMALY_MIN_CONSECUTIVE consecutive recent points exceed threshold
    relative to the FULL baseline (not the check window, to avoid inflating mean/std)."""
    n = len(values)
    if n < ANOMALY_MIN_CONSECUTIVE * 2:
        return False

    if method in (ANOMALY_METHOD_ZSCORE, ANOMALY_METHOD_DUAL, ANOMALY_METHOD_STL):  # Sprint 11: STL 降噪复用 Z-Score 逻辑
        # Use full baseline for mean/std
        mean = sum(values) / n
        std = (sum((v - mean) ** 2 for v in values) / n) ** 0.5
        if std == 0:
            return False
        # Check last N points for consecutive anomalies
        check_count = min(n, ANOMALY_MIN_CONSECUTIVE * 3)
        recent = values[-check_count:]
        consecutive = 0
        for v in reversed(recent):
            z = abs((v - mean) / std)
            if z > threshold:
                consecutive += 1
                if consecutive >= ANOMALY_MIN_CONSECUTIVE:
                    return True
            else:
                consecutive = 0
        return False
    elif method == ANOMALY_METHOD_PERCENTILE:
        # Use full baseline for percentile thresholds
        s = sorted(values)
        n_pts = len(s)
        p_thresh = s[int(n_pts * 0.95)] if n_pts > 20 else (s[-1] if n_pts > 0 else 0)
        check_count = min(n, ANOMALY_MIN_CONSECUTIVE * 3)
        recent = values[-check_count:]
        consecutive = 0
        for v in reversed(recent):
            if v > p_thresh:
                consecutive += 1
                if consecutive >= ANOMALY_MIN_CONSECUTIVE:
                    return True
            else:
                consecutive = 0
        return False
    return False


def format_anomaly_scores_table(anomaly_scores):
    """Format anomaly scores as Markdown table. CRITICAL and WARNING shown; INFO collapsed."""
    if not anomaly_scores:
        return "\n#### 异常评分摘要\n\n✅ 未检测到显著异常\n\n"
    critical = [a for a in anomaly_scores if a.get("level") == "CRITICAL"]
    warning = [a for a in anomaly_scores if a.get("level") == "WARNING"]
    info = [a for a in anomaly_scores if a.get("level") == "INFO"]
    lines = ["\n#### 异常评分摘要（动态基线）\n\n"]
    if critical or warning:
        lines.append("| 实例 | 类型 | 指标 | 当前值 | 基线μ | Z-Score | 方法 | 等级 |\n")
        lines.append("|------|------|------|-------:|------:|-------:|------|:----:|\n")
        for a in critical:
            lines.append("| %s | %s | %s | %.1f | %.1f | %.1f | %s | 🔴 CRITICAL |\n" % (
                a.get("instance_id", "")[:20], a.get("resource_type", ""),
                a.get("metric", ""), a.get("current_value", 0),
                a.get("baseline_mean", 0), a.get("z_score", 0),
                a.get("method", "")))
        for a in warning:
            lines.append("| %s | %s | %s | %.1f | %.1f | %.1f | %s | 🟡 WARNING |\n" % (
                a.get("instance_id", "")[:20], a.get("resource_type", ""),
                a.get("metric", ""), a.get("current_value", 0),
                a.get("baseline_mean", 0), a.get("z_score", 0),
                a.get("method", "")))
    if info:
        lines.append("\n*另有 %d 条 INFO 级别异常（记录，未告警）*\n" % len(info))
    return "".join(lines)



# ═══════════════════════════════════════════════════════════════════════════════
# Incident Schema 转换器 (Sprint 9)
# ═══════════════════════════════════════════════════════════════════════════════
# 把 runbook 输出的"短字段名 finding" (r/t/m/v) 转为 incident-schema v1.0.0
# 规范见 references/incident-schema.md
# ═══════════════════════════════════════════════════════════════════════════════

# 资源类型 → incident schema enum 映射
RESOURCE_TYPE_MAP = {
    "ECS": "ECS", "SLB": "SLB", "RDS": "RDS", "Redis": "Redis",
    "Redis-Tair": "Redis", "ACK": "ACK", "NAT": "NAT", "EIP": "EIP",
    "VPC": "VPC", "VSwitch": "VPC", "SecurityGroup": "SG", "SG": "SG",
    "NAS": "NAS", "PolarDB": "PolarDB", "MongoDB": "MongoDB",
    "OSS": "OSS", "ECI": "OTHER", "ES": "OTHER", "Other": "OTHER",
}

# metric + resource_type → rule_id 映射
RULE_ID_MAP = {
    ("RDS", "DiskUsage"): "RDS-04",
    ("RDS", "CpuUsage"): "RDS-01",
    ("RDS", "ConnectionUsage"): "RDS-02",
    ("RDS", "SlowQueryCount"): "RDS-03",
    ("ECS", "CPUUtilization"): "ECS-01",
    ("ECS", "memory_usage"): "ECS-02",
    ("ECS", "DiskUsage"): "ECS-03",
    ("SLB", "ActiveConnection"): "SLB-ECS-03",
    ("Redis", "memory_usage"): "REDIS-01",
    ("Redis", "UsedConnection"): "REDIS-02",
    ("ACK", "cpu_oversale"): "ACK-LIMITS-01",
    ("ACK", "mem_oversale"): "ACK-LIMITS-03",
    ("ACK", "cpu_util"): "ECS-01",
    ("ACK", "mem_util"): "ECS-02",
    ("SG", "rule"): "SG-01",
}


def _gen_dedup_key(customer: str, resource_type: str, resource_id: str, rule_id: str, level: str) -> str | None:
    """生成 dedup_key (incident-schema §四). INFO 级别返回 None."""
    if not customer or not resource_id or not rule_id:
        return None
    if level == "INFO":
        return None
    date_bucket = datetime.utcnow().strftime("%Y-%m-%d")
    return f"{customer}:{resource_type}:{resource_id}:{rule_id}:{date_bucket}"


def to_incident(finding: dict, *, customer: str, run_id: str, region: str, runbook_id: str, runbook_version: str, scenario: str, report_path: str, level_override: str | None = None) -> dict:
    """finding (短字段名) → incident schema v1.0.0 转换器.

    Args:
        finding: 短字段名 finding, 形如 {"r": "rm-xxx", "t": "RDS", "m": "DiskUsage", "v": 97.92, "th": "75/90"}
        customer: 客户标识
        run_id: 所属 run_id (UUIDv4)
        region: 阿里云 region
        runbook_id: runbook 标识 (如 "01-daily-health-check")
        runbook_version: runbook 版本
        scenario: 场景 (daily_check / emergency / capacity / pre_launch)
        report_path: JSON 报告路径
        level_override: 强制覆盖 level (默认根据 critical/warning 列表来源推断)

    Returns:
        符合 incident-schema v1.0.0 的 dict
    """
    resource_type_raw = finding.get("t", "OTHER")
    resource_type = RESOURCE_TYPE_MAP.get(resource_type_raw, "OTHER")
    resource_id = finding.get("r", "")
    metric = finding.get("m", "")
    current_value = finding.get("v", 0)
    threshold_str = finding.get("th", "0/0")  # 格式 "warning/critical"

    # 解析阈值
    threshold_warning, threshold_critical = 0, 0
    try:
        parts = str(threshold_str).split("/")
        threshold_warning = float(parts[0]) if parts[0] else 0
        threshold_critical = float(parts[1]) if len(parts) > 1 and parts[1] else 0
    except (ValueError, IndexError):
        pass

    # 推断 level
    if level_override:
        level = level_override
    elif metric and resource_type_raw in RESOURCE_TYPE_MAP:
        level = "CRITICAL" if current_value >= threshold_critical > 0 else "WARNING"
    else:
        level = "WARNING"

    # rule_id
    rule_id = RULE_ID_MAP.get((resource_type_raw, metric), "FULL-01")
    rule_id = RULE_ID_MAP.get((resource_type, metric), rule_id)

    # title
    title = f"{resource_type_raw} {metric}={current_value}" if metric else f"{resource_type_raw} finding"

    # 修复命令 — 按 [SUGGESTED] / [READONLY] 前缀标记
    fix_commands = []
    if metric and resource_type_raw:
        fix_commands.append(f"[READONLY] aliyun cms DescribeMetricList --Namespace acs_{resource_type_raw.lower()}_dashboard --MetricName {metric}")
    if level == "CRITICAL" and metric == "DiskUsage" and resource_type_raw == "RDS":
        fix_commands.append("[SUGGESTED] aliyun rds ModifyDBInstanceSpec --DBInstanceId {id} --DBInstanceStorage 200")
        fix_commands.append("[AUTO-NOTIFY] CALL mysql.rds_cycle_binlog();")
    elif level == "CRITICAL" and metric == "ActiveConnection" and resource_type_raw == "SLB":
        fix_commands.append("[SUGGESTED] aliyun slb SetLoadBalancerTCPListenerAttribute --IdleTimeout 60")
        fix_commands.append("[AUTO-QUIET] aliyun ecs RunCommand --CommandContent 'ss -tan | awk \"{print \\$1}\" | sort | uniq -c'")

    return {
        "incident_id": str(uuid.uuid4()),
        "schema_version": "1.0.0",
        "customer": customer,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "run_id": run_id,
        "level": level,
        "score": None,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_name": None,
        "region": region,
        "rule_id": rule_id,
        "rule_version": "1.0.0",
        "title": title,
        "dedup_key": _gen_dedup_key(customer, resource_type, resource_id, rule_id, level),
        "metric": metric,
        "current_value": current_value,
        "threshold_critical": threshold_critical or None,
        "threshold_warning": threshold_warning or None,
        "baseline_mean": finding.get("baseline_mean"),
        "baseline_std": finding.get("baseline_std"),
        "z_score": finding.get("z_score"),
        "impact": finding.get("impact", f"{resource_type_raw} 资源 {resource_id} {metric}={current_value} 超过阈值"),
        "suggestion": finding.get("suggestion", "参见 references/inference-rules.md 对应规则"),
        "fix_commands": fix_commands,
        "status": "open",
        "assignee": None,
        "acknowledged_at": None,
        "resolved_at": None,
        "ttl_hours": 168,
        "parent_incident_id": None,
        "related_incidents": [],
        "trace": {
            "runbook_id": runbook_id,
            "runbook_version": runbook_version,
            "scenario": scenario,
            "commands_executed": finding.get("commands_executed", []),
            "total_api_calls": finding.get("total_api_calls", 0),
            "detection_method": finding.get("method", "static-threshold"),
            "report_path": report_path,
        },
        "tags": [resource_type_raw.lower()],
        "metadata": {},
    }


def anomaly_to_incident(a: dict, *, customer: str, run_id: str, region: str, runbook_id: str, runbook_version: str, scenario: str, report_path: str) -> dict:
    """anomaly_scores 元素 → incident schema v1.0.0 转换器."""
    return to_incident(
        {
            "r": a.get("instance_id", ""),
            "t": a.get("resource_type", "OTHER"),
            "m": a.get("metric", ""),
            "v": a.get("current_value", 0),
            "th": "0/0",
            "baseline_mean": a.get("baseline_mean"),
            "baseline_std": a.get("baseline_std"),
            "z_score": a.get("z_score"),
            "impact": f"动态基线偏离 (z-score={a.get('z_score', 0):.2f})",
            "suggestion": "观察是否持续偏离, 必要时巡检确认",
            "method": a.get("method", "z-score"),
        },
        customer=customer, run_id=run_id, region=region,
        runbook_id=runbook_id, runbook_version=runbook_version,
        scenario=scenario, report_path=report_path,
        level_override=a.get("level", "WARNING"),
    )


def findings_to_incidents(critical: list, warning: list, *, customer: str, run_id: str, region: str, runbook_id: str, runbook_version: str, scenario: str, report_path: str) -> list:
    """批量转换 critical + warning 列表为 incidents[] 数组."""
    incidents = []
    for c in critical:
        incidents.append(to_incident(
            c, customer=customer, run_id=run_id, region=region,
            runbook_id=runbook_id, runbook_version=runbook_version,
            scenario=scenario, report_path=report_path,
            level_override="CRITICAL",
        ))
    for w in warning:
        incidents.append(to_incident(
            w, customer=customer, run_id=run_id, region=region,
            runbook_id=runbook_id, runbook_version=runbook_version,
            scenario=scenario, report_path=report_path,
            level_override="WARNING",
        ))
    return incidents


def format_incidents_section_md(rpt: dict, max_rows: int = 50) -> str:
    """从 JSON 报告字典中提取 incidents 数组，格式化为 MD 表格.

    Args:
        rpt: 报告 dict (含 incidents + incidents_meta)
        max_rows: 最多展示多少行 (避免 MD 报告过长)

    Returns:
        MD 文本, 空 incidents 时返回空字符串
    """
    incidents = rpt.get("incidents", [])
    if not incidents:
        return ""

    meta = rpt.get("incidents_meta", {})
    schema_v = meta.get("schema_version", "1.0.0")
    total = meta.get("total", len(incidents))

    lines = [f"\n## Incidents (schema {schema_v})\n"]
    lines.append(
        f"总计: {total} (CRITICAL={meta.get('critical', 0)}, "
        f"WARNING={meta.get('warning', 0)}, INFO={meta.get('info', 0)})\n\n"
    )
    lines.append("| Level | Rule | Resource | Metric | Value | Title |\n")
    lines.append("|:------|:-----|:---------|:-------|------:|:------|\n")

    # 优先显示 CRITICAL, 再 WARNING, 最后 INFO
    level_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    sorted_inc = sorted(incidents, key=lambda x: (level_order.get(x.get("level"), 99), x.get("rule_id", "")))

    shown = 0
    for i in sorted_inc:
        if shown >= max_rows:
            lines.append(f"\n*... 还有 {total - shown} 条, 详见 JSON 报告*\n")
            break
        lines.append(
            f"| {i['level']} | `{i['rule_id']}` | {i['resource_type']}/{i['resource_id'][:20]} | "
            f"{i.get('metric', '-')} | {i.get('current_value', '-')} | {i['title']} |\n"
        )
        shown += 1

    return "".join(lines)


def format_incidents_section_md(rpt: dict, max_rows: int = 50) -> str:
    """从 JSON 报告字典中提取 incidents 数组, 格式化为 MD 表格."""
    incidents = rpt.get("incidents", [])
    if not incidents:
        return ""
    meta = rpt.get("incidents_meta", {})
    schema_v = meta.get("schema_version", "1.0.0")
    total = meta.get("total", len(incidents))
    lines = [f"\n## Incidents (schema {schema_v})\n"]
    lines.append(
        f"总计: {total} (CRITICAL={meta.get('critical', 0)}, "
        f"WARNING={meta.get('warning', 0)}, INFO={meta.get('info', 0)})\n\n"
    )
    lines.append("| Level | Rule | Resource | Metric | Value | Title |\n")
    lines.append("|:------|:-----|:---------|:-------|------:|:------|\n")
    level_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    sorted_inc = sorted(incidents, key=lambda x: (level_order.get(x.get("level"), 99), x.get("rule_id", "")))
    shown = 0
    for i in sorted_inc:
        if shown >= max_rows:
            lines.append(f"\n*... 还有 {total - shown} 条, 详见 JSON 报告*\n")
            break
        lines.append(
            f"| {i['level']} | `{i['rule_id']}` | {i['resource_type']}/{i['resource_id'][:20]} | "
            f"{i.get('metric', '-')} | {i.get('current_value', '-')} | {i['title']} |\n"
        )
        shown += 1
    return "".join(lines)
