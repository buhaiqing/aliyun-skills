"""Tests for the HTTP POST adapter."""


class TestNormalizeHttp:
    def test_uses_user_id_header(self):
        from alicloud_shared.adapters.http_api import normalize_http
        ctx = normalize_http(
            headers={"X-Chat-User-Id": "alice"},
            body={"session_id": "sess-1"},
            caller_id="svc-x",
        )
        assert ctx.platform == "http"
        assert ctx.user_id == "alice"
        assert ctx.session_id == "sess-1"
        assert ctx.chat_type == "api"

    def test_falls_back_to_caller_id(self):
        from alicloud_shared.adapters.http_api import normalize_http
        ctx = normalize_http(
            headers={},
            body={"session_id": "s"},
            caller_id="svc-y",
        )
        assert ctx.user_id == "svc-y"

    def test_api_default_session_id_is_overridden(self):
        from alicloud_shared.adapters.http_api import normalize_http
        ctx = normalize_http(
            headers={},
            body={"session_id": "api:default"},
            caller_id="svc-z",
        )
        # Should NOT keep "api:default"
        assert ctx.session_id != "api:default"
        assert "svc-z" in ctx.session_id

    def test_authorization_redacted(self):
        from alicloud_shared.adapters.http_api import normalize_http
        ctx = normalize_http(
            headers={"Authorization": "Bearer secret", "X-Chat-User-Id": "u"},
            body={"session_id": "s"},
            caller_id="c",
        )
        assert "Authorization" not in ctx.raw["headers"]
        assert ctx.raw["headers"]["X-Chat-User-Id"] == "u"