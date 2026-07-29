"""WeCom (企业微信) smart bot adapter."""
from __future__ import annotations

import time

from alicloud_shared.chat_context import ChatContext, redact_raw


def normalize_wecom(body: dict) -> ChatContext:
    """Normalize a WeCom smart bot message body into ChatContext."""
    chat_type = "group" if body.get("chattype") == "group" else "p2p"
    user_id = body.get("from", {}).get("userid", "")
    if chat_type == "group" and body.get("chatid"):
        session_id = body["chatid"]
    else:
        # Synthesize session for single chat (WeCom lacks p2p session id)
        session_id = f"synth-p2p-{user_id}-{int(time.time())}"
    return ChatContext(
        user_id=user_id,
        session_id=session_id,
        platform="wecom",
        chat_type=chat_type,
        raw=redact_raw(body),
    )