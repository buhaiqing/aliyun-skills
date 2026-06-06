"""
_shared.py — AIOps Cruise 共享模块

所有 `runbooks/scripts/` 下的脚本从本模块导入公共函数。
减少重复代码，统一行为。

依赖: aliyun CLI + Python 3.10+
"""

import json
import os
import random
import subprocess
import time
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

# CMS 调用的并发控制: 最多 5 个同时执行
_CMS_SEM = Semaphore(5)
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
