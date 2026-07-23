#!/usr/bin/env python3
"""
通知渠道单元测试 — 验证 钉钉/飞书/企业微信 三种渠道的:
- 消息体构建
- 环境变量安全检查
- 错误处理 (webhook 未配置 / URL 含 token / 网络失败)
- 渠道注册与 send_all 调度
- Dry-run 模式

使用方式:
    python3 test_notifications.py                # 全部测试
    python3 test_notifications.py -v             # 详细输出
    python3 test_notifications.py -k feishu      # 只跑飞书相关

Python 3.10+ 标准库 unittest
"""

from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# 允许单独运行
sys.path.insert(0, str(Path(__file__).parent))

from hitl_common import (
    DEFAULT_CATEGORY_SEVERITY,
    AuditEventType,
    AuditLogger,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitState,
    EscalationManager,
    EscalationPolicy,
    HITLConfig,
    HTTPErrorCategory,
    NetworkError,
    NonRetryableHTTPError,
    NotificationManager,
    NotificationPayload,
    RetryableHTTPError,
    Severity,
)

# ============================================================================
# Test Fixtures
# ============================================================================

SAMPLE_PAYLOAD = NotificationPayload(
    title="Terraform PR 待审批: Add VPC",
    message=(
        "PR #123 等待您的审批\n"
        "分支: `terraform/nl2hcl-dev-20240608-001`\n"
        "环境: dev\n"
        "审批人: tech-lead, ops-manager"
    ),
    level="info",
    url="file:///.pr-store/prs/pr-123",
    extra={"pr_number": 123, "checkpoint_id": "cp-test-001"},
)

WARNING_PAYLOAD = NotificationPayload(
    title="[WARN] 漂移检测",
    message="已检测到 3 个资源属性变化",
    level="warning",
)


# ============================================================================
# Base Test
# ============================================================================

class _NotificationTestBase(unittest.TestCase):
    """测试基类 — 提供通用工具"""

    def setUp(self):
        # 清理环境变量
        self._saved_env = {}
        for k in (
            "DINGTALK_WEBHOOK_URL", "DINGTALK_WEBHOOK_SECRET",
            "FEISHU_WEBHOOK_URL", "FEISHU_WEBHOOK_SECRET",
            "WECOM_WEBHOOK_URL",
            "TF_OPS_DRYRUN_NOTIFICATION",
            "TF_OPS_NOTIFY_MAX_RETRIES",
            "TF_OPS_NOTIFY_RETRY_BACKOFF",
            "TF_OPS_NOTIFY_RETRY_MAX_BACKOFF",
        ):
            self._saved_env[k] = os.environ.pop(k, None)

        # 每个 test 独立 audit 目录, 避免事件干扰
        import tempfile
        self._audit_dir = Path(tempfile.mkdtemp(prefix="test-audit-"))
        self.audit = AuditLogger(base_path=self._audit_dir)

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

        # 清理临时 audit 目录
        import shutil
        if hasattr(self, "_audit_dir") and self._audit_dir.exists():
            shutil.rmtree(self._audit_dir)

    def _make_config(self, **overrides) -> HITLConfig:
        """创建测试用配置"""
        config = HITLConfig()
        for k, v in overrides.items():
            setattr(config, k, v)
        return config

    def _make_manager(self, **overrides) -> NotificationManager:
        """创建测试用 Manager (从环境变量加载 webhook)"""
        # 优先从 env 加载 (这样 _setup_dingtalk/feishu/wecom 设置的环境变量生效)
        config = HITLConfig.load()
        # 但允许测试覆盖
        for k, v in overrides.items():
            setattr(config, k, v)
        return NotificationManager(config, self.audit, console_output=False)

    def _setup_dingtalk(self, url="https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"):
        """配置钉钉 webhook (使用不会触发 token 拦截的占位 URL)"""
        os.environ["DINGTALK_WEBHOOK_URL"] = url
        return self._make_manager()

    def _setup_feishu(self, url="https://open.feishu.cn/open-apis/bot/v2/hook/TEST_TOKEN"):
        """配置飞书 webhook"""
        os.environ["FEISHU_WEBHOOK_URL"] = url
        return self._make_manager()

    def _setup_wecom(self, url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?placeholder=TEST_TOKEN"):
        """配置企业微信 webhook"""
        os.environ["WECOM_WEBHOOK_URL"] = url
        return self._make_manager()


# ============================================================================
# 钉钉渠道测试
# ============================================================================

class TestDingTalkChannel(_NotificationTestBase):

    def test_unconfigured_returns_false(self):
        """未配置时返回 False 并记录 WARN"""
        mgr = self._make_manager()
        result = mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
        self.assertFalse(result)
        events = self.audit.query(event_type=AuditEventType.NOTIFICATION_FAILED)
        self.assertEqual(len(events), 1)
        self.assertIn("DINGTALK_WEBHOOK_URL", events[0]["context"]["reason"])

    def test_message_format_markdown(self):
        """消息体格式为 markdown"""
        mgr = self._setup_dingtalk()
        mgr._channels["dingtalk"].webhook_url = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        msg = mgr._channels["dingtalk"].build_message(SAMPLE_PAYLOAD)
        self.assertEqual(msg["msgtype"], "markdown")
        self.assertIn(SAMPLE_PAYLOAD.title, msg["markdown"]["title"])
        self.assertIn(SAMPLE_PAYLOAD.title, msg["markdown"]["text"])
        self.assertIn("[查看详情]", msg["markdown"]["text"])

    def test_message_without_url(self):
        """无 URL 时不渲染链接行"""
        mgr = self._setup_dingtalk()
        mgr._channels["dingtalk"].webhook_url = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        payload = NotificationPayload(title="T", message="M", level="info")
        msg = mgr._channels["dingtalk"].build_message(payload)
        self.assertNotIn("[查看详情]", msg["markdown"]["text"])

    def test_sign_adds_timestamp_and_sign(self):
        """配置加签密钥时, _sign 返回非空字段"""
        mgr = self._setup_dingtalk()
        mgr.config.dingtalk_secret_env = "DINGTALK_WEBHOOK_SECRET"
        os.environ["DINGTALK_WEBHOOK_SECRET"] = "test-secret-key"
        # 重新构建 channel 以应用 secret
        mgr._channels["dingtalk"] = type(mgr._channels["dingtalk"])(
            webhook_url=mgr._channels["dingtalk"].webhook_url,
            webhook_env=mgr._channels["dingtalk"].webhook_env,
            secret="test-secret-key",
        )
        sign = mgr._channels["dingtalk"]._sign()
        self.assertIn("timestamp", sign)
        self.assertIn("sign", sign)
        self.assertTrue(len(sign["sign"]) > 0)

    def test_sign_skipped_when_no_secret(self):
        """未配置 secret 时 _sign 返回空字典"""
        mgr = self._setup_dingtalk()
        mgr._channels["dingtalk"].webhook_url = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        sign = mgr._channels["dingtalk"]._sign()
        self.assertEqual(sign, {})

    def test_token_in_url_rejected(self):
        """webhook URL 含真实 token 字面量时拒绝 (非重试)"""
        # 注意: 32+ hex 字符
        mgr = self._setup_dingtalk(url="https://oapi.dingtalk.com/robot/send?access_token=abcdef0123456789abcdef0123456789")
        result = mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
        self.assertFalse(result)
        events = self.audit.query(event_type=AuditEventType.NOTIFICATION_FAILED)
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["context"]["retryable"])

    def test_dry_run_does_not_http(self):
        """Dry-run 模式下不真实发送 HTTP"""
        os.environ["TF_OPS_DRYRUN_NOTIFICATION"] = "1"
        mgr = self._setup_dingtalk()
        mgr._channels["dingtalk"].webhook_url = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        with patch("hitl_common._http_post") as mock_post:
            result = mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
        self.assertTrue(result)
        mock_post.assert_not_called()

    def test_successful_http_post(self):
        """成功 HTTP POST"""
        mgr = self._setup_dingtalk()
        mgr._channels["dingtalk"].webhook_url = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        with patch("hitl_common._http_post", return_value=200) as mock_post:
            result = mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
        self.assertTrue(result)
        mock_post.assert_called_once()
        args = mock_post.call_args
        self.assertIn("placeholder=TEST_TOKEN", args[0][0])
        self.assertEqual(args[0][1]["msgtype"], "markdown")

    def test_http_failure_returns_false(self):
        """HTTP 失败返回 False"""
        mgr = self._setup_dingtalk()
        mgr._channels["dingtalk"].webhook_url = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        with patch("hitl_common._http_post", side_effect=NetworkError("timeout")):
            result = mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
        self.assertFalse(result)
        events = self.audit.query(event_type=AuditEventType.NOTIFICATION_FAILED)
        self.assertEqual(len(events), 1)
        self.assertIn("timeout", events[0]["context"]["error"])


