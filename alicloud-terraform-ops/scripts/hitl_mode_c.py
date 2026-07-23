#!/usr/bin/env python3
"""
HITL Mode C - CheckPoint Pause
人机介入模式C: 检查点暂停与恢复 (会话驱动)

支持:
- 会话状态持久化 (CheckpointStore)
- 暂停/恢复主循环 (PauseController)
- 资源分级 (PASS/WARN/SKIP) 与多选 UI (BatchSelector)
- 过期管理 (CheckpointExpirationManager)
- 漂移检测 (DriftDetector)
- 错误处理 (CheckpointErrorHandler)
- 与 Reverse Engineering 集成

Python 3.10+ 标准库实现，零外部依赖。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

try:
    from hitl_common import (
        AuditEvent,
        AuditEventType,
        AuditLogger,
        CheckpointErrorHandler,
        CLIErrorHandler,
        ConfigError,
        ErrorAction,
        ExpiredError,
        HITLConfig,
        NotificationManager,
        NotificationPayload,
        now_iso,
        parse_ttl,
        safe_load_json,
    )
    from hitl_mode_a import (
        Action,
        Checkpoint,
        CheckpointStatus,
        CheckpointStore,
        CheckpointType,
        Colors,
        Environment,
        EnvironmentPolicy,
        ResourceInfo,
        Step,
        StepResult,
        StepType,
        UserAbortedError,
    )
except ImportError:
    from scripts.hitl_common import (  # type: ignore
        AuditEventType,
        AuditLogger,
        HITLConfig,
        parse_ttl,
        safe_load_json,
    )
    from scripts.hitl_mode_a import (  # type: ignore
        Action,
        Checkpoint,
        CheckpointStatus,
        CheckpointStore,
        Colors,
        Environment,
        ResourceInfo,
        Step,
        StepResult,
    )


# ============================================================================
# 资源分级 — spec §10.3 资源分级
# ============================================================================

class ResourceClassification(str, Enum):
    """资源分类"""
    PASS = "pass"  # 可自动导入
    WARN = "warn"  # 需要确认
    SKIP = "skip"  # 不支持


@dataclass
class ClassifiedResource:
    """已分类的资源"""
    resource: ResourceInfo
    classification: ResourceClassification
    reason: str = ""
    warning: str | None = None
    selected: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": {
                "type": self.resource.resource_type,
                "name": self.resource.name,
                "id": self.resource.id,
                "status": self.resource.status,
                "attributes": self.resource.attributes,
            },
            "classification": self.classification.value,
            "reason": self.reason,
            "warning": self.warning,
            "selected": self.selected,
            "extra": self.extra,
        }


@dataclass
class SelectionResult:
    """选择结果"""
    selected_resources: list[ClassifiedResource] = field(default_factory=list)
    skipped_resources: list[ClassifiedResource] = field(default_factory=list)
    warned_resources: list[ClassifiedResource] = field(default_factory=list)
    selection_mode: str = "default"  # default / custom / all / dry-run


# ============================================================================
# 资源分类器 — spec §5
# ============================================================================

class ResourceClassifier:
    """资源分类器

    根据资源能力 (capability) 和已知问题将资源分为 PASS / WARN / SKIP
    """

    # 已知需要 WARN 的资源类型 (含敏感配置/复杂规则)
    WARN_TYPES = {
        "rds": "数据库含白名单/参数组敏感配置",
        "redis": "Redis 含 Tair 专有配置",
        "slb": "SLB 监听规则复杂，可能有后端健康检查差异",
        "nat_gateway": "NAT 网关涉及 SNAT/DNAT 规则",
        "vpn_gateway": "VPN 网关含 SSL 配置",
    }

    # 已知不支持的资源类型
    SKIP_TYPES = {
        "custom_image": "自定义镜像暂不支持导入",
        "snapshot": "快照数据量大，建议手动处理",
        "ram_role_attachment": "RAM 角色绑定关系复杂",
    }

    def __init__(self, audit: AuditLogger):
        self.audit = audit

    def classify(self, resources: list[ResourceInfo]) -> list[ClassifiedResource]:
        """对资源列表进行分类"""
        classified: list[ClassifiedResource] = []

        for r in resources:
            rtype = r.resource_type.lower()

            # 1. SKIP 优先
            if rtype in self.SKIP_TYPES:
                classified.append(ClassifiedResource(
                    resource=r,
                    classification=ResourceClassification.SKIP,
                    reason=self.SKIP_TYPES[rtype],
                    selected=False,
                ))
                continue

            # 2. WARN (有警告标记或类型匹配)
            if r.warnings or rtype in self.WARN_TYPES:
                warning = r.warnings[0] if r.warnings else self.WARN_TYPES[rtype]
                classified.append(ClassifiedResource(
                    resource=r,
                    classification=ResourceClassification.WARN,
                    reason="需确认",
                    warning=warning,
                    selected=False,  # WARN 默认不自动选中
                ))
                continue

            # 3. PASS
            classified.append(ClassifiedResource(
                resource=r,
                classification=ResourceClassification.PASS,
                reason="可安全导入",
                selected=True,
            ))

        return classified


# ============================================================================
# 批量选择器 — spec §5.4
# ============================================================================

class BatchSelector:
    """批量资源选择器

    提供交互式多选 UI (命令行简化版，支持 dry-run 渲染)
    """

    def __init__(self, audit: AuditLogger, use_color: bool = True):
        self.audit = audit
        self.use_color = use_color and sys.stdout.isatty()

    def _c(self, color: str, text: str) -> str:
        if self.use_color:
            return f"{color}{text}{Colors.RESET}"
        return text

    def render(self, classified: list[ClassifiedResource], title: str = "资源导入选择") -> None:
        """渲染分组选择界面 (dry-run / 只读模式)"""
        print()
        print(self._c(Colors.BOLD + Colors.CYAN, f"=== {title} ==="))
        print()

        groups = self._group_by_classification(classified)

        # PASS 组
        if groups[ResourceClassification.PASS]:
            print(self._c(Colors.GREEN, "[PASS] 可安全导入"))
            for cr in groups[ResourceClassification.PASS]:
                mark = "x" if cr.selected else " "
                _dim = self._c(Colors.DIM, "(" + (cr.resource.id or "-") + ")")
                print(f"  [{mark}] {cr.resource.resource_type}: {cr.resource.name} {_dim}")

        # WARN 组
        if groups[ResourceClassification.WARN]:
            print()
            print(self._c(Colors.YELLOW, "[WARN] 需要确认"))
            for cr in groups[ResourceClassification.WARN]:
                mark = "x" if cr.selected else " "
                _dim = self._c(Colors.DIM, "(" + (cr.resource.id or "-") + ")")
                print(f"  [{mark}] {cr.resource.resource_type}: {cr.resource.name} {_dim}")
                if cr.warning:
                    print(f"      {self._c(Colors.YELLOW, '⚠ ' + cr.warning)}")

        # SKIP 组
        if groups[ResourceClassification.SKIP]:
            print()
            print(self._c(Colors.RED, "[SKIP] 不支持"))
            for cr in groups[ResourceClassification.SKIP]:
                mark = " "  # SKIP 永远不可选
                _dim = self._c(Colors.DIM, "(" + (cr.resource.id or "-") + ")")
                print(f"  [{mark}] {cr.resource.resource_type}: {cr.resource.name} {_dim}")
                print(f"      {self._c(Colors.RED, '✗ ' + cr.reason)}")

        # 统计
        total = len(classified)
        selected = sum(1 for cr in classified if cr.selected)
        print()
        print(self._c(Colors.DIM, f"已选择: {selected}/{total}"))

    def select_interactive(
        self,
        classified: list[ClassifiedResource],
    ) -> SelectionResult:
        """交互式选择 (完整流程)"""
        # 1. 渲染初始状态
        self.render(classified)

        # 2. 询问选择模式
        print()
        print(self._c(Colors.BOLD, "请选择操作模式:"))
        print(f"  [1] 导入全部 [PASS] ({sum(1 for c in classified if c.classification == ResourceClassification.PASS)} 个)")
        print(f"  [2] 逐一审核 [WARN] ({sum(1 for c in classified if c.classification == ResourceClassification.WARN)} 个)")
        print("  [3] 自定义选择")
        print("  [4] 干运行 (dry-run)")
        print("  [5] 保存并退出 (稍后继续)")

        try:
            choice = input("\n请选择 [1-5]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            choice = "5"  # 默认保存退出

        if choice == "1":
            return self._select_all_pass(classified)
        if choice == "2":
            return self._review_warn(classified)
        if choice == "3":
            return self._select_custom(classified)
        if choice == "4":
            result = SelectionResult(
                selected_resources=list(classified),
                selection_mode="dry-run",
            )
            for cr in classified:
                cr.selected = True
            return result
        if choice == "5":
            return SelectionResult(selection_mode="save-and-exit")

        return SelectionResult(selection_mode="default")

    def _select_all_pass(self, classified: list[ClassifiedResource]) -> SelectionResult:
        """模式 1: 导入全部 PASS"""
        for cr in classified:
            cr.selected = cr.classification == ResourceClassification.PASS

        result = SelectionResult(
            selected_resources=[cr for cr in classified if cr.selected],
            skipped_resources=[cr for cr in classified if cr.classification == ResourceClassification.SKIP],
            warned_resources=[cr for cr in classified if cr.classification == ResourceClassification.WARN and not cr.selected],
            selection_mode="all-pass",
        )

        self.audit.emit(
            AuditEventType.STEP_EXECUTED,
            context={
                "action": "batch.select",
                "mode": "all-pass",
                "selected": len(result.selected_resources),
            },
        )
        return result

    def _review_warn(self, classified: list[ClassifiedResource]) -> SelectionResult:
        """模式 2: 逐一审核 WARN"""
        # PASS 自动选中
        for cr in classified:
            if cr.classification == ResourceClassification.PASS:
                cr.selected = True
            elif cr.classification == ResourceClassification.SKIP:
                cr.selected = False

        # WARN 逐个询问
        for cr in classified:
            if cr.classification != ResourceClassification.WARN:
                continue
            print()
            print(self._c(Colors.BOLD, f"资源: {cr.resource.resource_type} - {cr.resource.name}"))
            if cr.resource.id:
                print(f"  ID: {cr.resource.id}")
            if cr.warning:
                print(f"  {self._c(Colors.YELLOW, '⚠ ' + cr.warning)}")
            try:
                ans = input(f"  {self._c(Colors.CYAN, '导入? [Y/n/skip]')} ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = "n"
            cr.selected = ans in ("y", "yes", "")

        result = SelectionResult(
            selected_resources=[cr for cr in classified if cr.selected],
            skipped_resources=[cr for cr in classified if not cr.selected],
            warned_resources=[cr for cr in classified if cr.classification == ResourceClassification.WARN],
            selection_mode="review-warn",
        )

        self.audit.emit(
            AuditEventType.STEP_EXECUTED,
            context={
                "action": "batch.select",
                "mode": "review-warn",
                "selected": len(result.selected_resources),
            },
        )
        return result

    def _select_custom(self, classified: list[ClassifiedResource]) -> SelectionResult:
        """模式 3: 自定义选择 (简化版: 编号输入)"""
        print()
        print("自定义选择 (输入资源编号列表，逗号分隔；输入 a 全选；输入 q 取消):")

        for i, cr in enumerate(classified, 1):
            status = cr.classification.value.upper()
            mark = "x" if cr.selected else " "
            print(f"  [{mark}] {i}. {cr.resource.resource_type} - {cr.resource.name} [{status}]")

        try:
            ans = input("\n选择 (例: 1,3,5 或 a): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "q"

        if ans == "q":
            return SelectionResult(selection_mode="custom-cancelled")

        if ans == "a":
            for cr in classified:
                if cr.classification != ResourceClassification.SKIP:
                    cr.selected = True
        else:
            try:
                indices = {int(x.strip()) - 1 for x in ans.split(",") if x.strip()}
                for i, cr in enumerate(classified):
                    if cr.classification == ResourceClassification.SKIP:
                        cr.selected = False
                    else:
                        cr.selected = i in indices
            except ValueError:
                print(f"  {self._c(Colors.RED, '✗ 无效输入')}")
                return self._select_custom(classified)

        result = SelectionResult(
            selected_resources=[cr for cr in classified if cr.selected],
            skipped_resources=[cr for cr in classified if not cr.selected and cr.classification != ResourceClassification.SKIP],
            warned_resources=[cr for cr in classified if cr.classification == ResourceClassification.WARN],
            selection_mode="custom",
        )

        self.audit.emit(
            AuditEventType.STEP_EXECUTED,
            context={
                "action": "batch.select",
                "mode": "custom",
                "selected": len(result.selected_resources),
            },
        )
        return result

    @staticmethod
    def _group_by_classification(
        classified: list[ClassifiedResource],
    ) -> dict[ResourceClassification, list[ClassifiedResource]]:
        groups: dict[ResourceClassification, list[ClassifiedResource]] = {
            ResourceClassification.PASS: [],
            ResourceClassification.WARN: [],
            ResourceClassification.SKIP: [],
        }
        for cr in classified:
            groups[cr.classification].append(cr)
        return groups


# ============================================================================
# 漂移检测 — spec §5.3
# ============================================================================

@dataclass
class DriftReport:
    """漂移报告"""
    has_drift: bool
    changes: list[dict[str, Any]] = field(default_factory=list)
    missing_resources: list[str] = field(default_factory=list)  # 已不存在
    unexpected_resources: list[str] = field(default_factory=list)  # 新出现
    attribute_changes: dict[str, dict[str, tuple[Any, Any]]] = field(default_factory=dict)
    # resource_id -> {attr_name: (old_value, new_value)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_drift": self.has_drift,
            "changes_count": len(self.changes),
            "missing_resources": self.missing_resources,
            "unexpected_resources": self.unexpected_resources,
            "attribute_changes": {
                k: {ak: list(av) for ak, av in v.items()}
                for k, v in self.attribute_changes.items()
            },
        }


class DriftDetector:
    """漂移检测器

    对比检查点中的资源状态与当前阿里云资源状态
    """

    def __init__(self, audit: AuditLogger):
        self.audit = audit

    def detect(
        self,
        checkpoint: Checkpoint,
        current_resources: list[ResourceInfo] | None = None,
    ) -> DriftReport:
        """检测漂移

        简化实现: 通过 aliyun CLI 查询实际资源，与 checkpoint 中的 resources 对比
        """
        report = DriftReport(has_drift=False)

        # 如果没有提供 current_resources，跳过实际查询 (测试场景)
        if current_resources is None:
            return report

        # 1. 构建当前资源 ID 集合
        current_ids = {r.id for r in current_resources if r.id}
        checkpoint_ids = {r.id for r in checkpoint.resources if r.id}

        # 2. 检测消失的资源
        report.missing_resources = list(checkpoint_ids - current_ids)

        # 3. 检测新增资源 (可选)
        report.unexpected_resources = list(current_ids - checkpoint_ids)

        # 4. 属性变化检测
        cp_by_id = {r.id: r for r in checkpoint.resources if r.id}
        cur_by_id = {r.id: r for r in current_resources if r.id}
        for rid in checkpoint_ids & current_ids:
            cp_res = cp_by_id[rid]
            cur_res = cur_by_id[rid]
            changes = {}
            for attr, cp_val in cp_res.attributes.items():
                cur_val = cur_res.attributes.get(attr)
                if cur_val != cp_val:
                    changes[attr] = (cp_val, cur_val)
            if changes:
                report.attribute_changes[rid] = changes

        # 5. 综合判断
        report.has_drift = bool(
            report.missing_resources
            or report.unexpected_resources
            or report.attribute_changes
        )

        if report.has_drift:
            self.audit.emit(
                AuditEventType.DRIFT_DETECTED,
                checkpoint_id=checkpoint.id,
                context=report.to_dict(),
                level="WARN",
            )

        return report


# ============================================================================
# 会话恢复器 — spec §5.3
# ============================================================================

@dataclass
class RecoveryResult:
    """恢复结果"""
    success: bool
    checkpoint: Checkpoint | None = None
    drift: DriftReport | None = None
    warning: str | None = None
    error: str | None = None
    can_resume: bool = False
    next_action: str | None = None
    pending_steps: list[Step] = field(default_factory=list)


class SessionRecovery:
    """会话恢复管理 — spec §5.3"""

    def __init__(
        self,
        store: CheckpointStore,
        drift_detector: DriftDetector,
        audit: AuditLogger,
    ):
        self.store = store
        self.drift_detector = drift_detector
        self.audit = audit

    def resume(
        self,
        checkpoint_id: str,
        current_resources: list[ResourceInfo] | None = None,
    ) -> RecoveryResult:
        """恢复检查点"""
        self.audit.emit(
            AuditEventType.RECOVERY_STARTED,
            checkpoint_id=checkpoint_id,
        )

        # 1. 加载检查点
        try:
            checkpoint = self.store.load(checkpoint_id)
        except FileNotFoundError:
            return RecoveryResult(success=False, error=f"检查点不存在: {checkpoint_id}")
        except json.JSONDecodeError as e:
            return RecoveryResult(
                success=False,
                error=f"检查点文件损坏: {e}",
            )

        if checkpoint is None:
            return RecoveryResult(success=False, error=f"检查点不存在: {checkpoint_id}")

        # 2. 验证有效性
        if checkpoint.is_expired():
            return RecoveryResult(
                success=False,
                error=f"检查点已过期: {checkpoint_id} (过期时间: {checkpoint.expires_at})",
            )

        # 3. 恢复上下文
        self._restore_context(checkpoint)

        # 4. 检测漂移
        drift = self.drift_detector.detect(checkpoint, current_resources)
        warning = None
        if drift.has_drift:
            warning = (
                f"检测到资源漂移: 消失 {len(drift.missing_resources)} 个, "
                f"新增 {len(drift.unexpected_resources)} 个, "
                f"属性变化 {len(drift.attribute_changes)} 个"
            )

        # 5. 恢复检查点状态
        checkpoint.resume()
        self.store.save(checkpoint)

        # 6. 确定 next_action
        pending_steps = checkpoint.get_pending_steps()
        next_action = None
        if pending_steps:
            next_action = pending_steps[0].type.value

        self.audit.emit(
            AuditEventType.RECOVERY_COMPLETED,
            checkpoint_id=checkpoint_id,
            context={
                "drift_detected": drift.has_drift,
                "pending_steps": [s.type.value for s in pending_steps],
                "next_action": next_action,
            },
        )

        return RecoveryResult(
            success=True,
            checkpoint=checkpoint,
            drift=drift,
            warning=warning,
            can_resume=True,
            next_action=next_action,
            pending_steps=pending_steps,
        )

    def _restore_context(self, checkpoint: Checkpoint) -> dict[str, Any]:
        """恢复执行上下文 — spec §5.3

        子类/调用方可以扩展此方法以恢复生成的文件、临时数据等
        """
        return {
            "resources_count": len(checkpoint.resources),
            "generated_files": list(checkpoint.generated_files.keys()),
            "completed_steps": [s.type.value for s in checkpoint.steps
                              if s.status == CheckpointStatus.COMPLETED],
        }


# ============================================================================
# 检查点过期管理器 — spec §5
# ============================================================================

class CheckpointExpirationManager:
    """检查点过期管理器

    - 自动清理过期检查点
    - 按环境差异化 TTL
    """

    def __init__(
        self,
        store: CheckpointStore,
        config: HITLConfig,
        audit: AuditLogger,
    ):
        self.store = store
        self.config = config
        self.audit = audit

    def cleanup_expired(self, dry_run: bool = False) -> list[str]:
        """清理过期检查点

        Returns:
            被删除/将删除的检查点 ID 列表
        """
        expired: list[str] = []
        all_checkpoints: list[Checkpoint] = []
        for filepath in self.store.base_path.glob("*.json"):
            if filepath.suffix == ".json" and filepath.name.endswith(".json.bak"):
                continue
            cp = self.store.load(filepath.stem)
            if cp is not None:
                all_checkpoints.append(cp)

        for cp in all_checkpoints:
            if cp.is_expired():
                expired.append(cp.id)
                if not dry_run:
                    self._delete_checkpoint(cp.id)
                    self.audit.emit(
                        AuditEventType.CHECKPOINT_EXPIRED,
                        checkpoint_id=cp.id,
                        context={"action": "auto_cleanup"},
                    )
                else:
                    self.audit.emit(
                        AuditEventType.CHECKPOINT_EXPIRED,
                        checkpoint_id=cp.id,
                        context={"action": "dry_run"},
                    )

        return expired

    def _delete_checkpoint(self, checkpoint_id: str):
        """删除检查点文件 (含备份)"""
        filepath = self.store.base_path / f"{checkpoint_id}.json"
        backup = self.store.base_path / f"{checkpoint_id}.json.bak"
        if filepath.exists():
            filepath.unlink()
        if backup.exists():
            backup.unlink()
        self.audit.emit(
            AuditEventType.CHECKPOINT_DELETED,
            checkpoint_id=checkpoint_id,
        )

    def extend_ttl(self, checkpoint_id: str, new_ttl: str) -> bool:
        """延长检查点 TTL"""
        try:
            cp = self.store.load(checkpoint_id)
        except (FileNotFoundError, json.JSONDecodeError):
            return False

        if cp is None:
            return False

        ttl = parse_ttl(new_ttl)
        cp.expires_at = datetime.now() + ttl
        self.store.save(cp)
        return True

    def get_ttl_for_env(self, env: Environment) -> timedelta:
        """根据环境获取 TTL"""
        env_ttls = {
            Environment.PRODUCTION: self.config.checkpoint_production_ttl,
            Environment.UAT: "14d",
            Environment.PERFORMANCE: "7d",
            Environment.DEV: self.config.checkpoint_default_ttl,
            Environment.INT: "3d",
        }
        ttl_str = env_ttls.get(env, self.config.checkpoint_default_ttl)
        return parse_ttl(ttl_str)


# ============================================================================
# 暂停控制器 — spec §10.3 状态机
# ============================================================================

class PauseController:
    """暂停控制器

    负责:
    - 在每个步骤后保存检查点
    - 接收暂停信号 (Ctrl+C / 用户输入 q)
    - 处理保存/恢复逻辑
    """

    def __init__(
        self,
        store: CheckpointStore,
        audit: AuditLogger,
        ui_callback: Callable[[str], None] | None = None,
    ):
        self.store = store
        self.audit = audit
        self.ui_callback = ui_callback or print
        self._interrupted = False

    def request_interrupt(self):
        """外部请求中断 (信号处理调用)"""
        self._interrupted = True

    def is_interrupted(self) -> bool:
        return self._interrupted

    def save_progress(
        self,
        checkpoint: Checkpoint,
        step: Step | None = None,
        result: StepResult | None = None,
    ) -> Path:
        """保存进度"""
        if step and result:
            checkpoint.complete_step(step, result)
        checkpoint.pause()
        filepath = self.store.save(checkpoint)

        self.audit.emit(
            AuditEventType.CHECKPOINT_PAUSED,
            checkpoint_id=checkpoint.id,
            context={
                "current_step": checkpoint.current_step_index,
                "saved_to": str(filepath),
            },
        )

        self.ui_callback(
            f"\n[CHECKPOINT] 已保存到 {filepath}\n"
            f"  ID: {checkpoint.id}\n"
            f"  状态: {checkpoint.status.value}\n"
            f"  可使用 `terraform-ops resume {checkpoint.id}` 继续"
        )

        return filepath

    def run_with_pause(
        self,
        checkpoint: Checkpoint,
        step_executor: Callable[[Step], StepResult],
    ) -> Checkpoint:
        """运行检查点直至完成/暂停/中止

        Args:
            checkpoint: 检查点
            step_executor: 步骤执行函数 (返回 StepResult)
        """
        checkpoint.status = CheckpointStatus.RUNNING
        self._interrupted = False

        for step in checkpoint.get_pending_steps():
            if self._interrupted:
                self.save_progress(checkpoint)
                return checkpoint

            step.status = CheckpointStatus.RUNNING
            step.started_at = datetime.now()
            self.store.save(checkpoint)

            try:
                result = step_executor(step)
            except Exception as e:
                self.audit.emit(
                    AuditEventType.CHECKPOINT_PAUSED,
                    checkpoint_id=checkpoint.id,
                    context={"error": str(e), "error_type": type(e).__name__},
                    level="ERROR",
                )
                self.save_progress(checkpoint)
                raise

            if result.action == Action.PAUSE:
                self.save_progress(checkpoint, step, result)
                return checkpoint

            if result.action == Action.ABORT:
                checkpoint.abort(result.reason or "用户中止")
                self.store.save(checkpoint)
                self.audit.emit(
                    AuditEventType.CHECKPOINT_PAUSED,
                    checkpoint_id=checkpoint.id,
                    context={"reason": "user_abort"},
                )
                return checkpoint

            checkpoint.complete_step(step, result)
            self.store.save(checkpoint)

        checkpoint.status = CheckpointStatus.COMPLETED
        self.store.save(checkpoint)
        self.audit.emit(
            AuditEventType.CHECKPOINT_COMPLETED,
            checkpoint_id=checkpoint.id,
        )
        return checkpoint


# ============================================================================
# 备份增强版 CheckpointStore — spec §7.4
# ============================================================================

class CheckpointStoreWithBackup(CheckpointStore):
    """增强版 CheckpointStore

    - 保存时自动创建 .bak 备份 (用于损坏恢复)
    - 提供 load_backup() 方法
    """

    def save(self, checkpoint: Checkpoint) -> Path:
        """保存检查点 (含备份)"""
        filepath = self.base_path / f"{checkpoint.id}.json"
        backup = self.base_path / f"{checkpoint.id}.json.bak"

        # 如果存在旧文件，先备份
        if filepath.exists():
            try:
                shutil.copy2(filepath, backup)
            except OSError:
                pass  # 备份失败不阻塞保存

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, indent=2, ensure_ascii=False)
        return filepath

    def load_backup(self, checkpoint_id: str) -> Checkpoint | None:
        """从备份加载"""
        backup = self.base_path / f"{checkpoint_id}.json.bak"
        if not backup.exists():
            return None
        try:
            with open(backup, encoding="utf-8") as f:
                data = json.load(f)
            return self._deserialize(data)
        except (json.JSONDecodeError, KeyError, OSError):
            return None


# ============================================================================
# 工厂函数
# ============================================================================

def create_pause_controller(
    config: HITLConfig,
    audit: AuditLogger,
    store: CheckpointStore | None = None,
) -> PauseController:
    """创建暂停控制器"""
    store = store or CheckpointStoreWithBackup(
        base_path=Path(os.path.expanduser(config.checkpoint_local_path))
    )
    return PauseController(store, audit)


def create_session_recovery(
    config: HITLConfig,
    audit: AuditLogger,
    store: CheckpointStore | None = None,
) -> SessionRecovery:
    """创建会话恢复器"""
    store = store or CheckpointStoreWithBackup(
        base_path=Path(os.path.expanduser(config.checkpoint_local_path))
    )
    drift_detector = DriftDetector(audit)
    return SessionRecovery(store, drift_detector, audit)


def create_expiration_manager(
    config: HITLConfig,
    audit: AuditLogger,
    store: CheckpointStore | None = None,
) -> CheckpointExpirationManager:
    """创建过期管理器"""
    store = store or CheckpointStoreWithBackup(
        base_path=Path(os.path.expanduser(config.checkpoint_local_path))
    )
    return CheckpointExpirationManager(store, config, audit)


def create_batch_selector(audit: AuditLogger) -> BatchSelector:
    """创建批量选择器"""
    return BatchSelector(audit)


# ============================================================================
# CLI 入口
# ============================================================================

def _list_checkpoints(store: CheckpointStore) -> None:
    """列出活跃检查点"""
    checkpoints = store.list_active()
    if not checkpoints:
        print("无活跃检查点")
        return

    print("活跃检查点:")
    print(f"  {'ID':<40} {'类型':<10} {'环境':<12} {'状态':<10} {'更新时间'}")
    print("  " + "-" * 100)
    for cp in checkpoints:
        print(f"  {cp.id:<40} {cp.type.value:<10} {cp.environment.value:<12} "
              f"{cp.status.value:<10} {cp.updated_at}")


def main():
    """CLI 入口: 暂停/恢复/列表/清理"""
    import argparse

    parser = argparse.ArgumentParser(
        description="HITL Mode C - Checkpoint Pause for Terraform IaC",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list 子命令
    subparsers.add_parser("list", help="列出活跃检查点")

    # resume 子命令
    resume_parser = subparsers.add_parser("resume", help="恢复检查点")
    resume_parser.add_argument("checkpoint_id", help="检查点 ID")
    resume_parser.add_argument("--yes", "-y", action="store_true", help="跳过确认")

    # pause 子命令 (手动暂停)
    pause_parser = subparsers.add_parser("pause", help="暂停当前检查点")
    pause_parser.add_argument("checkpoint_id", help="检查点 ID")

    # cleanup 子命令
    cleanup_parser = subparsers.add_parser("cleanup", help="清理过期检查点")
    cleanup_parser.add_argument("--dry-run", action="store_true", help="仅显示，不删除")

    # delete 子命令
    delete_parser = subparsers.add_parser("delete", help="删除检查点")
    delete_parser.add_argument("checkpoint_id", help="检查点 ID")

    # extend-ttl 子命令
    extend_parser = subparsers.add_parser("extend-ttl", help="延长 TTL")
    extend_parser.add_argument("checkpoint_id", help="检查点 ID")
    extend_parser.add_argument("ttl", help="新 TTL (如 7d, 24h)")

    # batch-select 子命令 (Reverse Engineering 集成)
    batch_parser = subparsers.add_parser("batch-select", help="批量资源选择")
    batch_parser.add_argument("--input", help="输入 JSON 文件 (含 classified resources)")

    args = parser.parse_args()

    config = HITLConfig.load()
    audit = AuditLogger()
    store = CheckpointStoreWithBackup(
        base_path=Path(os.path.expanduser(config.checkpoint_local_path))
    )

    if args.command == "list":
        _list_checkpoints(store)

    elif args.command == "resume":
        recovery = create_session_recovery(config, audit, store)
        result = recovery.resume(args.checkpoint_id)

        if not result.success:
            print(f"[ERROR] {result.error}")
            sys.exit(1)

        cp = result.checkpoint
        print("[OK] 恢复成功")
        print(f"  ID: {cp.id}")
        print(f"  类型: {cp.type.value}")
        print(f"  环境: {cp.environment.value}")
        print(f"  当前步骤: {cp.current_step_index}/{len(cp.steps)}")
        if result.next_action:
            print(f"  下一步: {result.next_action}")
        if result.warning:
            print(f"  {Colors.YELLOW}⚠ {result.warning}{Colors.RESET}")
        if result.drift and result.drift.has_drift:
            print(f"  漂移详情: {result.drift.to_dict()}")

        if not args.yes:
            try:
                ans = input("\n继续执行? [Y/n]: ").strip().lower()
                if ans not in ("y", "yes", ""):
                    print("已取消")
                    return
            except (EOFError, KeyboardInterrupt):
                print("\n已取消")
                return

        print(f"\n[下一步] 调用对应 HITL Mode 继续执行: {result.next_action}")
        print(f"  使用 `python3 hitl_mode_a.py --resume {cp.id}` 恢复 CLI 模式")

    elif args.command == "pause":
        try:
            cp = store.load(args.checkpoint_id)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[ERROR] {e}")
            sys.exit(1)
        if cp is None:
            print(f"[ERROR] 检查点不存在: {args.checkpoint_id}")
            sys.exit(1)
        cp.pause()
        store.save(cp)
        audit.emit(
            AuditEventType.CHECKPOINT_PAUSED,
            checkpoint_id=cp.id,
            context={"action": "manual"},
        )
        print(f"[OK] 已暂停: {cp.id}")

    elif args.command == "cleanup":
        manager = create_expiration_manager(config, audit, store)
        expired = manager.cleanup_expired(dry_run=args.dry_run)
        if expired:
            action = "将删除" if args.dry_run else "已删除"
            print(f"[OK] {action} {len(expired)} 个过期检查点:")
            for cp_id in expired:
                print(f"  - {cp_id}")
        else:
            print("无过期检查点")

    elif args.command == "delete":
        manager = create_expiration_manager(config, audit, store)
        try:
            manager._delete_checkpoint(args.checkpoint_id)
            print(f"[OK] 已删除: {args.checkpoint_id}")
        except Exception as e:
            print(f"[ERROR] {e}")
            sys.exit(1)

    elif args.command == "extend-ttl":
        manager = create_expiration_manager(config, audit, store)
        if manager.extend_ttl(args.checkpoint_id, args.ttl):
            print(f"[OK] {args.checkpoint_id} TTL 已延长到 {args.ttl}")
        else:
            print("[ERROR] 延长失败: 检查点不存在")
            sys.exit(1)

    elif args.command == "batch-select":
        if not args.input:
            print("[ERROR] 需要 --input 参数")
            sys.exit(1)

        input_path = Path(args.input)
        if not input_path.exists():
            print(f"[ERROR] 输入文件不存在: {args.input}")
            sys.exit(1)

        data = safe_load_json(input_path)
        if not data:
            print(f"[ERROR] 无法解析 JSON: {args.input}")
            sys.exit(1)

        # 构造 ClassifiedResource 列表
        classified = []
        for item in data.get("classified", []):
            res_data = item.get("resource", {})
            resource = ResourceInfo(
                resource_type=res_data.get("type", "unknown"),
                name=res_data.get("name", "unnamed"),
                id=res_data.get("id"),
                status=res_data.get("status", "pending"),
                attributes=res_data.get("attributes", {}),
            )
            try:
                classification = ResourceClassification(item.get("classification", "pass"))
            except ValueError:
                classification = ResourceClassification.PASS
            classified.append(ClassifiedResource(
                resource=resource,
                classification=classification,
                reason=item.get("reason", ""),
                warning=item.get("warning"),
                selected=item.get("selected", True),
            ))

        selector = create_batch_selector(audit)
        result = selector.select_interactive(classified)

        # 输出结果
        output = {
            "selection_mode": result.selection_mode,
            "selected_count": len(result.selected_resources),
            "selected": [cr.to_dict() for cr in result.selected_resources],
        }
        print()
        print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
