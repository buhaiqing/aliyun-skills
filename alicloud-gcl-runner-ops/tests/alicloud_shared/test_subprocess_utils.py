"""Tests for subprocess env propagation helper."""
import os


class TestSafeSubprocessEnv:
    def test_preserves_chat_vars(self, monkeypatch):
        monkeypatch.setenv("CHAT_PLATFORM", "wecom")
        monkeypatch.setenv("CHAT_USER_ID", "u1")
        from alicloud_shared.subprocess_utils import safe_subprocess_env
        env = safe_subprocess_env()
        assert env["CHAT_PLATFORM"] == "wecom"
        assert env["CHAT_USER_ID"] == "u1"

    def test_preserves_chat_vars_with_extra(self, monkeypatch):
        monkeypatch.setenv("CHAT_PLATFORM", "wecom")
        from alicloud_shared.subprocess_utils import safe_subprocess_env
        env = safe_subprocess_env({"OTHER_VAR": "x"})
        assert env["CHAT_PLATFORM"] == "wecom"
        assert env["OTHER_VAR"] == "x"

    def test_extra_overrides_chat_vars(self, monkeypatch):
        monkeypatch.setenv("CHAT_PLATFORM", "wecom")
        from alicloud_shared.subprocess_utils import safe_subprocess_env
        env = safe_subprocess_env({"CHAT_PLATFORM": "feishu"})
        assert env["CHAT_PLATFORM"] == "feishu"

    def test_no_extra_returns_only_chat_vars(self, monkeypatch):
        monkeypatch.setenv("CHAT_PLATFORM", "wecom")
        monkeypatch.setenv("NON_CHAT_VAR", "noise")
        from alicloud_shared.subprocess_utils import safe_subprocess_env
        env = safe_subprocess_env()
        assert "CHAT_PLATFORM" in env
        assert "NON_CHAT_VAR" not in env