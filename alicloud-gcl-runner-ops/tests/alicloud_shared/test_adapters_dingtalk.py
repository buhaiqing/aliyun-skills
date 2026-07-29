"""Tests for the DingTalk (钉钉) Stream adapter."""


class TestNormalizeDingtalk:
    def test_p2p_when_chattype_1(self):
        from alicloud_shared.adapters.dingtalk import normalize_dingtalk
        data = {
            "chatId": "chat_xyz",
            "chatType": "1",
            "senderStaffId": "staff_abc",
        }
        ctx = normalize_dingtalk(data)
        assert ctx.platform == "dingtalk"
        assert ctx.chat_type == "p2p"
        assert ctx.session_id == "chat_xyz"
        assert ctx.user_id == "staff_abc"

    def test_group_when_chattype_2(self):
        from alicloud_shared.adapters.dingtalk import normalize_dingtalk
        data = {
            "chatId": "group_xyz",
            "chatType": "2",
            "senderStaffId": "staff_abc",
        }
        ctx = normalize_dingtalk(data)
        assert ctx.chat_type == "group"
        assert ctx.session_id == "group_xyz"