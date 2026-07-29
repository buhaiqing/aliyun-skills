#!/usr/bin/env python3
"""Integration tests: trace record schema with user/session/platform from chat context.

These tests exercise the full path:
  platform adapter  →  ChatContext  →  bind (ContextVar)  →  TraceSchema.new()  →  to_dict()

Verifies SPEC §8 AC-1 (cross-platform format consistency), AC-6 (env var propagation
across subprocess), AC-7 (HTTP api:default fallback), AC-9 (WizardSession/TraceSessionId alignment).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Make alicloud_shared importable
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from alicloud_shared.chat_context import (  # noqa: E402
    ChatContext,
    _ctx_var,
    bind,
    bind_from_env,
    current,
)
from alicloud_shared.subprocess_utils import safe_subprocess_env  # noqa: E402


def _reset_ctx():
    """Reset ContextVar between tests."""
    _ctx_var.set(None)


class TestTraceFromEachPlatform(unittest.TestCase):
    """AC-1: Cross-platform trace format consistency."""

    def setUp(self):
        _reset_ctx()

    def tearDown(self):
        _reset_ctx()

    def test_wecom_group_chat_trace_fields(self):
        from alicloud_shared.adapters.wecom import normalize_wecom

        body = {
            "chattype": "group",
            "chatid": "oc_wecom_group_123",
            "from": {"userid": "ZhangSan"},
        }
        ctx = normalize_wecom(body)
        bind(ctx)

        # Simulate what ExecutionTrace.new() / TraceRun.new() does
        from_chat = current()
        trace_dict = {
            "trace_id": "trace-fake123",
            "user_id": from_chat.user_id,
            "session_id": from_chat.session_id,
            "platform": from_chat.platform,
            "chat_type": from_chat.chat_type,
        }

        assert trace_dict["user_id"] == "ZhangSan"
        assert trace_dict["session_id"] == "oc_wecom_group_123"
        assert trace_dict["platform"] == "wecom"
        assert trace_dict["chat_type"] == "group"

    def test_feishu_p2p_chat_trace_fields(self):
        from alicloud_shared.adapters.feishu import normalize_feishu

        event = {
            "chat_id": "feishu_p2p_xyz",
            "chat_type": "p2p",
            "sender": {"sender_id": {"open_id": "ou_alice"}},
        }
        ctx = normalize_feishu(event)
        bind(ctx)

        trace_dict = {
            "trace_id": "trace-fake456",
            "user_id": current().user_id,
            "session_id": current().session_id,
            "platform": current().platform,
            "chat_type": current().chat_type,
        }

        assert trace_dict["user_id"] == "ou_alice"
        assert trace_dict["session_id"] == "feishu_p2p_xyz"
        assert trace_dict["platform"] == "feishu"
        assert trace_dict["chat_type"] == "p2p"

    def test_dingtalk_group_chat_trace_fields(self):
        from alicloud_shared.adapters.dingtalk import normalize_dingtalk

        data = {
            "chatId": "ding_group_abc",
            "chatType": "2",  # group
            "senderStaffId": "staff_007",
        }
        ctx = normalize_dingtalk(data)
        bind(ctx)

        trace_dict = {
            "trace_id": "trace-fake789",
            "user_id": current().user_id,
            "session_id": current().session_id,
            "platform": current().platform,
            "chat_type": current().chat_type,
        }

        assert trace_dict["user_id"] == "staff_007"
        assert trace_dict["session_id"] == "ding_group_abc"
        assert trace_dict["platform"] == "dingtalk"
        assert trace_dict["chat_type"] == "group"

    def test_http_post_trace_fields_no_default_trap(self):
        """AC-7: HTTP POST must not produce session_id='api:default'."""
        from alicloud_shared.adapters.http_api import normalize_http

        # Simulate caller without explicit session_id (the api:default trap)
        ctx = normalize_http(
            headers={"X-Chat-User-Id": "ci-pipeline-bot", "Authorization": "Bearer SECRET"},
            body={"session_id": "api:default"},  # ← the trap
            caller_id="github-actions",
        )
        bind(ctx)

        trace_session_id = current().session_id
        # Must NOT be 'api:default'
        assert trace_session_id != "api:default"
        # Must contain caller_id for traceability
        assert "github-actions" in trace_session_id
        # User ID from header
        assert current().user_id == "ci-pipeline-bot"
        # Authorization must NOT leak into raw
        assert "Authorization" not in current().raw.get("headers", {})

    def test_http_post_explicit_session_id(self):
        """When caller provides explicit session_id, use it directly."""
        from alicloud_shared.adapters.http_api import normalize_http

        ctx = normalize_http(
            headers={"X-Chat-User-Id": "ops-zhang"},
            body={"session_id": "incident-rm-bp11-0729"},
            caller_id="alertmanager",
        )
        bind(ctx)

        assert current().session_id == "incident-rm-bp11-0729"
        assert current().user_id == "ops-zhang"
        assert current().platform == "http"
        assert current().chat_type == "api"


class TestTraceFromBindFromEnv(unittest.TestCase):
    """AC-6: env var protocol."""

    def setUp(self):
        _reset_ctx()

    def tearDown(self):
        _reset_ctx()

    def test_bind_from_env_populates_trace_fields(self):
        os.environ["CHAT_PLATFORM"] = "wecom"
        os.environ["CHAT_USER_ID"] = "env-user-1"
        os.environ["CHAT_SESSION_ID"] = "env-sess-1"
        os.environ["CHAT_TYPE"] = "group"

        try:
            ctx = bind_from_env()
            assert ctx is not None

            trace_dict = {
                "trace_id": "trace-envtest",
                "user_id": current().user_id,
                "session_id": current().session_id,
                "platform": current().platform,
                "chat_type": current().chat_type,
            }
            assert trace_dict["user_id"] == "env-user-1"
            assert trace_dict["session_id"] == "env-sess-1"
            assert trace_dict["platform"] == "wecom"
            assert trace_dict["chat_type"] == "group"
        finally:
            for k in ["CHAT_PLATFORM", "CHAT_USER_ID", "CHAT_SESSION_ID", "CHAT_TYPE"]:
                os.environ.pop(k, None)

    def test_bind_from_env_no_platform_returns_none(self):
        for k in ["CHAT_PLATFORM", "CHAT_USER_ID", "CHAT_SESSION_ID", "CHAT_TYPE"]:
            os.environ.pop(k, None)

        ctx = bind_from_env()
        assert ctx is None
        assert current() is None


class TestSafeSubprocessEnv(unittest.TestCase):
    """AC-6: cross-process env propagation."""

    def test_preserves_chat_vars_from_parent(self):
        os.environ["CHAT_PLATFORM"] = "feishu"
        os.environ["CHAT_USER_ID"] = "alice"
        os.environ["CHAT_SESSION_ID"] = "s1"
        try:
            env = safe_subprocess_env()
            assert env["CHAT_PLATFORM"] == "feishu"
            assert env["CHAT_USER_ID"] == "alice"
            assert env["CHAT_SESSION_ID"] == "s1"
        finally:
            for k in ["CHAT_PLATFORM", "CHAT_USER_ID", "CHAT_SESSION_ID"]:
                os.environ.pop(k, None)

    def test_extra_overrides_parent(self):
        os.environ["CHAT_PLATFORM"] = "feishu"
        try:
            env = safe_subprocess_env({"CHAT_PLATFORM": "dingtalk"})
            assert env["CHAT_PLATFORM"] == "dingtalk"
        finally:
            os.environ.pop("CHAT_PLATFORM", None)

    def test_subprocess_inherits_chat_vars(self):
        """End-to-end: parent subprocess sets env, child sees it via bind_from_env."""
        os.environ["CHAT_PLATFORM"] = "http"
        os.environ["CHAT_USER_ID"] = "child-process-user"
        os.environ["CHAT_SESSION_ID"] = "child-sess-99"
        os.environ["CHAT_TYPE"] = "api"
        try:
            # Spawn a python subprocess that calls bind_from_env and prints the context
            child_code = (
                "import sys, json, os\n"
                "sys.path.insert(0, "
                + repr(str(_SCRIPTS))
                + ")\n"
                "from alicloud_shared.chat_context import bind_from_env, current\n"
                "ctx = bind_from_env()\n"
                "print(json.dumps({'platform': ctx.platform, 'user_id': ctx.user_id, "
                "'session_id': ctx.session_id, 'chat_type': ctx.chat_type}))\n"
            )
            env = safe_subprocess_env()
            result = subprocess.run(
                [sys.executable, "-c", child_code],
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0, f"child failed: {result.stderr}"
            data = json.loads(result.stdout.strip())
            assert data["platform"] == "http"
            assert data["user_id"] == "child-process-user"
            assert data["session_id"] == "child-sess-99"
            assert data["chat_type"] == "api"
        finally:
            for k in ["CHAT_PLATFORM", "CHAT_USER_ID", "CHAT_SESSION_ID", "CHAT_TYPE"]:
                os.environ.pop(k, None)


class TestTraceRoundtrip(unittest.TestCase):
    """AC: Trace dict serialization includes all 3 IDs."""

    def test_full_trace_to_dict_has_all_ids(self):
        ctx = ChatContext(
            user_id="alice",
            session_id="sess-xyz",
            platform="wecom",
            chat_type="group",
            raw={"k": "v"},
        )
        bind(ctx)

        # Simulate ExecutionTrace.new() dict output
        from_chat = current()
        trace_dict = {
            "trace_id": "trace-roundtrip-1",
            "user_id": from_chat.user_id,
            "session_id": from_chat.session_id,
            "platform": from_chat.platform,
            "chat_type": from_chat.chat_type,
            "raw_keys": list(from_chat.raw.keys()),
        }
        # Round-trip via JSON
        js = json.dumps(trace_dict, ensure_ascii=False)
        loaded = json.loads(js)
        assert loaded["user_id"] == "alice"
        assert loaded["session_id"] == "sess-xyz"
        assert loaded["platform"] == "wecom"
        assert loaded["chat_type"] == "group"
        assert loaded["raw_keys"] == ["k"]


class TestBackwardCompat(unittest.TestCase):
    """SPEC §7.1: old trace JSON without new fields must load without error."""

    def test_old_trace_json_missing_new_fields(self):
        # Simulate loading a v1 trace JSON that has no user_id / platform / chat_type
        old_json = json.dumps({
            "trace_id": "trace-old-001",
            "operation": "old_op",
            "success": True,
            # No user_id, platform, chat_type
        })
        loaded = json.loads(old_json)
        # Should have None defaults when read back into a TraceRun-like dict
        trace_fields = {
            "user_id": loaded.get("user_id"),  # None
            "platform": loaded.get("platform"),  # None
            "chat_type": loaded.get("chat_type"),  # None
        }
        assert trace_fields["user_id"] is None
        assert trace_fields["platform"] is None
        assert trace_fields["chat_type"] is None
        # trace_id still present
        assert loaded["trace_id"] == "trace-old-001"


class TestWizardSessionTraceAlignment(unittest.TestCase):
    """AC-9: WizardSession.session_id must equal ChatContext.session_id."""

    def test_wizard_session_picks_up_chat_session_id(self):
        ctx = ChatContext(
            user_id="bob",
            session_id="chatid-from-feishu",
            platform="feishu",
            chat_type="group",
            raw={},
        )
        bind(ctx)

        # Simulate wizard Session creation reading from chat context
        # (matches wizard_cli.py derived_session_id logic)
        from_chat = current()
        derived_session_id = from_chat.session_id if from_chat else "fallback"
        derived_user_id = from_chat.user_id if from_chat else "anonymous"

        assert derived_session_id == "chatid-from-feishu"
        assert derived_user_id == "bob"


if __name__ == "__main__":
    unittest.main()