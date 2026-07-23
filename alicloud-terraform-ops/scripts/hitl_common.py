#!/usr/bin/env python3
"""
HITL Common - 共享基础设施层

为 HITL Mode A / B / C 提供:
- 审计日志 (AuditLogger) — spec §8
- 错误处理 (CLI / PR / Checkpoint 错误处理器) — spec §7
- 配置加载 (HITLConfig) — spec §6
- 通知模板 (Webhook 模板) — spec §1.1
- Webhook 安全: 强制使用环境变量，禁止硬编码 token

Python 3.10+ 标准库实现，零外部依赖。
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

# ============================================================================
# 审计日志 — spec §8
# ============================================================================

class AuditEventType(str, Enum):
    """审计事件类型 — spec §8.1"""
    CHECKPOINT_CREATED = "checkpoint.created"
    CHECKPOINT_PAUSED = "checkpoint.paused"
    CHECKPOINT_RESUMED = "checkpoint.resumed"
    CHECKPOINT_COMPLETED = "checkpoint.completed"
    CHECKPOINT_EXPIRED = "checkpoint.expired"
    CHECKPOINT_DELETED = "checkpoint.deleted"

    STEP_EXECUTED = "step.executed"
    USER_CONFIRMED = "user.confirmed"
    USER_REJECTED = "user.rejected"
    USER_PAUSED = "user.paused"

    PR_CREATED = "pr.created"
    PR_APPROVED = "pr.approved"
    PR_REJECTED = "pr.rejected"
    PR_MERGED = "pr.merged"
    PR_CLOSED = "pr.closed"
    PR_COMMENT = "pr.comment"

    TERRAFORM_INIT = "terraform.init"
    TERRAFORM_PLAN = "terraform.plan"
    TERRAFORM_APPLY = "terraform.apply"
    TERRAFORM_DESTROY = "terraform.destroy"
    TERRAFORM_IMPORT = "terraform.import"

    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_FAILED = "notification.failed"
    NOTIFICATION_RETRY = "notification.retry"
    NOTIFICATION_CIRCUIT_OPENED = "notification.circuit_opened"
    NOTIFICATION_CIRCUIT_CLOSED = "notification.circuit_closed"
    NOTIFICATION_CIRCUIT_HALF_OPEN = "notification.circuit_half_open"
    NOTIFICATION_CIRCUIT_REJECTED = "notification.circuit_rejected"
    NOTIFICATION_ESCALATION_TRIGGERED = "notification.escalation_triggered"
    NOTIFICATION_ESCALATION_SUPPRESSED = "notification.escalation_suppressed"

    DRIFT_DETECTED = "drift.detected"
    RECOVERY_STARTED = "recovery.started"
    RECOVERY_COMPLETED = "recovery.completed"


@dataclass
class AuditEvent:
    """审计事件 — spec §8.2"""
    event: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    level: str = "INFO"
    checkpoint_id: str | None = None
    user: str | None = None
    environment: str | None = None
    step: dict[str, Any] | None = None
    context: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "timestamp": self.timestamp,
            "level": self.level,
            "event": self.event,
        }
        if self.checkpoint_id:
            d["checkpoint_id"] = self.checkpoint_id
        if self.user:
            d["user"] = self.user
        if self.environment:
            d["environment"] = self.environment
        if self.step:
            d["step"] = self.step
        if self.context:
            d["context"] = self.context
        if self.trace_id:
            d["trace_id"] = self.trace_id
        if self.span_id:
            d["span_id"] = self.span_id
        return d


class AuditLogger:
    """审计日志记录器 — 写入 ~/.pi/terraform-ops/audit/audit-{date}.jsonl

    日志格式: JSON Lines (每行一个 JSON 对象), 符合 spec §8.2
    """

    def __init__(self, base_path: Path | None = None):
        self.base_path = base_path or Path.home() / ".pi" / "terraform-ops" / "audit"
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._trace_id: str | None = None

    def _get_log_file(self) -> Path:
        today = datetime.now().strftime("%Y%m%d")
        return self.base_path / f"audit-{today}.jsonl"

    def log(self, event: AuditEvent):
        """记录事件"""
        log_file = self._get_log_file()
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def emit(
        self,
        event_type: AuditEventType,
        checkpoint_id: str | None = None,
        user: str | None = None,
        environment: str | None = None,
        step: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        level: str = "INFO",
    ):
        """便捷触发方法"""
        if self._trace_id is None:
            self._trace_id = f"trace-{uuid.uuid4().hex[:12]}"

        event = AuditEvent(
            event=event_type.value,
            checkpoint_id=checkpoint_id,
            user=user or os.environ.get("USER", "unknown"),
            environment=environment,
            step=step,
            context=context or {},
            trace_id=self._trace_id,
            span_id=f"span-{uuid.uuid4().hex[:8]}",
            level=level,
        )
        self.log(event)

    def set_trace(self, trace_id: str):
        """设置 trace id (用于跨操作追踪)"""
        self._trace_id = trace_id

    def query(
        self,
        event_type: AuditEventType | None = None,
        checkpoint_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """查询审计日志"""
        results: list[dict[str, Any]] = []
        log_files = sorted(self.base_path.glob("audit-*.jsonl"), reverse=True)

        for log_file in log_files:
            if len(results) >= limit:
                break
            with open(log_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if event_type and entry.get("event") != event_type.value:
                        continue
                    if checkpoint_id and entry.get("checkpoint_id") != checkpoint_id:
                        continue

                    results.append(entry)
                    if len(results) >= limit:
                        break

        return results


# ============================================================================
# 错误处理 — spec §7
# ============================================================================

class HITLError(Exception):
    """HITL 错误基类"""
    pass


class HTTPErrorCategory(str, Enum):
    """HTTP 错误语义化分类

    用于:
    - 熔断器决策 (哪些错误计入熔断计数)
    - 告警路由 (不同严重程度不同通知渠道)
    - 重试策略调优 (某些错误需要更长退避)
    """
    # ============ 客户端错误 (4xx) — 不可重试 ============
    BAD_REQUEST = "bad_request"             # 400 请求格式错误
    UNAUTHORIZED = "unauthorized"           # 401 凭证缺失/过期
    FORBIDDEN = "forbidden"                 # 403 权限不足
    NOT_FOUND = "not_found"                 # 404 webhook 不存在
    METHOD_NOT_ALLOWED = "method_not_allowed"  # 405
    CONFLICT = "conflict"                   # 409 webhook 冲突
    PAYLOAD_TOO_LARGE = "payload_too_large" # 413
    UNPROCESSABLE = "unprocessable"          # 422 请求格式正确但语义错误
    CLIENT_ERROR_OTHER = "client_error_other"  # 其他 4xx

    # ============ 服务端错误 (5xx) — 可重试 ============
    INTERNAL_ERROR = "internal_error"       # 500
    BAD_GATEWAY = "bad_gateway"             # 502
    SERVICE_UNAVAILABLE = "service_unavailable"  # 503
    GATEWAY_TIMEOUT = "gateway_timeout"     # 504
    SERVER_ERROR_OTHER = "server_error_other"  # 其他 5xx

    # ============ 限流 — 可重试 ============
    RATE_LIMITED = "rate_limited"           # 429

    # ============ 网络错误 — 可重试 ============
    NETWORK_TIMEOUT = "network_timeout"     # 连接/读超时
    NETWORK_DNS = "network_dns"             # DNS 解析失败
    NETWORK_CONNECTION = "network_connection"  # 连接被拒
    NETWORK_OTHER = "network_other"         # 其他网络层错误
    SSL_ERROR = "ssl_error"                 # SSL/TLS 错误


class Severity(str, Enum):
    """告警严重等级

    决定:
    - 是否重试 (P0 跳过重试, 立即告警)
    - 告警接收方 (P0 走升级渠道, P1+ 走默认渠道)
    - 是否静音 (P3 静默, 仅审计)
    """
    P0 = "p0"  # Critical - 凭证过期/权限不足/服务不可用  → 立即告警, 不重试
    P1 = "p1"  # High    - 5xx 部分限流                      → 重试到上限 + 告警
    P2 = "p2"  # Medium  - 通用网络错误                      → 标准重试 + 退避
    P3 = "p3"  # Low     - 零散可重试错误                    → 静默重试, 事后审计


# 错误类别 → 严重等级映射 (默认策略)
DEFAULT_CATEGORY_SEVERITY: dict[HTTPErrorCategory, Severity] = {
    # P0: 立即告警，不重试
    HTTPErrorCategory.UNAUTHORIZED: Severity.P0,           # 401 凭证过期
    HTTPErrorCategory.FORBIDDEN: Severity.P0,              # 403 权限不足
    HTTPErrorCategory.NOT_FOUND: Severity.P0,              # 404 webhook 已删除
    HTTPErrorCategory.SERVICE_UNAVAILABLE: Severity.P0,    # 503 长期不可用
    HTTPErrorCategory.NETWORK_DNS: Severity.P0,            # DNS 不可解 -> 配置错误
    HTTPErrorCategory.SSL_ERROR: Severity.P0,              # SSL 证书问题

    # P1: 重试到上限 + 告警
    HTTPErrorCategory.BAD_REQUEST: Severity.P1,            # 400 需检查请求
    HTTPErrorCategory.CONFLICT: Severity.P1,               # 409 资源冲突
    HTTPErrorCategory.PAYLOAD_TOO_LARGE: Severity.P1,      # 413 需裁剪
    HTTPErrorCategory.UNPROCESSABLE: Severity.P1,          # 422 语义错误
    HTTPErrorCategory.RATE_LIMITED: Severity.P1,           # 429 限流
    HTTPErrorCategory.INTERNAL_ERROR: Severity.P1,         # 500
    HTTPErrorCategory.BAD_GATEWAY: Severity.P1,            # 502
    HTTPErrorCategory.GATEWAY_TIMEOUT: Severity.P1,        # 504
    HTTPErrorCategory.SERVER_ERROR_OTHER: Severity.P1,

    # P2: 标准重试
    HTTPErrorCategory.METHOD_NOT_ALLOWED: Severity.P2,     # 405 不会自愈
    HTTPErrorCategory.CLIENT_ERROR_OTHER: Severity.P2,
    HTTPErrorCategory.NETWORK_TIMEOUT: Severity.P2,        # 偶发超时
    HTTPErrorCategory.NETWORK_CONNECTION: Severity.P2,     # 偶发连接拒绝
    HTTPErrorCategory.NETWORK_OTHER: Severity.P2,
}


def get_default_severity(category: HTTPErrorCategory) -> Severity:
    """获取类别的默认严重等级 (P3 作为 fallback)"""
    return DEFAULT_CATEGORY_SEVERITY.get(category, Severity.P3)


def _classify_http_status(status_code: int) -> HTTPErrorCategory:
    """HTTP 状态码 → 语义类别映射"""
    mapping = {
        400: HTTPErrorCategory.BAD_REQUEST,
        401: HTTPErrorCategory.UNAUTHORIZED,
        403: HTTPErrorCategory.FORBIDDEN,
        404: HTTPErrorCategory.NOT_FOUND,
        405: HTTPErrorCategory.METHOD_NOT_ALLOWED,
        409: HTTPErrorCategory.CONFLICT,
        413: HTTPErrorCategory.PAYLOAD_TOO_LARGE,
        422: HTTPErrorCategory.UNPROCESSABLE,
        429: HTTPErrorCategory.RATE_LIMITED,
        500: HTTPErrorCategory.INTERNAL_ERROR,
        502: HTTPErrorCategory.BAD_GATEWAY,
        503: HTTPErrorCategory.SERVICE_UNAVAILABLE,
        504: HTTPErrorCategory.GATEWAY_TIMEOUT,
    }
    if status_code in mapping:
        return mapping[status_code]
    if 400 <= status_code < 500:
        return HTTPErrorCategory.CLIENT_ERROR_OTHER
    if 500 <= status_code < 600:
        return HTTPErrorCategory.SERVER_ERROR_OTHER
    return HTTPErrorCategory.CLIENT_ERROR_OTHER


def _classify_network_error(error: Exception) -> HTTPErrorCategory:
    """根据底层异常类型推断网络错误类别"""
    import socket
    import ssl

    if isinstance(error, socket.timeout | TimeoutError):
        return HTTPErrorCategory.NETWORK_TIMEOUT
    if isinstance(error, ssl.SSLError):
        return HTTPErrorCategory.SSL_ERROR
    if isinstance(error, socket.gaierror):
        return HTTPErrorCategory.NETWORK_DNS
    if isinstance(error, ConnectionRefusedError):
        return HTTPErrorCategory.NETWORK_CONNECTION
    if isinstance(error, ConnectionError):
        return HTTPErrorCategory.NETWORK_CONNECTION
    return HTTPErrorCategory.NETWORK_OTHER


class NetworkError(HITLError):
    """网络错误 (可重试)

    category 字段标记具体网络错误类型 (timeout/dns/connection/ssl/other)
    """
    def __init__(self, message: str, category: HTTPErrorCategory | None = None):
        super().__init__(message)
        self.category = category or HTTPErrorCategory.NETWORK_OTHER


class PermissionError(HITLError):
    """权限错误 (需人工处理)"""
    pass


class StateConflictError(HITLError):
    """状态冲突错误"""
    pass


class ResourceNotFoundError(HITLError):
    """资源不存在错误"""
    pass


class ConfigError(HITLError):
    """配置错误"""
    pass


class ExpiredError(HITLError):
    """过期错误"""
    pass


class GitError(HITLError):
    """Git 操作错误"""
    def __init__(self, message: str, code: str = "unknown"):
        super().__init__(message)
        self.code = code


class WebhookError(HITLError):
    """Webhook 发送错误"""
    pass


class RetryableHTTPError(HITLError):
    """可重试的 HTTP 错误 (5xx / 429)

    由 _http_post 抛出, _Channel.send_with_retry 负责重试
    """
    def __init__(
        self,
        message: str,
        status_code: int,
        category: HTTPErrorCategory | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.category = category or _classify_http_status(status_code)
        # Retry-After header (秒), 部分服务会用
        self.retry_after = retry_after


class NonRetryableHTTPError(HITLError):
    """不可重试的 HTTP 错误 (4xx, 排除 429)"""
    def __init__(
        self,
        message: str,
        status_code: int,
        category: HTTPErrorCategory | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.category = category or _classify_http_status(status_code)


@dataclass
class ErrorAction:
    """错误处理动作"""
    action: str  # RETRY / PAUSE / HALT / UPDATE_EXISTING_PR / RETRY_WITH_NEW_BRANCH
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Circuit Breaker — 防止下游服务雪崩
# ============================================================================

class CircuitState(str, Enum):
    """熔断器状态"""
    CLOSED = "closed"          # 正常: 请求正常发送
    OPEN = "open"              # 熔断: 请求直接拒绝
    HALF_OPEN = "half_open"    # 半开: 允许一个探针请求


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    # 连续失败 N 次后熔断
    failure_threshold: int = 5
    # 熔断后多少秒进入半开状态
    reset_timeout: float = 60.0
    # 半开状态下, 连续成功 N 次后恢复正常
    success_threshold: int = 2
    # 哪些错误类别计入熔断计数 (默认仅服务端错误和网络错误)
    counted_categories: Set[HTTPErrorCategory] | None = None

    def __post_init__(self):
        if self.counted_categories is None:
            # 默认: 5xx, 限流, 网络错误计入熔断
            # 不计入: 4xx (客户端配置问题, 不会自愈)
            self.counted_categories = {
                HTTPErrorCategory.INTERNAL_ERROR,
                HTTPErrorCategory.BAD_GATEWAY,
                HTTPErrorCategory.SERVICE_UNAVAILABLE,
                HTTPErrorCategory.GATEWAY_TIMEOUT,
                HTTPErrorCategory.SERVER_ERROR_OTHER,
                HTTPErrorCategory.RATE_LIMITED,
                HTTPErrorCategory.NETWORK_TIMEOUT,
                HTTPErrorCategory.NETWORK_DNS,
                HTTPErrorCategory.NETWORK_CONNECTION,
                HTTPErrorCategory.NETWORK_OTHER,
                HTTPErrorCategory.SSL_ERROR,
            }


class CircuitBreakerOpenError(HITLError):
    """熔断器打开时尝试调用抛出的异常"""
    def __init__(self, channel: str, opened_at: float, reset_at: float):
        super().__init__(
            f"电路熔断器处于打开状态 (channel={channel}, "
            f"opened_at={opened_at}, reset_at={reset_at})"
        )
        self.channel = channel
        self.opened_at = opened_at
        self.reset_at = reset_at


class CircuitBreaker:
    """熔断器

    状态机:
        CLOSED --(连续失败 N 次)--> OPEN
        OPEN   --(reset_timeout 后)--> HALF_OPEN
        HALF_OPEN --(成功 N 次)--> CLOSED
        HALF_OPEN --(任意失败)--> OPEN (重置计时)

    使用:
        breaker = CircuitBreaker(config, audit)
        try:
            breaker.enter(channel)  # 失败时抛 CircuitBreakerOpenError
            try:
                do_http_call()
            except Exception as e:
                breaker.record_failure(channel, e)
            else:
                breaker.record_success(channel)
        except CircuitBreakerOpenError:
            return False  # 熔断中, 不重试

    线程安全: 是 (内部加锁)
    """

    def __init__(self, config: CircuitBreakerConfig, audit: AuditLogger):
        self.config = config
        self.audit = audit

        # 每个 channel 独立状态
        # channel_name -> {state, failure_count, success_count, opened_at, last_failure}
        self._states: dict[str, dict[str, Any]] = {}
        self._lock = __import__("threading").Lock()

    @classmethod
    def from_env(cls, audit: AuditLogger) -> CircuitBreaker:
        """从环境变量创建熔断器"""
        config = CircuitBreakerConfig(
            failure_threshold=int(os.environ.get("TF_OPS_CB_FAILURE_THRESHOLD", "5")),
            reset_timeout=float(os.environ.get("TF_OPS_CB_RESET_TIMEOUT", "60")),
            success_threshold=int(os.environ.get("TF_OPS_CB_SUCCESS_THRESHOLD", "2")),
        )
        return cls(config, audit)

    def _get_state(self, channel: str) -> dict[str, Any]:
        """获取 channel 状态, 惰性初始化"""
        if channel not in self._states:
            self._states[channel] = {
                "state": CircuitState.CLOSED,
                "failure_count": 0,
                "success_count": 0,
                "opened_at": 0.0,
                "last_failure": None,
            }
        return self._states[channel]

    def get_state(self, channel: str) -> CircuitState:
        """查询当前状态 (不修改)"""
        with self._lock:
            return self._get_state(channel)["state"]

    def is_counted_error(self, error: Exception) -> bool:
        """错误是否计入熔断计数"""
        if isinstance(error, RetryableHTTPError):
            return error.category in self.config.counted_categories
        if isinstance(error, NetworkError):
            return error.category in self.config.counted_categories
        return False

    def enter(self, channel: str) -> None:
        """尝试进入调用

        Raises:
            CircuitBreakerOpenError: 熔断器打开
        """
        with self._lock:
            state = self._get_state(channel)
            now = time.time()

            if state["state"] == CircuitState.OPEN:
                # 检查是否可以进入半开状态
                if now - state["opened_at"] >= self.config.reset_timeout:
                    # 超时, 转为半开
                    state["state"] = CircuitState.HALF_OPEN
                    state["success_count"] = 0
                    self.audit.emit(
                        AuditEventType.NOTIFICATION_CIRCUIT_HALF_OPEN,
                        context={
                            "channel": channel,
                            "opened_at": state["opened_at"],
                            "downtime_seconds": now - state["opened_at"],
                        },
                    )
                else:
                    # 仍在熔断中
                    remaining = self.config.reset_timeout - (now - state["opened_at"])
                    self.audit.emit(
                        AuditEventType.NOTIFICATION_CIRCUIT_REJECTED,
                        context={
                            "channel": channel,
                            "remaining_seconds": round(remaining, 2),
                        },
                        level="WARN",
                    )
                    raise CircuitBreakerOpenError(
                        channel=channel,
                        opened_at=state["opened_at"],
                        reset_at=state["opened_at"] + self.config.reset_timeout,
                    )

            # CLOSED 或 HALF_OPEN 状态: 允许调用

    def record_success(self, channel: str) -> None:
        """记录成功"""
        with self._lock:
            state = self._get_state(channel)

            if state["state"] == CircuitState.HALF_OPEN:
                state["success_count"] += 1
                if state["success_count"] >= self.config.success_threshold:
                    # 半开达到阈值, 恢复正常
                    state["state"] = CircuitState.CLOSED
                    state["failure_count"] = 0
                    state["success_count"] = 0
                    self.audit.emit(
                        AuditEventType.NOTIFICATION_CIRCUIT_CLOSED,
                        context={
                            "channel": channel,
                            "successful_probes": state["success_count"],
                        },
                    )
            else:
                # CLOSED 状态: 成功只是重置失败计数
                state["failure_count"] = 0

    def record_failure(self, channel: str, error: Exception) -> None:
        """记录失败 (仅在错误被计入时触发)"""
        if not self.is_counted_error(error):
            return  # 不计入的错误不触发熔断

        with self._lock:
            state = self._get_state(channel)
            now = time.time()
            state["failure_count"] += 1
            state["last_failure"] = {
                "error": str(error),
                "category": getattr(error, "category", HTTPErrorCategory.NETWORK_OTHER).value
                    if hasattr(error, "category") else "unknown",
                "at": now,
            }

            if state["state"] == CircuitState.HALF_OPEN:
                # 半开状态失败: 立即重新熔断
                state["state"] = CircuitState.OPEN
                state["opened_at"] = now
                state["success_count"] = 0
                self.audit.emit(
                    AuditEventType.NOTIFICATION_CIRCUIT_OPENED,
                    context={
                        "channel": channel,
                        "trigger": "half_open_failure",
                        "category": state["last_failure"]["category"],
                        "reset_at": now + self.config.reset_timeout,
                    },
                    level="ERROR",
                )
            elif state["state"] == CircuitState.CLOSED:
                if state["failure_count"] >= self.config.failure_threshold:
                    # 达到阈值, 熔断
                    state["state"] = CircuitState.OPEN
                    state["opened_at"] = now
                    self.audit.emit(
                        AuditEventType.NOTIFICATION_CIRCUIT_OPENED,
                        context={
                            "channel": channel,
                            "trigger": "failure_threshold_reached",
                            "failure_count": state["failure_count"],
                            "threshold": self.config.failure_threshold,
                            "category": state["last_failure"]["category"],
                            "reset_at": now + self.config.reset_timeout,
                        },
                        level="ERROR",
                    )

    def reset(self, channel: str) -> None:
        """强制重置 (用于测试/手动恢复)"""
        with self._lock:
            self._states.pop(channel, None)

    def stats(self, channel: str) -> dict[str, Any]:
        """获取 channel 状态 (用于调试/监控)"""
        with self._lock:
            state = self._get_state(channel)
            return {
                "state": state["state"].value,
                "failure_count": state["failure_count"],
                "success_count": state["success_count"],
                "opened_at": state["opened_at"],
                "last_failure": state["last_failure"],
            }


# ============================================================================
# 告警升级 (Escalation) — P0 错误立即告警，不再重试
# ============================================================================

@dataclass
class EscalationPolicy:
    """升级策略配置

    决定:
    - 哪些严重等级需要升级 (默认仅 P0)
    - 升级通知走哪些渠道 (默认 + 升级渠道)
    - 抑制窗口 (同 channel+category 在 N 秒内不重复升级)
    - 类别 → 严重等级 的自定义覆盖
    """
    # 哪些严重等级触发升级
    escalate_severities: Set[Severity] = field(
        default_factory=lambda: {Severity.P0}
    )
    # 升级通知渠道 (独立于主通知渠道)
    escalation_channels: list[str] = field(
        default_factory=lambda: ["console"]
    )
    # 抑制窗口 (秒): 同 channel+category 在此窗口内不重复升级
    suppression_window: float = 300.0
    # 类别 → 严重等级 覆盖 (未覆盖时使用 DEFAULT_CATEGORY_SEVERITY)
    category_severity_overrides: dict[HTTPErrorCategory, Severity] = field(
        default_factory=dict
    )

    def get_severity(self, category: HTTPErrorCategory) -> Severity:
        """获取类别的严重等级 (优先返回 override)"""
        if category in self.category_severity_overrides:
            return self.category_severity_overrides[category]
        return get_default_severity(category)

    def should_escalate(self, severity: Severity) -> bool:
        """该严重等级是否需要升级"""
        return severity in self.escalate_severities

    @classmethod
    def from_env(cls) -> EscalationPolicy:
        """从环境变量创建"""
        policy = cls()

        # 升级严重等级: TF_OPS_ESCALATE_SEVERITIES=p0,p1
        env_sev = os.environ.get("TF_OPS_ESCALATE_SEVERITIES")
        if env_sev:
            sevs = set()
            for s in env_sev.split(","):
                s = s.strip().lower()
                try:
                    sevs.add(Severity(s))
                except ValueError:
                    pass
            if sevs:
                policy.escalate_severities = sevs

        # 升级渠道: TF_OPS_ESCALATION_CHANNELS=console,dingtalk
        env_ch = os.environ.get("TF_OPS_ESCALATION_CHANNELS")
        if env_ch:
            policy.escalation_channels = [c.strip() for c in env_ch.split(",") if c.strip()]

        # 抑制窗口: TF_OPS_ESCALATION_SUPPRESSION_WINDOW=300 (秒)
        env_win = os.environ.get("TF_OPS_ESCALATION_SUPPRESSION_WINDOW")
        if env_win:
            try:
                policy.suppression_window = float(env_win)
            except ValueError:
                pass

        return policy


class EscalationManager:
    """升级管理器

    职责:
    1. 判定错误类别是否需要升级
    2. 检查抑制窗口 (避免告警风爆)
    3. 调用通知管理器发送升级告警
    4. 记录审计

    集成位置: _Channel.send_with_retry() 中的 P0 错误分支

    线程安全: 是 (内部加锁)
    """

    def __init__(
        self,
        policy: EscalationPolicy,
        audit: AuditLogger,
        notification: NotificationManager,
    ):
        self.policy = policy
        self.audit = audit
        self.notification = notification

        # 升级抑制记录: (channel_name, category) -> last_escalation_timestamp
        self._last_escalation: dict[Tuple[str, HTTPErrorCategory], float] = {}
        self._lock = __import__("threading").Lock()

    def evaluate(
        self,
        channel: str,
        category: HTTPErrorCategory,
    ) -> Tuple[Severity | None, bool]:
        """评估错误是否需要升级

        Returns:
            (severity, should_escalate) - severity 总是返回, should_escalate 决定是否发送
        """
        severity = self.policy.get_severity(category)
        if not self.policy.should_escalate(severity):
            return severity, False
        return severity, True

    def escalate(
        self,
        channel: str,
        category: HTTPErrorCategory,
        error: Exception,
        payload: NotificationPayload | None = None,
    ) -> bool:
        """发送升级告警 (检查抑制后)

        Returns:
            True: 告警已发送
            False: 被抑制 / 未发送
        """
        severity = self.policy.get_severity(category)
        if not self.policy.should_escalate(severity):
            return False

        # 抑制检查
        with self._lock:
            key = (channel, category)
            now = time.time()
            last = self._last_escalation.get(key, 0.0)
            if now - last < self.policy.suppression_window:
                # 抑制中: 记录但不发送
                self.audit.emit(
                    AuditEventType.NOTIFICATION_ESCALATION_SUPPRESSED,
                    context={
                        "channel": channel,
                        "category": category.value,
                        "severity": severity.value,
                        "suppressed_for_seconds": round(
                            self.policy.suppression_window - (now - last), 2
                        ),
                    },
                    level="WARN",
                )
                return False
            # 更新抑制时间戳
            self._last_escalation[key] = now

        # 构造升级告警负载
        title = self._build_title(channel, severity, category)
        message = self._build_message(channel, severity, category, error, payload)
        url = payload.url if payload else None

        escalation_payload = NotificationPayload(
            title=title,
            message=message,
            level="error",  # 升级告警始终是 error 级别
            url=url,
            extra={
                "escalation": True,
                "severity": severity.value,
                "category": category.value,
                "source_channel": channel,
            },
        )

        # 发送到升级渠道 (独立于主通知渠道)
        results = self.notification.send_all(
            escalation_payload,
            channels=self.policy.escalation_channels,
        )
        sent = any(results.values())

        # 记录审计
        self.audit.emit(
            AuditEventType.NOTIFICATION_ESCALATION_TRIGGERED,
            context={
                "channel": channel,
                "category": category.value,
                "severity": severity.value,
                "error": str(error),
                "error_type": type(error).__name__,
                "escalation_channels": self.policy.escalation_channels,
                "delivery_results": results,
                "payload_title": payload.title if payload else None,
            },
            level="ERROR" if severity == Severity.P0 else "WARN",
        )

        return sent

    @staticmethod
    def _build_title(channel: str, severity: Severity, category: HTTPErrorCategory) -> str:
        """构造升级告警标题"""
        prefix = {
            Severity.P0: "[P0 告警]",
            Severity.P1: "[P1 告警]",
            Severity.P2: "[P2 通知]",
            Severity.P3: "[P3 日志]",
        }.get(severity, "[告警]")
        return f"{prefix} {channel} 渠道失败: {category.value}"

    @staticmethod
    def _build_message(
        channel: str,
        severity: Severity,
        category: HTTPErrorCategory,
        error: Exception,
        payload: NotificationPayload | None,
    ) -> str:
        """构造升级告警详情"""
        lines = [
            f"**严重等级**: {severity.value.upper()}",
            f"**失败渠道**: {channel}",
            f"**错误类别**: {category.value}",
            f"**错误信息**: {error}",
        ]
        if payload:
            lines.append(f"**原始通知**: {payload.title}")
        lines.append("")
        if severity == Severity.P0:
            lines.append("⛔ **P0 错误处理**")
            lines.append("- 跳过重试逻辑")
            lines.append("- 同步触发告警")
            lines.append("- 需立即人工介入 (检查凭证/配置/服务可用性)")
        return "\n".join(lines)

    def reset_suppression(self, channel: str | None = None):
        """手动重置抑制 (运维场景)"""
        with self._lock:
            if channel is None:
                self._last_escalation.clear()
            else:
                self._last_escalation = {
                    k: v for k, v in self._last_escalation.items() if k[0] != channel
                }

    def stats(self) -> dict[str, Any]:
        """查询抑制状态 (调试/监控)"""
        with self._lock:
            now = time.time()
            return {
                policy_field if False else "tracked_keys": len(self._last_escalation),
                "active_suppressions": [
                    {
                        "channel": ch,
                        "category": cat.value,
                        "suppressed_for_seconds": max(
                            0, round(self.policy.suppression_window - (now - ts), 2)
                        ),
                    }
                    for (ch, cat), ts in self._last_escalation.items()
                    if now - ts < self.policy.suppression_window
                ],
            }


class CLIErrorHandler:
    """CLI 错误处理器 — spec §7.2"""

    def __init__(self, audit: AuditLogger, max_retries: int = 3):
        self.audit = audit
        self.max_retries = max_retries

    def handle(
        self,
        error: Exception,
        checkpoint: Any,  # 避免循环导入
        retry_count: int = 0,
    ) -> ErrorAction:
        if isinstance(error, NetworkError):
            if retry_count < self.max_retries:
                self.audit.emit(
                    AuditEventType.USER_PAUSED,
                    checkpoint_id=getattr(checkpoint, "id", None),
                    context={"error": str(error), "retry": retry_count + 1},
                    level="WARN",
                )
                return ErrorAction(
                    action="RETRY",
                    reason=f"网络错误，{retry_count + 1}/{self.max_retries} 次重试",
                )
            self.audit.emit(
                AuditEventType.CHECKPOINT_PAUSED,
                checkpoint_id=getattr(checkpoint, "id", None),
                context={"error": str(error), "max_retries_reached": True},
            )
            return ErrorAction(action="PAUSE", reason="网络错误重试耗尽")

        if isinstance(error, PermissionError):
            return ErrorAction(action="HALT", reason="权限不足，请联系管理员")

        if isinstance(error, TimeoutError) or isinstance(error, ExpiredError):
            return ErrorAction(action="PAUSE", reason="操作超时，检查点已保存")

        if isinstance(error, ResourceNotFoundError):
            return ErrorAction(
                action="HALT",
                reason=f"资源不存在: {getattr(error, 'resource_id', str(error))}",
            )

        if isinstance(error, ConfigError):
            return ErrorAction(action="HALT", reason=f"配置错误: {error}")

        # 未知错误
        self.audit.emit(
            AuditEventType.CHECKPOINT_PAUSED,
            checkpoint_id=getattr(checkpoint, "id", None),
            context={"error": str(error), "error_type": type(error).__name__},
            level="ERROR",
        )
        return ErrorAction(action="PAUSE", reason=f"未知错误: {error}")


class PRErrorHandler:
    """PR 错误处理器 — spec §7.3"""

    def __init__(self, audit: AuditLogger):
        self.audit = audit

    def handle_git_error(self, error: GitError, pr_id: str | None = None) -> ErrorAction:
        if error.code == "branch_already_exists":
            return ErrorAction(
                action="RETRY_WITH_NEW_BRANCH",
                reason="分支已存在，将使用新分支名",
            )

        if error.code == "push_rejected":
            return ErrorAction(
                action="HALT",
                reason="推送被拒绝，请检查权限或手动解决冲突",
            )

        if error.code == "pr_create_failed":
            msg = str(error).lower()
            if "already exists" in msg:
                return ErrorAction(
                    action="UPDATE_EXISTING_PR",
                    reason="PR 已存在，将更新现有 PR",
                )
            return ErrorAction(
                action="HALT",
                reason=f"创建 PR 失败: {error}",
            )

        if error.code == "not_found":
            return ErrorAction(
                action="HALT",
                reason=f"资源不存在: {error}",
            )

        # 默认
        return ErrorAction(
            action="HALT",
            reason=f"Git 错误 ({error.code}): {error}",
        )

    def handle_network_error(
        self,
        error: NetworkError,
        retry_count: int,
        max_retries: int = 3,
    ) -> ErrorAction:
        if retry_count < max_retries:
            return ErrorAction(
                action="RETRY",
                reason=f"网络错误，{retry_count + 1}/{max_retries} 次重试",
            )
        return ErrorAction(
            action="PAUSE",
            reason="网络错误重试耗尽，已保存状态可稍后恢复",
        )


class CheckpointErrorHandler:
    """CheckPoint 错误处理器 — spec §7.4"""

    def __init__(self, audit: AuditLogger, store: Any = None):
        self.audit = audit
        self.store = store  # CheckpointStore 引用

    def handle_load_error(
        self,
        error: Exception,
        checkpoint_id: str,
    ) -> dict[str, Any]:
        if isinstance(error, FileNotFoundError):
            return {
                "error": f"检查点不存在: {checkpoint_id}",
                "checkpoint": None,
            }

        if isinstance(error, json.JSONDecodeError):
            # 尝试从备份恢复
            backup = self._try_load_backup(checkpoint_id)
            if backup:
                self.audit.emit(
                    AuditEventType.RECOVERY_COMPLETED,
                    checkpoint_id=checkpoint_id,
                    context={"recovery_method": "backup_file"},
                    level="WARN",
                )
                return {
                    "warning": "检查点文件损坏，已从备份恢复",
                    "checkpoint": backup,
                }
            return {
                "error": "检查点文件损坏且无法从备份恢复",
                "checkpoint": None,
            }

        if isinstance(error, ExpiredError):
            return {
                "error": f"检查点已过期: {checkpoint_id}",
                "checkpoint": None,
            }

        return {
            "error": f"加载检查点失败: {error}",
            "checkpoint": None,
        }

    def _try_load_backup(self, checkpoint_id: str) -> Any | None:
        """尝试加载备份 (.bak 文件)"""
        if self.store is None:
            return None
        return self.store.load_backup(checkpoint_id)


# ============================================================================
# 配置加载 — spec §6
# ============================================================================

@dataclass
class HITLConfig:
    """HITL 配置 (优先级: CLI > env > project > user > default)"""

    # 基础
    mode: str = "cli"  # cli / pr / checkpoint
    environment: str = "dev"
    region: str = "cn-hangzhou"

    # 模式特定
    pr_provider: str = "local"  # local / github / gitlab / gitee
    pr_repository: str = ""
    pr_base_branch: str = "main"
    pr_auto_merge: bool = False
    pr_delete_branch: bool = True

    # Checkpoint 存储
    checkpoint_storage: str = "local"  # local / oss
    checkpoint_local_path: str = "~/.pi/terraform-ops/checkpoints"
    checkpoint_default_ttl: str = "7d"
    checkpoint_production_ttl: str = "30d"
    auto_cleanup: bool = True

    # 通知
    notification_enabled: bool = True

    # 钉钉
    dingtalk_webhook_env: str = "DINGTALK_WEBHOOK_URL"
    dingtalk_webhook: str | None = None  # 实际值，从环境变量解析
    dingtalk_secret_env: str = "DINGTALK_WEBHOOK_SECRET"  # 可选: 加签密钥

    # 飞书
    feishu_webhook_env: str = "FEISHU_WEBHOOK_URL"
    feishu_webhook: str | None = None
    feishu_secret_env: str = "FEISHU_WEBHOOK_SECRET"  # 可选: 签名校验密钥

    # 企业微信
    wecom_webhook_env: str = "WECOM_WEBHOOK_URL"
    wecom_webhook: str | None = None

    # 默认通知渠道
    default_notification_channels: list[str] = field(default_factory=lambda: ["console"])

    # 审批人 (CodeOwners)
    codeowners: dict[str, list[str]] = field(default_factory=dict)

    # 环境特定策略覆盖
    environment_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)

    # 来源
    sources: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, project_path: Path | None = None) -> HITLConfig:
        """加载配置 (合并多层来源)"""
        config = cls()

        # 5. 系统默认 (已由 dataclass 默认值提供)
        config.sources.append("default")

        # 4. 用户配置 ~/.pi/terraform-ops.yaml
        user_data: dict[str, Any] | None = None
        user_config_path = Path.home() / ".pi" / "terraform-ops.yaml"
        if user_config_path.exists():
            user_data = cls._parse_yaml(user_config_path)
            if user_data:
                config._merge(user_data)
                config.sources.append(f"user:{user_config_path}")

        # 3. 项目配置 ./.pi/terraform-ops.yaml
        proj_data: dict[str, Any] | None = None
        if project_path:
            project_config = project_path / ".pi" / "terraform-ops.yaml"
            if not project_config.exists():
                project_config = project_path / "terraform-ops.yaml"
            if project_config.exists():
                proj_data = cls._parse_yaml(project_config)
                if proj_data:
                    config._merge(proj_data)
                    config.sources.append(f"project:{project_config}")

        # 2. 环境变量
        env_overrides = {
            "mode": os.environ.get("TF_OPS_MODE"),
            "environment": os.environ.get("TF_OPS_ENV"),
            "region": os.environ.get("TF_OPS_REGION"),
            "pr_provider": os.environ.get("TF_OPS_PR_PROVIDER"),
            "pr_repository": os.environ.get("TF_OPS_PR_REPOSITORY"),
        }
        env_overrides = {k: v for k, v in env_overrides.items() if v is not None}
        if env_overrides:
            config._merge(env_overrides)
            config.sources.append("env")

        # Webhook 强制从环境变量解析 (安全要求: 禁止配置文件中硬编码)
        config.dingtalk_webhook = os.environ.get(config.dingtalk_webhook_env)
        config.feishu_webhook = os.environ.get(config.feishu_webhook_env)
        config.wecom_webhook = os.environ.get(config.wecom_webhook_env)

        # 通知渠道优先级
        # 默认渠道 = [console], 仅在用户未显式配置时根据 webhook 环境变量自动扩展
        env_explicit = (env_overrides or {}).get("default_notification_channels")
        user_explicit = bool(user_data and "default_notification_channels" in user_data)
        proj_explicit = bool(proj_data and "default_notification_channels" in proj_data)
        is_user_configured = env_explicit is not None or user_explicit or proj_explicit

        if not is_user_configured:
            # 自动检测: 若任一 webhook 已配置则启用
            channels = ["console"]
            if config.dingtalk_webhook:
                channels.append("dingtalk")
            if config.feishu_webhook:
                channels.append("feishu")
            if config.wecom_webhook:
                channels.append("wecom")
            config.default_notification_channels = channels

        return config

    @staticmethod
    def _parse_yaml(path: Path) -> dict[str, Any] | None:
        """轻量 YAML 解析 (仅支持 spec §6.2 中使用的子集)

        由于零依赖限制，仅支持:
        - key: value
        - key:\n  nested_key: value
        - 列表 (- item)
        - 注释 (#)
        不支持: 复杂嵌套、锚点、引用
        """
        try:
            import yaml  # type: ignore
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else None
        except ImportError:
            return HITLConfig._parse_yaml_minimal(path)

    @staticmethod
    def _parse_yaml_minimal(path: Path) -> dict[str, Any] | None:
        """最小化 YAML 解析 (无 PyYAML 依赖时的回退)"""
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except OSError:
            return None

        try:
            import yaml  # type: ignore  # noqa: F401
            # 如果 yaml 可用，直接使用
            return yaml.safe_load(content)
        except ImportError:
            pass

        # 真正的最小化解析 (只支持 spec 示例中的格式)
        return _MinimalYAMLParser.parse(content)

    def _merge(self, overrides: dict[str, Any]):
        """深度合并覆盖"""
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(getattr(self, key, None), dict):
                existing = getattr(self, key)
                existing.update(value)
            else:
                setattr(self, key, value)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典 (用于调试)"""
        return {
            "mode": self.mode,
            "environment": self.environment,
            "region": self.region,
            "pr_provider": self.pr_provider,
            "pr_repository": self.pr_repository,
            "pr_base_branch": self.pr_base_branch,
            "pr_auto_merge": self.pr_auto_merge,
            "pr_delete_branch": self.pr_delete_branch,
            "checkpoint_storage": self.checkpoint_storage,
            "checkpoint_local_path": self.checkpoint_local_path,
            "notification_enabled": self.notification_enabled,
            "dingtalk_webhook_configured": bool(self.dingtalk_webhook),
            "feishu_webhook_configured": bool(self.feishu_webhook),
            "wecom_webhook_configured": bool(self.wecom_webhook),
            "default_notification_channels": self.default_notification_channels,
            "codeowners": self.codeowners,
            "sources": self.sources,
        }


class _MinimalYAMLParser:
    """极简 YAML 解析器 — 仅支持 spec §6.2 中的格式

    支持的格式:
    ```yaml
    mode: pr
    environments:
      production:
        mode: pr
        require_jira_ticket: true
    codeowners:
      "*":
        - "@ops-team"
        - "@ops-manager"
    ```
    """

    @classmethod
    def parse(cls, content: str) -> dict[str, Any] | None:
        lines = []
        for raw in content.splitlines():
            # 去除注释
            line = re.sub(r"#.*$", "", raw).rstrip()
            if not line.strip():
                continue
            lines.append(line)

        if not lines:
            return None

        result: dict[str, Any] = {}
        cls._parse_block(lines, 0, 0, result)
        return result

    @classmethod
    def _parse_block(
        cls,
        lines: list[str],
        start: int,
        base_indent: int,
        out: dict[str, Any],
    ) -> int:
        i = start
        while i < len(lines):
            line = lines[i]
            indent = len(line) - len(line.lstrip())
            if indent < base_indent:
                return i
            if indent > base_indent:
                # 嵌套错误，回退
                i += 1
                continue

            stripped = line.strip()

            if stripped.startswith("- "):
                # 列表项 — 父级需要是 list
                # 此处简化: 列表项应在外层 dict 解析中处理
                i += 1
                continue

            if ":" not in stripped:
                i += 1
                continue

            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            if value == "":
                # 嵌套字典/列表
                if i + 1 < len(lines):
                    next_indent = len(lines[i + 1]) - len(lines[i + 1].lstrip())
                    if next_indent > base_indent:
                        if lines[i + 1].lstrip().startswith("- "):
                            # 列表
                            lst: list[Any] = []
                            j = i + 1
                            while j < len(lines):
                                next_line = lines[j]
                                next_ind = len(next_line) - len(next_line.lstrip())
                                if next_ind <= base_indent or not next_line.lstrip().startswith("- "):
                                    break
                                item = next_line.lstrip()[2:].strip()
                                # 处理嵌套 key: value
                                if ":" in item:
                                    sub: dict[str, Any] = {}
                                    sub_k, _, sub_v = item.partition(":")
                                    sub[sub_k.strip()] = cls._parse_value(sub_v.strip())
                                    lst.append(sub)
                                else:
                                    lst.append(cls._parse_value(item))
                                j += 1
                            out[key] = lst
                            i = j
                            continue
                        else:
                            sub_dict: dict[str, Any] = {}
                            i = cls._parse_block(lines, i + 1, next_indent, sub_dict)
                            out[key] = sub_dict
                            continue
                out[key] = {}
                i += 1
            else:
                out[key] = cls._parse_value(value)
                i += 1

        return i

    @staticmethod
    def _parse_value(value: str) -> Any:
        """解析值"""
        value = value.strip()
        if not value:
            return ""
        if value.lower() in ("true", "yes"):
            return True
        if value.lower() in ("false", "no"):
            return False
        if value.lower() in ("null", "~"):
            return None
        # 数字
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        # 字符串 (去除引号)
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            return value[1:-1]
        return value


# ============================================================================
# 通知模板 — spec §1.1 / §10.2
# ============================================================================

@dataclass
class NotificationPayload:
    """通知负载"""
    title: str
    message: str
    level: str = "info"  # info / warning / error / success
    url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class NotificationManager:
    """通知管理器

    支持渠道: console / dingtalk / feishu / wecom / slack
    安全要求: webhook URL 强制从环境变量注入，配置文件中只能引用变量名

    架构:
    - 使用 channel registry 模式: 每个渠道是一个 _Channel 实例
    - send() / send_all() 统一调度
    - 消息体构建与发送分离 (便于测试和扩展)
    """

    # 可疑 token 模式: 32+ 位 hex 或 access_token=xxx
    _TOKEN_PATTERN = re.compile(
        r"[a-f0-9]{32,}|access_token=[a-zA-Z0-9]+", re.IGNORECASE
    )

    def __init__(
        self,
        config: HITLConfig,
        audit: AuditLogger,
        console_output: bool = True,
        circuit_breaker: CircuitBreaker | None = None,
        escalation_manager: EscalationManager | None = None,
    ):
        self.config = config
        self.audit = audit
        self.console_output = console_output

        # 熔断器: 默认从环境变量创建, 可传入禁用
        if circuit_breaker is None and os.environ.get("TF_OPS_CB_ENABLED", "1") == "1":
            circuit_breaker = CircuitBreaker.from_env(audit)
        self.circuit_breaker = circuit_breaker

        # 升级管理器: 默认创建 (可通过 env 禁用)
        if (
            escalation_manager is None
            and os.environ.get("TF_OPS_ESCALATION_ENABLED", "1") == "1"
        ):
            policy = EscalationPolicy.from_env()
            escalation_manager = EscalationManager(policy, audit, self)
        self.escalation_manager = escalation_manager

        # 渠道注册表
        self._channels: dict[str, _Channel] = {
            "console": _ConsoleChannel(console_output),
            "dingtalk": _DingTalkChannel(
                webhook_url=config.dingtalk_webhook,
                webhook_env=config.dingtalk_webhook_env,
                secret=os.environ.get(config.dingtalk_secret_env),
            ),
            "feishu": _FeishuChannel(
                webhook_url=config.feishu_webhook,
                webhook_env=config.feishu_webhook_env,
                secret=os.environ.get(config.feishu_secret_env),
            ),
            "wecom": _WeComChannel(
                webhook_url=config.wecom_webhook,
                webhook_env=config.wecom_webhook_env,
            ),
            "slack": _SlackChannel(),
        }

        # 将熔断器/升级管理器注入所有渠道
        for ch in self._channels.values():
            if self.circuit_breaker is not None:
                ch.circuit_breaker = self.circuit_breaker
            if self.escalation_manager is not None:
                ch.escalation_manager = self.escalation_manager

    def register_channel(self, name: str, channel: _Channel):
        """注册自定义渠道 (扩展点)"""
        self._channels[name] = channel

    def list_channels(self) -> list[str]:
        """列出可用渠道"""
        return list(self._channels.keys())

    def send(self, payload: NotificationPayload, channel: str = "console") -> bool:
        """发送通知到指定渠道"""
        return self._dispatch(channel, payload)

    def send_all(
        self,
        payload: NotificationPayload,
        channels: list[str] | None = None,
    ) -> dict[str, bool]:
        """发送到多个渠道 (默认使用 config.default_notification_channels)

        Returns:
            {channel_name: success_bool}
        """
        if channels is None:
            channels = self.config.default_notification_channels or ["console"]

        results: dict[str, bool] = {}
        for ch in channels:
            results[ch] = self._dispatch(ch, payload)
        return results

    def _dispatch(self, channel: str, payload: NotificationPayload) -> bool:
        """内部: 调度单个渠道"""
        if not self.config.notification_enabled and channel != "console":
            return False

        ch = self._channels.get(channel)
        if ch is None:
            self.audit.emit(
                AuditEventType.NOTIFICATION_FAILED,
                context={
                    "channel": channel,
                    "error": f"未知渠道: {channel} (可用: {self.list_channels()})",
                    "title": payload.title,
                },
                level="ERROR",
            )
            return False

        try:
            return ch.send(payload, audit=self.audit)
        except Exception as e:
            self.audit.emit(
                AuditEventType.NOTIFICATION_FAILED,
                context={
                    "channel": channel,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "title": payload.title,
                },
                level="ERROR",
            )
            return False


# ============================================================================
# 通知渠道基类
# ============================================================================

class _Channel:
    """渠道抽象基类 — 模板方法模式

    子类需实现:
    - _do_send(payload, audit) -> bool
      返回 True/False (业务结果), 不要 raise 重试友好的错误
      (期望重试时, 让 _http_post 自行 raise RetryableHTTPError/NetworkError)

    基类提供:
    - send(payload, audit) -> bool   (公共入口, 包装重试)
    - send_with_retry(payload, audit) -> bool  (重试编排)
    - _is_retryable_error(e) -> bool  (错误分类)
    - _compute_backoff(attempt) -> float  (退避策略)
    """

    name: str = "base"

    # ============== 重试配置 (从环境变量读取) ==============
    # 子类可覆盖这些类变量
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BACKOFF = 1.0  # 初始退避秒数
    DEFAULT_MAX_BACKOFF = 30.0  # 单次退避上限

    def __init__(self):
        # 可选熔断器 (由 NotificationManager 注入)
        self.circuit_breaker: CircuitBreaker | None = None
        # 可选升级管理器 (由 NotificationManager 注入)
        self.escalation_manager: EscalationManager | None = None

    @classmethod
    def _get_retry_config(cls) -> tuple:
        """读取重试配置 (从环境变量)

        Returns:
            (max_retries, initial_backoff, max_backoff)
        """
        try:
            max_retries = int(os.environ.get("TF_OPS_NOTIFY_MAX_RETRIES", str(cls.DEFAULT_MAX_RETRIES)))
        except ValueError:
            max_retries = cls.DEFAULT_MAX_RETRIES
        try:
            initial_backoff = float(os.environ.get("TF_OPS_NOTIFY_RETRY_BACKOFF", str(cls.DEFAULT_BACKOFF)))
        except ValueError:
            initial_backoff = cls.DEFAULT_BACKOFF
        try:
            max_backoff = float(os.environ.get("TF_OPS_NOTIFY_RETRY_MAX_BACKOFF", str(cls.DEFAULT_MAX_BACKOFF)))
        except ValueError:
            max_backoff = cls.DEFAULT_MAX_BACKOFF
        return max(0, max_retries), max(0.0, initial_backoff), max(initial_backoff, max_backoff)

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        """判断异常是否可重试

        可重试: NetworkError, RetryableHTTPError (5xx/429)
        不可重试: WebhookError, NonRetryableHTTPError, 其他 Exception
        """
        return isinstance(error, NetworkError | RetryableHTTPError)

    @staticmethod
    def _compute_backoff(
        attempt: int,
        initial: float = 1.0,
        maximum: float = 30.0,
        retry_after: float | None = None,
    ) -> float:
        """计算指数退避时延 (秒)

        优先级: Retry-After > 指数退避
        公式: min(initial * 2^attempt, maximum) + jitter

        Args:
            attempt: 0-based 重试次数 (0 = 第一次重试前)
            initial: 初始退避
            maximum: 最大退避
            retry_after: 服务器返回的 Retry-After 值
        """
        if retry_after is not None and retry_after > 0:
            return min(retry_after, maximum)

        # 指数退避: 1, 2, 4, 8, 16, 30, 30, 30...
        delay = initial * (2 ** attempt)
        delay = min(delay, maximum)

        # 加 jitter (0-25%), 避免惊群
        import random
        jitter = delay * 0.25 * random.random()
        return delay + jitter

    def send(self, payload: NotificationPayload, audit: AuditLogger) -> bool:
        """公共入口: 调度重试"""
        return self.send_with_retry(payload, audit)

    def send_with_retry(self, payload: NotificationPayload, audit: AuditLogger) -> bool:
        """带重试的发送

        重试编排:
        1. 检查熔断器 (如开启则直接拒绝)
        2. 首次尝试 (attempt=0)
        3. 如果可重试错误, 计算退避, sleep, 重试
        4. 达到 max_retries 或不可重试错误, 返回 False
        5. 成功/失败 记录到熔断器

        Dry-run 模式 (TF_OPS_DRYRUN_NOTIFICATION=1) 不重试。
        """
        max_retries, initial_backoff, max_backoff = self._get_retry_config()
        # 0 = 禁用重试, 仅尝试 1 次
        # 3 = 首次 + 3 次重试 = 总共 4 次

        # Dry-run: 直接调用一次, 不重试, 不过熔断器
        if _is_dry_run():
            return self._attempt_send(payload, audit, attempt=0)

        # 熔断器: 允许进入调用?
        if self.circuit_breaker is not None:
            try:
                self.circuit_breaker.enter(self.name)
            except CircuitBreakerOpenError as e:
                audit.emit(
                    AuditEventType.NOTIFICATION_FAILED,
                    context={
                        "channel": self.name,
                        "title": payload.title,
                        "error": str(e),
                        "error_type": "CircuitBreakerOpenError",
                        "blocked_by": "circuit_breaker",
                    },
                    level="WARN",
                )
                return False

        # 总尝试次数 = 1 (首次) + max_retries
        for attempt in range(0, max_retries + 1):
            try:
                success = self._attempt_send(payload, audit, attempt=attempt)
                if success:
                    if self.circuit_breaker is not None:
                        self.circuit_breaker.record_success(self.name)
                    return True
                # 业务逻辑返回 False (如 4xx), 不重试
                if self.circuit_breaker is not None:
                    # NonRetryableHTTPError 不会进入这里 (4xx 会 raise),
                    # 但到达这里说明业务错误未走 raise, 记录为不计熔断的失败
                    pass
                return False
            except Exception as e:
                # 熔断器记录失败 (仅在错误被计入时触发熔断)
                if self.circuit_breaker is not None:
                    self.circuit_breaker.record_failure(self.name, e)

                # 获取错误类别 (如存在)
                error_category = getattr(e, "category", None) if hasattr(e, "category") else None

                # P0 错误: 跳过重试, 立即升级告警
                if (
                    self.escalation_manager is not None
                    and error_category is not None
                ):
                    severity, should_escalate = self.escalation_manager.evaluate(
                        self.name, error_category
                    )
                    if should_escalate and severity in (Severity.P0,):
                        # P0: 立即告警, 不再重试
                        self.escalation_manager.escalate(
                            channel=self.name,
                            category=error_category,
                            error=e,
                            payload=payload,
                        )
                        audit.emit(
                            AuditEventType.NOTIFICATION_FAILED,
                            context={
                                "channel": self.name,
                                "title": payload.title,
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "error_category": error_category.value
                                    if hasattr(error_category, "value") else str(error_category),
                                "severity": severity.value,
                                "escalated": True,
                                "retry_skipped": True,
                                "attempt": attempt,
                            },
                            level="ERROR",
                        )
                        return False

                if not self._is_retryable_error(e):
                    # 不可重试错误: 记录并立即返回
                    audit.emit(
                        AuditEventType.NOTIFICATION_FAILED,
                        context={
                            "channel": self.name,
                            "title": payload.title,
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "error_category": getattr(e, "category", "unknown")
                                if hasattr(e, "category") else "unknown",
                            "attempt": attempt,
                            "retryable": False,
                        },
                        level="ERROR",
                    )
                    return False

                # 可重试错误: 判断是否还能重试
                if attempt >= max_retries:
                    # 已达到最大重试次数
                    # 如配置升级 P1, 此时也触发告警
                    if (
                        self.escalation_manager is not None
                        and error_category is not None
                    ):
                        severity, should_escalate = self.escalation_manager.evaluate(
                            self.name, error_category
                        )
                        if should_escalate:
                            self.escalation_manager.escalate(
                                channel=self.name,
                                category=error_category,
                                error=e,
                                payload=payload,
                            )
                    audit.emit(
                        AuditEventType.NOTIFICATION_FAILED,
                        context={
                            "channel": self.name,
                            "title": payload.title,
                            "error": str(e),
                            "error_type": type(e).__name__,
                            "error_category": getattr(e, "category", "unknown")
                                if hasattr(e, "category") else "unknown",
                            "attempts": attempt + 1,
                            "max_retries": max_retries,
                            "retryable": True,
                        },
                        level="ERROR",
                    )
                    return False

                # 计算退避
                retry_after = getattr(e, "retry_after", None)
                backoff = self._compute_backoff(
                    attempt, initial_backoff, max_backoff, retry_after
                )
                # 记录重试
                audit.emit(
                    AuditEventType.NOTIFICATION_RETRY,
                    context={
                        "channel": self.name,
                        "title": payload.title,
                        "attempt": attempt + 1,
                        "next_attempt_in_seconds": round(backoff, 2),
                        "last_error": str(e),
                        "error_type": type(e).__name__,
                        "error_category": getattr(e, "category", "unknown")
                            if hasattr(e, "category") else "unknown",
                    },
                    level="WARN",
                )
                time.sleep(backoff)

        # 不应到达此处, 为防御性编程
        return False

    def _attempt_send(
        self,
        payload: NotificationPayload,
        audit: AuditLogger,
        attempt: int = 0,
    ) -> bool:
        """单次发送尝试 — 子类必须实现

        Returns:
            True: 发送成功
            False: 业务逻辑失败 (4xx等不可重试), 不抛异常

        Raises:
            NetworkError / RetryableHTTPError: 可重试
            WebhookError / NonRetryableHTTPError: 不可重试
        """
        raise NotImplementedError


def _is_dry_run() -> bool:
    """是否处于 dry-run 模式 (不真实发送)"""
    return os.environ.get("TF_OPS_DRYRUN_NOTIFICATION") == "1"


def _http_post(url: str, body: dict[str, Any], timeout: int = 10) -> int:
    """通过 stdlib urllib 发送 POST 请求

    Returns:
        HTTP 状态码

    Raises:
        NetworkError           - 网络/超时/SSL/连接错误 (可重试, 含 category)
        RetryableHTTPError     - HTTP 5xx / 429 (可重试, 含 category 和 Retry-After)
        NonRetryableHTTPError  - HTTP 4xx (不可重试, 排除 429, 含 category)
        WebhookError           - 配置/安全错误 (不可重试)
    """
    import urllib.error
    import urllib.request

    try:
        req = urllib.request.Request(  # nosec - URL 由用户从环境变量配置
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        # HTTP 错误响应 (4xx / 5xx)
        status = e.code
        category = _classify_http_status(status)
        # 尝试读取 Retry-After header
        retry_after: float | None = None
        try:
            ra_header = e.headers.get("Retry-After") if e.headers else None
            if ra_header:
                retry_after = float(ra_header)
        except (ValueError, TypeError):
            retry_after = None

        if status == 429 or 500 <= status < 600:
            raise RetryableHTTPError(
                f"HTTP {status}: {e.reason}",
                status_code=status,
                category=category,
                retry_after=retry_after,
            ) from e
        # 4xx (除 429) - 不可重试
        raise NonRetryableHTTPError(
            f"HTTP {status}: {e.reason}",
            status_code=status,
            category=category,
        ) from e
    except urllib.error.URLError as e:
        # DNS/连接错误
        cause = e.reason if hasattr(e, "reason") else e
        raise NetworkError(
            f"HTTP POST 失败: {e}",
            category=_classify_network_error(cause),
        ) from e
    except (TimeoutError, OSError) as e:
        # 超时 / 网络层错误
        raise NetworkError(
            f"HTTP POST 失败: {e}",
            category=_classify_network_error(e),
        ) from e
    except Exception as e:
        # 其他未知错误 (SSL证书错误等) — 保守地视为可重试
        raise NetworkError(
            f"HTTP POST 失败: {e}",
            category=_classify_network_error(e),
        ) from e


# ============================================================================
# Console 渠道
# ============================================================================

class _ConsoleChannel(_Channel):
    name = "console"

    def __init__(self, enabled: bool = True):
        super().__init__()
        self.enabled = enabled

    def _attempt_send(
        self,
        payload: NotificationPayload,
        audit: AuditLogger,
        attempt: int = 0,
    ) -> bool:
        prefix_map = {
            "info": "[INFO]",
            "warning": "[WARN]",
            "error": "[ERROR]",
            "success": "[OK]",
        }
        prefix = prefix_map.get(payload.level, "[INFO]")
        if self.enabled:
            print(f"{prefix} {payload.title}")
        if payload.message:
            for line in payload.message.splitlines():
                print(f"    {line}")
        if payload.url:
            print(f"    → {payload.url}")
        audit.emit(
            AuditEventType.NOTIFICATION_SENT,
            context={"channel": "console", "title": payload.title, "attempt": attempt},
        )
        return True


# ============================================================================
# 钉钉渠道 — https://open.dingtalk.com/document/orgapp/custom-robot-access
# ============================================================================

class _DingTalkChannel(_Channel):
    """钉钉自定义机器人 webhook

    - 消息格式: markdown
    - 安全: 支持加签 (从 DINGTALK_WEBHOOK_SECRET 环境变量读取)
    - 安全: webhook URL 强制从环境变量, 禁止字面量 token
    """
    name = "dingtalk"

    def __init__(self, webhook_url: str | None, webhook_env: str, secret: str | None = None):
        super().__init__()
        self.webhook_url = webhook_url
        self.webhook_env = webhook_env
        self.secret = secret

    def build_message(self, payload: NotificationPayload) -> dict[str, Any]:
        """构造钉钉 markdown 消息"""
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": payload.title,
                "text": f"## {payload.title}\n\n{payload.message}\n\n"
                + (f"[查看详情]({payload.url})" if payload.url else ""),
            },
        }

    def _sign(self) -> dict[str, str]:
        """加签 (钉钉可选安全机制)"""
        if not self.secret:
            return {}
        import base64
        import hashlib
        import hmac
        import urllib.parse
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            self.secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return {"timestamp": timestamp, "sign": sign}

    def _attempt_send(
        self,
        payload: NotificationPayload,
        audit: AuditLogger,
        attempt: int = 0,
    ) -> bool:
        """钉钉发送实现 (由基类 send_with_retry 调用)"""
        if not self.webhook_url:
            audit.emit(
                AuditEventType.NOTIFICATION_FAILED,
                context={
                    "channel": "dingtalk",
                    "reason": f"webhook 未配置 (需要设置环境变量 {self.webhook_env})",
                },
                level="WARN",
            )
            return False

        body = self.build_message(payload)
        if self.secret:
            body.update(self._sign())

        # Dry-run: 跳过安全检查和实际 HTTP (仅记录)
        if _is_dry_run():
            print(f"[DRY-RUN 钉钉] {payload.title}")
            audit.emit(
                AuditEventType.NOTIFICATION_SENT,
                context={"channel": "dingtalk", "title": payload.title, "dry_run": True, "attempt": attempt},
            )
            return True

        # 安全检查 (不可重试: WebhookError)
        # 必须在实际发送前检查, 但在 dry-run 之后 (避免误报)
        if NotificationManager._TOKEN_PATTERN.search(self.webhook_url):
            raise WebhookError("钉钉 webhook URL 中含有可疑 token 字面量，请使用环境变量引用")

        # _http_post 会在 4xx/5xx/网络错误时 raise 对应异常
        # 基类 send_with_retry 会判断是否可重试
        status = _http_post(self.webhook_url, body)
        success = 200 <= status < 300
        audit.emit(
            AuditEventType.NOTIFICATION_SENT if success else AuditEventType.NOTIFICATION_FAILED,
            context={
                "channel": "dingtalk",
                "http_status": status,
                "title": payload.title,
                "attempt": attempt,
            },
            level="INFO" if success else "ERROR",
        )
        return success


