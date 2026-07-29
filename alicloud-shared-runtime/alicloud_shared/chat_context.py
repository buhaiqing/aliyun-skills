"""Chat context propagation across IM platforms and HTTP.

Provides a unified ChatContext dataclass + ContextVar-based propagation,
plus platform adapters registered via a registry.
"""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable


RAW_REDACT_KEYS = frozenset({
    "authorization", "x-auth-token", "cookie", "set-cookie",
    "access_token", "secret", "api_key", "apikey",
    "password", "pwd", "credential", "private_key",
})


def redact_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of raw with sensitive keys redacted."""
    if not raw:
        return raw
    return {
        k: v for k, v in raw.items()
        if k.lower() not in RAW_REDACT_KEYS
    }


@dataclass(frozen=True)
class ChatContext:
    """Platform-agnostic chat context."""
    user_id: str
    session_id: str
    platform: str
    chat_type: str
    raw: dict[str, Any]
