#!/usr/bin/env python3
"""
HITL Mode A - Interactive CLI Implementation
人机介入模式A: 交互式命令行实现

支持五级环境策略 (int/dev/uat/performance/production)
支持检查点 CP1-CP5: 意图确认 → 配置审核 → Plan确认 → 导入确认 → 销毁确认
"""

from __future__ import annotations

import os
import sys
import json
import time
import signal
from datetime import datetime, timedelta
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Union
from pathlib import Path


# ============================================================================
# Enums and Constants
# ============================================================================

class CheckpointType(Enum):
    """检查点类型"""
    NL2HCL = "nl2hcl"
    IMPORT = "import"
    APPLY = "apply"
    DESTROY = "destroy"


class HITLMode(Enum):
    """HITL 模式"""
    CLI = "cli"
    PR = "pr"
    CHECKPOINT = "checkpoint"


class CheckpointStatus(Enum):
    """检查点状态"""
    INIT = "init"
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class StepType(Enum):
    """步骤类型"""
    CONFIRM_INTENT = "cp1_intent"      # CP1: 意图确认
    REVIEW_CONFIG = "cp2_review"       # CP2: 配置审核
    CONFIRM_PLAN = "cp3_plan"          # CP3: Plan确认
    CONFIRM_IMPORT = "cp4_import"      # CP4: 导入确认
    CONFIRM_DESTROY = "cp5_destroy"    # CP5: 销毁确认


class Action(Enum):
    """用户操作"""
    CONTINUE = "continue"
    ABORT = "abort"
    PAUSE = "pause"
    MODIFY = "modify"
    SKIP = "skip"
    RETRY = "retry"
    HELP = "help"


class Environment(str, Enum):
    """五级环境"""
    INT = "int"
    DEV = "dev"
    UAT = "uat"
    PERFORMANCE = "performance"
    PRODUCTION = "production"


