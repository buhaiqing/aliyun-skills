"""Platform-specific chat context adapters."""
from alicloud_shared.adapters import dingtalk, feishu, http_api, wecom
from alicloud_shared.chat_context import register_adapter

register_adapter("wecom", wecom.normalize_wecom)
register_adapter("feishu", feishu.normalize_feishu)
register_adapter("dingtalk", dingtalk.normalize_dingtalk)
register_adapter("http", http_api.normalize_http)

__all__ = ["dingtalk", "feishu", "http_api", "wecom"]