# ============================================================================
# 飞书渠道 — https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
# ============================================================================

class _FeishuChannel(_Channel):
    """飞书自定义机器人 webhook

    - 消息格式: interactive card (推荐) / text (备选)
    - 安全: 支持签名校验 (从 FEISHU_WEBHOOK_SECRET 环境变量读取)
    - 安全: webhook URL 强制从环境变量
    """
    name = "feishu"

    def __init__(self, webhook_url: str | None, webhook_env: str, secret: str | None = None):
        super().__init__()
        self.webhook_url = webhook_url
        self.webhook_env = webhook_env
        self.secret = secret

    def build_message(self, payload: NotificationPayload) -> dict[str, Any]:
        """构造飞书交互式卡片消息

        飞书推荐使用 interactive 卡片, 支持标题/多字段/链接, 体验优于纯文本
        """
        # 颜色映射 (与飞书 card header template 对应)
        color_map = {
            "info": "blue",
            "success": "green",
            "warning": "orange",
            "error": "red",
        }
        template = color_map.get(payload.level, "blue")

        # 消息内容 (支持 markdown)
        body_lines = []
        if payload.message:
            body_lines.append(payload.message)
        if payload.url:
            body_lines.append(f"\n[View Details]({payload.url})")

        elements: list[dict[str, Any]] = []
        if body_lines:
            elements.append({
                "tag": "markdown",
                "content": "\n".join(body_lines),
            })
        if payload.url:
            elements.append({
                "tag": "action",
                "actions": [{
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": "查看详情"},
                    "type": "primary",
                    "url": payload.url,
                }],
            })

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": payload.title,
                    },
                    "template": template,
                },
                "elements": elements,
            },
        }

    def _sign(self) -> str:
        """飞书签名校验 (timestamp + sign)

        签名字符串: timestamp + "\n" + secret
        HMAC-SHA256, base64 编码
        """
        if not self.secret:
            return ""
        import base64
        import hashlib
        import hmac
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def _attempt_send(
        self,
        payload: NotificationPayload,
        audit: AuditLogger,
        attempt: int = 0,
    ) -> bool:
        """飞书发送实现 (由基类 send_with_retry 调用)"""
        if not self.webhook_url:
            audit.emit(
                AuditEventType.NOTIFICATION_FAILED,
                context={
                    "channel": "feishu",
                    "reason": f"webhook 未配置 (需要设置环境变量 {self.webhook_env})",
                },
                level="WARN",
            )
            return False

        body = self.build_message(payload)

        # Dry-run: 跳过签名/安全检查/实际 HTTP
        if _is_dry_run():
            print(f"[DRY-RUN 飞书] {payload.title}")
            audit.emit(
                AuditEventType.NOTIFICATION_SENT,
                context={"channel": "feishu", "title": payload.title, "dry_run": True, "attempt": attempt},
            )
            return True

        # 安全检查 (不可重试: WebhookError)
        if NotificationManager._TOKEN_PATTERN.search(self.webhook_url):
            raise WebhookError("飞书 webhook URL 中含有可疑 token 字面量，请使用环境变量引用")

        # 签名 (timestamp + sign 作为 query string, 不在 body 内)
        url = self.webhook_url
        if self.secret:
            timestamp = str(int(time.time()))
            sign = self._sign()
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}timestamp={timestamp}&sign={sign}"

        # _http_post 会在 4xx/5xx/网络错误时 raise 对应异常
        status = _http_post(url, body)
        success = 200 <= status < 300
        audit.emit(
            AuditEventType.NOTIFICATION_SENT if success else AuditEventType.NOTIFICATION_FAILED,
            context={
                "channel": "feishu",
                "http_status": status,
                "title": payload.title,
                "attempt": attempt,
            },
            level="INFO" if success else "ERROR",
        )
        return success


