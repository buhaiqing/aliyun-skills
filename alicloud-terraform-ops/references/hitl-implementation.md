# HITL Implementation - 多模式人工介入实现规范

交互式 CLI、PR 式审核、CheckPoint 暂停三种模式的实现细节。

## 1. 架构概览

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│  User Interface Layer                                     │
│  ├─ Mode A: Interactive CLI (命令行交互)                  │
│  ├─ Mode B: PR-Based Review (Git PR 驱动)                 │
│  └─ Mode C: Checkpoint Pause (会话暂停恢复)               │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  Checkpoint Framework (检查点框架)                        │
│  ├─ Checkpoint Manager (状态管理)                        │
│  ├─ Flow Controller (流程控制)                           │
│  └─ Policy Engine (策略引擎)                             │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  Core Services                                            │
│  ├─ NL2HCL Service (F1: 自然语言生成)                    │
│  ├─ Import Service (F2: 逆向导入)                        │
│  ├─ Terraform Runtime (init/plan/apply)                  │
│  └─ Notification Service (通知推送)                      │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  State & Audit Layer                                      │
│  ├─ Checkpoint Store (检查点存储)                        │
│  ├─ Audit Log (审计日志)                                 │
│  └─ Session Cache (会话缓存)                             │
└─────────────────────────────────────────────��───────────┘
```

### 1.2 模式对比矩阵

| 维度 | Mode A CLI | Mode B PR | Mode C Checkpoint |
|------|-----------|-----------|-------------------|
| **交互方式** | 同步问答 | 异步评论 | 暂停/恢复 |
| **响应时间** | 实时 | 分钟~小时级 | 小时~天级 |
| **审计能力** | 本地日志 | Git 历史 | 检查点文件 |
| **适用场景** | 开发/测试 | 生产发布 | 批量导入 |
| **实现复杂度** | 低 | 中 | 中 |
| **用户体验** | 即时反馈 | 非阻塞 | 灵活控制 |

## 2. 检查点框架 (Checkpoint Framework)

### 2.1 核心抽象

// Checkpoint 定义 (Type: nl2hcl/import/apply/destroy, Mode: cli/pr/checkpoint)
type Checkpoint struct {
    ID, Type, Status, Environment, Mode string
    Context Context; Policy Policy; History []Step
    CreatedAt, UpdatedAt, ExpiresAt time.Time
}
type CheckpointType string
const (CPTypeNL2HCL CheckpointType = "nl2hcl"; CPTypeImport = "import"; CPTypeApply = "apply"; CPTypeDestroy = "destroy")
type HITLMode string
const (ModeCLI HITLMode = "cli"; ModePR = "pr"; ModeCheckpoint = "checkpoint")
```

### 2.2 检查点生命周期

```
┌─────────┐    create    ┌─────────┐    pause     ┌─────────┐
│  INIT   │ ───────────▶ │ PENDING │ ───────────▶ │ PAUSED  │
└─────────┘              └────┬────┘              └────┬────┘
                              │                         │
                              │ resume                  │ resume
                              ▼                         ▼
                         ┌─────────┐    complete    ┌─────────┐
                         │RUNNING  │ ────────────▶ │COMPLETED│
                         └────┬────┘                └─────────┘
                              │
                              │ fail
                              ▼
                         ┌─────────┐
                         │ FAILED  │
                         └─────────┘
```

### 2.3 策略引擎

```yaml
# policy.yaml - 五级环境策略
environments:
  int:
    checkpoints:
      cp1_intent:
        required: true
        mode: cli
        timeout: 5m
      
      cp2_review:
        required: false
      
      cp3_plan:
        required: true
        dry_run: true
        auto_approve: true  # int 环境自动批准小变更
      
      cp5_destroy:
        required: true
        confirm_count: 1
    
  dev:
    checkpoints:
      cp1_intent:
        required: true
      
      cp2_review:
        required: false
        optional_prompt: true  # 提示但可跳过
      
      cp3_plan:
        required: true
        dry_run: true
      
      cp5_destroy:
        required: true
        confirm_count: 1
    
  uat:
    checkpoints:
      cp1_intent:
        required: true
      
      cp2_review:
        required: true
        reviewers: ["tech-lead"]
      
      cp3_plan:
        required: true
        dry_run: true
        approvers: ["tech-lead"]
      
      cp5_destroy:
        required: true
        confirm_count: 2
        approvers: ["tech-lead", "ops-manager"]
    
  performance:
    similar_to: uat
    
  production:
    checkpoints:
      cp1_intent:
        required: true
        require_jira_ticket: true
      
      cp2_review:
        required: true
        mode: pr  # 强制 PR 模式
        reviewers: ["tech-lead", "ops-manager"]
      
      cp3_plan:
        required: true
        dry_run: true
        maintenance_window: "02:00-04:00"
        approvers:
          - role: "tech-lead"
            type: single
          - role: "ops-manager"
            type: single
      
      cp5_destroy:
        required: true
        confirm_count: 2
        cooldown: 30s
        approvers:
          - role: "tech-lead"
          - role: "ops-manager"
```

