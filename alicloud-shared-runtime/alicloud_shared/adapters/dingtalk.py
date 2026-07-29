"""DingTalk (钉钉) Stream adapter."""
from __future__ import annotations

from alicloud_shared.chat_context import ChatContext, redact_raw


def normalize_dingtalk(data: dict) -> ChatContext:
    """Normalize a DingTalk Stream message into ChatContext."""
    chat_type = "p2p" if data.get("chatType") == "1" else "group"
    return ChatContext(
        user_id=data.get("senderStaffId", ""),
        session_id=data.get("chatId", ""),
        platform="dingtalk",
        chat_type=chat_type,
        raw=redact_raw(data),
    )