# ANSI Colors
class Colors:
    """终端颜色"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class ResourceInfo:
    """资源信息"""
    resource_type: str
    name: str
    id: Optional[str] = None
    status: str = "pending"
    attributes: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


@dataclass
class StepResult:
    """步骤执行结果"""
    action: Action
    data: Dict[str, Any] = field(default_factory=dict)
    reason: Optional[str] = None
    modifications: Optional[Dict[str, Any]] = None


@dataclass
class Step:
    """检查点步骤"""
    type: StepType
    status: CheckpointStatus = CheckpointStatus.PENDING
    data: Dict[str, Any] = field(default_factory=dict)
    result: Optional[StepResult] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class PolicyConfig:
    """策略配置"""
    required: bool = True
    timeout: int = 300  # seconds
    allow_skip: bool = False
    dry_run: bool = False
    confirm_count: int = 1
    cooldown: int = 0  # seconds
    require_reason: bool = False
    require_jira_ticket: bool = False
    auto_approve: bool = False


@dataclass
class Checkpoint:
    """检查点"""
    id: str
    type: CheckpointType
    environment: Environment
    mode: HITLMode = HITLMode.CLI
    status: CheckpointStatus = CheckpointStatus.INIT
    
    # Context
    resources: List[ResourceInfo] = field(default_factory=list)
    generated_files: Dict[str, str] = field(default_factory=dict)
    user_inputs: Dict[str, Any] = field(default_factory=dict)
    
    # History
    steps: List[Step] = field(default_factory=list)
    current_step_index: int = 0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    
    # Retry
    retry_count: int = 0
    max_retries: int = 3
    
    def get_current_step(self) -> Optional[Step]:
        """获取当前步骤"""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    def get_pending_steps(self) -> List[Step]:
        """获取待执行的步骤"""
        return [s for s in self.steps[self.current_step_index:] 
                if s.status == CheckpointStatus.PENDING]
    
    def complete_step(self, step: Step, result: StepResult):
        """完成步骤"""
        step.status = CheckpointStatus.COMPLETED
        step.result = result
        step.completed_at = datetime.now()
        self.current_step_index += 1
        self.updated_at = datetime.now()
    
    def pause(self):
        """暂停检查点"""
        self.status = CheckpointStatus.PAUSED
        self.updated_at = datetime.now()
    
    def resume(self):
        """恢复检查点"""
        self.status = CheckpointStatus.RUNNING
        self.updated_at = datetime.now()
    
    def abort(self, reason: str):
        """中止检查点"""
        self.status = CheckpointStatus.FAILED
        self.updated_at = datetime.now()
    
    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at:
            return datetime.now() > self.expires_at
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "type": self.type.value,
            "environment": self.environment.value,
            "mode": self.mode.value,
            "status": self.status.value,
            "resources": [
                {
                    "type": r.resource_type,
                    "name": r.name,
                    "id": r.id,
                    "status": r.status,
                    "attributes": r.attributes
                } for r in self.resources
            ],
            "generated_files": self.generated_files,
            "user_inputs": self.user_inputs,
            "steps": [
                {
                    "type": s.type.value,
                    "status": s.status.value,
                    "data": s.data,
                    "result": {
                        "action": s.result.action.value if s.result else None,
                        "data": s.result.data if s.result else None,
                        "reason": s.result.reason if s.result else None
                    } if s.result else None
                } for s in self.steps
            ],
            "current_step_index": self.current_step_index,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "retry_count": self.retry_count
        }


# ============================================================================
# Environment Policy
# ============================================================================

class EnvironmentPolicy:
    """环境策略管理"""
    
    # 五级环境策略配置
    POLICIES = {
        Environment.INT: {
            StepType.CONFIRM_INTENT: PolicyConfig(
                required=True, timeout=300, allow_skip=False
            ),
            StepType.REVIEW_CONFIG: PolicyConfig(
                required=False, allow_skip=True
            ),
            StepType.CONFIRM_PLAN: PolicyConfig(
                required=True, dry_run=True, auto_approve=True
            ),
            StepType.CONFIRM_IMPORT: PolicyConfig(
                required=True, timeout=600
            ),
            StepType.CONFIRM_DESTROY: PolicyConfig(
                required=True, confirm_count=1
            ),
        },
        Environment.DEV: {
            StepType.CONFIRM_INTENT: PolicyConfig(
                required=True, timeout=600
            ),
            StepType.REVIEW_CONFIG: PolicyConfig(
                required=False, allow_skip=True
            ),
            StepType.CONFIRM_PLAN: PolicyConfig(
                required=True, dry_run=True
            ),
            StepType.CONFIRM_IMPORT: PolicyConfig(
                required=True, timeout=900
            ),
            StepType.CONFIRM_DESTROY: PolicyConfig(
                required=True, confirm_count=1
            ),
        },
        Environment.UAT: {
            StepType.CONFIRM_INTENT: PolicyConfig(
                required=True, timeout=600
            ),
            StepType.REVIEW_CONFIG: PolicyConfig(
                required=True, timeout=900
            ),
            StepType.CONFIRM_PLAN: PolicyConfig(
                required=True, dry_run=True
            ),
            StepType.CONFIRM_IMPORT: PolicyConfig(
                required=True, timeout=1200
            ),
            StepType.CONFIRM_DESTROY: PolicyConfig(
                required=True, confirm_count=2
            ),
        },
        Environment.PERFORMANCE: {
            StepType.CONFIRM_INTENT: PolicyConfig(
                required=True, timeout=600
            ),
            StepType.REVIEW_CONFIG: PolicyConfig(
                required=True, timeout=900
            ),
            StepType.CONFIRM_PLAN: PolicyConfig(
                required=True, dry_run=True
            ),
            StepType.CONFIRM_IMPORT: PolicyConfig(
                required=True, timeout=1200
            ),
            StepType.CONFIRM_DESTROY: PolicyConfig(
                required=True, confirm_count=2
            ),
        },
        Environment.PRODUCTION: {
            StepType.CONFIRM_INTENT: PolicyConfig(
                required=True, timeout=900, require_reason=True, require_jira_ticket=True
            ),
            StepType.REVIEW_CONFIG: PolicyConfig(
                required=True, timeout=1200
            ),
            StepType.CONFIRM_PLAN: PolicyConfig(
                required=True, dry_run=True, cooldown=30
            ),
            StepType.CONFIRM_IMPORT: PolicyConfig(
                required=True, timeout=1800
            ),
            StepType.CONFIRM_DESTROY: PolicyConfig(
                required=True, confirm_count=2, cooldown=30
            ),
        },
    }
    
    @classmethod
    def get_policy(cls, env: Environment, step: StepType) -> PolicyConfig:
        """获取策略配置"""
        env_policies = cls.POLICIES.get(env, cls.POLICIES[Environment.DEV])
        return env_policies.get(step, PolicyConfig())
    
    @classmethod
    def should_skip(cls, env: Environment, step: StepType) -> bool:
        """检查是否跳过步骤"""
        policy = cls.get_policy(env, step)
        return not policy.required


# ============================================================================
# CLI Renderer
# ============================================================================

class CLIRenderer:
    """CLI 渲染器"""
    
    def __init__(self, use_color: bool = True):
        self.use_color = use_color and sys.stdout.isatty()
    
    def _c(self, color: str, text: str) -> str:
        """添加颜色"""
        if self.use_color:
            return f"{color}{text}{Colors.RESET}"
        return text
    
    def render_header(self, title: str, env: Optional[Environment] = None):
        """渲染标题"""
        env_str = f" [{env.value.upper()}]" if env else ""
        print()
        print("=" * 60)
        print(f"  {self._c(Colors.BOLD + Colors.CYAN, title)}{self._c(Colors.YELLOW, env_str)}")
        print("=" * 60)
        print()
    
    def render_resources(self, resources: List[ResourceInfo]):
        """渲染资源列表"""
        if not resources:
            print(self._c(Colors.DIM, "  (无资源)"))
            return
        
        # 按类型分组
        by_type: Dict[str, List[ResourceInfo]] = {}
        for r in resources:
            by_type.setdefault(r.resource_type, []).append(r)
        
        for rtype, items in by_type.items():
            print(f"  {self._c(Colors.BOLD, rtype)}: {len(items)} 个")
            for item in items:
                name = item.name
                if item.id:
                    name += f" ({item.id})"
                status_color = Colors.GREEN if item.status == "ready" else Colors.YELLOW
                print(f"    • {name} {self._c(status_color, f'[{item.status}]')}")
                if item.warnings:
                    for w in item.warnings:
                        print(f"      {self._c(Colors.YELLOW, '⚠ ' + w)}")
        print()
    
    def render_config_preview(self, files: Dict[str, str], max_lines: int = 20):
        """渲染配置预览"""
        for filename, content in files.items():
            print(f"  {self._c(Colors.BOLD + Colors.BLUE, filename)}")
            lines = content.split('\n')
            if len(lines) > max_lines:
                for line in lines[:max_lines]:
                    print(f"    {line}")
                print(f"    {self._c(Colors.DIM, f'... ({len(lines) - max_lines} more lines)')}")
            else:
                for line in lines:
                    print(f"    {line}")
            print()
    
    def render_plan_summary(self, plan_data: Dict[str, Any]):
        """渲染 Plan 摘要"""
        create = plan_data.get('create', 0)
        update = plan_data.get('update', 0)
        delete = plan_data.get('delete', 0)
        
        print(f"  {self._c(Colors.BOLD, '变更概览:')}")
        if create:
            print(f"    {self._c(Colors.GREEN, f'+ 创建: {create}')}")
        if update:
            print(f"    {self._c(Colors.YELLOW, f'~ 修改: {update}')}")
        if delete:
            print(f"    {self._c(Colors.RED, f'- 销毁: {delete}')} ⚠️")
        
        if not any([create, update, delete]):
            print(f"    {self._c(Colors.GREEN, '无变更')}")
        print()
        
        # 风险提示
        risks = plan_data.get('risks', [])
        if risks:
            print(f"  {self._c(Colors.BOLD + Colors.RED, '⚠ 风险警告:')}")
            for risk in risks:
                print(f"    • {risk}")
            print()
    
    def render_selection_list(
        self, 
        items: List[Dict[str, Any]], 
        title: str = "选择资源",
        selected: Optional[set] = None
    ) -> set:
        """渲染选择列表（简化版，非交互式）"""
        print(f"  {self._c(Colors.BOLD, title)}")
        
        selected = selected or set()
        
        for i, item in enumerate(items, 1):
            mark = "x" if item['id'] in selected else " "
            status = item.get('status', '')
            status_str = ""
            
            if status == 'pass':
                status_str = self._c(Colors.GREEN, " [PASS]")
            elif status == 'warn':
                status_str = self._c(Colors.YELLOW, " [WARN]")
            elif status == 'skip':
                status_str = self._c(Colors.RED, " [SKIP]")
            
            print(f"    [{mark}] {i}. {item.get('name', item['id'])}{status_str}")
            if item.get('warning'):
                print(f"        {self._c(Colors.YELLOW, '⚠ ' + item['warning'])}")
        
        print()
        return selected
    
    def render_timer(self, remaining: int):
        """渲染倒计时"""
        mins, secs = divmod(remaining, 60)
        print(f"  {self._c(Colors.DIM, f'[超时: {mins:02d}:{secs:02d}]')}", end='\r')
    
    def render_success(self, message: str):
        """渲染成功消息"""
        print(f"  {self._c(Colors.GREEN, '✓')} {message}")
    
    def render_error(self, message: str):
        """渲染错误消息"""
        print(f"  {self._c(Colors.RED, '✗')} {message}")
    
    def render_warning(self, message: str):
        """渲染警告消息"""
        print(f"  {self._c(Colors.YELLOW, '!')} {message}")
    
    def render_info(self, message: str):
        """渲染信息消息"""
        print(f"  {self._c(Colors.BLUE, 'ℹ')} {message}")
    
    def prompt(
        self, 
        message: str, 
        options: Optional[List[str]] = None,
        default: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> str:
        """
        提示用户输入
        
        Args:
            message: 提示消息
            options: 可选选项列表
            default: 默认值
            timeout: 超时时间（秒）
        
        Returns:
            用户输入
        """
        opts_str = ""
        if options:
            opts_str = f" [{'/'.join(options)}]"
        if default:
            opts_str += f" (默认: {default})"
        
        prompt_text = f"{message}{opts_str}> "
        
        if timeout:
            return self._prompt_with_timeout(prompt_text, timeout, default)
        
        try:
            user_input = input(prompt_text).strip()
            return user_input if user_input else (default or "")
        except (EOFError, KeyboardInterrupt):
            print()
            return "q"  # 退出信号
    
    def _prompt_with_timeout(
        self, 
        prompt_text: str, 
        timeout: int, 
        default: Optional[str] = None
    ) -> str:
        """带超时的提示"""
        import select
        
        print(prompt_text, end='', flush=True)
        
        # 简单的超时实现
        start_time = time.time()
        while time.time() - start_time < timeout:
            if sys.stdin in select.select([sys.stdin], [], [], 1)[0]:
                try:
                    user_input = sys.stdin.readline().strip()
                    return user_input if user_input else (default or "")
                except (EOFError, KeyboardInterrupt):
                    print()
                    return "q"
            
            remaining = int(timeout - (time.time() - start_time))
            if remaining <= 0:
                break
        
        print()
        raise TimeoutError("输入超时")


# ============================================================================
# Checkpoint Store
# ============================================================================

class CheckpointStore:
    """检查点存储"""
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.home() / ".pi" / "terraform-ops" / "checkpoints"
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def save(self, checkpoint: Checkpoint) -> Path:
        """保存检查点"""
        filepath = self.base_path / f"{checkpoint.id}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(checkpoint.to_dict(), f, indent=2, ensure_ascii=False)
        return filepath
    
    def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """加载检查点"""
        filepath = self.base_path / f"{checkpoint_id}.json"
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return self._deserialize(data)
    
    def list_active(self) -> List[Checkpoint]:
        """列出活跃检查点"""
        checkpoints = []
        for filepath in self.base_path.glob("*.json"):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cp = self._deserialize(data)
            if cp.status in [CheckpointStatus.PENDING, CheckpointStatus.PAUSED]:
                if not cp.is_expired():
                    checkpoints.append(cp)
        return checkpoints
    
    def _deserialize(self, data: Dict[str, Any]) -> Checkpoint:
        """反序列化检查点"""
        resources = [
            ResourceInfo(
                resource_type=r['type'],
                name=r['name'],
                id=r.get('id'),
                status=r.get('status', 'pending'),
                attributes=r.get('attributes', {})
            ) for r in data.get('resources', [])
        ]
        
        steps = [
            Step(
                type=StepType(s['type']),
                status=CheckpointStatus(s['status']),
                data=s.get('data', {}),
                result=StepResult(
                    action=Action(s['result']['action']),
                    data=s['result'].get('data', {}),
                    reason=s['result'].get('reason')
                ) if s.get('result') and s['result'].get('action') else None
            ) for s in data.get('steps', [])
        ]
        
        return Checkpoint(
            id=data['id'],
            type=CheckpointType(data['type']),
            environment=Environment(data['environment']),
            mode=HITLMode(data['mode']),
            status=CheckpointStatus(data['status']),
            resources=resources,
            generated_files=data.get('generated_files', {}),
            user_inputs=data.get('user_inputs', {}),
            steps=steps,
            current_step_index=data.get('current_step_index', 0),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            expires_at=datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None,
            retry_count=data.get('retry_count', 0)
        )


# ============================================================================
# CLI Controller - Main
# ============================================================================

class CLIController:
    """CLI 控制器 - HITL Mode A 核心实现"""
    
    def __init__(
        self, 
        checkpoint: Checkpoint,
        store: Optional[CheckpointStore] = None,
        use_color: bool = True
    ):
        self.checkpoint = checkpoint
        self.store = store or CheckpointStore()
        self.ui = CLIRenderer(use_color=use_color)
        self.policy = EnvironmentPolicy()
        self._running = False
        self._interrupted = False
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理"""
        print("\n")
        self.ui.render_warning("收到中断信号，正在保存检查点...")
        self._interrupted = True
        self.checkpoint.pause()
        self.store.save(self.checkpoint)
        self.ui.render_info(f"检查点已保存: {self.checkpoint.id}")
        self.ui.render_info("可以使用 --resume 参数恢复执行")
        sys.exit(0)
    
    def run(self) -> Checkpoint:
        """
        主执行循环
        
        Returns:
            完成后的检查点
        
        Raises:
            UserAbortedError: 用户中止
            TimeoutError: 超时
        """
        self._running = True
        self.checkpoint.status = CheckpointStatus.RUNNING
        
        try:
            pending_steps = self.checkpoint.get_pending_steps()
            
            if not pending_steps:
                self.ui.render_info("所有步骤已完成")
                self.checkpoint.status = CheckpointStatus.COMPLETED
                return self.checkpoint
            
            for step in pending_steps:
                if self._interrupted:
                    break
                
                # 检查策略
                policy = self.policy.get_policy(
                    self.checkpoint.environment, 
                    step.type
                )
                
                if self.policy.should_skip(self.checkpoint.environment, step.type):
                    self.ui.render_info(f"跳过步骤: {step.type.value}")
                    self.checkpoint.complete_step(step, StepResult(Action.SKIP))
                    continue
                
                # 执行步骤
                result = self._execute_step(step, policy)
                
                if result.action == Action.PAUSE:
                    self.checkpoint.pause()
                    self.store.save(self.checkpoint)
                    self.ui.render_info(f"检查点已暂停: {self.checkpoint.id}")
                    return self.checkpoint
                
                elif result.action == Action.ABORT:
                    self.checkpoint.abort(result.reason or "用户中止")
                    self.store.save(self.checkpoint)
                    raise UserAbortedError(result.reason or "用户中止操作")
                
                elif result.action == Action.CONTINUE:
                    self.checkpoint.complete_step(step, result)
                    self.store.save(self.checkpoint)
                
                elif result.action == Action.RETRY:
                    if self.checkpoint.retry_count < self.checkpoint.max_retries:
                        self.checkpoint.retry_count += 1
                        self.ui.render_warning(f"重试 {self.checkpoint.retry_count}/{self.checkpoint.max_retries}")
                        # 重新执行当前步骤
                        result = self._execute_step(step, policy)
                        self.checkpoint.complete_step(step, result)
                        self.store.save(self.checkpoint)
                    else:
                        raise MaxRetryError(f"步骤 {step.type.value} 重试次数耗尽")
            
            # 所有步骤完成
            self.checkpoint.status = CheckpointStatus.COMPLETED
            self.store.save(self.checkpoint)
            self.ui.render_success("所有检查点已完成")
            return self.checkpoint
            
        except TimeoutError as e:
            self.checkpoint.pause()
            self.store.save(self.checkpoint)
            self.ui.render_error(f"操作超时: {e}")
            raise
        except Exception as e:
            self.checkpoint.status = CheckpointStatus.FAILED
            self.store.save(self.checkpoint)
            self.ui.render_error(f"执行失败: {e}")
            raise
    
    def _execute_step(self, step: Step, policy: PolicyConfig) -> StepResult:
        """执行单个步骤"""
        step.status = CheckpointStatus.RUNNING
        step.started_at = datetime.now()
        
        handlers: Dict[StepType, Callable[[Step, PolicyConfig], StepResult]] = {
            StepType.CONFIRM_INTENT: self._confirm_intent,
            StepType.REVIEW_CONFIG: self._review_config,
            StepType.CONFIRM_PLAN: self._confirm_plan,
            StepType.CONFIRM_IMPORT: self._confirm_import,
            StepType.CONFIRM_DESTROY: self._confirm_destroy,
        }
        
        handler = handlers.get(step.type)
        if not handler:
            return StepResult(Action.CONTINUE, reason=f"未支持的步骤类型: {step.type.value}")
        
        try:
            return handler(step, policy)
        except TimeoutError:
            return StepResult(Action.PAUSE, reason="操作超时")
    
    # ========================================================================
    # CP1: 意图确认 (Confirm Intent)
    # ========================================================================
    
    def _confirm_intent(self, step: Step, policy: PolicyConfig) -> StepResult:
        """CP1: 意图确认"""
        self.ui.render_header("检查点 1/5: 意图确认 (CP1)", self.checkpoint.environment)
        
        # 显示解析的资源
        if self.checkpoint.resources:
            self.ui.render_info("检测到以下资源需求:")
            self.ui.render_resources(self.checkpoint.resources)
        else:
            self.ui.render_info(step.data.get('intent', '用户请求'))
        
        # 生产环境特殊要求
        if self.checkpoint.environment == Environment.PRODUCTION:
            if policy.require_jira_ticket:
                jira = self.ui.prompt("请输入 Jira Ticket 编号 (如 PROJ-123):")
                if not jira:
                    return StepResult(Action.ABORT, reason="生产环境必须提供 Jira Ticket")
                step.data['jira_ticket'] = jira
            
            if policy.require_reason:
                reason = self.ui.prompt("请输入变更原因:")
                if not reason:
                    return StepResult(Action.ABORT, reason="生产环境必须提供变更原因")
                step.data['change_reason'] = reason
        
        # 确认
        try:
            choice = self.ui.prompt(
                "确认生成 Terraform 配置?",
                options=["Y", "n", "modify", "q"],
                default="Y",
                timeout=policy.timeout
            )
        except TimeoutError:
            return StepResult(Action.PAUSE, reason="确认超时")
        
        if choice.lower() in ("y", "yes", ""):
            self.ui.render_success("意图已确认")
            return StepResult(Action.CONTINUE)
        elif choice.lower() == "n":
            return StepResult(Action.ABORT, reason="用户取消")
        elif choice.lower() == "modify":
            modifications = self._collect_modifications()
            return StepResult(Action.CONTINUE, data={"modifications": modifications})
        elif choice.lower() == "q":
            return StepResult(Action.PAUSE, reason="用户选择退出")
        
        return StepResult(Action.CONTINUE)
    
    def _collect_modifications(self) -> Dict[str, Any]:
        """收集用户修改"""
        modifications = {}
        self.ui.render_info("进入修改模式 (直接回车保持原值)")
        
        for resource in self.checkpoint.resources:
            name = self.ui.prompt(
                f"修改 {resource.name} 的名称",
                default=resource.name
            )
            if name != resource.name:
                modifications[resource.name] = {"name": name}
        
        return modifications
    
    # ========================================================================
    # CP2: 配置审核 (Review Config)
    # ========================================================================
    
    def _review_config(self, step: Step, policy: PolicyConfig) -> StepResult:
        """CP2: 配置审核"""
        self.ui.render_header("检查点 2/5: 配置审核 (CP2)", self.checkpoint.environment)
        
        if not self.checkpoint.generated_files:
            self.ui.render_warning("暂无生成的配置文件")
            return StepResult(Action.CONTINUE)
        
        # 显示生成的文件
        self.ui.render_info("生成的配置文件预览:")
        self.ui.render_config_preview(self.checkpoint.generated_files)
        
        # 环境特定提示
        if self.checkpoint.environment in (Environment.UAT, Environment.PERFORMANCE, Environment.PRODUCTION):
            self.ui.render_warning("此环境要求配置必须经过审核")
        
        try:
            choice = self.ui.prompt(
                "配置审核",
                options=["Y", "n", "edit", "q"],
                default="Y",
                timeout=policy.timeout
            )
        except TimeoutError:
            return StepResult(Action.PAUSE, reason="审核超时")
        
        if choice.lower() in ("y", "yes", ""):
            self.ui.render_success("配置已审核通过")
            return StepResult(Action.CONTINUE)
        elif choice.lower() == "n":
            return StepResult(Action.ABORT, reason="配置审核未通过")
        elif choice.lower() == "edit":
            self.ui.render_info("请在编辑器中修改文件后重新运行")
            return StepResult(Action.PAUSE, reason="等待外部编辑")
        elif choice.lower() == "q":
            return StepResult(Action.PAUSE)
        
        return StepResult(Action.CONTINUE)
    
    # ========================================================================
    # CP3: Plan 确认 (Confirm Plan)
    # ========================================================================
    
    def _confirm_plan(self, step: Step, policy: PolicyConfig) -> StepResult:
        """CP3: Plan 确认"""
        self.ui.render_header("检查点 3/5: Plan 确认 (CP3)", self.checkpoint.environment)
        
        # 显示 Dry-run 信息
        if policy.dry_run:
            self.ui.render_info("╔════════════════════════════════════════════════════════╗")
            self.ui.render_info("║           🔍 DRY-RUN MODE (干运行模式)                  ║")
            self.ui.render_info("║    此执行仅用于预览和验证，不会创建或修改任何资源        ║")
            self.ui.render_info("╚════════════════════════════════════════════════════════╝")
            print()
        
        # 显示 Plan 摘要
        plan_data = step.data.get('plan', {
            'create': len([r for r in self.checkpoint.resources if r.status == 'pending']),
            'update': 0,
            'delete': 0
        })
        self.ui.render_plan_summary(plan_data)
        
        # 冷却期（生产环境）
        if policy.cooldown > 0:
            self.ui.render_warning(f"生产环境需要 {policy.cooldown} 秒冷却期...")
            for i in range(policy.cooldown, 0, -1):
                print(f"  冷却中... {i} 秒", end='\r')
                time.sleep(1)
            print()
        
        # 自动批准（int 环境小变更）
        if policy.auto_approve:
            total = plan_data.get('create', 0) + plan_data.get('update', 0) + plan_data.get('delete', 0)
            cost = plan_data.get('cost_hourly', 0)
            if total <= 5 and cost <= 10:  # 少于5个资源且小时费用低于10元
                self.ui.render_success("符合自动批准条件，继续执行")
                return StepResult(Action.CONTINUE, data={"auto_approved": True})
        
        try:
            choice = self.ui.prompt(
                "确认执行 terraform apply?",
                options=["Y", "n", "details", "q"],
                default="n" if self.checkpoint.environment == Environment.PRODUCTION else "Y",
                timeout=policy.timeout
            )
        except TimeoutError:
            return StepResult(Action.PAUSE, reason="确认超时")
        
        if choice.lower() in ("y", "yes"):
            self.ui.render_success("Plan 已确认")
            return StepResult(Action.CONTINUE)
        elif choice.lower() == "n":
            return StepResult(Action.ABORT, reason="Plan 未确认")
        elif choice.lower() == "details":
            self.ui.render_info("显示详细 Plan 输出...")
            return StepResult(Action.RETRY)  # 重新执行以显示详情
        elif choice.lower() == "q":
            return StepResult(Action.PAUSE)
        
        return StepResult(Action.CONTINUE)
    
    # ========================================================================
    # CP4: 导入确认 (Confirm Import)
    # ========================================================================
    
    def _confirm_import(self, step: Step, policy: PolicyConfig) -> StepResult:
        """CP4: 导入确认（逆向工程专用）"""
        self.ui.render_header("检查点 4/5: 导入确认 (CP4)", self.checkpoint.environment)
        
        if self.checkpoint.type != CheckpointType.IMPORT:
            return StepResult(Action.CONTINUE)
        
        # 显示发现的资源
        resources = step.data.get('discovered_resources', self.checkpoint.resources)
        
        if not resources:
            self.ui.render_warning("未发现可导入的资源")
            return StepResult(Action.CONTINUE)
        
        # 资源分级显示
        items = []
        for r in resources:
            item = {
                'id': r.id or r.name,
                'name': r.name,
                'type': r.resource_type,
                'status': 'pass',
                'selected': True
            }
            if r.warnings:
                item['status'] = 'warn'
                item['warning'] = r.warnings[0]
            items.append(item)
        
        self.ui.render_selection_list(items, "选择要导入的资源")
        
        self.ui.render_info("操作提示: [数字]选择/取消  [a]全选  [c]确认  [q]保存退出")
        
        try:
            choice = self.ui.prompt(
                "确认导入以上资源到 Terraform?",
                options=["Y", "n", "select", "q"],
                default="Y",
                timeout=policy.timeout
            )
        except TimeoutError:
            return StepResult(Action.PAUSE, reason="确认超时")
        
        if choice.lower() in ("y", "yes", ""):
            self.ui.render_success("导入已确认")
            return StepResult(Action.CONTINUE)
        elif choice.lower() == "n":
            return StepResult(Action.ABORT, reason="用户取消导入")
        elif choice.lower() in ("select", "s"):
            self.ui.render_info("请手动编辑 import 脚本以选择资源")
            return StepResult(Action.PAUSE)
        elif choice.lower() == "q":
            return StepResult(Action.PAUSE)
        
        return StepResult(Action.CONTINUE)
    
    # ========================================================================
    # CP5: 销毁确认 (Confirm Destroy)
    # ========================================================================
    
    def _confirm_destroy(self, step: Step, policy: PolicyConfig) -> StepResult:
        """CP5: 销毁确认（最高安全级别）"""
        self.ui.render_header("⚠️  检查点 5/5: 销毁确认 (CP5)", self.checkpoint.environment)
        
        # 危险警告
        self.ui.render_error("╔════════════════════════════════════════════════════════╗")
        self.ui.render_error("║              ⚠️  危险操作: 资源销毁                      ║")
        self.ui.render_error("║        此操作将永久删除资源，数据不可恢复!              ║")
        self.ui.render_error("╚════════════════════════════════════════════════════════╝")
        print()
        
        # 显示将要销毁的资源
        if self.checkpoint.resources:
            self.ui.render_info("以下资源将被销毁:")
            self.ui.render_resources(self.checkpoint.resources)
        
        # 环境特定警告
        if self.checkpoint.environment == Environment.PRODUCTION:
            self.ui.render_error("生产环境销毁需要双重确认!")
        
        # 冷却期
        if policy.cooldown > 0:
            self.ui.render_warning(f"冷却期: {policy.cooldown} 秒...")
            for i in range(policy.cooldown, 0, -1):
                print(f"  冷却中... {i} 秒  (按 Ctrl+C 取消)", end='\r')
                time.sleep(1)
            print()
        
        # 第一次确认
        confirm1 = self.ui.prompt(
            f"请输入环境名 '{self.checkpoint.environment.value}' 以确认销毁:"
        )
        if confirm1 != self.checkpoint.environment.value:
            return StepResult(Action.ABORT, reason="确认信息不匹配")
        
        # 第二次确认（UAT+）
        if policy.confirm_count >= 2:
            confirm2 = self.ui.prompt(
                "请再次输入 'yes-destroy' 以最终确认:"
            )
            if confirm2 != "yes-destroy":
                return StepResult(Action.ABORT, reason="二次确认失败")
        
        self.ui.render_success("销毁已确认")
        return StepResult(Action.CONTINUE, data={"destroy_confirmed": True})