## 3. 模式 A: 交互式 CLI 实现

### 3.1 核心组件

```
┌─────────────────────────────────────┐
│  CLI UI Manager                       │
│  ├─ Prompt Renderer (提示渲染)        │
│  ├─ Input Handler (输入处理)          │
│  ├─ Progress Display (进度显示)       │
│  └─ Help System (帮助系统)            │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  Checkpoint Controller                │
│  ├─ State Machine (状态机)            │
│  ├─ Timeout Manager (超时管理)        │
│  └─ Interrupt Handler (中断处理)      │
└─────────────────────────────────────┘
```

### 3.2 交互范式

#### 确认型提示
```
[确认] 检测到以下资源：
  - VPC: 1 个
  - ECS: 2 台

确认生成? [Y/n/modify/help] > 
```

#### 选择型提示
```
[选择] 请选择操作模式:
  [1] 快速模式 (使用默认值)
  [2] 标准模式 (可配置关键参数)
  [3] 高级模式 (完整配置)
  
请选择 [1-3] > 
```

#### 输入型提示
```
[输入] 请指定 VPC CIDR (默认: 10.0.0.0/16):
> 
```

#### 多选型提示
```
[多选] 选择要导入的资源 (↑↓移动, 空格选择, 回车确认):
  [x] VPC vpc-bp1xxx
  [x] VSwitch vsw-bp1xxx
  [ ] SLB lb-bp1xxx (⚠️  复杂规则)
  [x] ECS i-bp1xxx
  
已选择: 3/4  [确认] [全选] [取消]
```

### 3.3 实现代码示例

```python
# cli_controller.py

class CLIController:
    def __init__(self, checkpoint: Checkpoint):
        self.checkpoint = checkpoint
        self.ui = CLIRenderer()
        
    async def run(self):
        """主循环"""
        try:
            for step in self.checkpoint.get_pending_steps():
                result = await self.execute_step(step)
                
                if result.action == Action.PAUSE:
                    self.checkpoint.pause()
                    return  # 等待恢复
                    
                elif result.action == Action.ABORT:
                    self.checkpoint.abort(result.reason)
                    raise UserAbortedError(result.reason)
                    
                elif result.action == Action.CONTINUE:
                    self.checkpoint.complete_step(step, result.data)
                    
        except TimeoutError:
            self.checkpoint.timeout()
            raise
            
    async def execute_step(self, step: Step) -> Result:
        # 执行单个检查点步骤 (CP1-CP5)
        handlers = {
            StepType.CONFIRM_INTENT: self.confirm_intent,
            StepType.REVIEW_CONFIG: self.review_config,
            StepType.CONFIRM_PLAN: self.confirm_plan,
            # ... CP4, CP5 handlers
        }
        handler = handlers.get(step.type)
        return await handler(step) if handler else Result(Action.UNSUPPORTED)
        
    async def confirm_intent(self, step: Step) -> Result:
        """CP1: 意图确认"""
        self.ui.render_header("意图确认 (CP1)")
        self.ui.render_resources(step.data['resources'])
        
        choice = self.ui.prompt(
            "确认生成?",
            options=["Y", "n", "modify", "save-exit"],
            default="Y",
            timeout=300  # 5分钟超时
        )
        
        if choice == "Y":
            return Result(Action.CONTINUE)
        elif choice == "n":
            return Result(Action.ABORT, reason="用户取消")
        elif choice == "modify":
            modifications = await self.collect_modifications()
            return Result(Action.CONTINUE, data=modifications)
        elif choice == "save-exit":
            return Result(Action.PAUSE)
```

