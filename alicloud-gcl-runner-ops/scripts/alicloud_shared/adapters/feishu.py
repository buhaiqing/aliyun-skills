"""Feishu (飞书) bot adapter."""
from __future__ import annotations

from alicloud_shared.chat_context import ChatContext, redact_raw


def normalize_feishu(event: dict) -> ChatContext:
    """Normalize a Feishu message event into ChatContext."""
    sender_id = event.get("sender", {}).get("sender_id", {})
    return ChatContext(
        user_id=sender_id.get("open_id", ""),
        session_id=event.get("chat_id", ""),
        platform="feishu",
        chat_type=event.get("chat_type", "p2p"),
        raw=redact_raw(event),
    )