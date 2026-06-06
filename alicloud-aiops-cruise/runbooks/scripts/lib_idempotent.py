"""lib_idempotent.py — 幂等性公共工具 (Sprint 12 Stage 2 D1)

提供 4 个工具:
- acquire_lock(name, timeout=600) - 文件锁, 防并发重入
- release_lock(name) - 释放锁
- is_locked(name) - 检查是否被锁
- safe_append(path, line) - append + timestamp, 不覆盖

设计原则:
- 零外部依赖 (仅 os/time/pathlib)
- TTL 防止僵尸锁 (默认 10 分钟自动过期)
- PID 校验, 防止杀进程后锁残留
"""

import os
import time
from datetime import UTC, datetime
from pathlib import Path

LOCK_DIR = Path(os.environ.get("AIOPS_LOCK_DIR", "/tmp"))
DEFAULT_TTL_SECONDS = 600  # 10 分钟

# 工具集导出
__all__ = [
    "acquire_lock",
    "release_lock",
    "is_locked",
    "safe_append",
    "now_iso",
]


def now_iso() -> str:
    """返回当前时间 ISO 8601 (UTC) 字符串."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _lock_path(name: str) -> Path:
    """生成锁文件路径. 形如 /tmp/cruise-{name}.lock"""
    safe_name = name.replace("/", "_").replace(" ", "_")
    return LOCK_DIR / f"cruise-{safe_name}.lock"


def is_locked(name: str, ttl: int = DEFAULT_TTL_SECONDS) -> bool:
    """检查 lock 是否被持有.

    Args:
        name: 锁名 (e.g. "daily-health-check.rg-acfmvyfsd4znnoi")
        ttl: 锁 TTL, 超过视为自动过期

    Returns:
        True = 被锁 (TTL 内), False = 未锁 / 已过期
    """
    p = _lock_path(name)
    if not p.exists():
        return False
    # 检查 TTL
    mtime = p.stat().st_mtime
    age = time.time() - mtime
    if age > ttl:
        # 自动过期, 删掉
        try:
            p.unlink()
        except OSError:
            pass
        return False
    return True


def acquire_lock(name: str, ttl: int = DEFAULT_TTL_SECONDS) -> bool:
    """尝试获取文件锁.

    Args:
        name: 锁名
        ttl: 锁 TTL, 默认 10 分钟

    Returns:
        True = 获取成功, False = 已被持有
    """
    p = _lock_path(name)
    # 先检查是否已被锁
    if is_locked(name, ttl):
        return False
    # 写锁文件 (PID + hostname + start_time)
    try:
        p.write_text(
            f"pid={os.getpid()}\n"
            f"hostname={os.uname().nodename}\n"
            f"start_time={now_iso()}\n"
            f"ttl={ttl}\n"
        )
        return True
    except OSError:
        return False


def release_lock(name: str) -> None:
    """释放锁 (仅当本进程持有时)."""
    p = _lock_path(name)
    if not p.exists():
        return
    try:
        content = p.read_text()
        if f"pid={os.getpid()}" in content:
            p.unlink()
    except (OSError, ValueError):
        pass


def safe_append(path: str | Path, line: str) -> None:
    """安全追加一行 (带 ISO timestamp 前缀), 不覆盖.

    Args:
        path: 文件路径
        line: 内容 (不含换行)
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        f.write(f"[{now_iso()}] {line}\n")