### 3.4 五级环境差异化实现

```python
class EnvironmentPolicy:
    def get_checkpoint_behavior(self, env: str, cp: str) -> Behavior:
        behaviors = {
            ("int", "cp1"): Behavior(
                required=True,
                prompt_style=PromptStyle.SIMPLE,
                timeout=300,
                allow_skip=False
            ),
            ("dev", "cp1"): Behavior(
                required=True,
                prompt_style=PromptStyle.DETAILED,
                timeout=600,
                allow_skip=False
            ),
            ("production", "cp1"): Behavior(
                required=True,
                prompt_style=PromptStyle.STRICT,
                timeout=900,
                require_reason=True,
                pre_check=[
                    PreCheck.JIRA_TICKET,
                    PreCheck.MAINTENANCE_WINDOW
                ]
            ),
            # ... 其他组合
        }
        return behaviors.get((env, cp), Behavior.default())
```

## 4. 模式 B: PR 式审核实现

### 4.1 核心组件

```
┌─────────────────────────────────────┐
│  Git Integration Layer                │
│  ├─ Branch Manager (分支管理)         │
│  ├─ Commit Generator (提交生成)       │
│  ├─ PR Manager (PR 管理)              │
│  └─ Webhook Handler (Webhook 处理)    │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  Review Orchestrator                  │
│  ├─ Comment Parser (评论解析)         │
│  ├─ Approval Tracker (审批追踪)       │
│  ├─ Plan Generator (Plan 生成)        │
│  └─ Notification Manager (通知管理)   │
└─────────────────────────────────────┘
```

### 4.2 Git 工作流

```
User Request
    │
    ▼
┌──────────────┐
│  Create Branch │◀── terraform-{timestamp}-{hash}
│  (git checkout)│
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Generate HCL  │
│  + PLAN.md     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Commit & Push │◀── "[terraform] Add VPC and ECS resources"
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Create PR     │◀── 自动添加标签: terraform, needs-review
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Notify        │◀── 钉钉/Slack 通知审批人
│  Reviewers     │
└──────┬───────┘
       │
       │ 等待审批...
       │
       ▼
┌──────────────┐
│  Parse Comment │◀── /approve, /plan, /reject
│  or Approval   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Execute       │◀── terraform apply (CI/CD 或本地)
│  Apply         │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Update PR     │◀── 添加执行结果评论
│  Status        │    可选: 自动合并
└──────────────┘
```

### 4.3 实现代码示例

```python
# pr_manager.py

class PRManager:
    def __init__(self, provider: GitProvider):
        self.provider = provider
        
    async def create_terraform_pr(
        self,
        config: TerraformConfig,
        checkpoint: Checkpoint
    ) -> PullRequest:
        """创建 Terraform PR"""
        
        # 1. 创建分支
        branch_name = self.generate_branch_name(checkpoint)
        await self.provider.create_branch(
            base="main",
            name=branch_name
        )
        
        # 2. 生成文件
        files = self.generate_pr_files(config)
        
        # 3. 提交
        commit_message = self.generate_commit_message(checkpoint)
        await self.provider.commit_files(
            branch=branch_name,
            files=files,
            message=commit_message
        )
        
        # 4. 创建 PR
        pr = await self.provider.create_pr(
            title=f"[terraform] {checkpoint.description}",
            body=self.generate_pr_body(config, checkpoint),
            head=branch_name,
            base="main",
            labels=["terraform", "needs-review"],
            reviewers=self.get_reviewers(checkpoint.environment)
        )
        
        # 5. 启动监听
        await self.start_pr_monitoring(pr, checkpoint)
        
        return pr
        
    def generate_pr_files(self, config: TerraformConfig) -> List[File]:
        """生成 PR 文件"""
        files = [
            File(
                path="main.tf",
                content=config.main_tf
            ),
            File(
                path="variables.tf",
                content=config.variables_tf
            ),
            File(
                path="PLAN.md",
                content=self.generate_plan_md(config)
            ),
            File(
                path=".terraform-docs.yml",
                content=self.generate_terraform_docs_config()
            )
        ]
        return files
        
    def generate_plan_md(self, config: TerraformConfig) -> str:
        """生成 PLAN.md"""
        return f"""# Terraform Plan 摘要

## 变更概览

| 类型 | 数量 | 资源 |
|------|------|------|
| + 创建 | {config.stats.create} | {', '.join(config.stats.create_resources)} |
| ~ 修改 | {config.stats.update} | {', '.join(config.stats.update_resources)} |
| - 销毁 | {config.stats.delete} | {', '.join(config.stats.delete_resources)} |

## 预计费用

{config.cost_estimate}

## 风险检查

{self.render_risk_checks(config.risks)}

## 审批

- [ ] Tech Lead
- [ ] Ops Manager (production only)

---
*Generated by alicloud-terraform-ops*
*Checkpoint: {config.checkpoint_id}*
"""
```

