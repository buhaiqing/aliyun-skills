"""HTTP POST API adapter (Nanobot OpenAI-compatible endpoint)."""
from __future__ import annotations

import time

from alicloud_shared.chat_context import ChatContext, redact_raw


def normalize_http(*, headers: dict, body: dict, caller_id: str) -> ChatContext:
    """Normalize an HTTP POST /v1/chat/completions request into ChatContext.

    caller_id: service identity from Bearer Token lookup.
    """
    user_id = (
        headers.get("X-Chat-User-Id")
        or headers.get("X-User-Id")
        or caller_id
    )
    session_id = body.get("session_id")
    if not session_id or session_id == "api:default":
        session_id = f"http-{caller_id}-{int(time.time())}"
    safe_headers = redact_raw(dict(headers))
    return ChatContext(
        user_id=user_id,
        session_id=session_id,
        platform="http",
        chat_type="api",
        raw={"headers": safe_headers, "body_keys": list(body.keys())},
    )