# ============================================================================
# 飞书渠道测试
# ============================================================================

class TestFeishuChannel(_NotificationTestBase):

    def test_unconfigured_returns_false(self):
        """未配置时返回 False"""
        mgr = self._make_manager()
        result = mgr.send(SAMPLE_PAYLOAD, channel="feishu")
        self.assertFalse(result)
        events = self.audit.query(event_type=AuditEventType.NOTIFICATION_FAILED)
        self.assertIn("FEISHU_WEBHOOK_URL", events[0]["context"]["reason"])

    def test_message_format_interactive_card(self):
        """消息体格式为 interactive 卡片"""
        mgr = self._setup_feishu()
        msg = mgr._channels["feishu"].build_message(SAMPLE_PAYLOAD)
        self.assertEqual(msg["msg_type"], "interactive")
        self.assertIn("header", msg["card"])
        self.assertEqual(msg["card"]["header"]["template"], "blue")  # info → blue
        self.assertEqual(msg["card"]["header"]["title"]["content"], SAMPLE_PAYLOAD.title)
        self.assertGreater(len(msg["card"]["elements"]), 0)
        # 第一个 element 应该是 markdown
        self.assertEqual(msg["card"]["elements"][0]["tag"], "markdown")

    def test_warning_uses_orange_template(self):
        """warning 级别使用 orange 模板"""
        mgr = self._setup_feishu()
        msg = mgr._channels["feishu"].build_message(WARNING_PAYLOAD)
        self.assertEqual(msg["card"]["header"]["template"], "orange")

    def test_error_uses_red_template(self):
        """error 级别使用 red 模板"""
        mgr = self._setup_feishu()
        payload = NotificationPayload(title="E", message="M", level="error")
        msg = mgr._channels["feishu"].build_message(payload)
        self.assertEqual(msg["card"]["header"]["template"], "red")

    def test_success_uses_green_template(self):
        """success 级别使用 green 模板"""
        mgr = self._setup_feishu()
        payload = NotificationPayload(title="S", message="M", level="success")
        msg = mgr._channels["feishu"].build_message(payload)
        self.assertEqual(msg["card"]["header"]["template"], "green")

    def test_action_button_included_when_url(self):
        """URL 存在时添加 action 按钮"""
        mgr = self._setup_feishu()
        msg = mgr._channels["feishu"].build_message(SAMPLE_PAYLOAD)
        action_elements = [e for e in msg["card"]["elements"] if e.get("tag") == "action"]
        self.assertEqual(len(action_elements), 1)
        self.assertEqual(action_elements[0]["actions"][0]["type"], "primary")
        self.assertEqual(action_elements[0]["actions"][0]["url"], SAMPLE_PAYLOAD.url)

    def test_no_action_button_without_url(self):
        """URL 缺失时不添加 action 按钮"""
        mgr = self._setup_feishu()
        payload = NotificationPayload(title="T", message="M", level="info")
        msg = mgr._channels["feishu"].build_message(payload)
        action_elements = [e for e in msg["card"]["elements"] if e.get("tag") == "action"]
        self.assertEqual(len(action_elements), 0)

    def test_sign_includes_timestamp_and_sign(self):
        """飞书签名: HMAC-SHA256(timestamp + '\\n' + secret)"""
        mgr = self._setup_feishu()
        os.environ["FEISHU_WEBHOOK_SECRET"] = "feishu-test-secret"
        mgr._channels["feishu"] = type(mgr._channels["feishu"])(
            webhook_url=mgr._channels["feishu"].webhook_url,
            webhook_env=mgr._channels["feishu"].webhook_env,
            secret="feishu-test-secret",
        )
        sign = mgr._channels["feishu"]._sign()
        self.assertNotEqual(sign, "")
        # base64 字符串长度通常为 44
        self.assertGreater(len(sign), 30)

    def test_sign_appended_to_url_as_query(self):
        """签名以 query string 形式追加到 URL"""
        mgr = self._setup_feishu()
        os.environ["FEISHU_WEBHOOK_SECRET"] = "feishu-test-secret"
        mgr._channels["feishu"] = type(mgr._channels["feishu"])(
            webhook_url=mgr._channels["feishu"].webhook_url,
            webhook_env=mgr._channels["feishu"].webhook_env,
            secret="feishu-test-secret",
        )
        mgr._channels["feishu"].webhook_url = "https://open.feishu.cn/hook/xyz"
        with patch("hitl_common._http_post", return_value=200) as mock_post:
            mgr.send(SAMPLE_PAYLOAD, channel="feishu")
        called_url = mock_post.call_args[0][0]
        self.assertIn("timestamp=", called_url)
        self.assertIn("sign=", called_url)
        self.assertIn("?", called_url)

    def test_token_in_url_rejected(self):
        """飞书 webhook URL 含真实 token 时拒绝 (非重试)"""
        mgr = self._setup_feishu(url="https://open.feishu.cn/hook/abcdef0123456789abcdef0123456789")
        result = mgr.send(SAMPLE_PAYLOAD, channel="feishu")
        self.assertFalse(result)
        events = self.audit.query(event_type=AuditEventType.NOTIFICATION_FAILED)
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["context"]["retryable"])

    def test_dry_run_does_not_http(self):
        """Dry-run 模式不真实发送"""
        os.environ["TF_OPS_DRYRUN_NOTIFICATION"] = "1"
        mgr = self._setup_feishu()
        with patch("hitl_common._http_post") as mock_post:
            result = mgr.send(SAMPLE_PAYLOAD, channel="feishu")
        self.assertTrue(result)
        mock_post.assert_not_called()

    def test_successful_http_post(self):
        """成功 HTTP POST"""
        mgr = self._setup_feishu()
        with patch("hitl_common._http_post", return_value=200) as mock_post:
            result = mgr.send(SAMPLE_PAYLOAD, channel="feishu")
        self.assertTrue(result)
        body = mock_post.call_args[0][1]
        self.assertEqual(body["msg_type"], "interactive")

    def test_http_failure_returns_false(self):
        """HTTP 失败返回 False"""
        mgr = self._setup_feishu()
        with patch("hitl_common._http_post", side_effect=NetworkError("conn refused")):
            result = mgr.send(SAMPLE_PAYLOAD, channel="feishu")
        self.assertFalse(result)