# ============================================================================
# 企业微信渠道 — https://developer.work.weixin.qq.com/document/path/91770
# ============================================================================

class _WeComChannel(_Channel):
    """企业微信群机器人 webhook

    - 消息格式: markdown (支持 @提醒, 但需要 mentioned_list)
    - 安全: webhook URL 强制从环境变量
    """
    name = "wecom"

    def __init__(self, webhook_url: str | None, webhook_env: str):
        super().__init__()
        self.webhook_url = webhook_url
        self.webhook_env = webhook_env

    def build_message(self, payload: NotificationPayload) -> dict[str, Any]:
        """构造企业微信 markdown 消息"""
        content_parts = [f"## {payload.title}"]
        if payload.message:
            content_parts.append("")
            content_parts.append(payload.message)
        if payload.url:
            content_parts.append("")
            content_parts.append(f"[查看详情]({payload.url})")

        return {
            "msgtype": "markdown",
            "markdown": {
                "content": "\n".join(content_parts),
            },
        }

    def _attempt_send(
        self,
        payload: NotificationPayload,
        audit: AuditLogger,
        attempt: int = 0,
    ) -> bool:
        """企业微信发送实现 (由基类 send_with_retry 调用)"""
        if not self.webhook_url:
            audit.emit(
                AuditEventType.NOTIFICATION_FAILED,
                context={
                    "channel": "wecom",
                    "reason": f"webhook 未配置 (需要设置环境变量 {self.webhook_env})",
                },
                level="WARN",
            )
            return False

        body = self.build_message(payload)

        # Dry-run: 跳过安全检查和实际 HTTP
        if _is_dry_run():
            print(f"[DRY-RUN 企业微信] {payload.title}")
            audit.emit(
                AuditEventType.NOTIFICATION_SENT,
                context={"channel": "wecom", "title": payload.title, "dry_run": True, "attempt": attempt},
            )
            return True

        # 安全检查 (不可重试: WebhookError)
        if NotificationManager._TOKEN_PATTERN.search(self.webhook_url):
            raise WebhookError("企业微信 webhook URL 中含有可疑 token 字面量，请使用环境变量引用")

        # _http_post 会在 4xx/5xx/网络错误时 raise 对应异常
        status = _http_post(self.webhook_url, body)
        success = 200 <= status < 300
        audit.emit(
            AuditEventType.NOTIFICATION_SENT if success else AuditEventType.NOTIFICATION_FAILED,
            context={
                "channel": "wecom",
                "http_status": status,
                "title": payload.title,
                "attempt": attempt,
            },
            level="INFO" if success else "ERROR",
        )
        return success


