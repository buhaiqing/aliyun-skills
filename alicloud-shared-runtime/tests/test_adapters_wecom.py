"""Tests for the WeCom (企业微信) chat context adapter."""


class TestNormalizeWecom:
    def test_group_chat_uses_chatid_as_session(self):
        from alicloud_shared.adapters.wecom import normalize_wecom
        body = {
            "chattype": "group",
            "chatid": "oc_abc123",
            "from": {"userid": "ZhangSan"},
        }
        ctx = normalize_wecom(body)
        assert ctx.platform == "wecom"
        assert ctx.session_id == "oc_abc123"
        assert ctx.user_id == "ZhangSan"
        assert ctx.chat_type == "group"

    def test_single_chat_synthesizes_session(self):
        from alicloud_shared.adapters.wecom import normalize_wecom
        body = {"chattype": "single", "from": {"userid": "u1"}}
        ctx = normalize_wecom(body)
        assert ctx.platform == "wecom"
        assert ctx.chat_type == "p2p"
        assert ctx.user_id == "u1"
        assert "u1" in ctx.session_id
        # synthesized, not raw chatid
        assert "oc_" not in ctx.session_id

    def test_raw_redacted(self):
        from alicloud_shared.adapters.wecom import normalize_wecom
        body = {
            "chattype": "group",
            "chatid": "oc_x",
            "from": {"userid": "u1"},
            "Authorization": "secret",
        }
        ctx = normalize_wecom(body)
        assert "Authorization" not in ctx.raw