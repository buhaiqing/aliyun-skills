"""Tests for ChatContext dataclass and redact_raw."""
import pytest


class TestChatContext:
    def test_required_fields(self):
        from alicloud_shared.chat_context import ChatContext
        ctx = ChatContext(
            user_id="u1", session_id="s1", platform="wecom",
            chat_type="group", raw={"foo": "bar"},
        )
        assert ctx.user_id == "u1"
        assert ctx.session_id == "s1"
        assert ctx.platform == "wecom"
        assert ctx.chat_type == "group"
        assert ctx.raw == {"foo": "bar"}

    def test_is_frozen(self):
        from alicloud_shared.chat_context import ChatContext
        ctx = ChatContext(user_id="u", session_id="s", platform="cli", chat_type="n/a", raw={})
        with pytest.raises(Exception):
            ctx.user_id = "modified"


class TestRedactRaw:
    def test_redacts_authorization(self):
        from alicloud_shared.chat_context import redact_raw
        result = redact_raw({"Authorization": "secret-token", "foo": "bar"})
        assert "Authorization" not in result
        assert result["foo"] == "bar"

    def test_redacts_lowercase(self):
        from alicloud_shared.chat_context import redact_raw
        result = redact_raw({"authorization": "x", "x-auth-token": "y", "foo": "z"})
        assert "authorization" not in result
        assert "x-auth-token" not in result
        assert result["foo"] == "z"

    def test_redacts_secret_and_password(self):
        from alicloud_shared.chat_context import redact_raw
        result = redact_raw({"secret": "s", "password": "p", "credential": "c", "ok": "yes"})
        assert "secret" not in result
        assert "password" not in result
        assert "credential" not in result
        assert result["ok"] == "yes"

    def test_preserves_unknown_keys(self):
        from alicloud_shared.chat_context import redact_raw
        result = redact_raw({"foo": 1, "bar": True})
        assert result == {"foo": 1, "bar": True}