# ============================================================================
# Slack 渠道 (占位 — 保持向后兼容)
# ============================================================================

class _SlackChannel(_Channel):
    """Slack webhook (占位实现)"""
    name = "slack"

    def _attempt_send(
        self,
        payload: NotificationPayload,
        audit: AuditLogger,
        attempt: int = 0,
    ) -> bool:
        # 与原版保持一致: 仅记录到审计
        audit.emit(
            AuditEventType.NOTIFICATION_SENT,
            context={"channel": "slack", "title": payload.title, "stub": True, "attempt": attempt},
        )
        return True


# ============================================================================
# TTL 解析
# ============================================================================

def parse_ttl(ttl_str: str) -> timedelta:
    """解析 TTL 字符串 (如 '7d', '24h', '30m')"""
    match = re.match(r"^(\d+)([smhd])$", ttl_str.strip().lower())
    if not match:
        raise ConfigError(f"无效的 TTL 格式: {ttl_str} (支持: 30s/15m/24h/7d)")

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "s":
        return timedelta(seconds=value)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    raise ConfigError(f"不支持的 TTL 单位: {unit}")


# ============================================================================
# 工具函数
# ============================================================================

def now_iso() -> str:
    """当前时间的 ISO 格式"""
    return datetime.utcnow().isoformat() + "Z"


def safe_load_json(path: Path) -> dict[str, Any] | None:
    """安全加载 JSON 文件"""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def redact_secrets(data: dict[str, Any]) -> dict[str, Any]:
    """脱敏数据中的敏感字段"""
    sensitive_keys = {
        "password", "secret", "token", "api_key", "access_key",
        "webhook", "credential", "private_key",
    }
    redacted: dict[str, Any] = {}
    for k, v in data.items():
        if any(s in k.lower() for s in sensitive_keys):
            redacted[k] = "****"
        elif isinstance(v, dict):
            redacted[k] = redact_secrets(v)
        else:
            redacted[k] = v
    return redacted
