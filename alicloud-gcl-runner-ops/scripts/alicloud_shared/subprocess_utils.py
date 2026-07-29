"""Subprocess utilities that preserve CHAT_* env vars across process boundaries."""
from __future__ import annotations

import os
from typing import Any


def safe_subprocess_env(extra: dict[str, Any] | None = None) -> dict[str, str]:
    """Build a subprocess env dict that preserves CHAT_* vars from the parent.

    Use this instead of plain `env={...}` to avoid accidentally dropping
    chat context propagation when calling subprocess.run().

    Args:
        extra: Additional env vars to add (or override CHAT_* vars).

    Returns:
        Dict suitable for subprocess.run(env=...).

    Example:
        >>> subprocess.run(["python", "skill.py"], env=safe_subprocess_env({"FOO": "bar"}))
    """
    preserved = {k: v for k, v in os.environ.items() if k.startswith("CHAT_")}
    if extra:
        preserved.update(extra)
    return preserved