### 4.4 评论指令系统

```python
# comment_parser.py

class CommentCommand:
    """评论指令解析"""
    
    COMMANDS = {
        "/plan": {
            "description": "重新执行 terraform plan",
            "permission": ["author", "reviewer"],
            "action": Action.RERUN_PLAN
        },
        "/apply": {
            "description": "执行 terraform apply",
            "permission": ["reviewer"],
            "require_approval": True,
            "action": Action.EXECUTE_APPLY
        },
        "/approve": {
            "description": "批准变更",
            "permission": ["reviewer"],
            "action": Action.APPROVE
        },
        "/reject": {
            "description": "拒绝变更",
            "permission": ["reviewer"],
            "require_reason": True,
            "action": Action.REJECT
        },
        "/skip-cp": {
            "description": "跳过指定检查点",
            "permission": ["admin"],
            "args": ["checkpoint_id"],
            "action": Action.SKIP_CHECKPOINT
        },
        "/help": {
            "description": "显示帮助",
            "permission": ["anyone"],
            "action": Action.SHOW_HELP
        }
    }
    
    def parse(self, comment: str, user: User) -> CommandResult:
        """解析评论指令"""
        lines = comment.strip().split('\n')
        first_line = lines[0].strip()
        
        if not first_line.startswith('/'):
            return CommandResult(Action.NONE)
            
        parts = first_line.split()
        cmd = parts[0]
        args = parts[1:]
        
        if cmd not in self.COMMANDS:
            return CommandResult(Action.UNKNOWN, error=f"未知指令: {cmd}")
            
        cmd_def = self.COMMANDS[cmd]
        
        # 权限检查
        if not self.check_permission(user, cmd_def["permission"]):
            return CommandResult(Action.FORBIDDEN, error="权限不足")
            
        return CommandResult(
            cmd_def["action"],
            args=args,
            require_approval=cmd_def.get("require_approval", False)
        )
```

## 5. 模式 C: CheckPoint 暂停实现

### 5.1 核心组件

```
┌─────────────────────────────────────┐
│  Checkpoint Manager                   │
│  ├─ State Persistence (状态持久化)    │
│  ├─ Session Recovery (会话恢复)       │
│  ├─ Progress Tracking (进度追踪)      │
│  └─ Expiration Manager (过期管理)     │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  Resource Classifier                  │
│  ├─ Pass Detector (通过检测)          │
│  ├─ Warning Analyzer (警告分析)       │
│  ├─ Skip Determinator (跳过判定)      │
│  └─ Dependency Resolver (依赖解析)    │
└─────────────────────────────────────┘
```

### 5.2 状态持久化

```python
# checkpoint_store.py

class CheckpointStore:
    """检查点存储"""
    
    def __init__(self, backend: StorageBackend):
        self.backend = backend
        
    async def save(self, checkpoint: Checkpoint):
        """保存检查点"""
        data = {
            "id": checkpoint.id,
            "type": checkpoint.type.value,
            "status": checkpoint.status.value,
            "environment": checkpoint.environment,
            "mode": checkpoint.mode.value,
            
            "context": self.serialize_context(checkpoint.context),
            "history": [self.serialize_step(s) for s in checkpoint.history],
            
            "created_at": checkpoint.created_at.isoformat(),
            "updated_at": checkpoint.updated_at.isoformat(),
            "expires_at": checkpoint.expires_at.isoformat() if checkpoint.expires_at else None
        }
        
        await self.backend.write(
            key=f"checkpoints/{checkpoint.id}.json",
            data=json.dumps(data, indent=2)
        )
        
    async def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """加载检查点"""
        data = await self.backend.read(f"checkpoints/{checkpoint_id}.json")
        if not data:
            return None
            
        return self.deserialize(json.loads(data))
        
    async def list_active(self, user: str) -> List[CheckpointSummary]:
        """列出用户的活跃检查点"""
        checkpoints = await self.backend.list("checkpoints/")
        
        active = []
        for cp in checkpoints:
            if cp.status in [Status.PENDING, Status.PAUSED]:
                if not cp.is_expired():
                    active.append(cp.to_summary())
                    
        return active
```