# ============================================================================
# Exceptions
# ============================================================================

class UserAbortedError(Exception):
    """用户中止错误"""
    pass


class MaxRetryError(Exception):
    """最大重试错误"""
    pass


class TimeoutError(Exception):
    """超时错误"""
    pass


# ============================================================================
# Factory and Helper Functions
# ============================================================================

def create_checkpoint(
    checkpoint_type: CheckpointType,
    environment: Union[str, Environment],
    resources: Optional[List[Dict[str, Any]]] = None,
    checkpoint_id: Optional[str] = None,
    generated_files: Optional[Dict[str, str]] = None,
    user_inputs: Optional[Dict[str, Any]] = None,
) -> Checkpoint:
    """
    创建检查点
    
    Args:
        checkpoint_type: 检查点类型
        environment: 环境名称或枚举
        resources: 资源列表
        checkpoint_id: 自定义检查点ID
        generated_files: NL2HCL 生成的根目录 HCL 预览（main.tf 等）
        user_inputs: 附加上下文（request、output_dir 等）
    
    Returns:
        新创建的检查点
    """
    if isinstance(environment, str):
        environment = Environment(environment)
    
    # 生成检查点ID
    if not checkpoint_id:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        checkpoint_id = f"cp-{checkpoint_type.value}-{environment.value}-{timestamp}"
    
    # 转换资源
    resource_objects = []
    if resources:
        for r in resources:
            resource_objects.append(ResourceInfo(
                resource_type=r.get('type', 'unknown'),
                name=r.get('name', 'unnamed'),
                id=r.get('id'),
                status=r.get('status', 'pending'),
                attributes=r.get('attributes', {}),
                warnings=r.get('warnings', [])
            ))
    
    # 确定步骤顺序
    step_types = []
    if checkpoint_type == CheckpointType.NL2HCL:
        step_types = [StepType.CONFIRM_INTENT, StepType.REVIEW_CONFIG, StepType.CONFIRM_PLAN]
    elif checkpoint_type == CheckpointType.IMPORT:
        step_types = [StepType.CONFIRM_INTENT, StepType.CONFIRM_IMPORT, StepType.CONFIRM_PLAN]
    elif checkpoint_type == CheckpointType.APPLY:
        step_types = [StepType.CONFIRM_PLAN]
    elif checkpoint_type == CheckpointType.DESTROY:
        step_types = [StepType.CONFIRM_DESTROY]
    
    steps = [Step(type=st) for st in step_types]
    if user_inputs and user_inputs.get("request") and steps:
        steps[0].data["intent"] = user_inputs["request"]

    return Checkpoint(
        id=checkpoint_id,
        type=checkpoint_type,
        environment=environment,
        mode=HITLMode.CLI,
        resources=resource_objects,
        generated_files=generated_files or {},
        user_inputs=user_inputs or {},
        steps=steps,
        expires_at=datetime.now() + timedelta(days=7)
    )


