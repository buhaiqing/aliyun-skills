"""Chat context propagation across IM platforms and HTTP.

Provides a unified ChatContext dataclass + ContextVar-based propagation,
plus platform adapters registered via a registry.
"""
from __future__ import annotations

import datetime
import os
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


_ctx_var: ContextVar[ChatContext | None] = ContextVar("chat_ctx", default=None)


def bind(ctx: ChatContext) -> None:
    """Bind a chat context for the current async task / thread."""
    _ctx_var.set(ctx)


def current() -> ChatContext | None:
    """Return the currently bound chat context, or None."""
    return _ctx_var.get()


_ADAPTERS: dict[str, Callable[[Any], ChatContext]] = {}


def register_adapter(platform: str, fn: Callable[[Any], ChatContext]) -> None:
    """Register a platform-specific chat context adapter."""
    _ADAPTERS[platform] = fn


def normalize(platform: str, payload: Any) -> ChatContext:
    """Normalize a payload into ChatContext using the registered adapter.

    Falls back to normalize_cli for unknown platforms.
    """
    fn = _ADAPTERS.get(platform)
    if fn is not None:
        return fn(payload)
    return normalize_cli(source=platform)


def normalize_cli(*, source: str = "cli") -> ChatContext:
    """Default CLI fallback adapter."""
    user_id = os.environ.get("USER") or "anonymous"
    session_id = f"cli-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    return ChatContext(
        user_id=user_id,
        session_id=session_id,
        platform=source,
        chat_type="n/a",
        raw={},
    )


def bind_from_env() -> ChatContext | None:
    """Bind a chat context from CHAT_* environment variables.

    Returns the bound context, or None if CHAT_PLATFORM is not set.
    """
    platform = os.environ.get("CHAT_PLATFORM")
    if not platform:
        return None
    ctx = ChatContext(
        user_id=os.environ.get("CHAT_USER_ID") or "anonymous",
        session_id=os.environ.get("CHAT_SESSION_ID") or "unknown",
        platform=platform,
        chat_type=os.environ.get("CHAT_TYPE") or "n/a",
        raw={},
    )
    bind(ctx)
    return ctx