### 5.3 会话恢复

```python
# session_recovery.py

class SessionRecovery:
    """会话恢复管理"""
    
    async def resume(self, checkpoint_id: str) -> RecoveryResult:
        """恢复检查点"""
        
        # 1. 加载检查点
        checkpoint = await self.store.load(checkpoint_id)
        if not checkpoint:
            return RecoveryResult(error="检查点不存在")
            
        # 2. 验证有效性
        if checkpoint.is_expired():
            return RecoveryResult(error="检查点已过期")
            
        # 3. 恢复上下文
        context = await self.restore_context(checkpoint)
        
        # 4. 验证资源状态（可能已变化）
        drift = await self.detect_drift(checkpoint, context)
        if drift.has_changes:
            return RecoveryResult(
                checkpoint=checkpoint,
                context=context,
                warning="资源状态已变化",
                drift=drift
            )
            
        # 5. 恢复执行
        return RecoveryResult(
            checkpoint=checkpoint,
            context=context,
            can_resume=True
        )
        
    async def restore_context(self, checkpoint: Checkpoint) -> Context:
        """恢复执行上下文"""
        context = Context()
        
        # 恢复资源列表
        if checkpoint.type == CPTypeImport:
            context.resources = await self.rediscover_resources(
                checkpoint.context.source_vpc
            )
            
        # 恢复生成文件
        if checkpoint.context.generated_files:
            context.files = await self.regenerate_or_reload(
                checkpoint.context.generated_files
            )
            
        return context
```

### 5.4 批量选择 UI

```python
# batch_selector.py

class BatchSelector:
    """批量资源选择器"""
    
    def render_interactive(self, resources: List[Resource]) -> SelectionResult:
        """渲染交互式选择界面"""
        
        # 分组显示
        groups = self.group_by_status(resources)
        
        console.print("\n[bold]资源导入选择[/bold]\n")
        
        # PASS 组
        console.print("[green][PASS] 可安全导入[/green]")
        for r in groups["pass"]:
            console.print(f"  [{'x' if r.selected else ' '}] {r.id} ({r.name})")
            
        # WARN 组
        console.print("\n[yellow][WARN] 需要确认[/yellow]")
        for r in groups["warn"]:
            console.print(f"  [{'x' if r.selected else ' '}] {r.id} ({r.name})")
            console.print(f"      ⚠️  {r.warning_reason}")
            
        # SKIP 组
        console.print("\n[red][SKIP] 不支持[/red]")
        for r in groups["skip"]:
            console.print(f"  [ ] {r.id} ({r.name})")
            console.print(f"      ✗ {r.skip_reason}")
            
        # 操作提示
        console.print("\n[dim]操作: [空格]选择 [a]全选 [n]取消 [i]详情 [enter]确认 [q]保存退出[/dim]")
        
        # 处理用户输入...
```

## 6. 配置系统

### 6.1 配置层级

```
优先级 (高 → 低):

1. 命令行参数
   --mode=cli --env=production --skip-cp=cp2

2. 环境变量
   TF_OPS_MODE=cli
   TF_OPS_ENV=production

3. 项目配置 (项目根目录)
   ./.pi/terraform-ops.yaml

4. 用户配置 (家目录)
   ~/.pi/terraform-ops.yaml

5. 系统默认
   (内置在代码中)
```

### 6.2 完整配置示例

