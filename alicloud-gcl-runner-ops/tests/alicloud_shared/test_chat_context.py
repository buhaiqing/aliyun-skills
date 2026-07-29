"""Tests for ChatContext dataclass and redact_raw."""
import pytest


class TestContextVar:
    def test_current_returns_none_by_default(self):
        from alicloud_shared.chat_context import current
        assert current() is None

    def test_bind_then_current(self):
        from alicloud_shared.chat_context import bind, current, ChatContext
        ctx = ChatContext(user_id="u", session_id="s", platform="cli", chat_type="n/a", raw={})
        bind(ctx)
        try:
            assert current() == ctx
        finally:
            # reset for other tests
            from alicloud_shared.chat_context import _ctx_var
            _ctx_var.set(None)

    def test_bind_overwrites(self):
        from alicloud_shared.chat_context import bind, current, ChatContext, _ctx_var
        try:
            ctx1 = ChatContext(user_id="u1", session_id="s1", platform="wecom", chat_type="group", raw={})
            ctx2 = ChatContext(user_id="u2", session_id="s2", platform="feishu", chat_type="p2p", raw={})
            bind(ctx1)
            bind(ctx2)
            assert current() == ctx2
        finally:
            _ctx_var.set(None)


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


class TestAdapterRegistry:
    def test_normalize_unknown_returns_cli_fallback(self):
        from alicloud_shared.chat_context import normalize
        ctx = normalize("unknown-platform", {})
        assert ctx.platform == "unknown-platform"
        assert ctx.chat_type == "n/a"

    def test_register_then_normalize(self):
        from alicloud_shared.chat_context import normalize, register_adapter, _ADAPTERS
        from alicloud_shared.chat_context import ChatContext
        def my_adapter(payload):
            return ChatContext(user_id="x", session_id="y", platform="myplat", chat_type="api", raw=payload)
        try:
            register_adapter("myplat", my_adapter)
            ctx = normalize("myplat", {"k": "v"})
            assert ctx.platform == "myplat"
            assert ctx.user_id == "x"
            assert ctx.raw == {"k": "v"}
        finally:
            _ADAPTERS.pop("myplat", None)


class TestNormalizeCli:
    def test_default_user_id_anonymous(self, monkeypatch):
        monkeypatch.delenv("USER", raising=False)
        from alicloud_shared.chat_context import normalize_cli
        ctx = normalize_cli()
        assert ctx.user_id == "anonymous"

    def test_uses_user_env(self, monkeypatch):
        monkeypatch.setenv("USER", "alice")
        from alicloud_shared.chat_context import normalize_cli
        ctx = normalize_cli()
        assert ctx.user_id == "alice"

    def test_session_id_has_cli_prefix(self, monkeypatch):
        from alicloud_shared.chat_context import normalize_cli
        ctx = normalize_cli()
        assert ctx.session_id.startswith("cli-")
        assert ctx.platform == "cli"


class TestBindFromEnv:
    def test_no_env_returns_none(self, monkeypatch):
        for key in ["CHAT_PLATFORM", "CHAT_USER_ID", "CHAT_SESSION_ID", "CHAT_TYPE"]:
            monkeypatch.delenv(key, raising=False)
        from alicloud_shared.chat_context import bind_from_env, current, _ctx_var
        try:
            result = bind_from_env()
            assert result is None
            assert current() is None
        finally:
            _ctx_var.set(None)

    def test_full_env_binds(self, monkeypatch):
        monkeypatch.setenv("CHAT_PLATFORM", "wecom")
        monkeypatch.setenv("CHAT_USER_ID", "u1")
        monkeypatch.setenv("CHAT_SESSION_ID", "s1")
        monkeypatch.setenv("CHAT_TYPE", "group")
        from alicloud_shared.chat_context import bind_from_env, current, _ctx_var
        try:
            result = bind_from_env()
            assert result is not None
            assert result.platform == "wecom"
            assert result.user_id == "u1"
            assert result.session_id == "s1"
            assert result.chat_type == "group"
            assert current() == result
        finally:
            _ctx_var.set(None)

    def test_anonymous_fallback_for_user(self, monkeypatch):
        monkeypatch.setenv("CHAT_PLATFORM", "wecom")
        monkeypatch.delenv("CHAT_USER_ID", raising=False)
        from alicloud_shared.chat_context import bind_from_env, _ctx_var
        try:
            result = bind_from_env()
            assert result.user_id == "anonymous"
        finally:
            _ctx_var.set(None)