def resume_checkpoint(checkpoint_id: str, store: Optional[CheckpointStore] = None) -> Checkpoint:
    """
    恢复检查点
    
    Args:
        checkpoint_id: 检查点ID
        store: 存储实例
    
    Returns:
        恢复的检查点
    
    Raises:
        FileNotFoundError: 检查点不存在
    """
    store = store or CheckpointStore()
    checkpoint = store.load(checkpoint_id)
    
    if not checkpoint:
        raise FileNotFoundError(f"检查点不存在: {checkpoint_id}")
    
    if checkpoint.is_expired():
        raise ValueError(f"检查点已过期: {checkpoint_id}")
    
    checkpoint.resume()
    return checkpoint


def list_checkpoints(store: Optional[CheckpointStore] = None) -> List[Checkpoint]:
    """
    列出活跃检查点
    
    Args:
        store: 存储实例
    
    Returns:
        活跃检查点列表
    """
    store = store or CheckpointStore()
    return store.list_active()


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    """CLI 入口点"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="HITL Mode A - 交互式 CLI for Terraform IaC"
    )
    parser.add_argument(
        "--type", "-t",
        choices=["nl2hcl", "import", "apply", "destroy"],
        required=True,
        help="检查点类型"
    )
    parser.add_argument(
        "--env", "-e",
        choices=["int", "dev", "uat", "performance", "production"],
        default="dev",
        help="目标环境 (默认: dev)"
    )
    parser.add_argument(
        "--resume", "-r",
        metavar="CHECKPOINT_ID",
        help="恢复指定的检查点"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出活跃检查点"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="禁用颜色输出"
    )
    
    args = parser.parse_args()
    
    store = CheckpointStore()
    
    # 列出检查点
    if args.list:
        checkpoints = list_checkpoints(store)
        if checkpoints:
            print("活跃检查点:")
            for cp in checkpoints:
                print(f"  {cp.id} - {cp.type.value} [{cp.environment.value}] ({cp.status.value})")
        else:
            print("无活跃检查点")
        return
    
    # 恢复检查点
    if args.resume:
        try:
            checkpoint = resume_checkpoint(args.resume, store)
            print(f"恢复检查点: {checkpoint.id}")
        except (FileNotFoundError, ValueError) as e:
            print(f"错误: {e}")
            sys.exit(1)
    else:
        # 创建新检查点
        checkpoint = create_checkpoint(
            checkpoint_type=CheckpointType(args.type),
            environment=args.env
        )
    
    # 运行控制器
    controller = CLIController(
        checkpoint=checkpoint,
        store=store,
        use_color=not args.no_color
    )
    
    try:
        controller.run()
    except UserAbortedError as e:
        print(f"\n操作已中止: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n执行错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