```yaml
# terraform-ops.yaml
version: "1.0"

# 默认设置
defaults:
  mode: "cli"
  environment: "dev"
  region: "cn-hangzhou"

# 环境配置
environments:
  int:
    mode: "cli"
    policy:
      cp1_intent:
        required: true
        timeout: 300
      cp3_plan:
        dry_run: true
        auto_approve_threshold:
          create: 5      # 创建少于5个资源自动批准
          cost_hourly: 10  # 小时费用低于10元自动批准
          
  production:
    mode: "pr"
    require_jira_ticket: true
    maintenance_window: "02:00-04:00"
    
    policy:
      cp1_intent:
        required: true
        require_reason: true
        
      cp2_review:
        required: true
        mode: "pr"
        
      cp3_plan:
        dry_run: true
        approvers:
          - role: "tech-lead"
            users: ["zhangsan", "lisi"]
            type: "any"
          - role: "ops-manager"
            users: ["wangwu"]
            type: "single"
            
      cp5_destroy:
        confirm_count: 2
        cooldown: 30

# Git 集成配置 (Mode B)
git:
  provider: "gitlab"  # github / gitlab / gitee
  repository: "https://git.example.com/ops/terraform"
  base_branch: "main"
  
  pr:
    auto_merge: false
    delete_branch: true
    
  codeowners: |
    * @ops-team
    *production* @ops-manager
    
  notifications:
    channel: "dingtalk"
    # 安全警告: 使用环境变量注入 webhook URL，禁止硬编码真实 token
    # 示例: webhook: "${DINGTALK_WEBHOOK_URL}"
    webhook: "${DINGTALK_WEBHOOK_URL}"

# 检查点存储 (Mode C)
checkpoint:
  storage: "local"  # local / oss / s3
  local_path: "~/.pi/terraform-ops/checkpoints"
  
  expiration:
    default: "7d"
    production: "30d"
    
  auto_cleanup: true

# 通知配置
notifications:
  enabled: true
  channels:
    - type: "console"
      level: ["info", "warning", "error"]
    - type: "dingtalk"
      level: ["warning", "error"]
      webhook: "${DINGTALK_WEBHOOK}"

## 7. 错误处理规范

### 7.1 错误分类与处理策略

| 错误类型 | 示例场景 | 处理策略 | 用户通知 |
|----------|----------|----------|----------|
| **网络错误** | Git 推送失败、API 超时 | Retry 3 次 → HALT | 提示检查网络后重试 |
| **权限错误** | 无权限创建 PR、审批拒绝 | HALT | 提示联系管理员授权 |
| **状态冲突** | PR 已关闭、检查点已过期 | HALT | 提示重新创建任务 |
| **超时错误** | 用户长时间无响应 | PAUSE → 保存检查点 | 提示已保存，可稍后恢复 |
| **资源不存在** | 资源 ID 无效、VPC 已删除 | HALT | 提示验证资源 ID |
| **配置错误** | YAML 语法错误、缺少必填项 | HALT | 提示修正配置文件 |

### 7.2 CLI 模式错误处理

```python
# cli_error_handler.py

class CLIErrorHandler:
    """CLI 错误处理器"""
    
    async def handle(self, error: Exception, checkpoint: Checkpoint) -> Action:
        """处理错误，返回后续动作"""
        
        if isinstance(error, NetworkError):
            if checkpoint.retry_count < 3:
                checkpoint.retry_count += 1
                await self.notify(f"网络错误，{checkpoint.retry_count}/3 次重试...")
                return Action.RETRY
            else:
                checkpoint.pause()
                return Action.PAUSE
                
        elif isinstance(error, PermissionError):
            await self.notify("权限不足，请联系管理员")
            return Action.HALT
            
        elif isinstance(error, TimeoutError):
            checkpoint.pause()
            await self.notify("操作超时，已保存检查点，可稍后恢复")
            return Action.PAUSE
            
        elif isinstance(error, ResourceNotFoundError):
            await self.notify(f"资源不存在: {error.resource_id}")
            return Action.HALT
            
        else:
            # 未知错误，记录日志后暂停
            logger.error(f"未知错误: {error}", exc_info=True)
            checkpoint.pause()
            return Action.PAUSE
```

### 7.3 PR 模式错误处理

```python
# pr_error_handler.py