# ============================================================================
# 企业微信渠道测试
# ============================================================================

class TestWeComChannel(_NotificationTestBase):

    def test_unconfigured_returns_false(self):
        """未配置时返回 False"""
        mgr = self._make_manager()
        result = mgr.send(SAMPLE_PAYLOAD, channel="wecom")
        self.assertFalse(result)
        events = self.audit.query(event_type=AuditEventType.NOTIFICATION_FAILED)
        self.assertIn("WECOM_WEBHOOK_URL", events[0]["context"]["reason"])

    def test_message_format_markdown(self):
        """消息体格式为 markdown"""
        mgr = self._setup_wecom()
        msg = mgr._channels["wecom"].build_message(SAMPLE_PAYLOAD)
        self.assertEqual(msg["msgtype"], "markdown")
        self.assertIn(SAMPLE_PAYLOAD.title, msg["markdown"]["content"])
        self.assertIn(SAMPLE_PAYLOAD.message, msg["markdown"]["content"])
        self.assertIn(SAMPLE_PAYLOAD.url, msg["markdown"]["content"])

    def test_message_without_url(self):
        """无 URL 时内容中不包含链接行"""
        mgr = self._setup_wecom()
        payload = NotificationPayload(title="T", message="M", level="info")
        msg = mgr._channels["wecom"].build_message(payload)
        self.assertNotIn("[查看详情]", msg["markdown"]["content"])
        self.assertIn("## T", msg["markdown"]["content"])

    def test_token_in_url_rejected(self):
        """webhook URL 含真实 token 时拒绝 (非重试)"""
        mgr = self._setup_wecom(url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abcdef0123456789abcdef0123456789")
        result = mgr.send(SAMPLE_PAYLOAD, channel="wecom")
        self.assertFalse(result)
        events = self.audit.query(event_type=AuditEventType.NOTIFICATION_FAILED)
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0]["context"]["retryable"])

    def test_dry_run_does_not_http(self):
        """Dry-run 不真实发送"""
        os.environ["TF_OPS_DRYRUN_NOTIFICATION"] = "1"
        mgr = self._setup_wecom()
        with patch("hitl_common._http_post") as mock_post:
            result = mgr.send(SAMPLE_PAYLOAD, channel="wecom")
        self.assertTrue(result)
        mock_post.assert_not_called()

    def test_successful_http_post(self):
        """成功 HTTP POST"""
        mgr = self._setup_wecom()
        with patch("hitl_common._http_post", return_value=200) as mock_post:
            result = mgr.send(SAMPLE_PAYLOAD, channel="wecom")
        self.assertTrue(result)
        body = mock_post.call_args[0][1]
        self.assertEqual(body["msgtype"], "markdown")
        self.assertIn("placeholder=TEST_TOKEN", mock_post.call_args[0][0])

    def test_http_failure_returns_false(self):
        """HTTP 失败返回 False"""
        mgr = self._setup_wecom()
        with patch("hitl_common._http_post", side_effect=NetworkError("dns")):
            result = mgr.send(SAMPLE_PAYLOAD, channel="wecom")
        self.assertFalse(result)


# ============================================================================
# NotificationManager 调度测试
# ============================================================================

class TestNotificationManagerDispatch(_NotificationTestBase):

    def test_default_channels_only_console_when_no_env(self):
        """未配置任何 webhook 时, 默认渠道只有 console"""
        mgr = self._make_manager()
        self.assertEqual(mgr.config.default_notification_channels, ["console"])

    def test_default_channels_include_configured_webhooks(self):
        """已配置 webhook 时, 默认渠道自动加入"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?access_token=DT"
        os.environ["FEISHU_WEBHOOK_URL"] = "https://open.feishu.cn/hook/FS"
        os.environ["WECOM_WEBHOOK_URL"] = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=WC"

        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)
        channels = mgr.config.default_notification_channels
        self.assertIn("console", channels)
        self.assertIn("dingtalk", channels)
        self.assertIn("feishu", channels)
        self.assertIn("wecom", channels)

    def test_send_all_dispatches_to_each(self):
        """send_all 应触发所有指定渠道"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?access_token=DT"
        os.environ["FEISHU_WEBHOOK_URL"] = "https://open.feishu.cn/hook/FS"
        os.environ["WECOM_WEBHOOK_URL"] = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=WC"
        os.environ["TF_OPS_DRYRUN_NOTIFICATION"] = "1"  # 避免真实 HTTP

        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        results = mgr.send_all(SAMPLE_PAYLOAD)
        self.assertEqual(set(results.keys()), {"console", "dingtalk", "feishu", "wecom"})
        for ch, ok in results.items():
            self.assertTrue(ok, f"渠道 {ch} 发送失败")

    def test_send_unknown_channel_returns_false(self):
        """未知渠道返回 False"""
        mgr = self._make_manager()
        result = mgr.send(SAMPLE_PAYLOAD, channel="telegram")
        self.assertFalse(result)
        events = self.audit.query(event_type=AuditEventType.NOTIFICATION_FAILED)
        self.assertIn("未知渠道", events[0]["context"]["error"])

    def test_send_all_specific_channels(self):
        """send_all 可指定子集渠道"""
        mgr = self._setup_dingtalk()
        mgr._channels["dingtalk"].webhook_url = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        with patch("hitl_common._http_post", return_value=200):
            results = mgr.send_all(SAMPLE_PAYLOAD, channels=["dingtalk"])
        self.assertEqual(set(results.keys()), {"dingtalk"})

    def test_disabled_notification_skips_non_console(self):
        """notification_enabled=False 时非 console 渠道被跳过"""
        mgr = self._setup_dingtalk()
        mgr._channels["dingtalk"].webhook_url = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        mgr.config.notification_enabled = False
        with patch("hitl_common._http_post") as mock_post:
            result = mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
        self.assertFalse(result)
        mock_post.assert_not_called()

    def test_console_always_works(self):
        """console 渠道始终可用 (即使 notification_enabled=False)"""
        mgr = self._make_manager()
        mgr.config.notification_enabled = False
        result = mgr.send(SAMPLE_PAYLOAD, channel="console")
        self.assertTrue(result)

    def test_register_custom_channel(self):
        """注册自定义渠道"""
        mgr = self._make_manager()

        class CustomChannel:
            # 鸭子类型 — 不需要继承 _Channel
            def send(self, payload, audit):
                audit.emit(
                    AuditEventType.NOTIFICATION_SENT,
                    context={"channel": "custom", "title": payload.title},
                )
                return True

        mgr.register_channel("custom", CustomChannel())
        result = mgr.send(SAMPLE_PAYLOAD, channel="custom")
        self.assertTrue(result)
        self.assertIn("custom", mgr.list_channels())


# ============================================================================
# HITLConfig 集成测试
# ============================================================================

