"""Tests for the Feishu (飞书) chat context adapter."""


class TestNormalizeFeishu:
    def test_uses_open_id_for_user(self):
        from alicloud_shared.adapters.feishu import normalize_feishu
        event = {
            "chat_id": "oc_xyz",
            "chat_type": "group",
            "sender": {"sender_id": {"open_id": "ou_abc"}},
        }
        ctx = normalize_feishu(event)
        assert ctx.platform == "feishu"
        assert ctx.user_id == "ou_abc"
        assert ctx.session_id == "oc_xyz"
        assert ctx.chat_type == "group"

    def test_p2p_chat_also_has_chat_id(self):
        from alicloud_shared.adapters.feishu import normalize_feishu
        event = {
            "chat_id": "p2p_123",
            "chat_type": "p2p",
            "sender": {"sender_id": {"open_id": "ou_x"}},
        }
        ctx = normalize_feishu(event)
        assert ctx.session_id == "p2p_123"
        assert ctx.chat_type == "p2p"