class PRErrorHandler:
    """PR 模式错误处理器"""
    
    async def handle_git_error(self, error: GitError, pr: PullRequest) -> Action:
        """处理 Git 相关错误"""
        
        if error.code == "branch_already_exists":
            # 分支已存在，使用新分支名
            new_branch = f"{pr.branch}-{timestamp()}"
            await self.notify(f"分支已存在，使用新分支: {new_branch}")
            return Action.RETRY_WITH_NEW_BRANCH
            
        elif error.code == "push_rejected":
            # 推送被拒绝，可能是权限或冲突
            await self.notify("推送被拒绝，请检查权限或手动解决冲突")
            return Action.HALT
            
        elif error.code == "pr_create_failed":
            if "already exists" in error.message:
                # PR 已存在，更新现有 PR
                await self.notify("PR 已存在，更新现有 PR")
                return Action.UPDATE_EXISTING_PR
            else:
                await self.notify(f"创建 PR 失败: {error.message}")
                return Action.HALT
                
        else:
            logger.error(f"Git 错误: {error}")
            return Action.HALT
```

### 7.4 CheckPoint 模式错误处理

```python
# checkpoint_error_handler.py

class CheckpointErrorHandler:
    """检查点错误处理器"""
    
    async def handle_load_error(self, error: Exception, checkpoint_id: str) -> RecoveryResult:
        """处理检查点加载错误"""
        
        if isinstance(error, FileNotFoundError):
            return RecoveryResult(
                error=f"检查点不存在: {checkpoint_id}"
            )
            
        elif isinstance(error, JSONDecodeError):
            # 文件损坏，尝试备份恢复
            backup = await self.try_load_backup(checkpoint_id)
            if backup:
                return RecoveryResult(
                    warning="检查点文件损坏，已从备份恢复",
                    checkpoint=backup
                )
            else:
                return RecoveryResult(
                    error="检查点文件损坏且无法从备份恢复"
                )
                
        elif isinstance(error, ExpiredError):
            return RecoveryResult(
                error=f"检查点已过期: {checkpoint_id}"
            )
            
        else:
            return RecoveryResult(
                error=f"加载检查点失败: {error}"
            )
```

### 7.5 通用错误恢复策略

| 场景 | 自动恢复 | 人工介入 |
|------|----------|----------|
| 网络抖动 (瞬态) | Retry 3 次 | 第 3 次失败后暂停 |
| 临时 API 限流 | 指数退避 (1s, 2s, 4s) | 持续失败后暂停 |
| 检查点保存失败 | 尝试备用存储路径 | 提示手动保存 |
| Git 冲突 | 尝试自动 rebase | 冲突复杂时暂停 |
| 审批被拒绝 | N/A | 必须人工重新提交 |
```

## 8. 审计与日志

### 8.1 审计事件

```python
class AuditEvent:
    """审计事件"""
    
    CHECKPOINT_CREATED = "checkpoint.created"
    CHECKPOINT_PAUSED = "checkpoint.paused"
    CHECKPOINT_RESUMED = "checkpoint.resumed"
    CHECKPOINT_COMPLETED = "checkpoint.completed"
    
    STEP_EXECUTED = "step.executed"
    USER_CONFIRMED = "user.confirmed"
    USER_REJECTED = "user.rejected"
    
    PR_CREATED = "pr.created"
    PR_APPROVED = "pr.approved"
    PR_REJECTED = "pr.rejected"
    PR_MERGED = "pr.merged"
    
    TERRAFORM_INIT = "terraform.init"
    TERRAFORM_PLAN = "terraform.plan"
    TERRAFORM_APPLY = "terraform.apply"
    TERRAFORM_DESTROY = "terraform.destroy"
```

### 8.2 日志格式

```json
{
  "timestamp": "2024-06-08T10:30:00Z",
  "level": "INFO",
  "event": "checkpoint.step_executed",
  "checkpoint_id": "cp-20240608-001",
  "user": "developer",
  "environment": "production",
  
  "step": {
    "id": "cp3_plan",
    "type": "confirm_plan",
    "result": "confirmed"
  },
  
  "context": {
    "resources_count": 5,
    "estimated_cost": "2.5/hour"
  },
  
  "trace_id": "trace-abc123",
  "span_id": "span-def456"
}
```

---

*该规范用于驱动 alicloud-terraform-ops Skill 的 HITL 多模式实现。*