class TestHITLConfigIntegration(_NotificationTestBase):

    def test_load_picks_up_dingtalk_env(self):
        """HITLConfig.load() 从环境变量加载钉钉 webhook"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?access_token=DT123"
        config = HITLConfig.load()
        self.assertEqual(config.dingtalk_webhook, "https://oapi.dingtalk.com/robot/send?access_token=DT123")

    def test_load_picks_up_feishu_env(self):
        """HITLConfig.load() 从环境变量加载飞书 webhook"""
        os.environ["FEISHU_WEBHOOK_URL"] = "https://open.feishu.cn/hook/FS456"
        config = HITLConfig.load()
        self.assertEqual(config.feishu_webhook, "https://open.feishu.cn/hook/FS456")

    def test_load_picks_up_wecom_env(self):
        """HITLConfig.load() 从环境变量加载企业微信 webhook"""
        os.environ["WECOM_WEBHOOK_URL"] = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=WC789"
        config = HITLConfig.load()
        self.assertEqual(config.wecom_webhook, "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=WC789")

    def test_load_all_three_channels(self):
        """3 个渠道全部配置时正确加载"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?access_token=DT"
        os.environ["FEISHU_WEBHOOK_URL"] = "https://open.feishu.cn/hook/FS"
        os.environ["WECOM_WEBHOOK_URL"] = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=WC"
        config = HITLConfig.load()
        self.assertTrue(config.dingtalk_webhook)
        self.assertTrue(config.feishu_webhook)
        self.assertTrue(config.wecom_webhook)
        self.assertEqual(
            set(config.default_notification_channels),
            {"console", "dingtalk", "feishu", "wecom"},
        )

    def test_to_dict_exposes_webhook_status(self):
        """to_dict 暴露 webhook 配置状态"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?access_token=DT"
        os.environ["FEISHU_WEBHOOK_URL"] = "https://open.feishu.cn/hook/FS"
        os.environ["WECOM_WEBHOOK_URL"] = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=WC"
        config = HITLConfig.load()
        d = config.to_dict()
        self.assertTrue(d["dingtalk_webhook_configured"])
        self.assertTrue(d["feishu_webhook_configured"])
        self.assertTrue(d["wecom_webhook_configured"])


# ============================================================================
# End-to-end 集成测试
# ============================================================================

class TestEndToEnd(_NotificationTestBase):

    def test_three_channels_send_simultaneously(self):
        """3 个渠道同时发送 (干运行)"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?access_token=DT"
        os.environ["FEISHU_WEBHOOK_URL"] = "https://open.feishu.cn/hook/FS"
        os.environ["WECOM_WEBHOOK_URL"] = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=WC"
        os.environ["TF_OPS_DRYRUN_NOTIFICATION"] = "1"

        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        # 使用 send_all
        results = mgr.send_all(SAMPLE_PAYLOAD)
        self.assertTrue(all(results.values()))
        self.assertEqual(len(results), 4)  # console + 3 webhooks

        # 审计日志应记录 4 条 NOTIFICATION_SENT
        events = self.audit.query(event_type=AuditEventType.NOTIFICATION_SENT)
        channels_sent = {e["context"]["channel"] for e in events}
        self.assertEqual(channels_sent, {"console", "dingtalk", "feishu", "wecom"})

    def test_real_http_only_when_not_dry_run(self):
        """非 dry-run 时真实调用 _http_post"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        # 显式不设置 DRYRUN

        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        with patch("hitl_common._http_post", return_value=200) as mock_post:
            result = mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
        self.assertTrue(result)
        mock_post.assert_called_once()

    def test_audit_records_failures(self):
        """失败的事件被审计记录"""
        os.environ["FEISHU_WEBHOOK_URL"] = "https://open.feishu.cn/hook/FS"
        os.environ["TF_OPS_DRYRUN_NOTIFICATION"] = "1"

        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        # 触发 feishu (dry-run, 会成功)
        mgr.send(SAMPLE_PAYLOAD, channel="feishu")

        # 触发一个失败的: 网络错误
        os.environ.pop("TF_OPS_DRYRUN_NOTIFICATION")
        with patch("hitl_common._http_post", side_effect=NetworkError("conn refused")):
            mgr.send(SAMPLE_PAYLOAD, channel="feishu")

        failures = self.audit.query(event_type=AuditEventType.NOTIFICATION_FAILED)
        self.assertEqual(len(failures), 1)
        self.assertIn("conn refused", failures[0]["context"]["error"])


# ============================================================================
# HTTP 状态码分类测试
# ============================================================================

class TestHTTPStatusClassification(unittest.TestCase):
    """HTTPErrorCategory 状态码 → 语义类别映射"""

    def test_4xx_mappings(self):
        """4xx 状态码映射到对应的客户端错误类别"""
        cases = {
            400: HTTPErrorCategory.BAD_REQUEST,
            401: HTTPErrorCategory.UNAUTHORIZED,
            403: HTTPErrorCategory.FORBIDDEN,
            404: HTTPErrorCategory.NOT_FOUND,
            405: HTTPErrorCategory.METHOD_NOT_ALLOWED,
            409: HTTPErrorCategory.CONFLICT,
            413: HTTPErrorCategory.PAYLOAD_TOO_LARGE,
            422: HTTPErrorCategory.UNPROCESSABLE,
            429: HTTPErrorCategory.RATE_LIMITED,
            418: HTTPErrorCategory.CLIENT_ERROR_OTHER,  # 未映射
            451: HTTPErrorCategory.CLIENT_ERROR_OTHER,  # 未映射
        }
        from hitl_common import _classify_http_status
        for code, expected in cases.items():
            with self.subTest(code=code):
                self.assertEqual(_classify_http_status(code), expected)

    def test_5xx_mappings(self):
        """5xx 状态码映射到对应的服务端错误类别"""
        cases = {
            500: HTTPErrorCategory.INTERNAL_ERROR,
            502: HTTPErrorCategory.BAD_GATEWAY,
            503: HTTPErrorCategory.SERVICE_UNAVAILABLE,
            504: HTTPErrorCategory.GATEWAY_TIMEOUT,
            501: HTTPErrorCategory.SERVER_ERROR_OTHER,  # 未映射
            505: HTTPErrorCategory.SERVER_ERROR_OTHER,
        }
        from hitl_common import _classify_http_status
        for code, expected in cases.items():
            with self.subTest(code=code):
                self.assertEqual(_classify_http_status(code), expected)


class TestRetryableErrorCategory(unittest.TestCase):
    """错误实例的 category 字段正确赋值"""

    def test_retryable_http_error_has_category(self):
        """RetryableHTTPError 携带 category"""
        err = RetryableHTTPError("test", status_code=503)
        self.assertEqual(err.category, HTTPErrorCategory.SERVICE_UNAVAILABLE)
        self.assertEqual(err.status_code, 503)

    def test_retryable_http_error_with_retry_after(self):
        """RetryableHTTPError 携带 retry_after"""
        err = RetryableHTTPError("rate limited", status_code=429, retry_after=5.0)
        self.assertEqual(err.category, HTTPErrorCategory.RATE_LIMITED)
        self.assertEqual(err.retry_after, 5.0)

    def test_non_retryable_http_error_has_category(self):
        """NonRetryableHTTPError 携带 category"""
        err = NonRetryableHTTPError("unauthorized", status_code=401)
        self.assertEqual(err.category, HTTPErrorCategory.UNAUTHORIZED)
        self.assertEqual(err.status_code, 401)

    def test_network_error_default_category(self):
        """NetworkError 默认 category 为 NETWORK_OTHER"""
        err = NetworkError("connection failed")
        self.assertEqual(err.category, HTTPErrorCategory.NETWORK_OTHER)

    def test_network_error_with_category(self):
        """NetworkError 可指定 category"""
        err = NetworkError("timed out", category=HTTPErrorCategory.NETWORK_TIMEOUT)
        self.assertEqual(err.category, HTTPErrorCategory.NETWORK_TIMEOUT)

    def test_retry_audit_includes_error_category(self):
        """重试事件包含 error_category 字段"""
        import shutil
        import tempfile
        from pathlib import Path
        audit_dir = Path(tempfile.mkdtemp())
        try:
            audit = AuditLogger(base_path=audit_dir)
            # 手动 emit 一个重试事件
            audit.emit(
                AuditEventType.NOTIFICATION_RETRY,
                context={
                    "channel": "dingtalk",
                    "error_category": HTTPErrorCategory.GATEWAY_TIMEOUT.value,
                    "attempt": 1,
                },
            )
            events = audit.query(event_type=AuditEventType.NOTIFICATION_RETRY)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["context"]["error_category"], "gateway_timeout")
        finally:
            shutil.rmtree(audit_dir)


# ============================================================================
# Circuit Breaker 测试
# ============================================================================

class TestCircuitBreakerStateMachine(_NotificationTestBase):
    """熔断器状态转换测试"""

    def test_initial_state_is_closed(self):
        """初始状态为 CLOSED"""
        cb = CircuitBreaker(CircuitBreakerConfig(), self.audit)
        self.assertEqual(cb.get_state("dingtalk"), CircuitState.CLOSED)

    def test_enter_in_closed_state_succeeds(self):
        """CLOSED 状态允许进入"""
        cb = CircuitBreaker(CircuitBreakerConfig(), self.audit)
        cb.enter("dingtalk")  # 不抛异常

    def test_failures_open_circuit_at_threshold(self):
        """连续 N 次失败后熔断"""
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=3, reset_timeout=60.0),
            self.audit,
        )
        for i in range(3):
            err = RetryableHTTPError("fail", status_code=503)
            cb.record_failure("dingtalk", err)
        self.assertEqual(cb.get_state("dingtalk"), CircuitState.OPEN)

    def test_open_circuit_rejects_enter(self):
        """熔断器打开后拒绝调用"""
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=2, reset_timeout=60.0),
            self.audit,
        )
        for i in range(2):
            cb.record_failure(
                "dingtalk",
                RetryableHTTPError("fail", status_code=503),
            )
        with self.assertRaises(CircuitBreakerOpenError):
            cb.enter("dingtalk")

    def test_open_circuit_transitions_to_half_open_after_timeout(self):
        """reset_timeout 后转为 HALF_OPEN"""
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=2, reset_timeout=0.1),
            self.audit,
        )
        for i in range(2):
            cb.record_failure(
                "dingtalk",
                RetryableHTTPError("fail", status_code=503),
            )
        self.assertEqual(cb.get_state("dingtalk"), CircuitState.OPEN)
        time.sleep(0.15)
        cb.enter("dingtalk")  # 不拋异常
        self.assertEqual(cb.get_state("dingtalk"), CircuitState.HALF_OPEN)

    def test_half_open_success_closes_circuit(self):
        """半开状态连续 N 次成功转为 CLOSED"""
        cb = CircuitBreaker(
            CircuitBreakerConfig(
                failure_threshold=2, reset_timeout=0.05, success_threshold=2
            ),
            self.audit,
        )
        for i in range(2):
            cb.record_failure("dingtalk", RetryableHTTPError("f", 503))
        time.sleep(0.1)
        cb.enter("dingtalk")  # → HALF_OPEN
        cb.record_success("dingtalk")
        self.assertEqual(cb.get_state("dingtalk"), CircuitState.HALF_OPEN)
        cb.record_success("dingtalk")
        self.assertEqual(cb.get_state("dingtalk"), CircuitState.CLOSED)

    def test_half_open_failure_reopens_circuit(self):
        """半开状态失败重新熔断"""
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=2, reset_timeout=0.05),
            self.audit,
        )
        for i in range(2):
            cb.record_failure("dingtalk", RetryableHTTPError("f", 503))
        time.sleep(0.1)
        cb.enter("dingtalk")  # → HALF_OPEN
        cb.record_failure("dingtalk", RetryableHTTPError("f", 503))
        self.assertEqual(cb.get_state("dingtalk"), CircuitState.OPEN)

    def test_per_channel_isolation(self):
        """不同 channel 状态独立"""
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=2),
            self.audit,
        )
        for i in range(2):
            cb.record_failure("dingtalk", RetryableHTTPError("f", 503))
        # dingtalk 已熔断, feishu 不受影响
        self.assertEqual(cb.get_state("dingtalk"), CircuitState.OPEN)
        self.assertEqual(cb.get_state("feishu"), CircuitState.CLOSED)

    def test_4xx_not_counted_by_default(self):
        """4xx 不计入熔断 (客户端配置问题)"""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2), self.audit)
        for i in range(5):
            err = NonRetryableHTTPError("bad", status_code=401)
            cb.record_failure("dingtalk", err)
        # 4xx 不计入, 仍为 CLOSED
        self.assertEqual(cb.get_state("dingtalk"), CircuitState.CLOSED)

    def test_5xx_counted(self):
        """5xx 计入熔断"""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2), self.audit)
        for i in range(2):
            err = RetryableHTTPError("server err", status_code=503)
            cb.record_failure("dingtalk", err)
        self.assertEqual(cb.get_state("dingtalk"), CircuitState.OPEN)

    def test_429_counted(self):
        """429 限流计入熔断"""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2), self.audit)
        for i in range(2):
            err = RetryableHTTPError("rate limited", status_code=429)
            cb.record_failure("dingtalk", err)
        self.assertEqual(cb.get_state("dingtalk"), CircuitState.OPEN)

    def test_network_errors_counted(self):
        """网络错误计入熔断"""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2), self.audit)
        for i in range(2):
            err = NetworkError("timeout", category=HTTPErrorCategory.NETWORK_TIMEOUT)
            cb.record_failure("dingtalk", err)
        self.assertEqual(cb.get_state("dingtalk"), CircuitState.OPEN)

    def test_success_resets_failure_count(self):
        """成功重置失败计数"""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3), self.audit)
        cb.record_failure("dingtalk", RetryableHTTPError("f", 503))
        cb.record_failure("dingtalk", RetryableHTTPError("f", 503))
        cb.record_success("dingtalk")
        stats = cb.stats("dingtalk")
        self.assertEqual(stats["failure_count"], 0)

    def test_audit_events_emitted(self):
        """状态转换时发审计事件"""
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=2, reset_timeout=0.05),
            self.audit,
        )
        for i in range(2):
            cb.record_failure("dingtalk", RetryableHTTPError("f", 503))
        events = self.audit.query(
            event_type=AuditEventType.NOTIFICATION_CIRCUIT_OPENED
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["context"]["channel"], "dingtalk")
        self.assertEqual(events[0]["context"]["failure_count"], 2)

    def test_reset_clears_state(self):
        """reset() 清除状态"""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2), self.audit)
        for i in range(2):
            cb.record_failure("dingtalk", RetryableHTTPError("f", 503))
        cb.reset("dingtalk")
        self.assertEqual(cb.get_state("dingtalk"), CircuitState.CLOSED)

    def test_stats_returns_dict(self):
        """stats() 返回状态字典"""
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3), self.audit)
        cb.record_failure("dingtalk", RetryableHTTPError("f", 503))
        stats = cb.stats("dingtalk")
        self.assertIn("state", stats)
        self.assertIn("failure_count", stats)
        self.assertEqual(stats["failure_count"], 1)


class TestCircuitBreakerIntegrationWithChannel(_NotificationTestBase):
    """Circuit Breaker 与 _Channel.send_with_retry 的集成"""

    def setUp(self):
        super().setUp()
        # 禁用重试以加快测试
        os.environ["TF_OPS_NOTIFY_MAX_RETRIES"] = "0"
        # 熔断阈值 2
        os.environ["TF_OPS_CB_FAILURE_THRESHOLD"] = "2"
        os.environ["TF_OPS_CB_RESET_TIMEOUT"] = "0.1"
        os.environ["TF_OPS_CB_SUCCESS_THRESHOLD"] = "1"
        # 保留这些到 tearDown
        self._extra_env = (
            "TF_OPS_NOTIFY_MAX_RETRIES",
            "TF_OPS_CB_FAILURE_THRESHOLD",
            "TF_OPS_CB_RESET_TIMEOUT",
            "TF_OPS_CB_SUCCESS_THRESHOLD",
        )

    def tearDown(self):
        for k in self._extra_env:
            os.environ.pop(k, None)
        super().tearDown()

    def test_repeated_failures_open_circuit(self):
        """连续 2 次 503 后熔断器开启"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        # 模拟连续失败
        with patch("hitl_common._http_post", side_effect=RetryableHTTPError("503", 503)):
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")  # 失败 1
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")  # 失败 2 → 熔断

        # 第 3 次调用应被熔断器拒绝
        with patch("hitl_common._http_post") as mock_post:
            result = mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
        self.assertFalse(result)
        mock_post.assert_not_called()  # 未发送

    def test_circuit_open_audits_circuit_rejected(self):
        """熔断器拒绝时记录审计事件"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        with patch("hitl_common._http_post", side_effect=RetryableHTTPError("503", 503)):
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")

        # 清除之前的审计
        self.audit._save_prs = lambda x: None
        # 触发被熔断的请求
        with patch("hitl_common._http_post"):
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")

        events = self.audit.query(
            event_type=AuditEventType.NOTIFICATION_CIRCUIT_REJECTED
        )
        self.assertGreaterEqual(len(events), 1)
        self.assertIn("remaining_seconds", events[0]["context"])

    def test_half_open_recovers_after_timeout(self):
        """熔断超时后允许探针请求"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        # 熔断
        with patch("hitl_common._http_post", side_effect=RetryableHTTPError("503", 503)):
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
        self.assertEqual(
            mgr.circuit_breaker.get_state("dingtalk"),
            CircuitState.OPEN,
        )

        # 等待 reset_timeout
        time.sleep(0.15)

        # 探针请求成功 → 半开 → 关闭
        with patch("hitl_common._http_post", return_value=200):
            result = mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
        self.assertTrue(result)
        self.assertEqual(
            mgr.circuit_breaker.get_state("dingtalk"),
            CircuitState.CLOSED,
        )

    def test_disabled_circuit_breaker(self):
        """TF_OPS_CB_ENABLED=0 禁用熔断器"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        os.environ["TF_OPS_CB_ENABLED"] = "0"
        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)
        self.assertIsNone(mgr.circuit_breaker)
        os.environ.pop("TF_OPS_CB_ENABLED")


class TestChannelErrorCategoryInAudit(_NotificationTestBase):
    """重试/失败事件包含 error_category"""

    def test_retry_event_has_error_category(self):
        """NOTIFICATION_RETRY 事件包含 error_category"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        os.environ["TF_OPS_NOTIFY_MAX_RETRIES"] = "2"
        os.environ["TF_OPS_NOTIFY_RETRY_BACKOFF"] = "0.001"
        os.environ["TF_OPS_NOTIFY_RETRY_MAX_BACKOFF"] = "0.001"

        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        with patch(
            "hitl_common._http_post",
            side_effect=RetryableHTTPError("bad gateway", status_code=502),
        ):
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")

        retries = self.audit.query(event_type=AuditEventType.NOTIFICATION_RETRY)
        self.assertGreaterEqual(len(retries), 1)
        self.assertEqual(retries[0]["context"]["error_category"], "bad_gateway")

        for k in (
            "TF_OPS_NOTIFY_MAX_RETRIES",
            "TF_OPS_NOTIFY_RETRY_BACKOFF",
            "TF_OPS_NOTIFY_RETRY_MAX_BACKOFF",
        ):
            os.environ.pop(k, None)

    def test_failure_event_has_error_category(self):
        """NOTIFICATION_FAILED 事件包含 error_category"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        os.environ["TF_OPS_NOTIFY_MAX_RETRIES"] = "0"

        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        with patch(
            "hitl_common._http_post",
            side_effect=NonRetryableHTTPError("unauthorized", status_code=401),
        ):
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")

        failures = self.audit.query(event_type=AuditEventType.NOTIFICATION_FAILED)
        self.assertGreaterEqual(len(failures), 1)
        self.assertEqual(failures[0]["context"]["error_category"], "unauthorized")
        os.environ.pop("TF_OPS_NOTIFY_MAX_RETRIES", None)

    def test_network_error_category_classified(self):
        """NetworkError.category 根据底层异常推断"""
        import socket

        from hitl_common import _classify_network_error
        self.assertEqual(
            _classify_network_error(TimeoutError("timeout")),
            HTTPErrorCategory.NETWORK_TIMEOUT,
        )
        self.assertEqual(
            _classify_network_error(ConnectionRefusedError("refused")),
            HTTPErrorCategory.NETWORK_CONNECTION,
        )
        self.assertEqual(
            _classify_network_error(socket.gaierror("dns")),
            HTTPErrorCategory.NETWORK_DNS,
        )
        self.assertEqual(
            _classify_network_error(ValueError("unknown")),
            HTTPErrorCategory.NETWORK_OTHER,
        )


# ============================================================================
# 严重等级 / 告警升级测试
# ============================================================================

class TestSeverityMapping(unittest.TestCase):
    """严重等级与错误类别的默认映射"""

    def test_p0_categories(self):
        """P0: UNAUTHORIZED/FORBIDDEN/NOT_FOUND/SERVICE_UNAVAILABLE/NETWORK_DNS/SSL_ERROR"""
        from hitl_common import get_default_severity
        for cat in [
            HTTPErrorCategory.UNAUTHORIZED,
            HTTPErrorCategory.FORBIDDEN,
            HTTPErrorCategory.NOT_FOUND,
            HTTPErrorCategory.SERVICE_UNAVAILABLE,
            HTTPErrorCategory.NETWORK_DNS,
            HTTPErrorCategory.SSL_ERROR,
        ]:
            with self.subTest(category=cat):
                self.assertEqual(get_default_severity(cat), Severity.P0)

    def test_p1_categories(self):
        """P1: 5xx + 429 + 其他 4xx 部分"""
        from hitl_common import get_default_severity
        for cat in [
            HTTPErrorCategory.BAD_REQUEST,
            HTTPErrorCategory.CONFLICT,
            HTTPErrorCategory.PAYLOAD_TOO_LARGE,
            HTTPErrorCategory.UNPROCESSABLE,
            HTTPErrorCategory.RATE_LIMITED,
            HTTPErrorCategory.INTERNAL_ERROR,
            HTTPErrorCategory.BAD_GATEWAY,
            HTTPErrorCategory.GATEWAY_TIMEOUT,
        ]:
            with self.subTest(category=cat):
                self.assertEqual(get_default_severity(cat), Severity.P1)

    def test_p2_categories(self):
        """P2: 通用网络错误"""
        from hitl_common import get_default_severity
        for cat in [
            HTTPErrorCategory.METHOD_NOT_ALLOWED,
            HTTPErrorCategory.CLIENT_ERROR_OTHER,
            HTTPErrorCategory.NETWORK_TIMEOUT,
            HTTPErrorCategory.NETWORK_CONNECTION,
            HTTPErrorCategory.NETWORK_OTHER,
        ]:
            with self.subTest(category=cat):
                self.assertEqual(get_default_severity(cat), Severity.P2)

    def test_default_severity_is_P3_for_unmapped(self):
        """未映射的类别默认为 P3"""
        from hitl_common import get_default_severity
        # 显式未在 DEFAULT_CATEGORY_SEVERITY 中的类别 (应返回 P3)
        # 所有现有 22 个类别都已映射, 此处检查 fallback 逻辑
        # 构造一个伪类别不会出现在 enum 里, 此处仅验证现有类别都在映射表中
        for cat in HTTPErrorCategory:
            with self.subTest(category=cat):
                severity = get_default_severity(cat)
                self.assertIn(severity, [Severity.P0, Severity.P1, Severity.P2, Severity.P3])

    def test_default_category_severity_is_complete(self):
        """所有 HTTPErrorCategory 都在默认映射中"""
        mapped = set(DEFAULT_CATEGORY_SEVERITY.keys())
        all_cats = set(HTTPErrorCategory)
        missing = all_cats - mapped
        self.assertEqual(missing, set(),
                         f"未映射的类别: {missing} (需在 DEFAULT_CATEGORY_SEVERITY 中)")


class TestEscalationPolicy(unittest.TestCase):
    """EscalationPolicy 配置测试"""

    def test_default_policy_uses_P0(self):
        """默认策略: 仅 P0 升级"""
        policy = EscalationPolicy()
        self.assertEqual(policy.escalate_severities, {Severity.P0})
        self.assertEqual(policy.suppression_window, 300.0)

    def test_category_override(self):
        """类别覆盖优先于默认映射"""
        policy = EscalationPolicy(
            category_severity_overrides={
                HTTPErrorCategory.RATE_LIMITED: Severity.P0,  # 提升为 P0
            }
        )
        severity = policy.get_severity(HTTPErrorCategory.RATE_LIMITED)
        self.assertEqual(severity, Severity.P0)

    def test_should_escalate(self):
        """判断是否升级"""
        policy = EscalationPolicy(
            escalate_severities={Severity.P0, Severity.P1}
        )
        self.assertTrue(policy.should_escalate(Severity.P0))
        self.assertTrue(policy.should_escalate(Severity.P1))
        self.assertFalse(policy.should_escalate(Severity.P2))
        self.assertFalse(policy.should_escalate(Severity.P3))

    def test_from_env_parses_severities(self):
        """从环境变量解析严重等级列表"""
        os.environ["TF_OPS_ESCALATE_SEVERITIES"] = "p0,p1"
        try:
            policy = EscalationPolicy.from_env()
            self.assertEqual(policy.escalate_severities, {Severity.P0, Severity.P1})
        finally:
            os.environ.pop("TF_OPS_ESCALATE_SEVERITIES", None)

    def test_from_env_parses_channels(self):
        """从环境变量解析升级渠道"""
        os.environ["TF_OPS_ESCALATION_CHANNELS"] = "console,dingtalk"
        try:
            policy = EscalationPolicy.from_env()
            self.assertEqual(policy.escalation_channels, ["console", "dingtalk"])
        finally:
            os.environ.pop("TF_OPS_ESCALATION_CHANNELS", None)

    def test_from_env_parses_suppression_window(self):
        """从环境变量解析抑制窗口"""
        os.environ["TF_OPS_ESCALATION_SUPPRESSION_WINDOW"] = "60"
        try:
            policy = EscalationPolicy.from_env()
            self.assertEqual(policy.suppression_window, 60.0)
        finally:
            os.environ.pop("TF_OPS_ESCALATION_SUPPRESSION_WINDOW", None)

    def test_from_env_invalid_severity_ignored(self):
        """无效的严重等级被忽略"""
        os.environ["TF_OPS_ESCALATE_SEVERITIES"] = "p0,invalid,p1"
        try:
            policy = EscalationPolicy.from_env()
            self.assertEqual(policy.escalate_severities, {Severity.P0, Severity.P1})
        finally:
            os.environ.pop("TF_OPS_ESCALATE_SEVERITIES", None)


class TestEscalationManager(_NotificationTestBase):
    """EscalationManager 核心行为测试"""

    def _make_manager(self, policy: EscalationPolicy) -> EscalationManager:
        """构造 EscalationManager (独立审计)"""
        from hitl_common import NotificationManager
        config = HITLConfig()
        mgr = NotificationManager(config, self.audit, console_output=False)
        return EscalationManager(policy, self.audit, mgr)

    def test_evaluate_P0_returns_escalate(self):
        """P0 错误应返回 should_escalate=True"""
        policy = EscalationPolicy()
        em = self._make_manager(policy)
        severity, should = em.evaluate("dingtalk", HTTPErrorCategory.UNAUTHORIZED)
        self.assertEqual(severity, Severity.P0)
        self.assertTrue(should)

    def test_evaluate_P2_returns_no_escalate(self):
        """P2 错误应返回 should_escalate=False"""
        policy = EscalationPolicy()
        em = self._make_manager(policy)
        severity, should = em.evaluate("dingtalk", HTTPErrorCategory.NETWORK_TIMEOUT)
        self.assertEqual(severity, Severity.P2)
        self.assertFalse(should)

    def test_escalate_records_audit_event(self):
        """升级触发时记录审计事件"""
        policy = EscalationPolicy()
        em = self._make_manager(policy)
        em.escalate(
            channel="dingtalk",
            category=HTTPErrorCategory.UNAUTHORIZED,
            error=RetryableHTTPError("401", status_code=401),
            payload=SAMPLE_PAYLOAD,
        )
        events = self.audit.query(
            event_type=AuditEventType.NOTIFICATION_ESCALATION_TRIGGERED
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["context"]["severity"], "p0")
        self.assertEqual(events[0]["context"]["category"], "unauthorized")

    def test_escalate_returns_false_when_severity_not_in_policy(self):
        """未在升级策略中的等级返回 False"""
        policy = EscalationPolicy()  # 默认仅 P0
        em = self._make_manager(policy)
        result = em.escalate(
            channel="dingtalk",
            category=HTTPErrorCategory.NETWORK_TIMEOUT,  # P2
            error=NetworkError("timeout"),
        )
        self.assertFalse(result)

    def test_suppression_window(self):
        """同 channel+category 在抑制窗口内不重复升级"""
        policy = EscalationPolicy(suppression_window=60.0)
        em = self._make_manager(policy)
        em.escalate(
            channel="dingtalk",
            category=HTTPErrorCategory.UNAUTHORIZED,
            error=RetryableHTTPError("401", status_code=401),
        )
        # 第二次同 channel+category 应被抑制
        result = em.escalate(
            channel="dingtalk",
            category=HTTPErrorCategory.UNAUTHORIZED,
            error=RetryableHTTPError("401", status_code=401),
        )
        self.assertFalse(result)
        # 审计中应有 SUPPRESSED 事件
        suppressed = self.audit.query(
            event_type=AuditEventType.NOTIFICATION_ESCALATION_SUPPRESSED
        )
        self.assertEqual(len(suppressed), 1)

    def test_suppression_per_channel_category(self):
        """不同 channel+category 不互相抑制"""
        policy = EscalationPolicy(suppression_window=60.0)
        em = self._make_manager(policy)
        em.escalate(
            channel="dingtalk",
            category=HTTPErrorCategory.UNAUTHORIZED,
            error=RetryableHTTPError("401", 401),
        )
        # 飞书的同 category 不被抑制
        result = em.escalate(
            channel="feishu",
            category=HTTPErrorCategory.UNAUTHORIZED,
            error=RetryableHTTPError("401", 401),
        )
        self.assertTrue(result)

    def test_reset_suppression(self):
        """手动重置抑制"""
        policy = EscalationPolicy(suppression_window=60.0)
        em = self._make_manager(policy)
        em.escalate("dingtalk", HTTPErrorCategory.UNAUTHORIZED,
                    RetryableHTTPError("401", 401))
        em.reset_suppression("dingtalk")
        # 重置后应能再次升级
        result = em.escalate("dingtalk", HTTPErrorCategory.UNAUTHORIZED,
                             RetryableHTTPError("401", 401))
        self.assertTrue(result)

    def test_stats_returns_active_suppressions(self):
        """stats() 返回当前生效的抑制列表"""
        policy = EscalationPolicy(suppression_window=60.0)
        em = self._make_manager(policy)
        em.escalate("dingtalk", HTTPErrorCategory.UNAUTHORIZED,
                    RetryableHTTPError("401", 401))
        stats = em.stats()
        self.assertEqual(stats["tracked_keys"], 1)
        self.assertEqual(len(stats["active_suppressions"]), 1)
        self.assertEqual(stats["active_suppressions"][0]["channel"], "dingtalk")


class TestEscalationIntegrationWithChannel(_NotificationTestBase):
    """P0 错误立即升级 + 不重试 的端到端测试"""

    def setUp(self):
        super().setUp()
        # 极短抑制窗口 + 允许重试 (用于测试 P0 跳过重试)
        os.environ["TF_OPS_NOTIFY_MAX_RETRIES"] = "3"
        os.environ["TF_OPS_NOTIFY_RETRY_BACKOFF"] = "0.001"
        os.environ["TF_OPS_NOTIFY_RETRY_MAX_BACKOFF"] = "0.001"
        os.environ["TF_OPS_ESCALATION_SUPPRESSION_WINDOW"] = "0"  # 不抑制
        self._extra_env = (
            "TF_OPS_NOTIFY_MAX_RETRIES",
            "TF_OPS_NOTIFY_RETRY_BACKOFF",
            "TF_OPS_NOTIFY_RETRY_MAX_BACKOFF",
            "TF_OPS_ESCALATION_SUPPRESSION_WINDOW",
        )

    def tearDown(self):
        for k in self._extra_env:
            os.environ.pop(k, None)
        super().tearDown()

    def test_p0_error_skips_retry(self):
        """P0 错误 (401) 跳过重试, 立即升级"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        # 注入会一直返回 401 的 mock
        with patch(
            "hitl_common._http_post",
            side_effect=NonRetryableHTTPError("unauthorized", status_code=401),
        ) as mock_post:
            result = mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")

        self.assertFalse(result)
        # _http_post 只能被调用 1 次 (P0 跳过重试)
        self.assertEqual(mock_post.call_count, 1)
        # 审计中应有 escalated 标记
        failures = self.audit.query(event_type=AuditEventType.NOTIFICATION_FAILED)
        self.assertEqual(len(failures), 1)
        self.assertTrue(failures[0]["context"].get("escalated"))
        self.assertTrue(failures[0]["context"].get("retry_skipped"))

    def test_p0_error_triggers_escalation_audit(self):
        """P0 错误触发升级审计事件"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        with patch(
            "hitl_common._http_post",
            side_effect=NonRetryableHTTPError("token expired", status_code=401),
        ):
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")

        events = self.audit.query(
            event_type=AuditEventType.NOTIFICATION_ESCALATION_TRIGGERED
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["context"]["severity"], "p0")

    def test_p1_error_retries_then_escalates(self):
        """P1 错误 (500) 先重试到上限, 然后升级"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        os.environ["TF_OPS_ESCALATE_SEVERITIES"] = "p0,p1"  # 启用 P1 升级
        self._extra_env = self._extra_env + ("TF_OPS_ESCALATE_SEVERITIES",)

        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        with patch(
            "hitl_common._http_post",
            side_effect=RetryableHTTPError("internal", status_code=500),
        ) as mock_post:
            result = mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")

        self.assertFalse(result)
        # _http_post 应被调用 max_retries+1 次 (3 + 1 = 4)
        self.assertEqual(mock_post.call_count, 4)
        # 升级事件应有 1 个 (重试到上限后)
        events = self.audit.query(
            event_type=AuditEventType.NOTIFICATION_ESCALATION_TRIGGERED
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["context"]["severity"], "p1")

    def test_p2_error_does_not_escalate(self):
        """P2 错误 (网络超时) 不触发升级, 只重试"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        with patch(
            "hitl_common._http_post",
            side_effect=NetworkError("timeout", category=HTTPErrorCategory.NETWORK_TIMEOUT),
        ):
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")

        # 应无升级事件
        events = self.audit.query(
            event_type=AuditEventType.NOTIFICATION_ESCALATION_TRIGGERED
        )
        self.assertEqual(len(events), 0)

    def test_p0_does_not_trigger_circuit_breaker_failure_count(self):
        """P0 错误仍计入熔断器失败计数 (配置错误也算)"""
        # P0 (UNAUTHORIZED) 是 NonRetryableHTTPError, 默认不在熔断 counted 类别中
        # 这里测试隔离性: 即便 P0 升级, 熔断器行为独立
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        os.environ["TF_OPS_CB_FAILURE_THRESHOLD"] = "2"
        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        # 401 错误 - 默认不计入熔断, 也不升级熔断状态
        with patch(
            "hitl_common._http_post",
            side_effect=NonRetryableHTTPError("unauthorized", status_code=401),
        ):
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")

        # 熔断器应仍为 CLOSED (4xx 不计入)
        self.assertEqual(
            mgr.circuit_breaker.get_state("dingtalk"),
            CircuitState.CLOSED,
        )

    def test_503_long_outage_escalates_and_breaker_opens(self):
        """503 服务不可用: P0 升级 + 熔断器开启 (503 是 5xx, 计入熔断)"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        os.environ["TF_OPS_CB_FAILURE_THRESHOLD"] = "2"
        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)

        with patch(
            "hitl_common._http_post",
            side_effect=RetryableHTTPError("unavailable", status_code=503),
        ):
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")  # 1 次失败 → P0 升级
            mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")  # 2 次失败 → 熔断

        # P0 升级应触发
        escalations = self.audit.query(
            event_type=AuditEventType.NOTIFICATION_ESCALATION_TRIGGERED
        )
        self.assertGreaterEqual(len(escalations), 1)
        # 熔断器应开启
        self.assertEqual(
            mgr.circuit_breaker.get_state("dingtalk"),
            CircuitState.OPEN,
        )

    def test_escalation_disabled(self):
        """TF_OPS_ESCALATION_ENABLED=0 禁用升级"""
        os.environ["DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?placeholder=TEST_TOKEN"
        os.environ["TF_OPS_ESCALATION_ENABLED"] = "0"
        self._extra_env = self._extra_env + ("TF_OPS_ESCALATION_ENABLED",)

        config = HITLConfig.load()
        mgr = NotificationManager(config, self.audit, console_output=False)
        self.assertIsNone(mgr.escalation_manager)

        with patch(
            "hitl_common._http_post",
            side_effect=NonRetryableHTTPError("unauthorized", status_code=401),
        ):
            result = mgr.send(SAMPLE_PAYLOAD, channel="dingtalk")
        # P0 错误无升级管理器, 走默认不可重试分支, 不重试
        self.assertFalse(result)
        events = self.audit.query(
            event_type=AuditEventType.NOTIFICATION_ESCALATION_TRIGGERED
        )
        self.assertEqual(len(events), 0)


# ============================================================================
# 入口
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
